
import contextlib
import socket
import sys


@contextlib.contextmanager
def get_lock(process_name, *, log):
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        # The socket is created in abstract namespace. Linux only.
        lock_socket.bind('\0' + process_name)
        yield lock_socket
    except socket.error:
        log.error('lock exists')
        sys.exit()
