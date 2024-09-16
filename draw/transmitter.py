import threading
import traceback
from time import sleep
from spawn import spawn
from watch_bt import watch_bt
from btkbdevice import BTKbDevice

trying = None
locked = None
device = BTKbDevice()
error_event = threading.Event()

def manage_error(watch_loop, error_event):
    error_event.wait()
    print("An error occured. Exiting!")
    watch_loop.quit()

def manage_timer(error_event):
    try:
      while True:
          iterate_timer()
    except Exception as e:
        print(f"An unexpected error occurred in the timer manager: {e}")
        traceback.print_exc()
        error_event.set()

def iterate_timer():
    sleep(2)
    raise Exception("kek")

def on_bt_change(connected, address):
    print(connected, address)

watch_loop = watch_bt(on_bt_change)
error_thread = spawn(manage_error, watch_loop, error_event)
timer_thread = spawn(manage_timer, error_event)

watch_loop.run()
