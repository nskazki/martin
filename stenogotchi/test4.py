import evdev
import select

def monitor_keyboard(device_path):
    device = evdev.InputDevice(device_path)
    print(f"Monitoring keyboard: {device.name} at {device_path}")
    print("Press 'Esc' to exit.")

    while True:
        r, w, x = select.select([device.fd], [], [])
        for event in device.read():
            if event.type == evdev.ecodes.EV_KEY:
                key_event = evdev.categorize(event)
                print(f"Key event: {key_event.keycode} ({key_event.keystate})")
                if key_event.keycode == 'KEY_ESC' and key_event.keystate == evdev.KeyEvent.key_down:
                    print("Exiting...")
                    return

if __name__ == "__main__":
    try:
        # Directly use /dev/input/event0 for monitoring
        monitor_keyboard('/dev/input/event0')
    except Exception as e:
        print(f"Error: {e}")
