"""Diagnostic script - tests Kiwi RapidAPI endpoints."""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.environ.get("RAPIDAPI_KEY", "")
if not API_KEY:
    print("ERROR: No RAPIDAPI_KEY in .env!")
    sys.exit(1)

HOST = "kiwi-com-flights-api.p.rapidapi.com"
BASE = f"https://{HOST}/api/v1"
HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": HOST,
}

def test(name, endpoint, params, base_url=None):
    url = f"{base_url or BASE}{endpoint}"
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"  URL: {url}")
    print(f"  Params: {params}")
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())}")
                for key, val in data.items():
                    if isinstance(val, list):
                        print(f"  {key}: list, {len(val)} items")
                        if val:
                            print(f"  Sample[0]: {json.dumps(val[0], ensure_ascii=False)[:400]}")
                    elif isinstance(val, dict):
                        print(f"  {key}: dict, keys={list(val.keys())[:10]}")
                    else:
                        print(f"  {key}: {val}")
            else:
                print(f"  Type: {type(data).__name__}")
                print(f"  Sample: {json.dumps(data, ensure_ascii=False)[:500]}")
        else:
            print(f"  Response: {r.text[:500]}")
    except Exception as e:
        print(f"  ERROR: {e}")

# 1. Price Map WAW
test("Price Map WAW", "/flights/price-map",
     {"source": "WAW", "currency": "PLN", "start_date": "2026-06-01", "end_date": "2026-08-30"})

# 2. Search Oneway WAW->BCN
test("Search Oneway WAW->BCN", "/flights/search-oneway",
     {"source": "WAW", "destination": "BCN", "departure_date": "2026-06-15", "adults": 1, "currency": "PLN", "limit": 5})

# 3. Search Roundtrip WAW->BCN
test("Search Roundtrip WAW->BCN", "/flights/search-roundtrip",
     {"source": "WAW", "destination": "BCN", "departure_date": "2026-06-15", "return_date": "2026-06-22", "adults": 1, "currency": "PLN", "limit": 5})

# 4. Tequila-style /search
test("Tequila /v1/search", "/search",
     {"fly_from": "WAW", "fly_to": "BCN", "date_from": "15/06/2026", "date_to": "22/06/2026", "curr": "PLN", "adults": 1})

# 5. Tequila-style without /api/v1
test("Tequila root /search", "/search",
     {"fly_from": "WAW", "fly_to": "BCN", "date_from": "15/06/2026", "date_to": "22/06/2026", "curr": "PLN"},
     base_url=f"https://{HOST}")

# 6. Tequila /v2/search  
test("Tequila /v2/search", "/v2/search",
     {"fly_from": "WAW", "fly_to": "BCN", "date_from": "15/06/2026", "date_to": "22/06/2026", "curr": "PLN"},
     base_url=f"https://{HOST}")

# 7. Try /api/search
test("API /api/search", "/api/search",
     {"fly_from": "WAW", "fly_to": "BCN", "date_from": "15/06/2026", "date_to": "22/06/2026", "curr": "PLN"},
     base_url=f"https://{HOST}")

print(f"\n{'='*60}")
print("DONE")
