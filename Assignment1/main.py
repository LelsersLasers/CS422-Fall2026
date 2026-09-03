import json
from pathlib import Path
from auto_ping import auto_ping

REPO_ROOT = Path(__file__).parent.absolute()
DATA_PATH = REPO_ROOT / "data" / "listed_iperf3_servers.json"
with open(DATA_PATH,"r") as file:
    data = json.load(file)

address_list = []
for address in data:
    address_list.append(address["IP/HOST"])

auto_ping(address_list)