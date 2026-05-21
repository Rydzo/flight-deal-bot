import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.environ.get("RAPIDAPI_KEY", "")
HOST = "kiwi-com-flights-api.p.rapidapi.com"
url = f"https://{HOST}/api/v1/flights/search-oneway"

destinations = ['LON', 'BCN', 'PAR', 'ROM', 'MIL']
headers = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": HOST,
}

for dest in destinations:
    params = {
        'source': 'WAW',
        'destination': dest,
        'departure_date': '2026-06-04',
        'adults': 1,
        'currency': 'PLN',
        'limit': 3
    }
    
    print(f"Testing WAW->{dest} Search...")
    t0 = time.time()
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        dt = time.time() - t0
        print(f"  Status: {r.status_code} in {dt:.2f}s")
        if r.status_code == 200:
            data = r.json()
            itineraries = data.get('itineraries', [])
            print(f"  Found {len(itineraries)} flights. Cheapest: {itineraries[0].get('price', {}).get('amount') if itineraries else 'N/A'}")
        else:
            print(f"  Error: {r.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")
    time.sleep(1) # sleep 1s between requests
