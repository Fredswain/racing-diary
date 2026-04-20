# Racing diary - daily results check
import requests
import json
import os
import re
from datetime import date

USERNAME = os.environ["RACING_API_USERNAME"]
PASSWORD = os.environ["RACING_API_PASSWORD"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    })


def fetch_todays_results():
    """Fetch today's GB & IRE results"""
    url = "https://api.theracingapi.com/v1/results/today"
    params = [("region", "gb"), ("region", "ire")]
    response = requests.get(url, auth=(USERNAME, PASSWORD), params=params)
    response.raise_for_status()
    return response.json()


def load_todays_runners():
    """Load this morning's saved runner data including prize money available"""
    today = date.today().isoformat()
    filepath = f"data/runners_{today}.json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


def load_cumulative_stats():
    """Load cumulative Hugo Palmer stats"""
    filepath = "data/hugo_palmer_stats.json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {
        "total_runs": 0,
        "total_wins": 0,
        "total_prize_available": 0,
        "total_prize_won": 0,
        "runs": []
    }


def save_cumulative_stats(stats):
    """Save updated cumulative stats"""
    filepath = "data/hugo_palmer_stats.json"
    os.makedirs("data", exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(stats, f, indent=2)


def parse_prize(prize_str):
    """Parse prize money string to integer, e.g. '£3,240' -> 3240"""
    if not prize_str:
        return 0
    cleaned = re.sub(r'[£,\s]', '', str(prize_str))
    try:
        return int(float(cleaned))
    except:
        return 0


def check_hugo_palmer_results():
    today = date.today().isoformat()
    today_str = date.today().strftime("%d %b %Y")

    results_data = fetch_todays_results()
    todays_runners = load_todays_runners()
    stats = load_cumulative_stats()

    # Track which horses we've already recorded today to avoid duplicates
    already_recorded = {r["race_id"] for r in stats["runs"] if r["date"] == today}

    todays_results = []

    for race in results_data.get("results", []):
        race_id = race.get("race_id", "")

        # Skip if already recorded
        if race_id in already_recorded:
            continue

        for runner in race.get("runners", []):
            if "palmer" not in runner.get("trainer", "").lower():
                continue

            horse = runner.get("horse", "Unknown")
            position = runner.get("position", "")
            prize_won = parse_prize(runner.get("prize", ""))

            # Get prize available from morning's saved data
            prize_available = 0
            if race_id in todays_runners:
                prize_available = todays_runners[race_id].get("prize_available", 0)

            is_win = position == "1"

            run_record = {
                "date": today,
                "race_id": race_id,
                "horse": horse,
                "course": race.get("course", ""),
                "race_name": race.get("race_name", ""),
                "distance": race.get("dist_f", ""),
                "class": race.get("class", ""),
                "position": position,
                "prize_available": prize_available,
                "prize_won": prize_won,
            }

            # Update cumulative stats
            stats["total_runs"] += 1
            if is_win:
                stats["total_wins"] += 1
            stats["total_prize_available"] += prize_available
            stats["total_prize_won"] += prize_won
            stats["runs"].append(run_record)

            todays_results.append(run_record)

    # Build and send Telegram message
    if todays_results:
        msg = f"🏇 Hugo Palmer Results - {today_str}\n\n"

        for r in todays_results:
            pos = r["position"]
            pos_emoji = "🥇" if pos == "1" else "🥈" if pos == "2" else "🥉" if pos == "3" else f"#{pos}"
            msg += f"{pos_emoji} *{r['horse']}*\n"
            msg += f"📍 {r['course']} | {r['distance']} | {r['class']}\n"
            msg += f"🏁 {r['race_name']}\n"
            if r['prize_won']:
                msg += f"💰 Prize won: £{r['prize_won']:,}\n"
            msg += "\n"

        # Cumulative stats
        total = stats["total_runs"]
        wins = stats["total_wins"]
        win_pct = (wins / total * 100) if total > 0 else 0
        p_avail = stats["total_prize_available"]
        p_won = stats["total_prize_won"]
        pct_prize = (p_won / p_avail * 100) if p_avail > 0 else 0

        msg += f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"📊 *Hugo Palmer Cumulative Stats*\n"
        msg += f"Total Runs: {total}\n"
        msg += f"Total Wins: {wins} ({win_pct:.1f}%)\n"
        if p_avail > 0:
            msg += f"Prize Available: £{p_avail:,}\n"
            msg += f"Prize Won: £{p_won:,} ({pct_prize:.1f}%)\n"

        send_telegram(TELEGRAM_CHAT_ID, msg)
        print(msg)

        # Save updated stats
        save_cumulative_stats(stats)
    else:
        msg = f"🏇 Hugo Palmer Results - {today_str}\n\nNo results found today."
        send_telegram(TELEGRAM_CHAT_ID, msg)
        print(msg)


if __name__ == "__main__":
    print("Fetching Hugo Palmer results...")
    check_hugo_palmer_results()
    print("Done!")
