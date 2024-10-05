import socket

SOCKET_CAT = "/tmp/cat_socket"
SOCKET_BCTL = "/tmp/bctl_socket"
SOCKET_BUTTONS = "/tmp/buttons_socket"
SOCKET_TRANSMITTER = "/tmp/transmitter_socket"

def send_to_socket(socket_path, message):
    try:
        client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_socket.connect(socket_path)
        client_socket.sendall(message.encode('utf-8'))
        client_socket.close()
    except Exception as e:
        print(f"Couldn't send {message} to {socket_path} due to {e}")
