import os
import datetime
import pytz
import requests
import pysmashgg
from pysmashgg.api import run_query

# Configuration from GitHub Secrets
TIMEZONE = os.environ.get("TIMEZONE", "Europe/Berlin")
GAME_ID = os.environ["GAME_ID"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
STARTGG_TOKEN = os.environ["STARTGG_TOKEN"]
CACHE_FILE = "posted_ids.txt"

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

def make_embeds(name, url, start_ts, location, contact, images):
    profile = next((img["url"] for img in images if img["type"] == 'profile'), None)
    banner = next((img["url"] for img in images if img["type"] == 'banner'), None)
    
    date_obj = datetime.datetime.fromtimestamp(start_ts, tz=pytz.timezone(TIMEZONE))
    date_str = date_obj.strftime('%A, %B %d at %H:%M')
    
    return [{
        "title": name,
        "url": url,
        "color": 102204,
        "description": f"📅 **Date:** {date_str}\n📍 **Loc:** {location or 'Online'}\n👤 **Org:** {contact or 'N/A'}",
        "thumbnail": {"url": profile} if profile else None,
        "image": {"url": banner} if banner else None,
        "footer": {"text": "Official start.gg Scout"},
    }]

def main():
    print("--- Starting start.gg Scout Session ---")
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    window = now + datetime.timedelta(days=7)

    # State Management: Don't post duplicates
    if not os.path.exists(CACHE_FILE): open(CACHE_FILE, 'w').close()
    with open(CACHE_FILE, "r") as f: posted_ids = f.read().splitlines()

    try:
        smash = pysmashgg.SmashGG(STARTGG_TOKEN, True)
        response = run_query(CUSTOM_QUERY, {"page": 1, "videogameId": GAME_ID}, smash.header, smash.auto_retry)
        nodes = response.get('data', {}).get('tournaments', {}).get('nodes', [])
        
        with open(CACHE_FILE, "a") as f:
            for t in nodes:
                t_id = str(t['id'])
                if t_id not in posted_ids and now.timestamp() <= t['startAt'] <= window.timestamp():
                    payload = {
                        "username": "start.gg Scout", 
                        "embeds": make_embeds(t['name'], f"https://start.gg/{t['slug']}", t['startAt'], t['venueAddress'], t['primaryContact'], t['images'])
                    }
                    requests.post(WEBHOOK_URL, json=payload)
                    f.write(t_id + "\n")
                    print(f"✅ Posted: {t['name']}")
                    
    except Exception as e:
        print(f"❌ Error during scout: {e}")

if __name__ == "__main__":
    main()
