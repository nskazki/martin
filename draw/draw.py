import os
import re
import sys
import socket
import select
import atexit
import random
import traceback
import threading
from glob import glob
from time import sleep
from PIL import Image,ImageDraw,ImageFont
from collections import deque
from datetime import datetime, timedelta

libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
assets = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
sys.path.append(libdir)

from waveshare_epd import epd2in13_V4

LOW_CHANCE = 7
FAIR_CHANCE = 1

FRAME_INTERVAL = 0.5
TIMER_INTERVAL = 0.25

IDLE_DELAY = 120
CLEAR_DELAY = 30
ABORT_DELAY = 30

STEP_COUNT = 4
TRUNCAT_AT = 18

CAN = "can"
LOW = "low"
FAIR = "fair"
DEFAULT = "default"

STATE_CLIMB = "cat_climb"
STATE_SIT_LEFT = "cat_sit_left"
STATE_LIE_DOWN_LEFT = "cat_lie_down_left"
STATE_SLEEP_LEFT = "cat_sleep_left"
STATE_LOOK_UP_LEFT = "cat_look_up_left"
STATE_RUN_LEFT = "cat_run_left"
STATE_SIT_RIGHT = "cat_sit_right"
STATE_RUN_RIGHT = "cat_run_right"
STATE_JUMP = "cat_jump"

RUN_STATES = [STATE_RUN_LEFT, STATE_RUN_RIGHT]
SLEEP_STATES = [STATE_SLEEP_LEFT]
LOOK_UP_STATES = [STATE_LOOK_UP_LEFT]
LIE_DOWN_STATES = [STATE_LIE_DOWN_LEFT]
REWINDABLE_STATES = [STATE_SIT_LEFT, STATE_LIE_DOWN_LEFT, STATE_SLEEP_LEFT, STATE_LOOK_UP_LEFT, STATE_SIT_RIGHT]

STATES = {
    STATE_CLIMB: {
        CAN: STATE_LOOK_UP_LEFT,
        LOW: STATE_RUN_LEFT,
        DEFAULT: STATE_SIT_LEFT
    },
    STATE_SIT_LEFT: {
        CAN: STATE_LOOK_UP_LEFT,
        LOW: [STATE_LIE_DOWN_LEFT, STATE_RUN_LEFT],
    },
    STATE_LIE_DOWN_LEFT: {
        LOW: [STATE_SLEEP_LEFT, STATE_SIT_LEFT]
    },
    STATE_SLEEP_LEFT: {
        LOW: STATE_LIE_DOWN_LEFT
    },
    STATE_LOOK_UP_LEFT: {
        LOW: STATE_SIT_LEFT
    },
    STATE_RUN_LEFT: {
        DEFAULT: STATE_SIT_RIGHT
    },
    STATE_SIT_RIGHT: {
        LOW: [STATE_RUN_RIGHT, STATE_JUMP]
    },
    STATE_RUN_RIGHT: {
        CAN: STATE_LOOK_UP_LEFT,
        DEFAULT: STATE_SIT_LEFT
    },
    STATE_JUMP: {
        DEFAULT: STATE_CLIMB
    }
}

epd = epd2in13_V4.EPD()
font = ImageFont.truetype(os.path.join(assets, "Sevillana.ttf"), 32)

step_at = None
clear_at = None
updated_at = datetime.now()

current_bt = None
current_ip = None
current_text = None
current_step = 0
current_state = STATE_CLIMB
target_states = []

frame_event = threading.Event()
timer_event = threading.Event()

display_ready = False

def spawn(target, *args):
    thread = threading.Thread(target=target, args=args)
    thread.daemon = True
    thread.start()
    return thread

def manage_timer():
    while True:
        try:
            timer_event.clear()

            if is_past(clear_at):
                print("Clearing by timer")
                new_text(None)
                new_clear_at(None)

            if is_past(step_at):
                if should_rewind():
                    target_step = current_step + (STEP_COUNT - current_step % STEP_COUNT)
                else:
                    target_step = current_step + 1

                if cycled_through_state() or should_rewind():
                    wipe_reached_state()
                    switch_state()
                    print(f"Switched to {current_state}")

                new_step(target_step)
                new_step_at(None)
                print(f"Incremented {current_step}")

            if clear_at or step_at:
                sleep(TIMER_INTERVAL)
            else:
                timer_event.wait()
        except Exception as e:
            print(f"An unexpected error occurred in the timer manager: {e}")
            traceback.print_exc()

def manage_frame():
    while True:
        try:
            frame_event.clear()

            text = current_text or current_bt or current_ip or "You are beautiful"
            text = truncate(text)

            can_idle = cycled_through_state() and in_one_of(SLEEP_STATES)
            should_idle = not current_text and is_older_than(updated_at, IDLE_DELAY)

            if can_idle and should_idle:
                print("Have been idle for a while")
                draw_display(with_text("rina.bmp", text))
                freeze_display()
            else:
                new_step_at(FRAME_INTERVAL)
                frame = (current_step % STEP_COUNT) + 1
                draw_display(with_text(f"{current_state}/{frame}.bmp", text))

            frame_event.wait()
        except Exception as e:
            print(f"An unexpected error occurred in the frame manager: {e}")
            traceback.print_exc()

def listen_to_stdin():
    while True:
        try:
            input = sys.stdin.readline().strip()
            process_lines(input)
        except Exception as e:
            print(f"An unexpected error occurred in the stdin listener: {e}")
            traceback.print_exc()

def listen_to_socket():
    socket_path = "/tmp/example_socket"
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
    if line.startswith("Run Left!"):
        plan_run_left()
    elif line.startswith("Run Right!"):
        plan_run_right()
    elif line.startswith("Look Up!"):
        plan_look_up()
    elif line.startswith("Lie Down!"):
        plan_lie_down()
    elif line.startswith("Sleep!"):
        plan_sleep()
    elif line.startswith("Flush:"):
        plan_flush(value)
    elif line.startswith("Draw:"):
        plan_draw(value)
    elif line.startswith("Clear!"):
        plan_clear()
    elif line.startswith("IP:"):
        plan_stat_update(what, value)
    elif line.startswith("BT:"):
        plan_stat_update(what, value)
    else:
        plan_draw(line)

def parse_line(input):
    match = re.match(r"(\w+):\s*(.*)", input)
    if match:
        return [match.group(1), match.group(2)]
    else:
        return [None, None]

def plan_run_left():
    new_target_state(STATE_RUN_LEFT)

def plan_run_right():
    new_target_state(STATE_RUN_RIGHT)

def plan_look_up():
    new_target_state(LOOK_UP_STATES)

def plan_sleep():
    new_target_state(SLEEP_STATES)

def plan_lie_down():
    new_target_state(LIE_DOWN_STATES)

def plan_flush(value):
    new_text(value)
    new_clear_at(CLEAR_DELAY)
    new_target_state(LOOK_UP_STATES)

def plan_draw(value):
    new_text(value)
    new_clear_at(ABORT_DELAY)
    new_target_state(LOOK_UP_STATES)

def plan_clear():
    new_text(None)
    new_clear_at(None)
    new_target_state(None)

def plan_stat_update(what, value):
    if what == "IP":
        new_ip(value)
    elif what == "BT":
        new_bt(value)
    new_target_state(LOOK_UP_STATES)

def new_ip(value):
    global current_ip
    touch_updated_at()
    current_ip = value
    frame_event.set()

def new_bt(value):
    global current_bt
    touch_updated_at()
    current_bt = value
    frame_event.set()

def new_step(value):
    global current_step
    current_step = value
    frame_event.set()

def new_text(value):
    global current_text
    touch_updated_at()
    current_text = value
    frame_event.set()

def new_target_state(states):
    global target_states
    touch_updated_at()
    target_states = wrap_list(states)
    timer_event.set()

def new_step_at(seconds):
    global step_at
    if seconds:
        step_at = seconds_from_now(seconds)
    else:
        step_at = None
    timer_event.set()

def new_clear_at(seconds):
    global clear_at
    if seconds:
        clear_at = seconds_from_now(seconds)
    else:
        clear_at = None
    timer_event.set()

def touch_updated_at():
    global updated_at
    updated_at = datetime.now()

def wipe_reached_state():
    global target_states
    if in_target_state():
        new_target_state(None)
        print(f"Reached the target state!")

def cycled_through_state():
    return (current_step % STEP_COUNT) + 1 == STEP_COUNT

def in_one_of(states):
    return current_state in states

def in_target_state():
    return in_one_of(target_states)

def should_rewind():
    return target_states and current_state in REWINDABLE_STATES

def switch_state():
    global current_state

    if target_states:
        path = bfs_path(current_state, target_states)
        if len(path) >= 2:
            current_state = path[1]
            return
        else:
            print(f"Couldn't find a path from {current_state} to {target_states}")

    rules = read_rules(current_state)

    for state in wrap_list(rules.get(LOW)):
        if low_chance():
            current_state = state
            return

    for state in wrap_list(rules.get(FAIR)):
        if fair_chance():
            current_state = state
            return

    default = rules.get(DEFAULT)
    if default:
        current_state = default

def bfs_path(start, targets):
    queue = deque([(start, [start])])
    visited = set()
    while queue:
        (state, path) = queue.popleft()
        if state in targets and len(path) != 1:
            return path
        if state not in visited:
            visited.add(state)
            for neighbor in flatten_list(read_rules(state).values()):
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))
    return []

def read_rules(state):
    result = STATES[state]
    if isinstance(result, str):
        return read_rules(result)
    else:
        return result

def wrap_list(value):
    if isinstance(value, list):
        return value
    elif value == None:
        return []
    else:
        return [value]

def flatten_list(nested_list):
    flattened = []
    for item in nested_list:
        if isinstance(item, list):
            flattened.extend(flatten_list(item))
        else:
            flattened.append(item)
    return flattened

def seconds_ago(seconds):
    return datetime.now() - timedelta(seconds=seconds)

def seconds_from_now(seconds):
    return datetime.now() + timedelta(seconds=seconds)

def draw_display(image):
    if display_ready:
        epd.displayPartial(epd.getbuffer(image))
    else:
        init_display(image)

def init_display(image):
    global display_ready
    print("Initalizing display")
    display_ready = True
    epd.init()
    epd.displayPartBaseImage(epd.getbuffer(image))

def freeze_display():
    global display_ready
    print("Freezing display")
    display_ready = False
    epd.sleep()

def halt_display():
    print("Exiting the EPD module")
    if display_ready:
        epd.sleep()
    epd2in13_V4.epdconfig.module_exit(cleanup=True)

def with_text(asset_path, text):
    path = os.path.join(assets, asset_path)
    base = Image.new("1", (250, 122), 255)
    base.paste(Image.open(path), (0, 0))
    draw = ImageDraw.Draw(base)
    draw.text((0, 0), text, font=font, fill=0)
    return base

def low_chance():
    return random.randint(0, LOW_CHANCE) == 0

def fair_chance():
    return random.randint(0, FAIR_CHANCE) == 0

def is_past(time):
    return time and time <= datetime.now()

def is_older_than(time, seconds):
    return time and time <= seconds_ago(seconds)

def truncate(text):
    if len(text) >= TRUNCAT_AT:
        return text[:TRUNCAT_AT] + "..."
    else:
        return text

atexit.register(halt_display)

frame_thread = spawn(manage_frame)
timer_thread = spawn(manage_timer)
stdin_thread = spawn(listen_to_stdin)
socket_thread = spawn(listen_to_socket)

frame_thread.join()
timer_thread.join()
stdin_thread.join()
socket_thread.join()
