import os
import socket
import traceback
from spawn import spawn
from line_helpers import process_lines

def create_socket(socket_path):
    if os.path.exists(socket_path):
        os.remove(socket_path)

    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(socket_path)
    server_sock.listen(1)
    return server_sock

def listen_to_connection(connection, process_line, error_event):
    try:
        while True:
            data = connection.recv(1024)
            if data:
                input = data.decode("utf-8")
                process_lines(input, process_line)
            else:
                connection.close()
                break
    except Exception as e:
        print(f"An unexpected error occurred in the connection listener: {e}")
        traceback.print_exc()
        error_event.set()

def listen_to_socket(socket_path, process_line, error_event):
    try:
        socket = create_socket(socket_path)
        while True:
            connection, _ = socket.accept()
            spawn(listen_to_connection, connection, process_line, error_event)
    except Exception as e:
        print(f"An unexpected error occurred in the socket thread: {e}")
        traceback.print_exc()
        error_event.set()

def spawn_socket(socket_path, process_line, error_event):
    return spawn(listen_to_socket, socket_path, process_line, error_event)
