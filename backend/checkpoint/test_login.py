import json
from checkpoint_client import CheckPointClient


with open("config.json") as f:
    config = json.load(f)


client = CheckPointClient(
    config["checkpoint"]["url"],
    config["checkpoint"]["username"],
    config["checkpoint"]["password"]
)


sid = client.login()

print("======================")
print("SID generado:")
print(sid)
print("======================")


client.logout()
