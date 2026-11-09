import json
import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE = "https://setam.net.ua"
FIRST_PAGE = BASE + "/auctions/filters/region=15"
NEXT_PAGE = BASE + "/auctions/page/{page}/filters/region=15"
MAX_PAGES = 10
HEADERS = {"User-Agent": "Mozilla/5.0"}
SEEN_FILE = "seen.json"
LINK_RE = re.compile(r"/auction/(\d+)")


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text},
        timeout=30,
    )
    r.raise_for_status()


def find(pattern, text):
    m = re.search(pattern, text)
    return m.group(1).strip() if m else "-"


def parse_lots(html):
    soup = BeautifulSoup(html, "html.parser")
    lots = {}
    for a in soup.find_all("a", href=LINK_RE):
        lot_id = LINK_RE.search(a["href"]).group(1)
        if lot_id in lots:
            continue
        card = a
        while card.parent is not None:
            ids = {
                LINK_RE.search(x["href"]).group(1)
                for x in card.parent.find_all("a", href=LINK_RE)
            }
            if len(ids) > 1:
                break
            card = card.parent
        text = card.get_text(" ", strip=True)
        h3 = card.find("h3")
        title = h3.get_text(" ", strip=True) if h3 else a.get_text(" ", strip=True)
        lots[lot_id] = {
            "title": title[:400],
            "price": find(r"Початкова ціна:\s*([\d\s.,]+?)\s*грн", text),
            "date": find(r"Дата початку:\s*(\d+\s+\S+\s+\d{4})", text),
            "link": f"{BASE}/auction/{lot_id}",
        }
    return lots


def fetch_all():
    all_lots = {}
    for page in range(1, MAX_PAGES + 1):
        url = FIRST_PAGE if page == 1 else NEXT_PAGE.format(page=page)
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        lots = parse_lots(r.text)
        fresh = {k: v for k, v in lots.items() if k not in all_lots}
        if not fresh:
            break
        all_lots.update(fresh)
        time.sleep(2)
    return all_lots


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return None


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f)


def main():
    seen = load_seen()
    lots = fetch_all()
    print(f"Знайдено лотів на сайті: {len(lots)}")
    if not lots:
        print("Нічого не знайдено - можливо, змінилась верстка або сайт не відповідає.")
        sys.exit(1)

    if seen is None:
        save_seen(set(lots))
        send(
            f"✅ Бот працює. Зараз на СЕТАМ по Одеській області {len(lots)} лотів. "
            "Надалі писатиму лише про нові."
        )
        print("Перший запуск: лоти збережено.")
        return

    new_count = 0
    try:
        for lot_id, lot in lots.items():
            if lot_id in seen:
                continue
            send(
                "🆕 Новий лот СЕТАМ (Одеська обл.)\n"
                f"{lot['title']}\n"
                f"Початкова ціна: {lot['price']} грн\n"
                f"Початок торгів: {lot['date']}\n"
                f"{lot['link']}"
            )
            seen.add(lot_id)
            new_count += 1
            time.sleep(1)
    finally:
        save_seen(seen)
    print(f"Нових лотів: {new_count}")


main()
