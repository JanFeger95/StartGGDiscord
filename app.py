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

from playwright.sync_api import sync_playwright
import json

def scout_battlefy():
    results = []
    # This URL is the actual browse page where the data is triggered
    target_url = "https://battlefy.com/browse/rematch"
    
    with sync_playwright() as p:
        print("--- Battlefy Browser Scout Starting ---")
        browser = p.chromium.launch(headless=True)
        # Mimic a real person's screen size and browser signature
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # This 'catch' function triggers whenever the browser talks to an API
        def handle_response(response):
            if "search.battlefy.com/tournament/homepage/rematch" in response.url:
                try:
                    data = response.json()
                    # We found the JSON data! Store it.
                    tourneys = data if isinstance(data, list) else data.get('tournaments', [])
                    results.extend(tourneys)
                    print(f"Captured {len(tourneys)} tournaments from network traffic.")
                except:
                    pass

        page.on("response", handle_response)
        
        try:
            # Go to the site and wait for it to stop loading data
            page.goto(target_url, wait_until="networkidle", timeout=60000)
            # Small extra wait to ensure all 'Upcoming' filters finish
            page.wait_for_timeout(5000) 
        except Exception as e:
            print(f"Browser timeout or error: {e}")
        finally:
            browser.close()
            
    return results

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
