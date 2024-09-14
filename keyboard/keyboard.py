#!/usr/bin/env python

import signal
import socket
import buttonshim
from evdev import uinput, UInput, ecodes as e

KEYCODES = [e.KEY_A, e.KEY_B, e.KEY_C, e.KEY_D, e.KEY_E]
BUTTONS = [buttonshim.BUTTON_A, buttonshim.BUTTON_B, buttonshim.BUTTON_C, buttonshim.BUTTON_D, buttonshim.BUTTON_E]

ui = UInput({e.EV_KEY: KEYCODES}, name="Button-SHIM", bustype=e.BUS_USB)
buttonshim.set_pixel(0x00, 0x00, 0x00)

@buttonshim.on_press(BUTTONS)
def button_p_handler(button, pressed):
    keycode = KEYCODES[button]

    if keycode == e.KEY_D:
        send_run_right()
    elif keycode == e.KEY_C:
        send_look_up()
    elif keycode == e.KEY_B:
        send_lie_down()
    elif keycode == e.KEY_A:
        send_run_left()

    ui.write(e.EV_KEY, keycode, 1)
    ui.syn()

@buttonshim.on_release(BUTTONS)
def button_r_handler(button, pressed):
    keycode = KEYCODES[button]
    ui.write(e.EV_KEY, keycode, 0)
    ui.syn()

def send_run_right():
    send("Run Right!")

def send_lie_down():
    send("Lie Down!")

def send_look_up():
    send("Look Up!")

def send_run_left():
    send("Run Left!")

def send(message):
    socket_path = "/tmp/example_socket"
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client_socket.connect(socket_path)
    client_socket.sendall(message.encode('utf-8'))
    client_socket.close()

signal.pause()
