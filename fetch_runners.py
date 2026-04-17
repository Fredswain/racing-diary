import requests
import json
import os
from datetime import date

USERNAME = os.environ["RACING_API_USERNAME"]
PASSWORD = os.environ["RACING_API_PASSWORD"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})

def fetch_hugo_palmer_runners():
    url = "https://api.theracingapi.com/v1/racecards/free"
    params = [
        ("day", "today"),
        ("region_codes", "gb"),
        ("region_codes", "ire"),
    ]
    
    response = requests.get(url, auth=(USERNAME, PASSWORD), params=params)
    response.raise_for_status()
    data = response.json()

    today = date.today().strftime("%d %b %Y")
    hugo_runners = []

    for race in data.get("racecards", []):
        for runner in race.get("runners", []):
            if "palmer" in runner.get("trainer", "").lower():
                hugo_runners.append({
                    "course": race.get("course"),
                    "off_time": race.get("off_time"),
                    "race_name": race.get("race_name"),
                    "horse": runner.get("horse"),
                    "jockey": runner.get("jockey"),
                    "form": runner.get("form"),
                })

    if hugo_runners:
        message = f"🏇 Hugo Palmer Runners - {today}\n"
        message += f"{len(hugo_runners)} runner(s) found:\n\n"
        for r in hugo_runners:
            message += f"🐴 {r['horse']}\n"
            message += f"📍 {r['course']} | {r['off_time']}\n"
            message += f"🏁 {r['race_name']}\n"
            message += f"👤 {r['jockey']}\n"
            message += f"📊 Form: {r['form']}\n\n"
    else:
        message = f"🏇 Hugo Palmer Runners - {today}\n\nNo runners found today."

    send_telegram(message)
    print(message)

    os.makedirs("data", exist_ok=True)
    filename = f"data/hugo_palmer_{date.today().isoformat()}.json"
    with open(filename, "w") as f:
        json.dump({"date": today, "runners_found": len(hugo_runners), "runners": hugo_runners}, f, indent=2)

if __name__ == "__main__":
    fetch_hugo_palmer_runners()
