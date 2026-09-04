import socket

def get_local_ip() -> str:
    """
    Get the local IP address of the machine.
    Works by creating a UDP socket and connecting to a non-routable IP address
    and then retrieving the socket's own address.
    On failure, it defaults to '127.0.0.1'.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        print("Could not determine local IP address, defaulting to 127.0.0.1")
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip
