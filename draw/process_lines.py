def process_lines(lines, process_line):
    for line in lines.splitlines():
        process_line(line)
