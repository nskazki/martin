import os
import re
import sys
import socket
import select
import atexit
import threading
from glob import glob
from time import sleep
from PIL import Image,ImageDraw,ImageFont

libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
assets = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
sys.path.append(libdir)

from waveshare_epd import epd2in13_V4

epd = epd2in13_V4.EPD()

font = ImageFont.truetype(os.path.join(assets, "Sevillana.ttf"), 32)
base = Image.new("1", (250, 122), 255)
base.paste(Image.open(os.path.join(assets, "rina.bmp")), (0, 0))

ip = None
bt = None

idling = True
initialized = False

walk_step = 1
walk_limit = 8
chaos_event = threading.Event()

def spawn(target):
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    return thread

def do_chaos():
    global walk_step
    chaos_event.clear()

    if idling:
        image = Image.open(os.path.join(assets, "cat_walk", f"{walk_step}.bmp"))
        if walk_step == 1:
            epd.init()
            epd.displayPartBaseImage(epd.getbuffer(image))
        elif walk_step <= 8:
            epd.displayPartial(epd.getbuffer(image))

        walk_step += 1
        sleep(1)
        do_chaos()
    else:
        chaos_event.wait()
        do_chaos()

def listen_to_stdin():
    while True:
        try:
            input = sys.stdin.readline().strip()
            process_lines(input)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

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
    value = extract_text(line)
    if line.startswith("Show:"):
        show(value)
    elif line.startswith("Draw:"):
        draw(value)
    elif line.startswith("Stop!"):
        stop()
    elif line.startswith("Idle!"):
        idle()
    elif line.startswith("IP:"):
        save("ip", value)
    elif line.startswith("BT:"):
        save("bt", value)
    else:
        draw(line)

def extract_text(input):
    match = re.match(r"\w+:\s*(.*)", input)
    if match:
        return match.group(1)

def show(text):
    global idling
    idling = False
    draw_display(text)
    stop_display()

def draw(text):
    global idling
    idling = False
    draw_display(text)

def stop():
    stop_display()

def idle():
    global idling
    idling = True
    chaos_event.set()

def save(what, value):
    global ip, bt

    if what == "ip":
        ip = value
    elif what == "bt":
        bt = value

    chaos_event.set()

def draw_display(text):
    if initialized:
        epd.displayPartial(epd.getbuffer(with_text(text)))
    else:
        init_display(text)

def init_display(text):
    global initialized
    initialized = True
    epd.init()
    epd.displayPartBaseImage(epd.getbuffer(with_text(text)))

def stop_display():
    global initialized
    initialized = False
    epd.sleep()

def exit_display():
    print("Exiting the EPD module")
    epd2in13_V4.epdconfig.module_exit(cleanup=True)

def with_text(text):
    copy = base.copy()
    draw = ImageDraw.Draw(copy)
    draw.text((0, 0), text, font=font, fill=0)
    return copy

atexit.register(exit_display)

chaos_thread = spawn(do_chaos)
stdin_thread = spawn(listen_to_stdin)
socket_thread = spawn(listen_to_socket)

chaos_thread.join()
stdin_thread.join()
socket_thread.join()
