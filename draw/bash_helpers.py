import os
import subprocess
from time import sleep

PARENT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
BUILTIN_LED_ON = os.path.join(PARENT, "builtin_led_on.sh")
BUILTIN_LED_OFF = os.path.join(PARENT, "builtin_led_off.sh")

def run_script(script):
  result = subprocess.run([script], capture_output=True, text=True, shell=True)
  if result.stderr:
    raise Exception(result.stderr)

def bash_led_on():
  run_script(BUILTIN_LED_ON)

def bash_led_off():
  run_script(BUILTIN_LED_OFF)

def bash_halt(delay=0):
  sleep(delay)
  run_script("halt")
