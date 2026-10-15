# MarcoPad

This turns an [Adafruit MacroPad RP2040](https://www.adafruit.com/product/5128) into a **USB game controller button box for sim racing**. Each of the 12 keys is a gamepad button that you bind in your sim to things like pit limiter, wipers, lights, TC/ABS steps, radio or the MFD. You can set each key's LED to its own color with the knob, so you can find the right button at a glance during a race.

It runs on [CircuitPython](https://circuitpython.org/board/adafruit_macropad_rp2040/) and uses only built-in modules, so there's nothing else to install.

## Why a gamepad and not a keyboard?

Most MacroPad projects make the pad act as a keyboard that sends shortcuts. For sim racing, showing up as a game controller (a USB HID gamepad) works better:

- **Bindings don't clash with keyboard shortcuts.** A keyboard-based pad sends real key presses. They can collide with keys the sim already uses, with Windows or overlay hotkeys, or with text you're typing in chat. Gamepad buttons only do what you bind them to.
- **The sim can read the pad when it isn't the focused window.** Key presses only go to the active window. If you click on SimHub, Discord or a telemetry tool, keyboard bindings stop reaching the sim. Most sims read controller buttons through DirectInput whatever window has focus.
- **Binding works like your wheel and pedals.** You bind the pad in the sim's controls menu as "MarcoPad HID button 5", the same way you bind your wheel buttons. Most sims let you combine buttons from several controllers in one profile.
- **It doesn't depend on keyboard layout or modifiers.** No QWERTY/AZERTY differences, no stuck Ctrl or Shift, and no auto-repeat when you hold a key.
- **The pad needs no software or driver on the PC.** Windows recognizes it as a standard game controller. You set your bindings in the sim and the pad itself never needs reprogramming.

> **Note:** The pad is a generic DirectInput controller, not an Xbox (XInput) controller. Practically every sim racing title supports DirectInput button boxes. A few console-style games only accept Xbox controllers and won't see it.

## Features

- 12 gamepad buttons, one per key. The controller has no axes and no keyboard or mouse functions.
- Shows up in Windows as **MarcoPad HID**.
- A color for each key, chosen with the knob and saved in the board so it survives unplugging.
- The screen shows the knob controls while you set colors. In normal mode it shows "Control mode" and fades to black after 30 seconds.
- The CIRCUITPY drive and the serial console stay available for editing and debugging.

## Button layout

USB connector at the top:

```
 ┌────────────────────────┐
 │  [ OLED ]       ( ◎ )  │   ◎ = knob (sets colors)
 │                        │
 │   1      2      3      │
 │   4      5      6      │
 │   7      8      9      │
 │  10     11     12      │
 └────────────────────────┘
```

Buttons 13–15 are part of the controller layout but never pressed. The knob is used only for setting colors.

## Installation

1. Back up anything already on the `CIRCUITPY` drive.
2. Install CircuitPython for the [MacroPad RP2040](https://circuitpython.org/board/adafruit_macropad_rp2040/). The code was developed on 10.x.
3. Copy `boot.py` and `code.py` to the root of the `CIRCUITPY` drive. You don't need anything in `lib/`.
4. Eject the drive, **unplug the USB cable and plug it back in**. `boot.py`, which sets up the controller, only runs on a full restart.
5. In Windows, press `Win+R` and enter `joy.cpl`. Select **MarcoPad HID**, open **Properties** and press the keys to test them.
6. Bind the buttons in your sim's controls menu.

## Setting the key colors

| Action | What happens |
|---|---|
| **Push the knob** | Programming mode starts. Key 1 blinks white. |
| **Turn left** | The blinking key shows the next color: Off, Red, Orange, Yellow, Green, Cyan, Blue, Purple, Magenta, White, then back to Off. |
| **Turn right** | Confirms the color and moves to the next key. After key 12 it goes back to key 1. |
| **Push the knob again** | Programming mode ends and the colors are saved. |

Things to know:

- A color you picked with left turns but didn't confirm with a right turn is discarded when you exit.
- To skip a key, turn right without turning left first. It keeps its color.
- If you choose "Off", the key blinks dim white so you can still see which key you're on.
- The keys send no button presses while you're in programming mode, so you can't trigger anything in the sim by accident.
- The colors are stored in the board's non-volatile memory, not in a file, so they survive unplugging.

`key-colors.html` explains the same steps with drawings and has a small simulator. Open it in any browser.

## Configuration

These settings are at the top of `code.py`:

| Setting | Default | Meaning |
|---|---|---|
| `BRIGHTNESS` | `0.3` | LED brightness, from 0.0 to 1.0 |
| `BLINK_SECONDS` | `0.25` | Blink speed while setting colors |
| `IDLE_SECONDS` | `30.0` | Seconds before "Control mode" fades out |
| `FADE_SECONDS` | `1.5` | How long the fade takes |
| `REVERSE_ENCODER` | `False` | Swaps the left and right knob directions |
| `PALETTE` | 10 colors | The colors the knob steps through |

## Troubleshooting

- **"Gamepad not found" in the serial console:** `boot.py` is missing from the root of the drive, or the board hasn't been restarted since you copied it. Unplug it and plug it back in.
- **Windows still shows the old name or button layout:** Windows remembers controllers it has seen before. Unplug the pad, open Device Manager, choose *View → Show hidden devices*, uninstall the old MacroPad entries and plug it back in. Don't uninstall your normal keyboard or mouse.
- **The colors look wrong, for example red shows as green:** the LED color order may be different on your board. Swap the byte order in `show()` in `code.py`.
- **Errors aren't shown on the screen:** the screen is used for this project's own text. Connect to the serial console, for example with [Mu](https://codewith.mu/) or [Tio](https://github.com/tio/tio), to see them.

## Files

| File | Purpose |
|---|---|
| `boot.py` | Sets up the USB controller and the "MarcoPad HID" name. Runs once at power-up. |
| `code.py` | Reads the keys and knob, sends button presses, handles LEDs, colors and the screen. |
| `key-colors.html` | Illustrated guide to setting the key colors. |

## Hardware

- [Adafruit MacroPad RP2040](https://www.adafruit.com/product/5128) (product 5128)
- Key switches and keycaps. Clear or translucent caps let the colors show best.
- A USB-C data cable

## 3D-printed case

This repository includes **two STL files** for a 3D-printed case that fits the original Adafruit MacroPad RP2040 board. Print both parts and fit the MacroPad inside.

## Credits

Made by **Frank Lemmen**, with the help of [Claude Code](https://claude.com/claude-code) (model: Claude Opus 5.5, medium effort).
