# Racing diary - daily results check
import requests
import json
import os
import re
from datetime import date, timedelta

USERNAME = os.environ["RACING_API_USERNAME"]
PASSWORD = os.environ["RACING_API_PASSWORD"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CHANNEL_ALL_RUNNERS = os.environ["TELEGRAM_CHANNEL_ALL_RUNNERS"]
CHANNEL_PYTHIA_TOP50 = os.environ["TELEGRAM_CHANNEL_PYTHIA_TOP50"]
CHANNEL_PYTHIA_PURCHASES = os.environ["TELEGRAM_CHANNEL_PYTHIA_PURCHASES"]
CHANNEL_BLANDFORD = os.environ["TELEGRAM_CHANNEL_BLANDFORD"]
CHANNEL_SUMMARY = os.environ["TELEGRAM_CHANNEL_SUMMARY"]


def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})


def clean_name(name):
    return re.sub(r'\s*\([A-Z]+\)', '', str(name)).strip().lower()


def parse_prize(prize_str):
    if not prize_str:
        return 0
    cleaned = re.sub(r'[£,\s]', '', str(prize_str))
    try:
        return int(float(cleaned))
    except:
        return 0


def position_emoji(pos):
    if pos == "1": return "🥇"
    if pos == "2": return "🥈"
    if pos == "3": return "🥉"
    if pos in ["PU", "F", "UR", "RO", "BD"]: return "❌"
    return f"#{pos}"


def load_sales_data():
    with open("data/sales_data.json", "r") as f:
        data = json.load(f)
    lookup = {}
    for lot in data["lots"]:
        key = clean_name(lot["dam"])
        lookup[key] = lot
    return lookup, data["lots"]


def load_stats():
    filepath = "data/breeze_up_stats.json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {"recorded_race_ids": [], "runs": []}


def save_stats(stats):
    os.makedirs("data", exist_ok=True)
    with open("data/breeze_up_stats.json", "w") as f:
        json.dump(stats, f, indent=2)


def load_hugo_stats():
    filepath = "data/hugo_palmer_stats.json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {"recorded_race_ids": [], "runs": [], "total_runs": 0, "total_wins": 0, "total_prize_won": 0}


def save_hugo_stats(stats):
    os.makedirs("data", exist_ok=True)
    with open("data/hugo_palmer_stats.json", "w") as f:
        json.dump(stats, f, indent=2)


def fetch_todays_results():
    url = "https://api.theracingapi.com/v1/results/today"
    params = [("region", "gb"), ("region", "ire")]

    response = requests.get(url, auth=(USERNAME, PASSWORD), params=params)
    response.raise_for_status()
    return response.json()


def format_horse_block(r):
    pos_str = position_emoji(r["position"])
    price_str = f"£{r['price_gns']:,}" if r["price_gns"] else "Unknown"
    prize_str = f"£{r['prize_won']:,}" if r["prize_won"] else "No prize"
    block = "━━━━━━━━━━━━━━━━━━━━\n"
    block += f"🐴 *{r['horse'].upper()}*\n"
    block += f"📍 {r['course']} | {r['off_time']} | {r['distance']} | {r['race_type']} | {r['race_class']}\n"
    block += f"{pos_str} Position: {r['position']}\n"
    block += f"👤 {r['jockey']}\n"
    block += f"💰 Prize: {prize_str}\n"
    block += f"🏠 {r['sale_short']} | Lot {r['lot']} | Pythia #{r['combined_rank']} | {price_str}\n"
    return block


def compute_group_stats(runs, filter_fn=None):
    if filter_fn:
        runs = [r for r in runs if filter_fn(r)]
    if not runs:
        return None
    horses = set(r["horse"] for r in runs)
    runners = len(horses)
    total_runs = len(runs)
    wins = sum(1 for r in runs if r["is_win"])
    winners = len(set(r["horse"] for r in runs if r["is_win"]))
    places = sum(1 for r in runs if r["is_place"])
    prize = sum(r["prize_won"] for r in runs)
    spent = sum(r["price_gns"] for r in runs if r["price_gns"])
    win_pct = (wins / total_runs * 100) if total_runs > 0 else 0
    prize_per_runner = (prize / runners) if runners > 0 else 0
    prize_pct_spend = (prize / spent * 100) if spent > 0 else 0
    return {
        "horses": len(horses), "runners": runners, "runs": total_runs,
        "winners": winners, "wins": wins, "win_pct": win_pct,
        "places": places, "prize": prize, "prize_per_runner": prize_per_runner,
        "spent": spent, "prize_pct_spend": prize_pct_spend,
    }


def format_group_block(label, s):
    if not s:
        return f"*{label}*\nNo runners yet\n\n"
    block = f"*{label}*\n"
    if s["spent"]:
        block += f"Spent: £{s['spent']:,}\n"
    block += f"Horses: {s['horses']} | Runners: {s['runners']} | Runs: {s['runs']}\n"
    block += f"Winners: {s['winners']} | Wins: {s['wins']} | Win%: {s['win_pct']:.1f}%\n"
    block += f"Prize: £{s['prize']:,} | £/runner: £{s['prize_per_runner']:,.0f}\n"
    if s["spent"]:
        block += f"Prize as % of spend: {s['prize_pct_spend']:.2f}%\n"
    block += "\n"
    return block


def get_market_top50(all_lots, sale=None):
    if sale:
        lots = [l for l in all_lots if l["sale"] == sale and l["price_gns"]]
    else:
        lots_by_sale = {}
        for l in all_lots:
            if l["price_gns"]:
                lots_by_sale.setdefault(l["sale"], []).append(l)
        top50_dams = set()
        for sale_lots in lots_by_sale.values():
            sale_lots.sort(key=lambda x: x["price_gns"], reverse=True)
            for lot in sale_lots[:50]:
                top50_dams.add(clean_name(lot["dam"]))
        return top50_dams
    lots.sort(key=lambda x: x["price_gns"], reverse=True)
    return set(clean_name(l["dam"]) for l in lots[:50])


def check_breeze_up_results(results_data, sales_lookup, all_lots, stats):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = yesterday
    today_str = (date.today() - timedelta(days=1)).strftime("%d %b %Y")
    already_recorded = set(stats.get("recorded_race_ids", []))
    all_matched = []

    for race in results_data.get("results", []):
        race_id = race.get("race_id", "")
        if race_id in already_recorded:
            continue
        for runner in race.get("runners", []):
            if str(runner.get("age", "")) != "2":
                continue
            dam_clean = clean_name(runner.get("dam", "") or "")
            if dam_clean and dam_clean in sales_lookup:
                lot = sales_lookup[dam_clean]
                prize_won = parse_prize(runner.get("prize", ""))
                position = str(runner.get("position", ""))
                run_record = {
                    "date": today,
                    "race_id": race_id,
                    "horse": runner.get("horse", "Unknown"),
                    "dam": lot["dam"],
                    "sale": lot["sale"],
                    "sale_short": lot["sale_short"],
                    "lot": lot["lot"],
                    "sire": lot["sire"],
                    "purchaser": lot["purchaser"],
                    "price_gns": lot["price_gns"],
                    "combined_rank": lot["combined_rank"],
                    "combined_rating": lot["combined_rating"],
                    "pythia_top50": lot["pythia_top50"],
                    "pythia_purchase": lot["pythia_purchase"],
                    "blandford_purchase": lot["blandford_purchase"],
                    "course": race.get("course", ""),
                    "off_time": race.get("off", ""),
                    "distance": race.get("dist_f", ""),
                    "race_class": race.get("class", ""),
                    "race_type": race.get("type", ""),
                    "race_name": race.get("race_name", ""),
                    "position": position,
                    "is_win": position == "1",
                    "is_place": position in ["1", "2", "3"],
                    "prize_won": prize_won,
                    "jockey": runner.get("jockey", "Unknown"),
                    "or_rating": runner.get("or", ""),
                }
                all_matched.append(run_record)
                already_recorded.add(race_id)

    def time_key(r):
        t = r.get("off_time", "99:99")
        try:
            h, m = t.split(":")
            return int(h) * 60 + int(m)
        except:
            return 9999

    all_matched.sort(key=time_key)

    if not all_matched:
        for ch in [CHANNEL_ALL_RUNNERS, CHANNEL_PYTHIA_TOP50, CHANNEL_PYTHIA_PURCHASES, CHANNEL_BLANDFORD]:
            send_telegram(ch, f"🏁 No breeze-up runners today - {today_str}")
        print("No breeze-up results found today")
        return stats

    stats["runs"].extend(all_matched)
    stats["recorded_race_ids"] = list(already_recorded)

    channel_filters = {
        CHANNEL_ALL_RUNNERS: ("All Runners", lambda r: True),
        CHANNEL_PYTHIA_TOP50: ("Pythia Top 50", lambda r: r["pythia_top50"]),
        CHANNEL_PYTHIA_PURCHASES: ("Pythia Purchases", lambda r: r["pythia_purchase"]),
        CHANNEL_BLANDFORD: ("Blandford", lambda r: r["blandford_purchase"]),
    }

    for channel, (label, filter_fn) in channel_filters.items():
        filtered = [r for r in all_matched if filter_fn(r)]
        if filtered:
            msg = f"🏁 *{label} Results - {today_str}*\n{len(filtered)} runner(s) today\n\n"
            for r in filtered:
                msg += format_horse_block(r)
            msg += "━━━━━━━━━━━━━━━━━━━━"
            send_telegram(channel, msg)
            print(f"{label}: {len(filtered)} results sent")
        else:
            send_telegram(channel, f"🏁 {label} Results - {today_str}\n\nNo runners today.")
            print(f"{label}: no results")

    return stats


def send_summary_messages(stats, all_lots):
    today_str = (date.today() - timedelta(days=1)).strftime("%d %b %Y")
    all_runs = stats.get("runs", [])
    market_top50 = get_market_top50(all_lots)

    if not all_runs:
        send_telegram(CHANNEL_SUMMARY, f"🏇 Breeze Up Tracker - {today_str}\n\nNo runners recorded yet.")
        return

    sales = sorted(set(r["sale"] for r in all_runs))

    # Message 1 - Combined
    msg1 = f"🏇 *BREEZE UP TRACKER - {today_str}*\n\n"
    msg1 += "━━━━━━━━━━━━━━━━━━━━\n*ALL SALES COMBINED*\n━━━━━━━━━━━━━━━━━━━━\n"
    s = compute_group_stats(all_runs)
    if s:
        msg1 += f"Horses: {s['horses']} | Runners: {s['runners']} | Runs: {s['runs']}\n"
        msg1 += f"Winners: {s['winners']} | Wins: {s['wins']} | Win%: {s['win_pct']:.1f}%\n"
        msg1 += f"Prize: £{s['prize']:,} | £/runner: £{s['prize_per_runner']:,.0f}\n\n"

    msg1 += "━━━━━━━━━━━━━━━━━━━━\n*BUYER COMPARISON*\n━━━━━━━━━━━━━━━━━━━━\n"
    msg1 += format_group_block("Pythia Purchases", compute_group_stats(all_runs, lambda r: r["pythia_purchase"]))
    msg1 += format_group_block("Blandford Purchases", compute_group_stats(all_runs, lambda r: r["blandford_purchase"]))

    msg1 += "━━━━━━━━━━━━━━━━━━━━\n*SELECTION COMPARISON*\n━━━━━━━━━━━━━━━━━━━━\n"
    msg1 += format_group_block("Pythia Top 50", compute_group_stats(all_runs, lambda r: r["pythia_top50"]))
    msg1 += format_group_block("Market Top 50", compute_group_stats(all_runs, lambda r: clean_name(r.get("dam", "")) in market_top50))
    msg1 += format_group_block("Rest of Field", compute_group_stats(all_runs, lambda r: not r["pythia_top50"] and clean_name(r.get("dam", "")) not in market_top50))

    send_telegram(CHANNEL_SUMMARY, msg1)
    print("Summary message 1 sent")

    # Message 2 - Per sale
    msg2 = f"🏇 *BREEZE UP BY SALE - {today_str}*\n\n"
    for sale in sales:
        sale_runs = [r for r in all_runs if r["sale"] == sale]
        if not sale_runs:
            continue
        sale_market_top50 = get_market_top50(all_lots, sale)
        sale_short = sale_runs[0]["sale_short"]
        msg2 += f"━━━━━━━━━━━━━━━━━━━━\n*{sale_short.upper()}*\n━━━━━━━━━━━━━━━━━━━━\n"
        s = compute_group_stats(sale_runs)
        if s:
            msg2 += f"Horses: {s['horses']} | Runners: {s['runners']} | Runs: {s['runs']}\n"
            msg2 += f"Winners: {s['winners']} | Wins: {s['wins']} | Win%: {s['win_pct']:.1f}%\n"
            msg2 += f"Prize: £{s['prize']:,} | £/runner: £{s['prize_per_runner']:,.0f}\n\n"
        msg2 += format_group_block("Pythia Purchases", compute_group_stats(sale_runs, lambda r: r["pythia_purchase"]))
        msg2 += format_group_block("Blandford", compute_group_stats(sale_runs, lambda r: r["blandford_purchase"]))
        msg2 += format_group_block("Pythia Top 50", compute_group_stats(sale_runs, lambda r: r["pythia_top50"]))
        msg2 += format_group_block("Market Top 50", compute_group_stats(sale_runs, lambda r: clean_name(r.get("dam", "")) in sale_market_top50))
        msg2 += format_group_block("Rest of Field", compute_group_stats(sale_runs, lambda r: not r["pythia_top50"] and clean_name(r.get("dam", "")) not in sale_market_top50))

    send_telegram(CHANNEL_SUMMARY, msg2)
    print("Summary message 2 sent")


def check_hugo_palmer_results(results_data):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = yesterday
    today_str = (date.today() - timedelta(days=1)).strftime("%d %b %Y")
    stats = load_hugo_stats()
    already_recorded = set(stats.get("recorded_race_ids", []))
    todays_results = []

    for race in results_data.get("results", []):
        race_id = race.get("race_id", "")
        if race_id in already_recorded:
            continue
        for runner in race.get("runners", []):
            if "palmer" not in runner.get("trainer", "").lower():
                continue
            position = str(runner.get("position", ""))
            prize_won = parse_prize(runner.get("prize", ""))
            run_record = {
                "date": today,
                "race_id": race_id,
                "horse": runner.get("horse", "Unknown"),
                "course": race.get("course", ""),
                "race_name": race.get("race_name", ""),
                "distance": race.get("dist_f", ""),
                "race_class": race.get("class", ""),
                "off_time": race.get("off", ""),
                "position": position,
                "prize_won": prize_won,
                "jockey": runner.get("jockey", "Unknown"),
            }
            stats["total_runs"] = stats.get("total_runs", 0) + 1
            if position == "1":
                stats["total_wins"] = stats.get("total_wins", 0) + 1
            stats["total_prize_won"] = stats.get("total_prize_won", 0) + prize_won
            stats["runs"].append(run_record)
            already_recorded.add(race_id)
            todays_results.append(run_record)

    stats["recorded_race_ids"] = list(already_recorded)

    if todays_results:
        msg = f"🏁 *Hugo Palmer Results - {today_str}*\n\n"
        for r in sorted(todays_results, key=lambda x: x.get("off_time", "99:99")):
            pos_str = position_emoji(r["position"])
            msg += f"{pos_str} *{r['horse']}*\n"
            msg += f"📍 {r['course']} | {r['distance']} | {r['race_class']}\n"
            msg += f"🏁 {r['race_name']}\n"
            msg += f"👤 {r['jockey']}\n"
            if r["prize_won"]:
                msg += f"💰 Prize: £{r['prize_won']:,}\n"
            msg += "\n"
        total = stats["total_runs"]
        wins = stats["total_wins"]
        win_pct = (wins / total * 100) if total > 0 else 0
        msg += f"━━━━━━━━━━━━━━━━━━━━\n📊 *Cumulative Stats*\n"
        msg += f"Runs: {total} | Wins: {wins} | Win%: {win_pct:.1f}%\n"
        if stats["total_prize_won"]:
            msg += f"Prize won: £{stats['total_prize_won']:,}\n"
        send_telegram(TELEGRAM_CHAT_ID, msg)
        print(msg)
    else:
        send_telegram(TELEGRAM_CHAT_ID, f"🏁 Hugo Palmer Results - {today_str}\n\nNo results found today.")
        print("No Hugo Palmer results today")

    save_hugo_stats(stats)


def main():
    print("Fetching today's results...")
    results_data = fetch_todays_results()

    print("Checking Hugo Palmer results...")
    check_hugo_palmer_results(results_data)

    print("Loading sales data...")
    sales_lookup, all_lots = load_sales_data()
    print(f"Loaded {len(sales_lookup)} lots")

    print("Checking breeze-up results...")
    stats = load_stats()
    stats = check_breeze_up_results(results_data, sales_lookup, all_lots, stats)
    save_stats(stats)

    print("Sending summary messages...")
    send_summary_messages(stats, all_lots)

    print("Done!")


if __name__ == "__main__":
    main()
