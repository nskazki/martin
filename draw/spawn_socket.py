import os
import socket
import traceback
from spawn import spawn
from process_lines import process_lines

def create_socket(socket_path):
    if os.path.exists(socket_path):
        os.remove(socket_path)

    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(socket_path)
    server_sock.listen(1)
    return server_sock

def listen_to_connection(connection, process_line):
    while True:
        data = connection.recv(1024)
        if data:
            try:
                input = data.decode("utf-8")
                print(f"Processing {input}")
                process_lines(input, process_line)
            except Exception as e:
                print(f"An unexpected error occurred in the socket listener: {e}")
                traceback.print_exc()
        else:
            print(f"Closing the connection")
            connection.close()
            break

def listen_to_socket(process_line):
    socket_path = "/tmp/cat_socket"
    socket = create_socket(socket_path)
    while True:
        connection, _ = socket.accept()
        print(f"Handling a connection")
        spawn(listen_to_connection, connection, process_line)

def spawn_socket(process_line):
  return spawn(listen_to_socket, process_line)
