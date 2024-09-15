import signal
import socket
import traceback
import threading
import buttonshim
from time import sleep
from spawn import spawn
from spawn_stdin import spawn_stdin
from spawn_socket import spawn_socket
from line_helpers import parse_line
from time_helpers import is_past, seconds_from_now
from evdev import uinput, UInput, ecodes as e

TIMER_INTERVAL = 0.1
FAST_BLINK_INTERVAL = 0.5
SLOW_BLINK_INTERVAL = 1

KEYCODES = [e.KEY_A, e.KEY_B, e.KEY_C, e.KEY_D, e.KEY_E]
BUTTONS = [buttonshim.BUTTON_A, buttonshim.BUTTON_B, buttonshim.BUTTON_C, buttonshim.BUTTON_D, buttonshim.BUTTON_E]

COLOR_OFF = [0x00, 0x00, 0x00]
COLOR_RED = [0xff, 0x00, 0x00]
COLOR_BLUE = [0x00, 0x00, 0xff]
COLOR_GREEN = [0x00, 0xff, 0x00]

toggle_at = None
pixel_event = threading.Event()
current_state = False
current_color = None
current_interval = None

ui = UInput({e.EV_KEY: KEYCODES}, name="Button-SHIM", bustype=e.BUS_USB)
buttonshim.set_pixel(*COLOR_OFF)

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

def manage_pixel():
    global toggle_at, current_state

    while True:
        try:
            pixel_event.clear()

            if not current_color:
                buttonshim.set_pixel(*COLOR_OFF)
            elif not toggle_at or is_past(toggle_at):
                toggle_at = seconds_from_now(current_interval)
                current_state = not current_state
                if current_state:
                    buttonshim.set_pixel(*COLOR_OFF)
                else:
                    buttonshim.set_pixel(*current_color)

            if toggle_at:
                sleep(TIMER_INTERVAL)
            else:
                pixel_event.wait()
        except Exception as e:
            print(f"An unexpected error occurred in the pixel manager: {e}")
            traceback.print_exc()

def process_line(line):
    what, value = parse_line(line)
    if line.startswith("Blink Slow:"):
        plan_start_blinking(value, SLOW_BLINK_INTERVAL)
    elif line.startswith("Blink Fast:"):
        plan_start_blinking(value, FAST_BLINK_INTERVAL)
    elif line.startswith("Stop Blinking!"):
        plan_stop_blinking()
    else:
        print(f"Unknown {line}")

def plan_start_blinking(value, interval):
    global toggle_at, current_state, current_color, current_interval
    toggle_at = None
    current_state = False
    current_color = encode_color(value)
    current_interval = interval
    pixel_event.set()
    print(f"Start Blinking {value} each {interval} seconds")

def plan_stop_blinking():
    global toggle_at, current_state, current_color, current_interval
    toggle_at = None
    current_state = False
    current_color = None
    current_interval = None
    pixel_event.set()
    print("Stop Blinking")

def encode_color(name):
    if name == "red":
        return COLOR_RED
    elif name == "blue":
        return COLOR_BLUE
    elif name == "green":
        return COLOR_GREEN

pixel_thread = spawn(manage_pixel)
stdin_thread = spawn_stdin(process_line)
socket_thread = spawn_socket("/tmp/buttons_socket", process_line)

pixel_thread.join()
stdin_thread.join()
socket_thread.join()
# signal.pause()
