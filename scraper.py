import requests
from bs4 import BeautifulSoup
import csv
import json
import time
import re
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://www.transfermarkt.fr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

FLARESOLVERR_URL = os.environ.get("FLARESOLVERR_URL")

LIST_URL = (
    "https://www.transfermarkt.fr/spieler-statistik/wertvollstespieler/"
    "marktwertetop?page={page}"
)

session = requests.Session()
session.headers.update(HEADERS)


def _flare_get(url, timeout=60):
    if not FLARESOLVERR_URL:
        return None
    try:
        resp = requests.post(
            f"{FLARESOLVERR_URL}/v1",
            json={"cmd": "request.get", "url": url, "maxTimeout": timeout * 1000, "userAgent": HEADERS["User-Agent"]},
            timeout=timeout,
        )
        data = resp.json()
        sol = data.get("solution", {})
        code = sol.get("status", 0)
        html = sol.get("response", "")
        if code == 200 and len(html) > 100:
            return BeautifulSoup(html, "html.parser")
        print(f"  FlareSolverr returned status={code} len={len(html)}")
        return None
    except Exception as e:
        print(f"  FlareSolverr error: {e}")
        return None


def get_page(url, retries=3):
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=15, verify=False)
            if resp.status_code == 200 and len(resp.text) > 100:
                return BeautifulSoup(resp.text, "html.parser")
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  HTTP {resp.status_code} for {url}")
            if attempt == retries - 1:
                flare = _flare_get(url)
                if flare:
                    return flare
            return None
        except requests.RequestException as e:
            print(f"  Request error: {e}")
            time.sleep(5)
    return None


def parse_int(value):
    m = re.search(r"\d+", str(value))
    return int(m.group(0)) if m else None


def parse_market_value(text):
    if not text:
        return None
    m = re.search(r"([\d]+(?:\s*[,.]\s*[\d]+)?)\s*(Mrd\.?|mio\.?|K)", text, re.IGNORECASE)
    if not m:
        m2 = re.search(r"([\d]+(?:\s*[,.]\s*[\d]+)?)", text)
        if not m2:
            return None
        return float(m2.group(1).replace(",", "."))
    num = float(m.group(1).replace(",", "."))
    unit = m.group(2).lower()
    if unit.startswith("mrd"):
        num *= 1000.0
    elif unit.startswith("k"):
        num /= 1000.0
    return round(num, 2)


def enrich_player(p):
    p = dict(p)
    p["portrait_url"] = p.get("portrait_url", "").replace("/portrait/small/", "/portrait/big/")
    p["age_int"] = parse_int(p.get("age"))
    p["market_value_millions"] = parse_market_value(p.get("market_value"))
    return p


def scrape_list_page(page_num):
    url = LIST_URL.format(page=page_num)
    print(f"Fetching list page {page_num}...")
    soup = get_page(url)
    if not soup:
        return []

    rows = soup.select("table.items > tbody > tr")
    players = []

    for row in rows:
        try:
            # Rank
            rank_td = row.select_one("td.zentriert")
            rank = rank_td.get_text(strip=True) if rank_td else ""

            # Player name + profile link
            name_link = row.select_one("td.hauptlink a")
            if not name_link:
                continue
            name = name_link.get("title", name_link.get_text(strip=True))
            profile_path = name_link.get("href", "")
            player_id = ""
            m = re.search(r"/spieler/(\d+)", profile_path)
            if m:
                player_id = m.group(1)
            profile_url = BASE_URL + profile_path if profile_path else ""

            # Position
            inline_table = row.select_one("table.inline-table")
            position = ""
            if inline_table:
                cells = inline_table.select("td")
                if len(cells) >= 2:
                    position = cells[-1].get_text(strip=True)

            # Age
            zentriert_cells = row.select("td.zentriert")
            age = ""
            if len(zentriert_cells) >= 2:
                age = zentriert_cells[1].get_text(strip=True)

            # Nationality
            flags = row.select("img.flaggenrahmen")
            nationalities = [f.get("title", f.get("alt", "")) for f in flags]

            # Club
            club = ""
            club_url = ""
            club_imgs = row.select("td.zentriert a img")
            if club_imgs:
                club = club_imgs[0].get("title", club_imgs[0].get("alt", ""))
                parent_a = club_imgs[0].find_parent("a")
                if parent_a:
                    club_url = BASE_URL + parent_a.get("href", "")

            # Market value
            mv_cell = row.select_one("td.rechts.hauptlink a")
            market_value = mv_cell.get_text(strip=True) if mv_cell else ""

            # Portrait image
            portrait_img = row.select_one("img.bilderrahmen-fixed")
            portrait_url = portrait_img.get("src", "") if portrait_img else ""

            players.append({
                "rank": rank,
                "name": name,
                "player_id": player_id,
                "profile_url": profile_url,
                "position": position,
                "age": age,
                "nationalities": nationalities,
                "club": club,
                "club_url": club_url,
                "market_value": market_value,
                "portrait_url": portrait_url,
            })
        except Exception as e:
            print(f"  Error parsing row: {e}")
            continue

    return players


def get_total_pages(soup):
    last_link = soup.select_one("li.tm-pagination__list-item--icon-last-page a")
    if last_link:
        href = last_link.get("href", "")
        m = re.search(r"(?:/page/|\?page=)(\d+)", href)
        if m:
            return int(m.group(1))

    pagination_items = soup.select("li.tm-pagination__list-item a.tm-pagination__link")
    max_page = 1
    for item in pagination_items:
        text = item.get_text(strip=True)
        if text.isdigit():
            max_page = max(max_page, int(text))
    return max_page


def scrape_player_profile(profile_url):
    soup = get_page(profile_url)
    if not soup:
        return {}

    info = {}

    # Full name from header
    name_strong = soup.select_one("h1.data-header__headline-wrapper > strong")
    if name_strong:
        info["full_name"] = name_strong.get_text(strip=True)

    # Shirt number
    shirt = soup.select_one("span.data-header__shirt-number")
    if shirt:
        info["shirt_number"] = shirt.get_text(strip=True).lstrip("#")

    # Market value block from header
    mv_wrapper = soup.select_one("a.data-header__market-value-wrapper")
    if mv_wrapper:
        mv_link = mv_wrapper.get_text(" ", strip=True)
        info["market_value_header"] = mv_link
        last_update = mv_wrapper.select_one("p.data-header__last-update")
        if last_update:
            info["market_value_last_update"] = last_update.get_text(strip=True)

    # Header info boxes (birth date, place of birth, nationality, height, position, agent, intl caps)
    labels = soup.select("ul.data-header__items li.data-header__label")
    for li in labels:
        text = li.get_text(" ", strip=True)
        value_span = li.select_one("span.data-header__content")
        if not value_span:
            continue
        label_text = text.split(":")[0].strip() if ":" in text else text.strip()
        value = value_span.get_text(" ", strip=True).strip()
        if label_text and value:
            info[label_text] = value

    # Current club from header box --big
    club_span = soup.select_one("span.data-header__club a")
    if club_span:
        info["current_club"] = club_span.get("title", club_span.get_text(strip=True))

    league_span = soup.select_one("span.data-header__league-link")
    if league_span:
        info["current_league"] = league_span.get("title", league_span.get_text(strip=True))

    # Main info table "Informations et faits" (flat sibling label/value spans)
    info_table = soup.select_one("div.info-table")
    if info_table:
        cells = info_table.select("span.info-table__content")
        labels_txt = [c.get_text(strip=True).rstrip(":") for c in cells]
        seen = []
        for i, cell in enumerate(cells):
            if "info-table__content--regular" in cell.get("class", []):
                continue
            prev = cells[i - 1] if i > 0 else None
            if prev and "info-table__content--regular" in prev.get("class", []):
                label = prev.get_text(strip=True).rstrip(":")
                value = cell.get_text(" ", strip=True).strip()
                key = label if label else f"detail_{i}"
                if label not in seen:
                    info[key] = value
                    seen.append(label)

    # Detailed positions
    positions = soup.select("dd.detail-position__position")
    if positions:
        info["positions_detail"] = [p.get_text(strip=True) for p in positions]

    # Birth place image / place (untruncated via title)
    birth_place = soup.select_one('span.data-header__content[itemprop="birthPlace"] .cp')
    if birth_place:
        info["birth_place"] = birth_place.get("title", birth_place.get_text(strip=True))

    # Parsed height in cm and foot for the quiz
    taille = info.get("Taille")
    if taille:
        m = re.search(r"([\d]+(?:[,.]\s*[\d]+)?)", taille)
        if m:
            info["height_cm"] = int(round(float(m.group(1).replace(",", ".")) * 100))
    pied = info.get("Pied")
    if pied:
        info["foot"] = pied.lower()

    return info


def scrape_all(max_pages=None, scrape_profiles=False, output_dir="output", save_files=True):
    if save_files and output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Fetch first page to determine total pages
    print("Fetching page 1 to determine total pages...")
    first_soup = get_page(LIST_URL.format(page=1))
    if not first_soup:
        print("Failed to fetch first page. Exiting.")
        return

    total_pages = get_total_pages(first_soup)
    if max_pages:
        total_pages = min(total_pages, max_pages)
    print(f"Total pages to scrape: {total_pages}")

    all_players = []

    for page in range(1, total_pages + 1):
        if page == 1:
            soup = first_soup
            rows = soup.select("table.items > tbody > tr")
            # Parse page 1 players
            for row in rows:
                try:
                    rank_td = row.select_one("td.zentriert")
                    rank = rank_td.get_text(strip=True) if rank_td else ""
                    name_link = row.select_one("td.hauptlink a")
                    if not name_link:
                        continue
                    name = name_link.get("title", name_link.get_text(strip=True))
                    profile_path = name_link.get("href", "")
                    player_id = ""
                    m2 = re.search(r"/spieler/(\d+)", profile_path)
                    if m2:
                        player_id = m2.group(1)
                    profile_url = BASE_URL + profile_path if profile_path else ""
                    inline_table = row.select_one("table.inline-table")
                    position = ""
                    if inline_table:
                        cells = inline_table.select("td")
                        if len(cells) >= 2:
                            position = cells[-1].get_text(strip=True)
                    zentriert_cells = row.select("td.zentriert")
                    age = ""
                    if len(zentriert_cells) >= 2:
                        age = zentriert_cells[1].get_text(strip=True)
                    flags = row.select("img.flaggenrahmen")
                    nationalities = [f.get("title", f.get("alt", "")) for f in flags]
                    club = ""
                    club_url = ""
                    club_imgs = row.select("td.zentriert a img")
                    if club_imgs:
                        club = club_imgs[0].get("title", club_imgs[0].get("alt", ""))
                        parent_a = club_imgs[0].find_parent("a")
                        if parent_a:
                            club_url = BASE_URL + parent_a.get("href", "")
                    mv_cell = row.select_one("td.rechts.hauptlink a")
                    market_value = mv_cell.get_text(strip=True) if mv_cell else ""
                    portrait_img = row.select_one("img.bilderrahmen-fixed")
                    portrait_url = portrait_img.get("src", "") if portrait_img else ""
                    all_players.append({
                        "rank": rank, "name": name, "player_id": player_id,
                        "profile_url": profile_url, "position": position,
                        "age": age, "nationalities": nationalities, "club": club,
                        "club_url": club_url, "market_value": market_value,
                        "portrait_url": portrait_url,
                    })
                except Exception as e:
                    print(f"  Error parsing row: {e}")
                    continue
        else:
            players = scrape_list_page(page)
            all_players.extend(players)

        print(f"  Collected {len(all_players)} players so far.")
        if page < total_pages:
            time.sleep(2)

    print(f"\nTotal players collected: {len(all_players)}")

    # Enrich with parsed numeric fields + big portrait
    all_players = [enrich_player(p) for p in all_players]

    # Optionally scrape individual profile pages for extra info
    if scrape_profiles:
        print("\nScraping individual player profiles...")
        for i, player in enumerate(all_players):
            if player.get("profile_url"):
                print(f"  [{i+1}/{len(all_players)}] {player['name']}...")
                profile_data = scrape_player_profile(player["profile_url"])
                player.update(profile_data)
                time.sleep(2)

    if save_files:
        # Save to CSV
        csv_path = os.path.join(output_dir, "transfermarkt_players.csv")
        if all_players:
            csv_rows = []
            for p in all_players:
                row = dict(p)
                row["nationalities"] = " | ".join(row.get("nationalities", []))
                csv_rows.append(row)

            fieldnames = []
            for row in csv_rows:
                for key in row:
                    if key not in fieldnames:
                        fieldnames.append(key)

            with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(csv_rows)
            print(f"\nCSV saved to {csv_path}")

        # Save to JSON
        json_path = os.path.join(output_dir, "transfermarkt_players.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_players, f, ensure_ascii=False, indent=2)
        print(f"JSON saved to {json_path}")

    return all_players


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Transfermarkt market value scraper")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Max number of pages to scrape (default: all)")
    parser.add_argument("--profiles", action="store_true",
                        help="Also scrape each player's profile page for detailed info")
    parser.add_argument("--output", type=str, default="output",
                        help="Output directory (default: output)")
    args = parser.parse_args()

    scrape_all(
        max_pages=args.max_pages,
        scrape_profiles=args.profiles,
        output_dir=args.output,
    )
