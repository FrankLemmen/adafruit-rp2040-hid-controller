"""Buttons-only USB gamepad for Adafruit MacroPad RP2040 / product 5128.

Requires CircuitPython for this board, not stock MicroPython.
Uses only built-in modules; no files are needed in lib/.

Buttons 1-12: keypad, left to right / top to bottom (USB port at top).
Buttons 13-15: reserved in the descriptor, never pressed.

Encoder push toggles key color programming mode:
  - The key being programmed blinks (white until a color is picked).
  - Turn left: show the next color for that key.
  - Turn right: confirm the color and move to the next key (wraps around).
  - Push again: leave programming mode and save the colors.
Keys send no gamepad presses while programming.

The OLED shows the controls while programming. In normal mode it shows
"Control mode", which fades to black after IDLE_SECONDS.
"""

import time
import board
import digitalio
import displayio
import keypad
import microcontroller
import neopixel_write
import rotaryio
import terminalio
import usb_hid

REVERSE_ENCODER = False
BRIGHTNESS = 0.3          # 0.0 - 1.0, applied to all key LEDs.
BLINK_SECONDS = 0.25      # Half period of the programming blink.
IDLE_SECONDS = 30.0       # "Control mode" text fades out after this.
FADE_SECONDS = 1.5        # Duration of that fade.

NUM_KEYS = 12
ENCODER_KEY = 12          # keypad index of the encoder push switch.

PALETTE = (
    (0, 0, 0),            # Off
    (255, 0, 0),          # Red
    (255, 80, 0),         # Orange
    (255, 200, 0),        # Yellow
    (0, 255, 0),          # Green
    (0, 255, 255),        # Cyan
    (0, 0, 255),          # Blue
    (128, 0, 255),        # Purple
    (255, 0, 160),        # Magenta
    (255, 255, 255),      # White
)
COLOR_NAMES = (
    "Off", "Red", "Orange", "Yellow", "Green",
    "Cyan", "Blue", "Purple", "Magenta", "White",
)
WHITE = (255, 255, 255)
DIM_WHITE = (40, 40, 40)  # Blink color when "Off" is the candidate.

# Colors persist in non-volatile memory: magic header + one index per key.
NVM_MAGIC = b"MP"
NVM_SIZE = len(NVM_MAGIC) + NUM_KEYS


def load_colors():
    data = bytes(microcontroller.nvm[0:NVM_SIZE])
    if data[0:len(NVM_MAGIC)] == NVM_MAGIC:
        indices = list(data[len(NVM_MAGIC):])
        if all(i < len(PALETTE) for i in indices):
            return indices
    return [0] * NUM_KEYS


def save_colors(indices):
    data = NVM_MAGIC + bytes(indices)
    if bytes(microcontroller.nvm[0:NVM_SIZE]) != data:
        microcontroller.nvm[0:NVM_SIZE] = data


# These pin names match the official Adafruit MacroPad library.
pins = tuple(getattr(board, "KEY{}".format(i)) for i in range(1, 13))
keys = keypad.Keys(
    pins + (board.BUTTON,),
    value_when_pressed=False,
    pull=True,
    interval=0.020,
    max_events=64,
)
encoder = rotaryio.IncrementalEncoder(board.ROTA, board.ROTB)

pixel_pin = digitalio.DigitalInOut(board.NEOPIXEL)
pixel_pin.direction = digitalio.Direction.OUTPUT
pixel_buf = bytearray(3 * NUM_KEYS)
last_pixel_buf = None


def show(colors):
    global last_pixel_buf
    for i, (r, g, b) in enumerate(colors):
        # The MacroPad NeoPixels expect GRB byte order.
        pixel_buf[3 * i] = int(g * BRIGHTNESS)
        pixel_buf[3 * i + 1] = int(r * BRIGHTNESS)
        pixel_buf[3 * i + 2] = int(b * BRIGHTNESS)
    if last_pixel_buf is None or pixel_buf != last_pixel_buf:
        neopixel_write.neopixel_write(pixel_pin, pixel_buf)
        last_pixel_buf = bytes(pixel_buf)


# OLED text grid built from the built-in font: 21 columns x 5 rows.
# Uses only core modules, so no lib/ files are needed.
display = board.DISPLAY
font = terminalio.FONT
glyph_w, glyph_h = font.get_bounding_box()[:2]
TEXT_COLS = display.width // glyph_w
TEXT_ROWS = display.height // glyph_h
text_palette = displayio.Palette(2)
text_palette[0] = 0x000000
text_palette[1] = 0xFFFFFF
text_grid = displayio.TileGrid(
    font.bitmap,
    pixel_shader=text_palette,
    width=TEXT_COLS,
    height=TEXT_ROWS,
    tile_width=glyph_w,
    tile_height=glyph_h,
    y=(display.height - TEXT_ROWS * glyph_h) // 2,
)
text_group = displayio.Group()
text_group.append(text_grid)
display.root_group = text_group
shown_lines = None


def tile_for(char):
    glyph = font.get_glyph(ord(char)) or font.get_glyph(ord(" "))
    return glyph.tile_index


def show_text(lines):
    global shown_lines
    lines = tuple(lines) + ("",) * (TEXT_ROWS - len(lines))
    if lines == shown_lines:
        return
    for row, line in enumerate(lines[:TEXT_ROWS]):
        line = line[:TEXT_COLS]
        for col in range(TEXT_COLS):
            text_grid[col, row] = tile_for(line[col] if col < len(line) else " ")
    shown_lines = lines


shown_brightness = None


def set_display_brightness(level):
    global shown_brightness
    level = round(max(0.0, min(1.0, level)), 1)  # Few steps = few writes.
    if level == shown_brightness:
        return
    shown_brightness = level
    try:
        display.brightness = level
    except (AttributeError, NotImplementedError, RuntimeError, ValueError):
        pass  # Fall back to simply blanking the text.


def centered(text):
    pad = (TEXT_COLS - len(text)) // 2
    return " " * pad + text


# Find the custom gamepad installed by boot.py.
gamepad = None
for device in usb_hid.devices:
    if device.usage_page == 0x01 and device.usage == 0x05:
        gamepad = device
        break
if gamepad is None:
    raise RuntimeError("Gamepad not found. Install boot.py, then unplug/replug USB.")

key_colors = load_colors()
programming = False
prog_key = 0
candidate = None          # Palette index shown but not yet confirmed.
normal_since = time.monotonic()

held_buttons = 0
last_position = -encoder.position  # Same direction convention as Adafruit.
report = bytearray(2)
last_sent = None
last_sent_at = 0.0

while True:
    now = time.monotonic()

    # Process one event per loop so a queued quick tap still sends both
    # its press and release as separate USB reports.
    event = keys.events.get()
    if event is not None:
        if event.key_number == ENCODER_KEY:
            if event.pressed:
                programming = not programming
                if programming:
                    held_buttons = 0
                    prog_key = 0
                    candidate = None
                else:
                    # An unconfirmed candidate is discarded.
                    save_colors(key_colors)
                    normal_since = now
        else:
            bit = 1 << event.key_number
            if event.pressed:
                if not programming:
                    held_buttons |= bit
            else:
                held_buttons &= ~bit

    # Always consume encoder movement; it is ignored outside programming.
    position = -encoder.position
    delta = position - last_position
    last_position = position
    if REVERSE_ENCODER:
        delta = -delta

    if programming:
        while delta < 0:  # Left: next color.
            start = key_colors[prog_key] if candidate is None else candidate
            candidate = (start + 1) % len(PALETTE)
            delta += 1
        while delta > 0:  # Right: confirm and move to the next key.
            if candidate is not None:
                key_colors[prog_key] = candidate
            prog_key = (prog_key + 1) % NUM_KEYS
            candidate = None
            delta -= 1

        colors = [PALETTE[i] for i in key_colors]
        if int(now / BLINK_SECONDS) % 2 == 0:
            if candidate is None:
                colors[prog_key] = WHITE
            elif candidate == 0:
                colors[prog_key] = DIM_WHITE
            else:
                colors[prog_key] = PALETTE[candidate]
        else:
            colors[prog_key] = (0, 0, 0)
        show(colors)

        shown = key_colors[prog_key] if candidate is None else candidate
        set_display_brightness(1.0)
        show_text((
            "PROGRAMMING  Key {}".format(prog_key + 1),
            "Color: {}".format(COLOR_NAMES[shown]),
            "Turn left : color",
            "Turn right: next key",
            "Press knob: done",
        ))
    else:
        show([PALETTE[i] for i in key_colors])

        # Show "Control mode", then fade to black to spare the OLED.
        idle = now - normal_since
        if idle < IDLE_SECONDS:
            set_display_brightness(1.0)
            show_text(("", "", centered("Control mode")))
        elif idle < IDLE_SECONDS + FADE_SECONDS:
            set_display_brightness(1.0 - (idle - IDLE_SECONDS) / FADE_SECONDS)
        else:
            show_text(())
            set_display_brightness(1.0)

    buttons = held_buttons

    # Two-byte, little-endian bitmap. Bit 15 is always zero (padding).
    # No Report ID prefix and no axis values are included.
    if buttons != last_sent or now - last_sent_at >= 1.0:
        report[0] = buttons & 0xFF
        report[1] = (buttons >> 8) & 0x7F
        try:
            gamepad.send_report(report)
        except OSError:
            # USB can be temporarily unavailable during enumeration.
            # Leave last_sent unchanged so the next loop retries.
            pass
        else:
            last_sent = buttons
            last_sent_at = now

    time.sleep(0.001)
