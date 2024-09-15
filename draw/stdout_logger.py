import sys

class StdoutLogger:
    def __init__(self):
        self.logfile = sys.stdout

    def write(self, data):
        if isinstance(data, bytes):
            self.logfile.write(data.decode("utf-8"))
        else:
            self.logfile.write(data)

    def flush(self):
        self.logfile.flush()
