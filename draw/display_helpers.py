import os
import sys
import math
from PIL import Image, ImageDraw, ImageFont

libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "lib")
assets = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
sys.path.append(libdir)

from waveshare_epd import epd2in13_V4

MAX_LINE_LENGTH = 20

epd = epd2in13_V4.EPD()
font_32 = ImageFont.truetype(os.path.join(assets, "Sevillana.ttf"), 32)
display_ready = False
display_halted = False

def draw_display(image):
    if display_halted:
        return

    if display_ready:
        epd.displayPartial(epd.getbuffer(image))
    else:
        init_display(image)

def init_display(image):
    global display_ready

    if display_halted:
        return

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
    global display_halted

    if display_halted:
        return

    display_halted = True
    print("Exiting the EPD module")
    if display_ready:
        epd.sleep()
    epd2in13_V4.epdconfig.module_exit(cleanup=True)

def is_long_text(text):
    return text and len(text) > MAX_LINE_LENGTH

def with_text(asset_path, text, half_screen):
    path = os.path.join(assets, asset_path)
    base = Image.new("1", (250, 122), 255)
    base.paste(Image.open(path), (0, 0))
    draw = ImageDraw.Draw(base)

    if is_long_text(text):
        first_line, second_line = devide_at_middle(text)
        if not half_screen:
            first_line += "..."
            second_line = ""

        draw.text((0, -4), first_line, font=font_32, fill=0)
        draw.text((0, 28), second_line, font=font_32, fill=0)
    else:
        draw.text((0, -4), text, font=font_32, fill=0)

    return base

def find_middle(text):
    middle = len(text) // 2
    spaces = [index for index, char in enumerate(text) if char == " "]

    if spaces:
        return min(spaces, key=lambda x: abs(x - middle))
    else:
        return middle - 1

def devide_at_middle(text):
    middle = find_middle(text)
    first_line = text[:middle]
    second_line = text[(middle + 1):]
    return [first_line, second_line]
