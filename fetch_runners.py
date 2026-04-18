# Racing diary - daily runner check
import requests
import json
import os
import re
from datetime import date

USERNAME = os.environ["RACING_API_USERNAME"]
PASSWORD = os.environ["RACING_API_PASSWORD"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# Hugo Palmer channel
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Breeze-up sale channels
CHANNEL_ALL_RUNNERS = os.environ["TELEGRAM_CHANNEL_ALL_RUNNERS"]
CHANNEL_PYTHIA_PURCHASES = os.environ["TELEGRAM_CHANNEL_PYTHIA_PURCHASES"]
CHANNEL_PYTHIA_TOP30 = os.environ["TELEGRAM_CHANNEL_PYTHIA_TOP30"]
CHANNEL_BLANDFORD = os.environ["TELEGRAM_CHANNEL_BLANDFORD"]

SALE_SIZE = 160  # Total lots in Craven 2026 sale


def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    })


def clean_name(name):
    """Strip country suffixes like (IRE), (GB) etc for matching"""
    return re.sub(r'\s*\([A-Z]+\)', '', str(name)).strip().lower()


def load_sales_data():
    """Load the sales data JSON from the repo"""
    with open("data/sales_data.json", "r") as f:
        data = json.load(f)
    # Build a lookup dict by cleaned dam name
    lookup = {}
    for lot in data["lots"]:
        key = clean_name(lot["dam"])
        lookup[key] = lot
    return lookup


def fetch_racecards():
    """Fetch today's GB & IRE racecards"""
    url = "https://api.theracingapi.com/v1/racecards/basic"
    params = [
        ("day", "today"),
        ("region_codes", "gb"),
        ("region_codes", "ire"),
    ]
    response = requests.get(url, auth=(USERNAME, PASSWORD), params=params)
    response.raise_for_status()
    return response.json()


def format_price(price_gns):
    if price_gns is None:
        return "Price unknown"
    return f"{price_gns:,} gns"


def format_runner_block(runner_info, race_info):
    """Format a single runner block for the message"""
    lot = runner_info["lot_data"]
    horse_name = runner_info["horse_name"].upper()
    
    bio = lot.get("biomechanics_rating")
    bio_rank = lot.get("biomechanics_rank") or "N/A"

    block = f"━━━━━━━━━━━━━━━━━━━━\n"
    block += f"🐴 {horse_name}\n"
    block += f"Sire: {lot['sire']} | Dam: {lot['dam']}\n"
    block += f"📍 {race_info['course']} | {race_info['off_time']} | {race_info.get('distance', 'N/A')} | {race_info.get('type', 'N/A')} | {race_info.get('class', 'N/A')}\n"
    block += f"👤 Jockey: {runner_info['jockey']}\n"
    block += f"🏠 {lot['sale_short']} | Lot {lot['lot']}\n"
    block += f"💰 {format_price(lot['price_gns'])} | {lot['purchaser']}\n"
    block += f"📊 Pythia Rankings (of {SALE_SIZE}):\n"
    block += f"  *Combined: #{lot['combined_rank']}* | Time: #{lot.get('time_rank', 'N/A')}\n"
    block += f"  Stride: #{lot.get('stride_rank', 'N/A')} | Biomechanics: #{bio_rank}\n"

    return block


def build_message(title, matched_runners, today_str):
    """Build a full grouped digest message"""
    count = len(matched_runners)
    msg = f"🏇 {title} - {today_str}\n"
    msg += f"{count} runner(s) found today:\n\n"

    # Sort by off time
    def time_sort_key(r):
        t = r["race_info"].get("off_time", "99:99")
        try:
            h, m = t.split(":")
            return int(h) * 60 + int(m)
        except:
            return 9999

    for r in sorted(matched_runners, key=time_sort_key):
        msg += format_runner_block(r, r["race_info"])

    msg += "━━━━━━━━━━━━━━━━━━━━"
    return msg


def fetch_hugo_palmer_runners(racecards):
    """Existing Hugo Palmer logic"""
    today = date.today().strftime("%d %b %Y")
    hugo_runners = []

    for race in racecards.get("racecards", []):
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
        for r in sorted(hugo_runners, key=lambda x: x.get("off_time", "99:99")):
            message += f"🐴 {r['horse']}\n"
            message += f"📍 {r['course']} | {r['off_time']}\n"
            message += f"🏁 {r['race_name']}\n"
            message += f"👤 {r['jockey']}\n"
            message += f"📊 Form: {r['form']}\n\n"
    else:
        message = f"🏇 Hugo Palmer Runners - {today}\n\nNo runners found today."

    send_telegram(TELEGRAM_CHAT_ID, message)
    print(message)
    return hugo_runners


def fetch_sale_runners(racecards, sales_lookup):
    """Match today's 2yo runners against sale data by dam name"""
    today = date.today().strftime("%d %b %Y")
    all_matched = []

    for race in racecards.get("racecards", []):
        race_info = {
            "course": race.get("course", "Unknown"),
            "off_time": race.get("off_time", ""),
            "distance": race.get("dist", race.get("distance", "N/A")),
            "type": race.get("type", "N/A"),
            "class": f"Class {race.get('class', 'N/A')}",
        }

        for runner in race.get("runners", []):
            age = str(runner.get("age", ""))
            if age != "2":
                continue

            dam_raw = runner.get("dam", "") or runner.get("dam_name", "") or ""
            dam_clean = clean_name(dam_raw)

            if dam_clean and dam_clean in sales_lookup:
                lot_data = sales_lookup[dam_clean]
                all_matched.append({
                    "horse_name": runner.get("horse", "Unknown"),
                    "jockey": runner.get("jockey", "Unknown"),
                    "dam_clean": dam_clean,
                    "lot_data": lot_data,
                    "race_info": race_info,
                })

    # Remove duplicates (same horse in same race)
    seen = set()
    unique_matched = []
    for r in all_matched:
        key = (r["horse_name"], r["race_info"]["off_time"], r["race_info"]["course"])
        if key not in seen:
            seen.add(key)
            unique_matched.append(r)

    # Filter into the 4 channel groups
    pythia_purchases = [r for r in unique_matched if r["lot_data"]["pythia_purchase"]]
    top30 = [r for r in unique_matched if r["lot_data"]["pythia_top30"]]
    blandford = [r for r in unique_matched if r["lot_data"]["blandford_purchase"]]

    # Send to all runners channel
    if unique_matched:
        msg = build_message("Craven Sale Runners", unique_matched, today)
        send_telegram(CHANNEL_ALL_RUNNERS, msg)
        print(f"All runners: {len(unique_matched)} sent")
    else:
        send_telegram(CHANNEL_ALL_RUNNERS, f"🏇 Craven Sale Runners - {today}\n\nNo runners found today.")
        print("All runners: none found")

    # Send to Pythia purchases channel
    if pythia_purchases:
        msg = build_message("Pythia Purchase Runners", pythia_purchases, today)
        send_telegram(CHANNEL_PYTHIA_PURCHASES, msg)
        print(f"Pythia purchases: {len(pythia_purchases)} sent")
    else:
        send_telegram(CHANNEL_PYTHIA_PURCHASES, f"🏇 Pythia Purchase Runners - {today}\n\nNo runners found today.")
        print("Pythia purchases: none found")

    # Send to Top 30 channel
    if top30:
        msg = build_message("Pythia Top 30 Runners", top30, today)
        send_telegram(CHANNEL_PYTHIA_TOP30, msg)
        print(f"Top 30: {len(top30)} sent")
    else:
        send_telegram(CHANNEL_PYTHIA_TOP30, f"🏇 Pythia Top 30 Runners - {today}\n\nNo runners found today.")
        print("Top 30: none found")

    # Send to Blandford channel
    if blandford:
        msg = build_message("Blandford Purchase Runners", blandford, today)
        send_telegram(CHANNEL_BLANDFORD, msg)
        print(f"Blandford: {len(blandford)} sent")
    else:
        send_telegram(CHANNEL_BLANDFORD, f"🏇 Blandford Purchase Runners - {today}\n\nNo runners found today.")
        print("Blandford: none found")

    return unique_matched


def main():
    print("Fetching racecards...")
    racecards = fetch_racecards()

    print("Running Hugo Palmer check...")
    fetch_hugo_palmer_runners(racecards)

    print("Loading sales data...")
    sales_lookup = load_sales_data()
    print(f"Loaded {len(sales_lookup)} lots from sale data")

    print("Running sale runners check...")
    fetch_sale_runners(racecards, sales_lookup)

    # Save daily log
    today = date.today().isoformat()
    os.makedirs("data", exist_ok=True)
    log = {"date": today, "status": "completed"}
    with open(f"data/log_{today}.json", "w") as f:
        json.dump(log, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    print("Fetching results for diagnostic...")
    url = "https://api.theracingapi.com/v1/results/today"
    params = [("region", "gb"), ("region", "ire")]
    response = requests.get(url, auth=(USERNAME, PASSWORD), params=params)
    data = response.json()
    for race in data.get("results", []):
        trainer_match = any("palmer" in r.get("trainer", "").lower() for r in race.get("runners", []))
        if trainer_match:
            print("=== RACE FIELDS ===")
            for k, v in race.items():
                if k != "runners":
                    print(f"  {k}: {v}")
            print("=== RUNNER FIELDS ===")
            for r in race.get("runners", []):
                if "palmer" in r.get("trainer", "").lower():
                    for k, v in r.items():
                        print(f"  {k}: {v}")
                    break
            break
