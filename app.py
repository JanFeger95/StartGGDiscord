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
