import threading
import traceback
from time import sleep
from spawn import spawn
from watch_bt import watch_bt
from btkeyboard import BtKeyboard
from spawn_stdin import spawn_stdin
from line_helpers import parse_line
from spawn_socket import spawn_socket
from time_helpers import seconds_from_now, is_past
from socket_helpers import send_to_socket, SOCKET_CAT, SOCKET_BUTTONS, SOCKET_TRANSMITTER
from last_address_helpers import read_last_address, write_last_address

ZERO_DELAY = 0
SHORT_DELAY = 3
ABORT_DELAY = 120
ATTEMPT_DELAY = 10
TIMER_INTERVAL = 0.25

btkeyboard = BtKeyboard()

attempt_at = seconds_from_now(SHORT_DELAY)
current_target = read_last_address()
external_unlock_at = None
internal_unlock_at = None

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
    attempt_event.clear()

    if is_past(external_unlock_at):
        print("External unlock")
        new_external_unlock_at(None)

    if is_past(internal_unlock_at):
        print("Internal unlock")
        new_internal_unlock_at(None)

    if not is_connected():
        report_disconnect()

    if should_attempt():
        local_target = current_target
        new_attempt_at(None)
        new_internal_unlock_at(ABORT_DELAY)

        print(f"Locking and trying {local_target}")
        report_attempt(local_target)
        connected = btkeyboard.connect(local_target)

        if local_target != current_target or external_unlock_at:
            print(f"Ignoring {local_target} changing its state to Connected={connected}")
            btkeyboard.disconnect()
        elif connected:
            print(f"Connected to {local_target}")
            report_connect(local_target)
            write_last_address(local_target)
        else:
            print(f"Couldn't connect to {local_target}")
            report_unsuccessful_attempt(current_target)

        new_internal_unlock_at(SHORT_DELAY)

    if should_schedule_attempt():
        print("Planning a new attempt")
        new_attempt_at(ATTEMPT_DELAY)

    if attempt_at or internal_unlock_at or external_unlock_at:
        sleep(TIMER_INTERVAL)
    else:
        attempt_event.wait()

def process_line(line):
    print(f"Processing {line}")
    what, value = parse_line(line)

    if what == "Retry":
        retry_target()
    elif what == "Next":
        next_target()
    elif what == "Test":
        test_target()
    elif what == "Pause":
        pause_timer()
    elif what == "Unpause":
        unpause_timer()
    else:
        print(f"Unknown {line}")

def pause_timer():
    new_external_unlock_at(ABORT_DELAY)

def unpause_timer():
    new_external_unlock_at(None)

def retry_target():
    if not current_target:
        next_target()
    else:
        new_attempt_at(ZERO_DELAY)
        btkeyboard.disconnect()

def next_target():
    addresses = get_addresses()

    if not addresses:
        print("No addresses to iterate")
        report_failure("Look around first!")
        return

    if current_target in addresses:
        new_index = addresses.index(current_target) + 1
        if new_index >= len(addresses):
            new_index = 0
    else:
        new_index = 0

    new_target(addresses[new_index])
    new_attempt_at(ZERO_DELAY)

def test_target():
    btkeyboard.test()

def on_bt_change(connected, address):
    if internal_unlock_at:
        print(f"Ignoring {address} changing to Connected={connected}")
        return

    if connected:
        print(f"{address} connected")
        new_target(address)
        new_attempt_at(ZERO_DELAY)
    elif address == current_target:
        print(f"{address} disconnected")
        new_attempt_at(ZERO_DELAY)

def new_target(value):
    global current_target
    current_target = value
    attempt_event.set()

def new_attempt_at(value):
    global attempt_at
    if value is None:
        attempt_at = None
    else:
        attempt_at = seconds_from_now(value)
    attempt_event.set()

def new_internal_unlock_at(value):
    global internal_unlock_at
    if value is None:
        internal_unlock_at = None
    else:
        internal_unlock_at = seconds_from_now(value)
    attempt_event.set()

def new_external_unlock_at(value):
    global external_unlock_at
    if value is None:
        external_unlock_at = None
    else:
        external_unlock_at = seconds_from_now(value)
    attempt_event.set()

def can_attempt():
    return not is_connected() and current_target and not external_unlock_at

def should_attempt():
    return can_attempt() and is_past(attempt_at)

def should_schedule_attempt():
    return can_attempt() and not attempt_at

def is_connected():
    return btkeyboard.is_connected and btkeyboard.target == current_target

def get_addresses():
    return [device["address"] for device in btkeyboard.devices]

def get_alias(address):
    for device in btkeyboard.devices:
        if device["address"] == address:
            return device["alias"]
    return address

def report_failure(message):
    send_to_socket(SOCKET_CAT, f"Flush: {message}")
    send_to_socket(SOCKET_BUTTONS, "Blink Short: Red")

def report_attempt(address):
    send_to_socket(SOCKET_CAT, f"Flush: Calling for {get_alias(address)}")
    send_to_socket(SOCKET_BUTTONS, "Blink Slow: Blue")

def report_connect(address):
    send_to_socket(SOCKET_CAT, f"Flush: Playing with {get_alias(address)}")
    send_to_socket(SOCKET_BUTTONS, "Blink Short: Green")
    send_to_socket(SOCKET_BUTTONS, "Light On: Blue")

def report_disconnect():
    send_to_socket(SOCKET_BUTTONS, "Light Off!")

def report_unsuccessful_attempt(address):
    send_to_socket(SOCKET_CAT, f"Flush: Can't reach {get_alias(address)}")
    send_to_socket(SOCKET_BUTTONS, "Blink Short: Red")

watch_loop = watch_bt(on_bt_change)
error_thread = spawn(manage_error)
timer_thread = spawn(manage_timer)
stdin_thread = spawn_stdin(process_line, error_event)
socket_thread = spawn_socket(SOCKET_TRANSMITTER, process_line, error_event)

watch_loop.run()
