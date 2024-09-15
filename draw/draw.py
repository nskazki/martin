import atexit
import traceback
import threading
from text_helpers import truncate
from list_helpers import wrap_list
from line_helpers import parse_line
from time_helpers import seconds_from_now, is_past, is_older_than
from state_helpers import next_state, CAN, LOW, FAIR, DEFAULT
from display_helpers import draw_display, freeze_display, halt_display, with_text
from spawn import spawn
from spawn_stdin import spawn_stdin
from spawn_socket import spawn_socket
from time import sleep
from datetime import datetime

FRAME_INTERVAL = 0.5
TIMER_INTERVAL = 0.25

IDLE_DELAY = 120
CLEAR_DELAY = 30
ABORT_DELAY = 30

STEP_COUNT = 4
TRUNCAT_AT = 18

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
        DEFAULT: STATE_SIT_LEFT
    },
    STATE_JUMP: {
        DEFAULT: STATE_CLIMB
    }
}

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
            text = truncate(text, TRUNCAT_AT)

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
    frame_event.set()

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
    current_state = next_state(STATES, current_state, target_states)

atexit.register(halt_display)

frame_thread = spawn(manage_frame)
timer_thread = spawn(manage_timer)
stdin_thread = spawn_stdin(process_line)
socket_thread = spawn_socket("/tmp/cat_socket", process_line)

frame_thread.join()
timer_thread.join()
stdin_thread.join()
socket_thread.join()
