import sys
import os
import re
import traceback
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

def iterate_input():
    while True:
        for line in input().splitlines():
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
    elif line.startswith("Kill!"):
        kill()
    else
        step(line)

def extract_text(input):
    match = re.match(r"\w+:\s*(.*)", input)
    if match:
        return match.group(1)

def show(text):
    init(text)
    stop()

def init(text):
    epd.init()
    epd.displayPartBaseImage(epd.getbuffer(with_text(text)))

def step(text):
    epd.displayPartial(epd.getbuffer(with_text(text)))

def stop():
    epd.sleep()

def kill():
    epd2in13_V4.epdconfig.module_exit(cleanup=True)

def with_text(text):
    copy = base.copy()
    draw = ImageDraw.Draw(copy)
    draw.text((0, 0), text, font=font, fill=0)
    return copy

iterate_input()
