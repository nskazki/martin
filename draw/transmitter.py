import threading
import traceback
from time import sleep
from spawn import spawn
from watch_bt import watch_bt
from btkeyboard import BtKeyboard
from spawn_stdin import spawn_stdin
from spawn_socket import spawn_socket
from time_helpers import seconds_from_now, is_past
from socket_helpers import send_to_socket, SOCKET_CAT, SOCKET_BUTTONS, SOCKET_TRANSMITTER
from last_address_helpers import read_last_address, write_last_address

FIRST_ATTEMPT = 1
ATTEMPT_DELAY = 10
UNPAUSE_DELAY = 120
TIMER_INTERVAL = 0.25

bt_keyboard = BtKeyboard()

unpause_at = None
attempt_at = seconds_from_now(FIRST_ATTEMPT)
current_address = read_last_address()

watch_loop = None
error_event = threading.Event()
attempt_event = threading.Event()

def manage_error():
    error_event.wait()
    print("An error occured. Exiting!")
    if watch_loop:
        watch_loop.quit()

def manage_timer():
    try:
        while True:
            iterate_timer()
    except Exception as e:
        print(f"An unexpected error occurred in the timer manager: {e}")
        traceback.print_exc()
        error_event.set()

def iterate_timer():
    global attempt_at, unpause_at
    attempt_event.clear()

    if is_past(unpause_at):
        print("Unpausing")
        unpause_at = None

    if not unpause_at and not is_connected() and (not attempt_at or is_past(attempt_at)):
        print("Currently disconnected")
        report_disconnect()
        attempt_at = None
        local_address = current_address

        if current_address:
            print(f"Trying {local_address}")
            report_attempt(local_address)
            if bt_keyboard.connect(local_address):
                print(f"Connected to {local_address}")
                write_last_address(local_address)
                report_connect(local_address)
            else:
                print(f"Couldn't connect to {local_address}")

    if is_connected() or not current_address:
        print("Will wait for an event")
        attempt_event.wait()
    else:
        if not unpause_at and not attempt_at:
            print(f"Will try again in {ATTEMPT_DELAY} seconds")
            attempt_at = seconds_from_now(ATTEMPT_DELAY)
        sleep(TIMER_INTERVAL)

def process_line(line):
    print(f"Processing {line}")
    if line == "Retry!":
        retry_address()
    elif line == "Next!":
        next_address()
    elif line == "Test!":
        test_address()
    elif line == "Pause!":
        pause_timer()
    elif line == "Unpause!":
        unpause_timer()
    else:
        print(f"Unknown {line}")

def pause_timer():
    global unpause_at
    unpause_at = seconds_from_now(UNPAUSE_DELAY)
    attempt_event.set()

def unpause_timer():
    global unpause_at
    unpause_at = False
    attempt_event.set()

def retry_address():
    if not current_address:
        next_address()
    else:
        try_address()

def next_address():
    addresses = get_addresses()

    if not addresses:
        print("No addresses to iterate")
        report_failure()
        return

    if current_address in addresses:
        new_index = addresses.index(current_address) + 1
        if new_index >= len(addresses):
            new_index = 0
    else:
        new_index = 0

    new_address(addresses[new_index])

def test_address():
    bt_keyboard.test()

def on_bt_change(connected, address):
    if connected:
        print(f"{address} connected")
        new_address(address)
    elif address == current_address:
        print(f"{address} disconnected")
        retry_address()

def new_address(address):
    global current_address
    current_address = address
    try_address()

def try_address():
    global attempt_at
    attempt_at = None
    attempt_event.set()

def is_connected():
    return bt_keyboard.is_connected and bt_keyboard.target == current_address

def get_addresses():
    return [device["address"] for device in bt_keyboard.devices]

def get_alias(address):
    for device in bt_keyboard.devices:
        if device["address"] == address:
            return device["alias"]
    return address

def report_failure():
    send_to_socket(SOCKET_BUTTONS, "Blink Short: Red")

def report_attempt(address):
    send_to_socket(SOCKET_CAT, f"Flush: Calling for {get_alias(address)}")
    send_to_socket(SOCKET_BUTTONS, "Blink Short: Blue")

def report_connect(address):
    send_to_socket(SOCKET_CAT, f"Flush: Playing with {get_alias(address)}")
    send_to_socket(SOCKET_BUTTONS, "Light On: Blue")

def report_disconnect():
    send_to_socket(SOCKET_BUTTONS, "Light Off!")

watch_loop = watch_bt(on_bt_change)
error_thread = spawn(manage_error)
timer_thread = spawn(manage_timer)
stdin_thread = spawn_stdin(process_line, error_event)
socket_thread = spawn_socket(SOCKET_TRANSMITTER, process_line, error_event)

watch_loop.run()
