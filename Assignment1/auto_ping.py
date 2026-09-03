import platform
import subprocess

def auto_ping(address_list:list):
    parameter = "-n" if platform.system.lower() == "windows" else "-c"
    packets = 10
    time_between_pings = 0.01
    for address in address_list:
        command = ["ping",parameter,packets, "-i", time_between_pings, address]
        result = subprocess.run(command, capture_output=True, text=True)
        print(result.stdout)
    return