import requests
import json
import os
from datetime import date

USERNAME = os.environ["RACING_API_USERNAME"]
PASSWORD = os.environ["RACING_API_PASSWORD"]

def fetch_hugo_palmer_runners():
    url = "https://api.theracingapi.com/v1/racecards/free"
    params = {"day": "today", "region_codes": "gb,ire"}
    
    response = requests.get(url, auth=(USERNAME, PASSWORD), params=params)
    response.raise_for_status()
    data = response.json()

    today = date.today().isoformat()
    hugo_runners = []

    for race in data.get("racecards", []):
        for runner in race.get("runners", []):
            if "palmer" in runner.get("trainer", "").lower():
                hugo_runners.append({
                    "date": today,
                    "course": race.get("course"),
                    "off_time": race.get("off_time"),
                    "race_name": race.get("race_name"),
                    "horse": runner.get("horse"),
                    "jockey": runner.get("jockey"),
                    "form": runner.get("form"),
                })

    output = {
        "date": today,
        "runners_found": len(hugo_runners),
        "runners": hugo_runners
    }

    os.makedirs("data", exist_ok=True)
    filename = f"data/hugo_palmer_{today}.json"
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Done! Found {len(hugo_runners)} Hugo Palmer runner(s) today.")
    if hugo_runners:
        for r in hugo_runners:
            print(f"  - {r['horse']} in the {r['off_time']} at {r['course']}")

if __name__ == "__main__":
    fetch_hugo_palmer_runners()
