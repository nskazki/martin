import atexit
import traceback
import threading
import buttonshim
from time import sleep
from spawn import spawn
from bash_helpers import bash_halt, bash_led_on, bash_led_off
from spawn_stdin import spawn_stdin
from spawn_socket import spawn_socket
from line_helpers import parse_line
from time_helpers import is_past, seconds_from_now
from socket_helpers import send_to_socket, SOCKET_CAT, SOCKET_BCTL, SOCKET_BUTTONS, SOCKET_TRANSMITTER
from evdev import UInput, ecodes

TIMER_INTERVAL = 0.1
FAST_BLINK_INTERVAL = 0.5
SLOW_BLINK_INTERVAL = 1

KEYCODES = [ecodes.KEY_A, ecodes.KEY_B, ecodes.KEY_C, ecodes.KEY_D, ecodes.KEY_E]
BUTTONS = [buttonshim.BUTTON_A, buttonshim.BUTTON_B, buttonshim.BUTTON_C, buttonshim.BUTTON_D, buttonshim.BUTTON_E]

COLOR_OFF = [0x00, 0x00, 0x00]
COLOR_RED = [0x3f, 0x00, 0x00]
COLOR_BLUE = [0x00, 0x00, 0x4f]
COLOR_GREEN = [0x00, 0x3f, 0x00]

cat_layer = True

static_color = None

blink_at = None
blink_state = False
blink_color = None
blink_interval = None
blink_countdown = None

pixel_event = threading.Event()
error_event = threading.Event()

ui = UInput({ecodes.EV_KEY: KEYCODES}, name="Button-SHIM", bustype=ecodes.BUS_USB)

@buttonshim.on_press(BUTTONS)
def button_p_handler(button, _):
    try:
        process_button_press(button)
    except Exception as e:
        print(f"An unexpected error occurred in the button press handler: {e}")
        traceback.print_exc()
        error_event.set()

@buttonshim.on_release(BUTTONS)
def button_r_handler(button, _):
    try:
        process_button_release(button)
    except Exception as e:
        print(f"An unexpected error occurred in the button press handler: {e}")
        traceback.print_exc()
        error_event.set()

def process_button_release(button):
    keycode = KEYCODES[button]
    ui.write(ecodes.EV_KEY, keycode, 0)
    ui.syn()

def process_button_press(button):
    keycode = KEYCODES[button]

    if keycode == ecodes.KEY_E:
        toggle_layer()
    elif keycode == ecodes.KEY_D:
        if cat_layer:
            cat_run_right()
        else:
            bctl_pair()
    elif keycode == ecodes.KEY_C:
        if cat_layer:
            cat_say_wish()
        else:
            transmitter_retry()
    elif keycode == ecodes.KEY_B:
        if cat_layer:
            cat_lie_down()
        else:
            transmitter_next()
    elif keycode == ecodes.KEY_A:
        if cat_layer:
            cat_run_left()
        else:
            all_halt()

    ui.write(ecodes.EV_KEY, keycode, 1)
    ui.syn()

def toggle_layer():
    global cat_layer
    cat_layer = not cat_layer
    if cat_layer:
        print(f"Switched to the cat layer")
        bash_led_off()
    else:
        print(f"Switched from the cat layer")
        bash_led_on()

def bctl_pair():
    send_to_socket(SOCKET_BCTL, "Pair!")

def transmitter_retry():
    send_to_socket(SOCKET_TRANSMITTER, "Retry!")

def transmitter_next():
    send_to_socket(SOCKET_TRANSMITTER, "Next!")

def all_halt():
    send_to_socket(SOCKET_CAT, "Halt: See you space cowboy")
    bash_halt(5)

def cat_run_right():
    send_to_socket(SOCKET_CAT, "Run Right!")

def cat_lie_down():
    send_to_socket(SOCKET_CAT, "Lie Down!")

def cat_say_wish():
    send_to_socket(SOCKET_CAT, "Say Wish!")

def cat_run_left():
    send_to_socket(SOCKET_CAT, "Run Left!")

def manage_pixel():
    try:
        while True:
            iterate_pixel()
    except Exception as e:
        print(f"An unexpected error occurred in the pixel manager: {e}")
        traceback.print_exc()
        error_event.set()

def iterate_pixel():
    global blink_at, blink_state, blink_color, blink_countdown

    pixel_event.clear()

    if not blink_color and not static_color:
        turn_pixel_off()
    if not blink_at or is_past(blink_at):
        if blink_countdown and not blink_state:
            blink_countdown -= 1
            print(f"Decremented {blink_countdown}")

        if not blink_countdown:
            blink_at = None
            blink_color = None

        if blink_color:
            blink_at = seconds_from_now(blink_interval)
            blink_state = not blink_state

            if blink_state:
                buttonshim.set_pixel(*blink_color)
            else:
                turn_pixel_off()
        elif static_color:
            buttonshim.set_pixel(*static_color)

    if blink_at:
        sleep(TIMER_INTERVAL)
    else:
        pixel_event.wait()

def turn_pixel_off():
    buttonshim.set_pixel(*COLOR_OFF)

def process_line(line):
    print(f"Processing {line}")
    what, value = parse_line(line)
    if what == "Light On":
        plan_light_on(value)
    elif what == "Light Off":
        plan_light_off()
    elif what == "Blink Short":
        plan_short_blink(value)
    elif what == "Blink Slow":
        plan_start_blinking(value, SLOW_BLINK_INTERVAL)
    elif what == "Blink Fast":
        plan_start_blinking(value, FAST_BLINK_INTERVAL)
    elif what == "Stop Blinking":
        plan_stop_blinking()
    else:
        print(f"Unknown {line}")

def plan_light_on(value):
    global static_color
    static_color = encode_color(value)
    pixel_event.set()

def plan_light_off():
    global static_color
    static_color = None
    pixel_event.set()

def plan_short_blink(value):
    plan_start_blinking(value, FAST_BLINK_INTERVAL, 4)

def plan_start_blinking(value, interval, countdown=100):
    global blink_at, blink_state, blink_color, blink_interval, blink_countdown
    blink_at = None
    blink_state = False
    blink_color = encode_color(value)
    blink_interval = interval
    blink_countdown = countdown
    pixel_event.set()

def plan_stop_blinking():
    global blink_at, blink_state, blink_color, blink_interval, blink_countdown
    blink_at = None
    blink_state = False
    blink_color = None
    blink_interval = None
    blink_countdown = None
    pixel_event.set()

def encode_color(name):
    if name == "Red":
        return COLOR_RED
    elif name == "Blue":
        return COLOR_BLUE
    elif name == "Green":
        return COLOR_GREEN

bash_led_off()
turn_pixel_off()

atexit.register(turn_pixel_off)

pixel_thread = spawn(manage_pixel)
stdin_thread = spawn_stdin(process_line, error_event)
socket_thread = spawn_socket(SOCKET_BUTTONS, process_line, error_event)

error_event.wait()
print("An error occured. Exiting!")
