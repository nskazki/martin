#!/usr/bin/env python

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
        run_right()
    elif keycode == e.KEY_C:
        look_up()
    elif keycode == e.KEY_B:
        lie_down()
    elif keycode == e.KEY_A:
        run_left()

    ui.write(e.EV_KEY, keycode, 1)
    ui.syn()

@buttonshim.on_release(BUTTONS)
def button_r_handler(button, pressed):
    keycode = KEYCODES[button]
    ui.write(e.EV_KEY, keycode, 0)
    ui.syn()

def run_right():
    command_cat("Run Right!")

def lie_down():
    command_cat("Lie Down!")

def look_up():
    command_cat("Look Up!")

def run_left():
    command_cat("Run Left!")

def command_cat(message):
    socket_path = "/tmp/cat_socket"
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client_socket.connect(socket_path)
    client_socket.sendall(message.encode('utf-8'))
    client_socket.close()

def spawn(target, *args):
    thread = threading.Thread(target=target, args=args)
    thread.daemon = True
    thread.start()
    return thread

def manage_timer():
    while True:
        try:
            timer_event.clear()

            if is_past(step_at):
                new_step(current_step + 1)
                new_step_at(None)
                print(f"Incremented {current_step}")

            timer_event.wait()
        except Exception as e:
            print(f"An unexpected error occurred in the timer manager: {e}")
            traceback.print_exc()

def listen_to_socket():
    socket_path = "/tmp/buttons_socket"
    socket = create_socket(socket_path)
    while True:
        connection, _ = socket.accept()
        print(f"Handling a connection")
        spawn(listen_to_connection, connection)

def listen_to_connection(connection):
    while True:
        data = connection.recv(1024)
        if data:
            try:
                input = data.decode("utf-8")
                print(f"Processing {input}")
                process_lines(input)
            except Exception as e:
                print(f"An unexpected error occurred in the socket listener: {e}")
                traceback.print_exc()
        else:
            print(f"Closing the connection")
            connection.close()
            break

def create_socket(socket_path):
    if os.path.exists(socket_path):
        os.remove(socket_path)

    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(socket_path)
    server_sock.listen(1)
    return server_sock

def process_lines(lines):
    for line in lines.splitlines():
        process_line(line)

def process_line(line):
    what, value = parse_line(line)
    if line.startswith("Blink Slow!"):
        plan_run_left()
    elif line.startswith("Blink Fast!"):
        plan_run_right()

timer_thread = spawn(manage_timer)
socket_thread = spawn(listen_to_socket)

timer_thread.join()
socket_thread.join()
