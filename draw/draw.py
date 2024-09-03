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

epd = epd2in13_V4.EPD()
font = ImageFont.truetype(os.path.join(assets, "Sevillana.ttf"), 32)

ip = None
bt = None
idle_at = None
updated_at = datetime.now()
initialized = False
current_text = None

walk_step = 1
walk_limit = 8

timer_event = threading.Event()
display_event = threading.Event()

def spawn(target):
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    return thread

def manage_timer():
    global idle_at, updated_at, current_text
    timer_event.clear()
    if idle_at:
        if idle_at >= datetime.now():
            print("Idling by timer")
            idle_at = None
            updated_at = datetime.now()
            current_text = None
            display_event.set()
        else:
            sleep(10)
            manage_timer()
    else:
        timer_event.wait()
        manage_timer()

def manage_frame():
    global walk_step
    display_event.clear()

    text = current_text or bt or ip or "You are beautiful"
    if len(text) >= 20:
        text = text[:17] + "..."

    if updated_at <= seconds_ago(30) and not current_text:
        print("Have been idle for a while")
        draw_display(with_text(os.path.join(assets, "rina.bmp"), text))
        freeze_display()
        display_event.wait()
        manage_frame()
    else:
        print(f"Animating {walk_step}")
        draw_display(with_text(os.path.join(assets, "cat_walk", f"{walk_step}.bmp"), text))
        walk_step += 1
        if walk_step > walk_limit:
            walk_step = 1
        sleep(0.5)
        manage_frame()

def listen_to_stdin():
    while True:
        try:
            input = sys.stdin.readline().strip()
            process_lines(input)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
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
                    print(f"An unexpected error occurred: {e}")
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
    target, value = parse_line(line)
    if line.startswith("Flush:"):
        plan_flush(value)
    elif line.startswith("Draw:"):
        plan_draw(value)
    elif line.startswith("Idle!"):
        plan_idle()
    elif line.startswith("IP:"):
        plan_stat_update(target, value)
    elif line.startswith("BT:"):
        plan_stat_update(target, value)
    else:
        plan_draw(line)

def parse_line(input):
    match = re.match(r"(\w+):\s*(.*)", input)
    if match:
        return [match.group(1), match.group(2)]
    else:
        return []

def plan_flush(value):
    global idle_at, updated_at, current_text
    idle_at = seconds_from_now(30)
    updated_at = datetime.now()
    current_text = value
    set_events()

def plan_draw(value):
    global idle_at, updated_at, current_text
    idle_at = None
    updated_at = datetime.now()
    current_text = value
    set_events()

def plan_idle():
    global idle_at, updated_at, current_text
    idle_at = None
    updated_at = datetime.now()
    current_text = None
    set_events()

def plan_stat_update(what, value):
    global ip, bt, updated_at
    updated_at = datetime.now()

    if what == "IP":
        ip = value
    elif what == "BT":
        bt = value

    set_events()

def set_events():
    timer_event.set()
    display_event.set()

def seconds_ago(seconds):
    return datetime.now() - timedelta(seconds=seconds)

def seconds_from_now(seconds):
    return datetime.now() + timedelta(seconds=seconds)

def draw_display(image):
    if initialized:
        print("Drawing on display")
        epd.displayPartial(epd.getbuffer(image))
    else:
        init_display(image)

def init_display(image):
    global initialized
    print("Initalizing display")
    initialized = True
    epd.init()
    epd.displayPartBaseImage(epd.getbuffer(image))

def freeze_display():
    global initialized
    print("Freezing display")
    initialized = False
    epd.sleep()

def halt_display():
    print("Exiting the EPD module")
    epd2in13_V4.epdconfig.module_exit(cleanup=True)

def with_text(path, text):
    base = Image.new("1", (250, 122), 255)
    base.paste(Image.open(path), (0, 0))
    draw = ImageDraw.Draw(base)
    draw.text((0, 0), text, font=font, fill=0)
    return base

atexit.register(halt_display)

frame_thread = spawn(manage_frame)
timer_thread = spawn(manage_timer)
stdin_thread = spawn(listen_to_stdin)
socket_thread = spawn(listen_to_socket)

frame_thread.join()
timer_thread.join()
stdin_thread.join()
socket_thread.join()
