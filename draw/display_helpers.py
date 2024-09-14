import os
import sys
from PIL import Image, ImageDraw, ImageFont

libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
assets = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
sys.path.append(libdir)

from waveshare_epd import epd2in13_V4

epd = epd2in13_V4.EPD()
font = ImageFont.truetype(os.path.join(assets, "Sevillana.ttf"), 32)
display_ready = False

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
