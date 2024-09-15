import re

def process_lines(lines, process_line):
    for line in lines.splitlines():
        process_line(line)

def parse_line(line):
    match = re.match(r"([\w\s]+)[:!]\s*(.*)", line)
    if match:
        return [match.group(1), match.group(2)]
    else:
        return [None, None]
