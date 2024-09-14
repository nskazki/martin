from datetime import datetime, timedelta

def seconds_ago(seconds):
    return datetime.now() - timedelta(seconds=seconds)

def seconds_from_now(seconds):
    return datetime.now() + timedelta(seconds=seconds)

def is_past(time):
    return time and time <= datetime.now()

def is_older_than(time, seconds):
    return time and time <= seconds_ago(seconds)
