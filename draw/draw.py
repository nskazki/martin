import os
import re
import sys
import socket
import select
import atexit
import traceback
import threading
from glob import glob
from time import sleep
from PIL import Image,ImageDraw,ImageFont
from datetime import datetime, timedelta

libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
assets = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
sys.path.append(libdir)

from waveshare_epd import epd2in13_V4

TRUNCAT_AT = 18
IDLE_DELAY = 5
CLEAR_DELAY = 3
TIMER_INTERVAL = 0.25
FRAME_INTERVAL = 0.5

epd = epd2in13_V4.EPD()
font = ImageFont.truetype(os.path.join(assets, "Sevillana.ttf"), 32)

step_at = None
clear_at = None
updated_at = datetime.now()

current_bt = None
current_ip = None
current_text = None

step_count = 8
current_step = 0

frame_event = threading.Event()
timer_event = threading.Event()

display_ready = False

def spawn(target):
    thread = threading.Thread(target=target)
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
                print("Incrementing the step")
                new_step(current_step + 1)
                new_step_at(None)

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

            if not current_text and is_older_than(updated_at, IDLE_DELAY):
                print("Have been idle for a while")
                draw_display(with_text("rina.bmp", text))
                freeze_display()
            else:
                new_step_at(FRAME_INTERVAL)
                animation = (current_step % step_count) + 1
                draw_display(with_text(f"cats/{animation}.bmp", text))
                if not current_text:
                    freeze_in = updated_at - seconds_ago(IDLE_DELAY)
                    if freeze_in >= timedelta(seconds=0):
                        print(f"Freeze in {freeze_in}")

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
    if line.startswith("Flush:"):
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

def plan_flush(value):
    new_text(value)
    new_clear_at(CLEAR_DELAY)

def plan_draw(value):
    new_text(value)
    new_clear_at(None)

def plan_clear():
    new_text(None)
    new_clear_at(None)

def plan_stat_update(what, value):
    if what == "IP":
        new_ip(value)
    elif what == "BT":
        new_bt(value)

def new_ip(value):
    global updated_at, current_ip
    current_ip = value
    updated_at = datetime.now()
    frame_event.set()

def new_bt(value):
    global updated_at, current_bt
    current_bt = value
    updated_at = datetime.now()
    frame_event.set()

def new_step(value):
    global current_step
    current_step = value
    frame_event.set()

def new_text(value):
    global updated_at, current_text
    updated_at = datetime.now()
    current_text = value
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
    epd.sleep()
    epd2in13_V4.epdconfig.module_exit(cleanup=True)

def with_text(asset_path, text):
    path = os.path.join(assets, asset_path)
    base = Image.new("1", (250, 122), 255)
    base.paste(Image.open(path), (0, 0))
    draw = ImageDraw.Draw(base)
    draw.text((0, 0), text, font=font, fill=0)
    return base

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
