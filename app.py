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

import urllib.parse

def scout_battlefy():
    now = datetime.datetime.now(datetime.timezone.utc)
    start_date = now - datetime.timedelta(days=1)
    end_date = now + datetime.timedelta(days=10)

    date_fmt = "%a %b %d %Y %H:%M:%S GMT+0000"
    start_str = urllib.parse.quote(start_date.strftime(date_fmt))
    end_str = urllib.parse.quote(end_date.strftime(date_fmt))

    url = f"https://search.battlefy.com/tournament/homepage/rematch?&&start={start_str}&end={end_str}&showLadderTournaments=true&page=0"
    
    # Enhanced Stealth Headers to bypass the 403 Forbidden error
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://battlefy.com/browse/rematch",
        "Origin": "https://battlefy.com",
        "Connection": "keep-alive"
    }
    
    try:
        print(f"--- Battlefy Stealth Scout ---")
        # Using a Session object can sometimes help maintain 'connection state'
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            results = response.json()
            print(f"Success! Battlefy found {len(results)} items.")
            return results
        elif response.status_code == 403:
            print("Battlefy 403: Still blocked. Battlefy is detecting the GitHub IP.")
        else:
            print(f"Battlefy Error: Status {response.status_code}")
    except Exception as e:
        print(f"Battlefy Connection Crash: {e}")
    return []

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
