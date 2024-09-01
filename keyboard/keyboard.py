#!/usr/bin/env python

import signal
import buttonshim
from evdev import uinput, UInput, ecodes as e

KEYNAMES = ["A", "B", "C", "D", "E"]
KEYCODES = [e.KEY_A, e.KEY_B, e.KEY_C, e.KEY_D, e.KEY_E]
BUTTONS = [buttonshim.BUTTON_A, buttonshim.BUTTON_B, buttonshim.BUTTON_C, buttonshim.BUTTON_D, buttonshim.BUTTON_E]

ui = UInput({e.EV_KEY: KEYCODES}, name="Button-SHIM", bustype=e.BUS_USB)

@buttonshim.on_press(BUTTONS)
def button_p_handler(button, pressed):
    keycode = KEYCODES[button]
    keyname = KEYNAMES[button]
    printf(f"Press {keyname}")
    ui.write(e.EV_KEY, keycode, 1)
    ui.syn()

@buttonshim.on_release(BUTTONS)
def button_r_handler(button, pressed):
    keycode = KEYCODES[button]
    keyname = KEYNAMES[button]
    printf(f"Release {keyname}")
    ui.write(e.EV_KEY, keycode, 0)
    ui.syn()

signal.pause()
