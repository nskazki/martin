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

partial_update_initialized = False

def spawn(target):
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    return thread

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
                    input = data.decode('utf-8')
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
    text = extract_text(line)
    if line.startswith("Show:"):
        show(text)
    elif line.startswith("Init:"):
        init(text)
    elif line.startswith("Step:"):
        step(text)
    elif line.startswith("Stop!"):
        stop()
    else:
        step(line)

def extract_text(input):
    match = re.match(r"\w+:\s*(.*)", input)
    if match:
        return match.group(1)

def show(text):
    init(text)
    stop()

def init(text):
    global partial_update_initialized
    partial_update_initialized = True
    epd.init()
    epd.displayPartBaseImage(epd.getbuffer(with_text(text)))

def step(text):
    if partial_update_initialized:
        epd.displayPartial(epd.getbuffer(with_text(text)))
    else:
        init(text)

def stop():
    global partial_update_initialized
    partial_update_initialized = False
    epd.sleep()

def kill():
    print("Exiting the EPD module")
    epd2in13_V4.epdconfig.module_exit(cleanup=True)

def with_text(text):
    copy = base.copy()
    draw = ImageDraw.Draw(copy)
    draw.text((0, 0), text, font=font, fill=0)
    return copy

atexit.register(kill)

stdin_thread = spawn(listen_to_stdin)
socket_thread = spawn(listen_to_socket)

stdin_thread.join()
socket_thread.join()
