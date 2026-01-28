import os
import datetime
import time
import pytz
import requests
import pysmashgg
from pysmashgg.api import run_query

TIMEZONE = os.environ["TIMEZONE"]
GAME_ID = os.environ["GAME_ID"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
STARTGG_TOKEN = os.environ["STARTGG_TOKEN"]

CUSTOM_QUERY = """query TournamentsByGame($page: Int!, $videogameId: ID!) {
    tournaments(query: {
        perPage: 32
        page: $page
        filter: {
            past: false
            videogameIds: [
                $videogameId
            ]
        }
    }) {
        nodes {
            id
            name
            slug
            startAt
            images {
                type
                url
            }
            venueAddress
            primaryContact
        }
    }
}"""

def tournaments_filter(response, start_time: datetime, end_time: datetime):
    if not response.get('data') or not response['data'].get('tournaments'):
        return []
    
    nodes = response['data']['tournaments'].get('nodes', [])
    found = []
    
    for node in nodes:
        ts = node['startAt']
        # Check if the tournament falls within our 7-day window
        if start_time.timestamp() <= ts <= end_time.timestamp():
            found.append(node)
            
    found.sort(key=lambda t: t["startAt"])
    return found

def make_embeds(tournament):
    profile = next((img["url"] for img in tournament["images"] if img["type"] == 'profile'), None)
    banner = next((img["url"] for img in tournament["images"] if img["type"] == 'banner'), None)
    
    date_obj = datetime.datetime.fromtimestamp(tournament["startAt"], tz=pytz.timezone(TIMEZONE))
    date_str = date_obj.strftime('%A, %B %d at %H:%M')
    
    return [{
        "title": tournament["name"],
        "url": f'https://start.gg/{tournament["slug"]}',
        "color": 102204,
        "description": f'📅 **Match Date:** {date_str} (Berlin Time)\n📍 **Location:** {tournament["venueAddress"] or "Online"}\n👤 **Organizer:** {tournament["primaryContact"] or "N/A"}',
        "thumbnail": {"url": profile} if profile else None,
        "image": {"url": banner} if banner else None,
        "footer": {"text": "7-Day Team Scout - System Online"},
    }]

def main():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    # Start looking from right now up to 7 days in the future
    seven_days_later = now + datetime.timedelta(days=7)

    print(f"Scouting for Rematch from {now.date()} to {seven_days_later.date()}...")

    smash = pysmashgg.SmashGG(STARTGG_TOKEN, True)    
    variables = {"page": 1, "videogameId": GAME_ID}
    
    response = run_query(CUSTOM_QUERY, variables, smash.header, smash.auto_retry)
    upcoming = tournaments_filter(response, now, seven_days_later)

    if not upcoming:
        print("Scout Report: No tournaments found in the 7-day window.")
        return

    print(f"Found {len(upcoming)} tournaments! Sending to Discord...")
    for t in upcoming:
        payload = {
            "username": "Weekly Tourney Scout",
            "embeds": make_embeds(t),
        }
        requests.post(WEBHOOK_URL, json=payload)
        time.sleep(1) # Prevent rate-limiting

if __name__ == "__main__":
    main()
