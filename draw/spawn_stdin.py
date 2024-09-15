import sys
import traceback
from spawn import spawn
from line_helpers import process_lines

def listen_to_stdin(process_line, error_event):
    try:
        while True:
            lines = sys.stdin.readline().strip()
            process_lines(lines, process_line)
    except Exception as e:
        print(f"An unexpected error occurred in the stdin listener: {e}")
        traceback.print_exc()
        error_event.set()

def spawn_stdin(process_line, error_event):
    return spawn(listen_to_stdin, process_line, error_event)
