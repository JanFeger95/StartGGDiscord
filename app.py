import os
import datetime
import time
import pytz
import requests
import pysmashgg
from pysmashgg.api import run_query

# Configuration
TIMEZONE = os.environ["TIMEZONE"]
GAME_ID = os.environ["GAME_ID"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
STARTGG_TOKEN = os.environ["STARTGG_TOKEN"]

CUSTOM_QUERY = """query TournamentsByGame($page: Int!, $videogameId: ID!) {
    tournaments(query: {
        perPage: 32
        page: $page
        filter: { past: false, videogameIds: [$videogameId] }
    }) {
        nodes {
            id
            name
            slug
            startAt
            images { type url }
            venueAddress
            primaryContact
        }
    }
}"""

import os
import datetime
import time
import pytz
import requests
import json
from playwright.sync_api import sync_playwright

# 1. SETUP & CONFIGURATION
TIMEZONE = os.environ.get("TIMEZONE", "Europe/Berlin")
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
CACHE_FILE = "posted_ids.txt"

def get_posted_ids():
    if not os.path.exists(CACHE_FILE):
        return []
    with open(CACHE_FILE, "r") as f:
        return f.read().splitlines()

def save_posted_id(t_id):
    with open(CACHE_FILE, "a") as f:
        f.write(f"{t_id}\n")

def scout_battlefy():
    print("--- Battlefy Strategic Scout Starting ---")
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()

        # FIXED: Corrected .status syntax
        def on_response(response):
            if "search.battlefy.com" in response.url and response.status == 200:
                try:
                    data = response.json()
                    tourneys = data if isinstance(data, list) else data.get('tournaments', [])
                    if tourneys:
                        results.extend(tourneys)
                        print(f"✅ Intercepted {len(tourneys)} tournaments from API.")
                except: pass

        page.on("response", on_response)

        try:
            print("Navigating to Battlefy...")
            # wait_until="networkidle" ensures we wait for all API calls to finish
            page.goto("https://battlefy.com/browse/rematch", wait_until="networkidle", timeout=60000)
            
            # FALLBACK: Screen Reading (Updated selectors)
            if not results:
                print("⚠️ API Interception yielded no data. Attempting Screen Reading...")
                # We wait for any div that looks like a tournament card
                page.wait_for_selector("div[class*='TournamentCard']", timeout=15000)
                cards = page.query_selector_all("div[class*='TournamentCard']")
                
                for card in cards:
                    # Look for names in h4 or specific spans
                    name_el = card.query_selector("h4") or card.query_selector("span[class*='name']")
                    if name_el:
                        results.append({
                            "_id": name_el.inner_text()[:20], # Fallback ID using name
                            "name": name_el.inner_text(),
                            "slug": "browse/rematch" 
                        })
                print(f"✅ Screen Reading found {len(results)} items.")

        except Exception as e:
            print(f"❌ Scraper Failure: {e}")
        finally:
            browser.close()
            
    return results

def main():
    posted_ids = get_posted_ids()
    tourneys = scout_battlefy()
    
    for t in tourneys:
        t_id = str(t.get('_id', t.get('name')))
        if t_id not in posted_ids:
            # 2. DISCORD POSTING LOGIC
            url = f"https://battlefy.com/tournaments/{t.get('slug')}/{t.get('_id')}/info" if t.get('_id') else "https://battlefy.com/browse/rematch"
            
            payload = {
                "username": "Rematch Scout",
                "embeds": [{
                    "title": t.get('name'),
                    "url": url,
                    "color": 102204,
                    "footer": {"text": "Battlefy Direct Scrape"}
                }]
            }
            
            res = requests.post(WEBHOOK_URL, json=payload)
            if res.status_code == 204:
                save_posted_id(t_id)
                print(f"🚀 Posted to Discord: {t.get('name')}")
            else:
                print(f"❌ Discord Error: {res.status_code}")

if __name__ == "__main__":
    main()

def make_embeds(name, url, start_ts, location, contact, images):
    profile = next((img["url"] for img in images if img["type"] == 'profile'), None)
    banner = next((img["url"] for img in images if img["type"] == 'banner'), None)
    
    date_obj = datetime.datetime.fromtimestamp(start_ts, tz=pytz.timezone(TIMEZONE))
    date_str = date_obj.strftime('%A, %B %d at %H:%M')
    
    return [{
        "title": name,
        "url": url,
        "color": 102204,
        "description": f'📅 **Date:** {date_str}\n📍 **Loc:** {location or "Online"}\n👤 **Org:** {contact or "N/A"}',
        "thumbnail": {"url": profile} if profile else None,
        "image": {"url": banner} if banner else None,
        "footer": {"text": "Dual-Source Scout (start.gg + Battlefy)"},
    }]

def main():
    print("--- Starting Scout Session ---")
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    window = now + datetime.timedelta(days=7)

    cache_file = "posted_ids.txt"
    if not os.path.exists(cache_file): open(cache_file, 'w').close()
    with open(cache_file, "r") as f: posted_ids = f.read().splitlines()

    # --- 1. START.GG SCOUT ---
    try:
        smash = pysmashgg.SmashGG(STARTGG_TOKEN, True)
        response = run_query(CUSTOM_QUERY, {"page": 1, "videogameId": GAME_ID}, smash.header, smash.auto_retry)
        nodes = response.get('data', {}).get('tournaments', {}).get('nodes', [])
        
        with open(cache_file, "a") as f:
            for t in nodes:
                t_id = str(t['id'])
                if t_id not in posted_ids and now.timestamp() <= t['startAt'] <= window.timestamp():
                    payload = {"username": "start.gg Scout", "embeds": make_embeds(t['name'], f'https://start.gg/{t["slug"]}', t['startAt'], t['venueAddress'], t['primaryContact'], t['images'])}
                    requests.post(WEBHOOK_URL, json=payload)
                    f.write(t_id + "\n")
                    posted_ids.append(t_id) # Avoid dupe if same ID in same run
                    print(f"Posted start.gg: {t['name']}")
    except Exception as e: print(f"Start.gg Error: {e}")

    # --- 2. BATTLEFY SCOUT ---
    try:
        bfy_data = scout_battlefy()
        with open(cache_file, "a") as f:
            for t in bfy_data:
                t_id = str(t.get('_id'))
                if t_id not in posted_ids:
                    # Battlefy dates can be tricky; we'll parse and convert to UTC for clean comparison
                    start_dt = datetime.datetime.fromisoformat(t['startTime'].replace('Z', '+00:00'))
                    
                    # RELAXED FILTER: Look for anything in the 7-day window
                    # We remove the "now.timestamp() <=" check to ensure "same-day" matches aren't missed
                    if start_dt.timestamp() <= window.timestamp():
                        slug = t['slug']
                        id_bfy = t['_id']
                        url = f"https://battlefy.com/tournaments/{slug}/{id_bfy}/info"
                        
                        payload = {
                            "username": "Battlefy Scout", 
                            "embeds": make_embeds(t['name'], url, start_dt.timestamp(), "Online", t.get('organizationName'), [])
                        }
                        requests.post(WEBHOOK_URL, json=payload)
                        f.write(t_id + "\n")
                        print(f"Posted Battlefy: {t['name']}")
    except Exception as e: 
        print(f"Battlefy Error: {e}")

    print("--- Session Finished ---")

if __name__ == "__main__":
    main()
