import os
import datetime
import time
import pytz
import requests
import pysmashgg
from pysmashgg.api import run_query

# Remove STATE as it's no longer used in the query
TIMEZONE = os.environ["TIMEZONE"]
GAME_ID = os.environ["GAME_ID"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
STARTGG_TOKEN = os.environ["STARTGG_TOKEN"]

# Modified Query: Removed $state variable and addrState filter
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
            addrState
            city
            countryCode
            createdAt
            startAt
            endAt
            hasOfflineEvents
            hasOnlineEvents
            images {
                id
                height
                width
                ratio
                type
                url
            }
            isRegistrationOpen
            numAttendees
            primaryContact
            primaryContactType
            registrationClosesAt
            slug
            state
            streams {
                id
                streamName
            }
            timezone
            venueAddress
            venueName
        }
    }
}"""

def tournaments_filter(response, earliestTime: datetime, latestTime: datetime, useCreatedAt: bool):
    if not response.get('data') or not response['data'].get('tournaments'):
        return []

    nodes = response['data']['tournaments'].get('nodes')
    if not nodes:
        return []

    tournaments = []
    for node in nodes:
        checkDate = node["createdAt"] if useCreatedAt else node['startAt']
        if earliestTime.timestamp() <= checkDate <= latestTime.timestamp():
            tournaments.append(node)

    tournaments.sort(key=lambda t: t["startAt"])
    return tournaments

def make_embeds(tournament):
    profile = None
    banner = None
    for image in tournament["images"]:
        if image["type"] == 'profile':
            profile = {"url": image["url"]}
        if image["type"] == 'banner':
            banner = {"url": image["url"]}
    
    # Formats date based on your Berlin timezone
    date = datetime.datetime.fromtimestamp(tournament["startAt"], tz=pytz.timezone(TIMEZONE)).strftime('%A, %B %d')
    
    return [
        {
            "title": tournament["name"],
            "url": f'https://start.gg/{tournament["slug"]}',
            "color": 102204,
            "description": f'📅 **Date:** {date}\n📍 **Location:** {tournament["venueAddress"] or "Online"}\n👤 **Contact:** {tournament["primaryContact"] or "N/A"}',
            "thumbnail": profile,
            "image": banner,
            "footer": {"text": "Rematch Scout - Bulletproof Edition"},
        }
    ]

def main():
    tz = pytz.timezone(TIMEZONE)
    this_morning = datetime.datetime.combine(datetime.datetime.now(tz).date(), datetime.time(0, 0, tzinfo=tz), tzinfo=tz)
    tomorrow = this_morning + datetime.timedelta(days=1)
    overmorrow = this_morning + datetime.timedelta(days=2)
    next_week = this_morning + datetime.timedelta(days=8)

    smash = pysmashgg.SmashGG(STARTGG_TOKEN, True)    
    # Removed "state" from variables
    variables = {"page": 1, "videogameId": GAME_ID}
    
    response = run_query(CUSTOM_QUERY, variables, smash.header, smash.auto_retry)
    
    tournaments_tomorrow = tournaments_filter(response, tomorrow, overmorrow, False)
    tournaments_created_recently = tournaments_filter(response, this_morning, tomorrow, True)

    # Post Events Tomorrow
    for tournament in tournaments_tomorrow:
        payload = {
            "username": "Match Tomorrow!",
            "embeds": make_embeds(tournament),
        }
        requests.post(WEBHOOK_URL, json=payload)
    
    time.sleep(1)

    # Post Recently Created Events
    for tournament in tournaments_created_recently:
        if tournament in tournaments_tomorrow:
            continue
        payload = {
            "username": "New Tournament Discovered",
            "embeds": make_embeds(tournament),
        }
        requests.post(WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    main()
