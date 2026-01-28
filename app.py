import os
import datetime
import pytz
import requests

# 1. Configuration
TIMEZONE = os.environ.get("TIMEZONE", "Europe/Berlin")
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
CACHE_FILE = "posted_ids.txt"

# 2. Your Discovery URL (Upcoming Only)
REMATCH_API_URL = "https://esports.playrematch.com/api/tournaments?statuses=pending&start_after_now=true&sort=scheduled_asc"

def scout_rematch():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://esports.playrematch.com/tournaments" # Added Referer for security bypass
    }
    try:
        print("--- Rematch Official API Scout Starting ---")
        response = requests.get(REMATCH_API_URL, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else data.get('data', [])
        else:
            print(f"❌ API Error: Status {response.status_code}")
            # THIS IS THE CRITICAL DEBUG LINE:
            print(f"🔍 Server Reason: {response.text}") 
    except Exception as e:
        print(f"❌ Connection Crash: {e}")
    return []

def main():
    # 3. State Management (Avoid Duplicates)
    if not os.path.exists(CACHE_FILE): open(CACHE_FILE, 'w').close()
    with open(CACHE_FILE, "r") as f: posted_ids = f.read().splitlines()

    tourneys = scout_rematch()
    print(f"Found {len(tourneys)} potential upcoming tournaments.")

    with open(CACHE_FILE, "a") as f:
        for t in tourneys:
            # Check the unique ID (usually 'id' or 'uuid')
            t_id = str(t.get('id', t.get('uuid')))
            
            if t_id not in posted_ids:
                name = t.get('name')
                # Construct the direct link for players
                link = f"https://esports.playrematch.com/tournaments/{t_id}"
                
                # Format the date nicely for Discord
                raw_start = t.get('scheduled_at') # Check if this is the correct key in the JSON
                
                payload = {
                    "username": "Rematch Intel",
                    "embeds": [{
                        "title": name,
                        "url": link,
                        "color": 3066993, # A clean blue color
                        "description": f"🏆 **New Rematch Tournament!**\n📅 **Starts:** {raw_start if raw_start else 'Check Link'}",
                        "footer": {"text": "PlayRematch Scout Activated"}
                    }]
                }
                
                res = requests.post(WEBHOOK_URL, json=payload)
                if res.status_code == 204:
                    f.write(t_id + "\n")
                    print(f"🚀 Posted to Discord: {name}")

if __name__ == "__main__":
    main()
