# wait_for_mission.py
# Raspberry Pi: poll Flask server for the LATEST mission for this USER_ID.
# saves mission.json, then ACKs it (marks delivered) so it won't be re-downloaded.
#
# pip install requests

import time
import json
import requests
from pathlib import Path

BASE = "https://agrivision-website-v2.onrender.com" 
USER_ID = "7dd1806f-97d7-4228-95eb-c45e8b52b283"

POLL_SECONDS = 2
OUT_PATH = Path("mission.json")


def poll_latest_mission_for_user():
    while True:
        try:
            
            r = requests.get(
                f"{BASE}/device/missions/latest",
                params={"user_id": USER_ID},
                timeout=20,
            )

            if r.status_code != 200:
                print("GET LATEST:", r.status_code, r.text)
                time.sleep(POLL_SECONDS)
                continue

            data = r.json()
            print(data)
            
            requested_by = data.get("requested_by")
            requested_at = data.get("mission_id")

            if not data or data.get("mission_id") is None:
                print("No mission yet... waiting")
                time.sleep(POLL_SECONDS)
                continue

            # mission becomes the JSON file content that matches requested_at + requested_by
            dl = requests.get(
                f"{BASE}/device/missions/download",
                params={"requested_at": requested_at, "requested_by": requested_by},
                timeout=20,
                allow_redirects=True,
            )

            print(f"Mission received! id={requested_at}")

            if dl.status_code != 200:
                print("DOWNLOAD:", dl.status_code, dl.text[:200])
                time.sleep(POLL_SECONDS)
                continue

            # Now parse JSON from the final response body
            try:
                mission = dl.json()
            except Exception:
                print("DOWNLOAD returned non-JSON:", dl.headers.get("Content-Type"), dl.text[:200])
                time.sleep(POLL_SECONDS)
                continue

            OUT_PATH.write_text(json.dumps(mission, indent=2), encoding="utf-8")
            print(f"Saved to: {OUT_PATH.resolve()}")

            # 2) ACK it (so next poll doesn't return the same mission)
            if mission:
                ack = requests.post(
                    f"{BASE}/device/missions/ack",
                    json={"requested_at": requested_at, "user_id": USER_ID},
                    timeout=20,
                )
                print("ACK:", ack.status_code, ack.text)

            return mission

        except requests.RequestException as e:
            print("Network error:", e)
            time.sleep(POLL_SECONDS)
        except Exception as e:
            print("Unexpected error:", e)
            time.sleep(POLL_SECONDS)


def main():
    print("Waiting for latest mission uploads for user:", USER_ID)
    poll_latest_mission_for_user()


if __name__ == "__main__":
    main()
