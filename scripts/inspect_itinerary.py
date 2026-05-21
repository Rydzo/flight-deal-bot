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
    'destination': 'BCN',
    'departure_date': '2026-06-04',
    'adults': 1,
    'currency': 'PLN',
    'limit': 1
}

headers = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": HOST,
}

try:
    r = requests.get(url, headers=headers, params=params, timeout=15)
    data = r.json()
    itineraries = data.get('itineraries', [])
    if itineraries:
        print(json.dumps(itineraries[0], indent=2))
    else:
        print("No itineraries found")
except Exception as e:
    print(f"Error: {e}")
