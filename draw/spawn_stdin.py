import sys
import traceback
from spawn import spawn
from process_lines import process_lines

def listen_to_stdin(process_line):
    while True:
        try:
            input = sys.stdin.readline().strip()
            process_lines(input, process_line)
        except Exception as e:
            print(f"An unexpected error occurred in the stdin listener: {e}")
            traceback.print_exc()

def spawn_stdin(process_line):
  return spawn(listen_to_stdin, process_line)
