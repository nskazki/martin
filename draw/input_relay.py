import json
import evdev
import pyudev
import traceback
import threading
from spawn import spawn
from select import select
from list_helpers import difference
from socket_helpers import send_to_socket, SOCKET_CAT, SOCKET_TRANSMITTER

TARGET_LENGTH = 6

KEYTABLE = {
    "KEY_RESERVED": 0,
    "KEY_ESC": 41,
    "KEY_1": 30,
    "KEY_2": 31,
    "KEY_3": 32,
    "KEY_4": 33,
    "KEY_5": 34,
    "KEY_6": 35,
    "KEY_7": 36,
    "KEY_8": 37,
    "KEY_9": 38,
    "KEY_0": 39,
    "KEY_MINUS": 45,
    "KEY_EQUAL": 46,
    "KEY_BACKSPACE": 42,
    "KEY_TAB": 43,
    "KEY_Q": 20,
    "KEY_W": 26,
    "KEY_E": 8,
    "KEY_R": 21,
    "KEY_T": 23,
    "KEY_Y": 28,
    "KEY_U": 24,
    "KEY_I": 12,
    "KEY_O": 18,
    "KEY_P": 19,
    "KEY_LEFTBRACE": 47,
    "KEY_RIGHTBRACE": 48,
    "KEY_ENTER": 40,
    "KEY_LEFTCTRL": 224,
    "KEY_A": 4,
    "KEY_S": 22,
    "KEY_D": 7,
    "KEY_F": 9,
    "KEY_G": 10,
    "KEY_H": 11,
    "KEY_J": 13,
    "KEY_K": 14,
    "KEY_L": 15,
    "KEY_SEMICOLON": 51,
    "KEY_APOSTROPHE": 52,
    "KEY_GRAVE": 53,
    "KEY_LEFTSHIFT": 225,
    "KEY_BACKSLASH": 50,
    "KEY_Z": 29,
    "KEY_X": 27,
    "KEY_C": 6,
    "KEY_V": 25,
    "KEY_B": 5,
    "KEY_N": 17,
    "KEY_M": 16,
    "KEY_COMMA": 54,
    "KEY_DOT": 55,
    "KEY_SLASH": 56,
    "KEY_RIGHTSHIFT": 229,
    "KEY_KPASTERISK": 85,
    "KEY_LEFTALT": 226,
    "KEY_SPACE": 44,
    "KEY_CAPSLOCK": 57,
    "KEY_F1": 58,
    "KEY_F2": 59,
    "KEY_F3": 60,
    "KEY_F4": 61,
    "KEY_F5": 62,
    "KEY_F6": 63,
    "KEY_F7": 64,
    "KEY_F8": 65,
    "KEY_F9": 66,
    "KEY_F10": 67,
    "KEY_NUMLOCK": 83,
    "KEY_SCROLLLOCK": 71,
    "KEY_KP7": 95,
    "KEY_KP8": 96,
    "KEY_KP9": 97,
    "KEY_KPMINUS": 86,
    "KEY_KP4": 92,
    "KEY_KP5": 93,
    "KEY_KP6": 94,
    "KEY_KPPLUS": 87,
    "KEY_KP1": 89,
    "KEY_KP2": 90,
    "KEY_KP3": 91,
    "KEY_KP0": 98,
    "KEY_KPDOT": 99,
    "KEY_ZENKAKUHANKAKU": 148,
    "KEY_102ND": 100,
    "KEY_F11": 68,
    "KEY_F12": 69,
    "KEY_RO": 135,
    "KEY_KATAKANA": 146,
    "KEY_HIRAGANA": 147,
    "KEY_HENKAN": 138,
    "KEY_KATAKANAHIRAGANA": 136,
    "KEY_MUHENKAN": 139,
    "KEY_KPJPCOMMA": 140,
    "KEY_KPENTER": 88,
    "KEY_RIGHTCTRL": 228,
    "KEY_KPSLASH": 84,
    "KEY_SYSRQ": 70,
    "KEY_RIGHTALT": 230,
    "KEY_HOME": 74,
    "KEY_UP": 82,
    "KEY_PAGEUP": 75,
    "KEY_LEFT": 80,
    "KEY_RIGHT": 79,
    "KEY_END": 77,
    "KEY_DOWN": 81,
    "KEY_PAGEDOWN": 78,
    "KEY_INSERT": 73,
    "KEY_DELETE": 76,
    "KEY_MUTE": 239,
    "KEY_VOLUMEDOWN": 238,
    "KEY_VOLUMEUP": 237,
    "KEY_POWER": 102,
    "KEY_KPEQUAL": 103,
    "KEY_PAUSE": 72,
    "KEY_KPCOMMA": 133,
    "KEY_HANGEUL": 144,
    "KEY_HANJA": 145,
    "KEY_YEN": 137,
    "KEY_LEFTMETA": 227,
    "KEY_RIGHTMETA": 231,
    "KEY_COMPOSE": 101,
    "KEY_STOP": 243,
    "KEY_AGAIN": 121,
    "KEY_PROPS": 118,
    "KEY_UNDO": 122,
    "KEY_FRONT": 119,
    "KEY_COPY": 124,
    "KEY_OPEN": 116,
    "KEY_PASTE": 125,
    "KEY_FIND": 244,
    "KEY_CUT": 123,
    "KEY_HELP": 117,
    "KEY_CALC": 251,
    "KEY_SLEEP": 248,
    "KEY_WWW": 240,
    "KEY_COFFEE": 249,
    "KEY_BACK": 241,
    "KEY_FORWARD": 242,
    "KEY_EJECTCD": 236,
    "KEY_NEXTSONG": 235,
    "KEY_PLAYPAUSE": 232,
    "KEY_PREVIOUSSONG": 234,
    "KEY_STOPCD": 233,
    "KEY_REFRESH": 250,
    "KEY_EDIT": 247,
    "KEY_SCROLLUP": 245,
    "KEY_SCROLLDOWN": 246,
    "KEY_F13": 104,
    "KEY_F14": 105,
    "KEY_F15": 106,
    "KEY_F16": 107,
    "KEY_F17": 108,
    "KEY_F18": 109,
    "KEY_F19": 110,
    "KEY_F20": 111,
    "KEY_F21": 112,
    "KEY_F22": 113,
    "KEY_F23": 114,
    "KEY_F24": 115
}

MODKEYS = {
    "KEY_RIGHTMETA": 0,
    "KEY_RIGHTALT": 1,
    "KEY_RIGHTSHIFT": 2,
    "KEY_RIGHTCTRL": 3,
    "KEY_LEFTMETA": 4,
    "KEY_LEFTALT": 5,
    "KEY_LEFTSHIFT": 6,
    "KEY_LEFTCTRL": 7
}

mod_keys = 0b00000000
pressed_keys = []

devices = []
error_event = threading.Event()
device_event = threading.Event()
device_observer = None

def manage_inputs():
    while True:
        try:
            iterate_inputs()
        except Exception as e:
            print(f"An unexpected error occurred in the inputs manager: {e}")
            traceback.print_exc()
            print("Carrying on")

def iterate_inputs():
    read_list, _, _ = select(devices, [], [], 0.01)
    for file_descriptor in read_list:
        for event in file_descriptor.read():
            if event.type == evdev.ecodes.EV_KEY and event.value <= 1:
                key_str = evdev.ecodes.KEY[event.code]
                mod_key = to_mod_key(key_str)
                ord_key = to_ord_key(key_str)

                if mod_key != -1:
                    update_mod_keys(mod_key, event.value)
                elif ord_key != -1:
                    update_ord_keys(ord_key, event.value)

                send_keys()

def to_mod_key(key_str):
    if key_str in MODKEYS:
        return MODKEYS[key_str]
    else:
        return -1

def to_ord_key(key_str):
    if key_str in KEYTABLE:
        return KEYTABLE[key_str]
    else:
        return -1

def update_mod_keys(mod_key, value):
    global mod_keys
    bit_mask = 1 << (7 - mod_key)
    if value:
        mod_keys |= bit_mask
    else:
        mod_keys &= ~bit_mask

def update_ord_keys(ord_key, value):
    global pressed_keys
    if value == 0:
        pressed_keys.remove(ord_key)
    elif ord_key not in pressed_keys:
        pressed_keys.insert(0, ord_key)

    len_delta = TARGET_LENGTH - len(pressed_keys)
    if len_delta < 0:
        pressed_keys = pressed_keys[:len_delta]
    elif len_delta > 0:
        pressed_keys.extend([0] * len_delta)

def send_keys():
    send_to_socket(SOCKET_TRANSMITTER, f"Send: {json.dumps(encode_keys())}")

def encode_keys():
    return [0xA1, 0x01, mod_keys, 0, *pressed_keys]

def manage_devices():
    try:
        while True:
            iterate_devices()
    except Exception as e:
        print(f"An unexpected error occurred in the devices manager: {e}")
        traceback.print_exc()
        error_event.set()

def iterate_devices():
    global devices
    device_event.clear()
    cur_devices = get_keyboard_devices()
    new_devices = difference(cur_devices, devices)
    del_devices = difference(devices, cur_devices)
    if new_devices or del_devices:
        for device in new_devices:
            device.grab()
            print(f"Grabbed keyboard {device.name} at path {device.path}")
        for device in del_devices:
            device.close()
            print(f"Lost keyboard {device.name} at path {device.path}")

        if not cur_devices:
            send_to_socket(SOCKET_CAT, "Lost all toys")
        elif len(cur_devices) > len(devices):
            send_to_socket(SOCKET_CAT, "Found a toy!")
        else:
            send_to_socket(SOCKET_CAT, "Lost a toy")

        devices = cur_devices
    device_event.wait()

def get_keyboard_devices():
    keyboards = []
    for device in get_input_devices():
        all_keys = device.capabilities().get(evdev.ecodes.EV_KEY, [])
        good_keys = evdev.ecodes.KEY_1 in all_keys
        if good_keys:
            keyboards.append(device)
    return keyboards

def get_input_devices():
    inputs = []
    for path in evdev.list_devices():
        try:
            inputs.append(evdev.InputDevice(path))
        except Exception as e:
            print(f"Ignoring {path} due to {e}")
    return inputs

def on_device_change(event, device):
    try:
        iterate_device_change(event, device)
    except Exception as e:
        print(f"An unexpected error occurred in the device change handler: {e}")
        traceback.print_exc()
        error_event.set()

def iterate_device_change(event, device):
    if event == "remove" or event == "add":
        print(f"{event} {device}")
        device_event.set()

def create_device_observer(callback):
    device_monitor = pyudev.Monitor.from_netlink(pyudev.Context())
    device_monitor.filter_by(subsystem="usb")
    return pyudev.MonitorObserver(device_monitor, callback)

input_thread = spawn(manage_inputs)
device_thread = spawn(manage_devices)
device_observer = create_device_observer(on_device_change)
device_observer.start()

error_event.wait()
print("An error occured. Exiting!")
