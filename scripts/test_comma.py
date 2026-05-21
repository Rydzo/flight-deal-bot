import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.environ.get("RAPIDAPI_KEY", "")
HOST = "kiwi-com-flights-api.p.rapidapi.com"
url = f"https://{HOST}/api/v1/flights/search-oneway"

params = {
    'source': 'WAW',
    'destination': 'LON,BCN,PAR,ROM',
    'departure_date': '2026-06-04',
    'adults': 1,
    'currency': 'PLN',
    'limit': 5
}

headers = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": HOST,
}

try:
    print("Sending request for multiple destinations 'LON,BCN,PAR,ROM'...")
    r = requests.get(url, headers=headers, params=params, timeout=15)
    print(f"Status code: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        itineraries = data.get('itineraries', [])
        print(f"Success! Found {len(itineraries)} itineraries.")
        for i, item in enumerate(itineraries[:5]):
            # Try to parse destination
            outbound = item.get('outbound')
            dest = "Unknown"
            if outbound and isinstance(outbound, dict):
                segments = outbound.get('segments', [])
                if segments:
                    dest = segments[-1].get('destination', {}).get('station', {}).get('code', '')
            print(f"  [{i}] Destination: {dest}, Price: {item.get('price', {}).get('amount')} PLN")
    else:
        print(f"Response: {r.text}")
except Exception as e:
    print(f"Error: {e}")
