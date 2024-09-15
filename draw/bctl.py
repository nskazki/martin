import sys
import atexit
import pexpect
import threading
import traceback
from time import sleep
from spawn import spawn
from spawn_stdin import spawn_stdin
from spawn_socket import spawn_socket
from time_helpers import is_past, seconds_from_now
from socket_helpers import send_to_socket
from socket_helpers import send_to_socket, SOCKET_CAT, SOCKET_BCTL, SOCKET_BUTTONS
from stdout_logger import StdoutLogger

BCTL_TIMEOUT = 5
USER_TIMEOUT = 60
WARNING_TIMEOUT = 20
TIMER_INTERVAL = 1

bctl = None
pkey = None
warn_at = None
reject_at = None
timer_event = threading.Event()

def manage_reject():
    global warn_at, reject_at

    while True:
        try:
            timer_event.clear()

            if is_past(warn_at):
                warn_at = None
                send_to_socket(SOCKET_CAT, "Draw: Looking some more")

            if is_past(reject_at):
                reject_at = None
                close_bctl()

            if warn_at or reject_at:
                sleep(TIMER_INTERVAL)
            else:
                timer_event.wait()
        except Exception as e:
            print(f"An unexpected error occurred in the rejection manager: {e}")
            traceback.print_exc()

def handle_yes():
    global warn_at, reject_at

    if not pkey and not bctl:
        warn_at = seconds_from_now(WARNING_TIMEOUT)
        reject_at = None
        timer_event.set()

        send_to_socket(SOCKET_CAT, "Draw: Looking around")
        send_to_socket(SOCKET_BUTTONS, "Blink Slow: blue")
        wait_passkey()

        if pkey:
            warn_at = None
            reject_at = seconds_from_now(USER_TIMEOUT)
            timer_event.set()

            send_to_socket(SOCKET_CAT, f"Confirm? {pkey}")
            send_to_socket(SOCKET_BUTTONS, "Blink Fast: blue")
        else:
            send_to_socket(SOCKET_CAT, "Flush: Nobody's around")
            send_to_socket(SOCKET_CAT, "Lie Down!")
            send_to_socket(SOCKET_BUTTONS, "Blink: red")
    elif pkey:
        reject_at = None

        if pair_passkey():
            send_to_socket(SOCKET_CAT, f"Flush: Found a friend!")
            send_to_socket(SOCKET_CAT, "Run Left!")
            send_to_socket(SOCKET_BUTTONS, "Blink: green")
        else:
            send_to_socket(SOCKET_CAT, f"Flush: Can't be friends")
            send_to_socket(SOCKET_CAT, "Lie Down!")
            send_to_socket(SOCKET_BUTTONS, "Blink: red")

def close_bctl():
    global bctl

    if not bctl:
        return

    try:
        bctl.sendline("no")
        bctl.sendline("discoverable off")
        bctl.expect("Changing discoverable off succeeded")
    except Exception:
        print("Couldn't hide in time!")
    finally:
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
    except Exception:
        print("Couldn't spawn in time!")
        close_bctl()

def wait_passkey():
    global pkey

    spawn_bctl()

    if not bctl:
        return

    try:
        bctl.sendline("power on")
        bctl.expect("Changing power on succeeded")
        bctl.sendline("system-alias Martin")
        bctl.expect("Changing Martin succeeded")
        bctl.sendline("discoverable on")
        bctl.expect("Changing discoverable on succeeded")
        bctl.sendline("default-agent")
        bctl.expect(r"Confirm passkey (\d+)", timeout=USER_TIMEOUT)
        pkey = bctl.match.group(1).decode("utf-8")
    except Exception:
        print("Didn't receive a pkey in time!")
        close_bctl()

def pair_passkey():
    global pkey

    if not bctl or not pkey:
        return

    pkey = None

    try:
        bctl.sendline("yes")
        bctl.expect(r"Authorize service|Bonded: yes")
        match = bctl.match.group(0).decode("utf-8")

        if match == "Authorize service":
            bctl.sendline("yes")
            bctl.expect("Player")

        return True
    except Exception:
        print("Couldn't pair in time!")
        return False
    finally:
        close_bctl()

def process_line(line):
    if line.startswith("Yes!"):
        handle_yes()
    else:
        print(f"Unknown {line}")

atexit.register(close_bctl)

timer_thread = spawn(manage_reject)
stdin_thread = spawn_stdin(process_line)
socket_thread = spawn_socket(SOCKET_BCTL, process_line)

stdin_thread.join()
socket_thread.join()
timer_thread.join()
