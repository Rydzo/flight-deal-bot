import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.environ.get("RAPIDAPI_KEY", "")
HOST = "kiwi-com-flights-api.p.rapidapi.com"
url = f"https://{HOST}/api/v1/flights/search-oneway"

# Załaduj lotniska
airports_path = Path(__file__).parent.parent / "data" / "airports.json"
with open(airports_path, 'r', encoding='utf-8') as f:
    airports = json.load(f)

# Pobierz kody docelowych (pomijając polskie)
POLISH_AIRPORTS = {'WAW', 'KRK', 'GDN', 'KTW', 'WRO', 'POZ', 'RZE', 'SZZ', 'LUZ', 'BYG', 'LCJ'}
dest_codes = [a['code'] for a in airports if a['code'] not in POLISH_AIRPORTS]

print(f"Loaded {len(dest_codes)} destination codes.")

# Łączymy w zapytanie zbiorcze
params = {
    'source': 'WAW,KRK,GDN',
    'destination': ','.join(dest_codes),  # przetestujmy wszystkie 929 destynacji na raz
    'departure_date': '2026-06-15',
    'adults': 1,
    'currency': 'PLN',
    'one_for_city': 1,
    'limit': 10
}

headers = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": HOST,
}

print(f"Querying {url} with {len(params['destination'].split(','))} destinations...")
try:
    r = requests.get(url, headers=headers, params=params, timeout=15)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
