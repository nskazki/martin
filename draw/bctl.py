import atexit
import pexpect
import threading
import traceback
from time import sleep
from spawn import spawn
from watch_bt import parse_address
from spawn_stdin import spawn_stdin
from spawn_socket import spawn_socket
from time_helpers import is_past, seconds_from_now
from socket_helpers import send_to_socket
from socket_helpers import send_to_socket, SOCKET_CAT, SOCKET_BCTL, SOCKET_BUTTONS, SOCKET_TRANSMITTER
from stdout_logger import StdoutLogger

BCTL_TIMEOUT = 5
PKEY_TIMEOUT = 60
PKEY_WARNING = 50
CONFIRM_TIMEOUT = 15
CONFIRM_WARNING = 10

TIMER_INTERVAL = 1

bctl = None
pkey = None
warn_at = None
reject_at = None
timer_event = threading.Event()
error_event = threading.Event()

def manage_timer():
    try:
        while True:
            iterate_timer()
    except Exception as e:
        print(f"An unexpected error occurred in the rejection manager: {e}")
        traceback.print_exc()
        error_event.set()

def iterate_timer():
    timer_event.clear()

    if is_past(warn_at):
        new_warn_at(None)
        if pkey:
            send_to_socket(SOCKET_CAT, "Draw: Unsure about them")
            send_to_socket(SOCKET_BUTTONS, "Blink Fast: Blue")
        else:
            send_to_socket(SOCKET_CAT, "Draw: Looking some more")
            send_to_socket(SOCKET_BUTTONS, "Blink Fast: Blue")

    if is_past(reject_at):
        new_reject_at(None)
        close_bctl()
        send_to_socket(SOCKET_CAT, "Flush: Didn't like them")
        send_to_socket(SOCKET_CAT, "Lie Down!")
        send_to_socket(SOCKET_BUTTONS, "Blink Short: Red")
        send_to_socket(SOCKET_TRANSMITTER, "Unpause!")

    if warn_at or reject_at:
        sleep(TIMER_INTERVAL)
    else:
        timer_event.wait()

def handle_pair():
    if not bctl:
        new_warn_at(PKEY_WARNING)
        new_reject_at(None)

        send_to_socket(SOCKET_CAT, "Draw: Looking around")
        send_to_socket(SOCKET_BUTTONS, "Blink Slow: Blue")
        send_to_socket(SOCKET_TRANSMITTER, "Pause!")
        wait_passkey()

        if pkey:
            new_warn_at(CONFIRM_WARNING)
            new_reject_at(CONFIRM_TIMEOUT)

            send_to_socket(SOCKET_CAT, f"Befriend? {pkey}")
            send_to_socket(SOCKET_BUTTONS, "Blink Slow: Blue")
        else:
            send_to_socket(SOCKET_CAT, "Flush: Nobody's around")
            send_to_socket(SOCKET_CAT, "Lie Down!")
            send_to_socket(SOCKET_BUTTONS, "Blink Short: Red")
            send_to_socket(SOCKET_TRANSMITTER, "Unpause!")
    elif pkey:
        new_warn_at(None)
        new_reject_at(None)

        address = pair_passkey()
        if address:
            send_to_socket(SOCKET_CAT, "Flush: Found a friend!")
            send_to_socket(SOCKET_CAT, "Run Left!")
            send_to_socket(SOCKET_BUTTONS, "Blink Short: Green")
            send_to_socket(SOCKET_TRANSMITTER, f"Unpause: {address}")
        else:
            send_to_socket(SOCKET_CAT, "Flush: Can't be friends")
            send_to_socket(SOCKET_CAT, "Lie Down!")
            send_to_socket(SOCKET_BUTTONS, "Blink Short: Red")
            send_to_socket(SOCKET_TRANSMITTER, "Unpause!")
    else:
        print("Ignoring!")

def new_warn_at(in_seconds):
    global warn_at
    if in_seconds is None:
        warn_at = None
    else:
        warn_at = seconds_from_now(in_seconds)
    timer_event.set()

def new_reject_at(in_seconds):
    global reject_at
    if in_seconds is None:
        reject_at = None
    else:
        reject_at = seconds_from_now(in_seconds)
    timer_event.set()

def close_bctl():
    global bctl

    if not bctl:
        return

    try:
        bctl.sendline("no")
        bctl.sendline("discoverable off")
        bctl.expect("Changing discoverable off succeeded")
    except Exception as e:
        print(f"Couldn't turn off discoverability due to {e}")
    finally:
        if bctl:
            bctl.close()
        bctl = None

def spawn_bctl():
    global bctl

    if bctl:
        close_bctl()

    try:
        bctl = pexpect.spawn("bluetoothctl")
        bctl.logfile = StdoutLogger()
        bctl.timeout = BCTL_TIMEOUT
        bctl.expect("#")
    except Exception as e:
        print(f"Couldn't spawn bluetoothctl due to {e}")
        close_bctl()

def wait_passkey():
    global pkey

    spawn_bctl()

    if not bctl:
        return

    try:
        pkey = None
        bctl.sendline("power on")
        bctl.expect("Changing power on succeeded")
        bctl.sendline("system-alias Martin")
        bctl.expect("Changing Martin succeeded")
        bctl.sendline("discoverable on")
        bctl.expect("Changing discoverable on succeeded")
        bctl.sendline("default-agent")
        bctl.expect(r"Confirm passkey (\d+)", timeout=PKEY_TIMEOUT)
        pkey = bctl.match.group(1).decode("utf-8")
    except Exception as e:
        print(f"Couldn't receive a passkey due to {e}")
        close_bctl()

def pair_passkey():
    try:
        bctl.sendline("yes")
        bctl.expect(r"Authorize service|[\w:]+ Bonded: yes")
        match = bctl.match.group(0).decode("utf-8")

        if "Authorize service" in match:
            bctl.sendline("yes")
            bctl.expect(r"Player [\w\/_]+")
            match = bctl.match.group(0).decode("utf-8")

        return parse_address(match)
    except Exception as e:
        print(f"Couldn't pair due to {e}")
        return False
    finally:
        close_bctl()

def process_line(line):
    print(f"Processing {line}")
    if line == "Pair!":
        handle_pair()
    elif line == "Close!":
        close_bctl()
    else:
        print(f"Unknown {line}")

atexit.register(close_bctl)

timer_thread = spawn(manage_timer)
stdin_thread = spawn_stdin(process_line, error_event)
socket_thread = spawn_socket(SOCKET_BCTL, process_line, error_event)

error_event.wait()
print("An error occured. Exiting!")
