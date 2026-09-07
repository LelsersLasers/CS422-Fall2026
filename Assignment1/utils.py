import json
import socket
from pathlib import Path


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


def read_targets(path: Path) -> list[str]:
    """Read the iperf3 server list JSON and return all IP/HOST values."""
    return [item["IP/HOST"] for item in json.loads(path.read_text())]
