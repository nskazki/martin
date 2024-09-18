import os

ROOT_PATH = os.path.dirname(os.path.realpath(__file__))
PREV_ADDRESS_PATH = os.path.join(ROOT_PATH, "../.prev_address")
LAST_ADDRESS_PATH = os.path.join(ROOT_PATH, "../.last_address")

def read_last_address():
    return read_address(LAST_ADDRESS_PATH)

def write_last_address(address):
    write_address(LAST_ADDRESS_PATH, address)

def read_address(path):
    try:
        with open(path, "r") as file:
            content = file.read().strip()
        return content
    except FileNotFoundError:
        pass

def write_address(path, address):
    if address:
        with open(path, "w") as file:
            file.write(address)
    else:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
