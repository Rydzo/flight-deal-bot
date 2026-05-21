"""
Moduł konfiguracyjny bota do wyszukiwania okazji lotniczych.

Zawiera:
- Zmienne środowiskowe (klucze API, tokeny)
- Listę polskich lotnisk i funkcję rotacji
- Progi cenowe dla wykrywania błędnych cen
- Mapowanie regionów i krajów
- Funkcje ładowania i parsowania lotnisk
- Stałe konfiguracyjne (waluta, interwały, historia cen)
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Konfiguracja logowania
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ścieżki projektu
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Zmienne środowiskowe – klucze API i tokeny
# ---------------------------------------------------------------------------
RAPIDAPI_KEY: str = os.environ.get("RAPIDAPI_KEY", "")
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Waluta i zakres dat
# ---------------------------------------------------------------------------
CURRENCY: str = "PLN"
DATE_RANGE_MONTHS: int = 12

# ---------------------------------------------------------------------------
# Polskie lotniska
# ---------------------------------------------------------------------------
POLISH_AIRPORTS: list[str] = [
    "WAW",  # Warszawa Chopina
    "KRK",  # Kraków Balice
    "GDN",  # Gdańsk Lech Wałęsa
    "KTW",  # Katowice Pyrzowice
    "WRO",  # Wrocław Kopernika
    "POZ",  # Poznań Ławica
    "RZE",  # Rzeszów Jasionka
    "SZZ",  # Szczecin Goleniów
    "LUZ",  # Lublin
    "BYG",  # Bydgoszcz
    "LCJ",  # Łódź Lublinek
]


def get_today_origin() -> str:
    """Zwraca kod IATA lotniska wybranego na podstawie dnia w roku.

    Lotniska są rotowane cyklicznie – każdego dnia aktywne jest
    inne lotnisko wylotowe z listy POLISH_AIRPORTS.

    Returns:
        Kod IATA polskiego lotniska (np. 'WAW', 'KRK').
    """
    day_of_year = datetime.now().timetuple().tm_yday
    index = day_of_year % len(POLISH_AIRPORTS)
    selected = POLISH_AIRPORTS[index]
    logger.debug(f"Dzień roku: {day_of_year}, wybrane lotnisko: {selected}")
    return selected


# ---------------------------------------------------------------------------
# Interwał skanowania
# ---------------------------------------------------------------------------
SCAN_INTERVAL_HOURS: int = 6

# ---------------------------------------------------------------------------
# Historia cen
# ---------------------------------------------------------------------------
PRICE_HISTORY_MAX_ENTRIES: int = 30    # Maksymalna liczba wpisów na trasę
PRICE_HISTORY_MAX_AGE_DAYS: int = 90   # Maksymalny wiek wpisu w dniach

# ---------------------------------------------------------------------------
# Próg wykrywania błędnych cen (bug deals)
# ---------------------------------------------------------------------------
BUG_THRESHOLD_PERCENT: int = 40  # Minimalny procent zniżki, aby oznaczyć jako bug

# ---------------------------------------------------------------------------
# Progi absolutne cen minimalnych (w PLN) wg regionów
# ---------------------------------------------------------------------------
ABSOLUTE_THRESHOLDS: dict[str, int] = {
    "europe_short":  30,   # Krótkie loty europejskie
    "europe_long":   80,   # Dłuższe loty europejskie
    "asia":         400,   # Azja
    "americas":     600,   # Ameryki (Północna i Południowa)
    "africa":       350,   # Afryka
    "oceania":      800,   # Oceania (Australia, Nowa Zelandia itp.)
}

# ---------------------------------------------------------------------------
# Mapowanie krajów na regiony
# ---------------------------------------------------------------------------
REGION_MAPPING: dict[str, str] = {
    # Europa – krótki dystans (bliskie kraje)
    "Germany": "europe_short",
    "Czech Republic": "europe_short",
    "Slovakia": "europe_short",
    "Austria": "europe_short",
    "Hungary": "europe_short",
    "Lithuania": "europe_short",
    "Latvia": "europe_short",
    "Estonia": "europe_short",
    "Denmark": "europe_short",
    "Sweden": "europe_short",
    "Netherlands": "europe_short",
    "Belgium": "europe_short",
    "Switzerland": "europe_short",
    "France": "europe_short",
    "UK": "europe_short",
    "Ireland": "europe_short",

    # Europa – daleki dystans
    "Spain": "europe_long",
    "Portugal": "europe_long",
    "Italy": "europe_long",
    "Greece": "europe_long",
    "Croatia": "europe_long",
    "Slovenia": "europe_long",
    "Romania": "europe_long",
    "Bulgaria": "europe_long",
    "Serbia": "europe_long",
    "Bosnia and Herzegovina": "europe_long",
    "Albania": "europe_long",
    "North Macedonia": "europe_long",
    "Montenegro": "europe_long",
    "Moldova": "europe_long",
    "Ukraine": "europe_long",
    "Belarus": "europe_long",
    "Russia": "europe_long",
    "Turkey": "europe_long",
    "Cyprus": "europe_long",
    "Norway": "europe_long",
    "Finland": "europe_long",
    "Iceland": "europe_long",
    "Malta": "europe_long",
    "Luxembourg": "europe_long",
    "Switzerland/France/Germany": "europe_short",

    # Azja
    "Japan": "asia",
    "South Korea": "asia",
    "China": "asia",
    "Hong Kong": "asia",
    "Macau": "asia",
    "Taiwan": "asia",
    "Mongolia": "asia",
    "Thailand": "asia",
    "Vietnam": "asia",
    "Cambodia": "asia",
    "Laos": "asia",
    "Myanmar": "asia",
    "Malaysia": "asia",
    "Singapore": "asia",
    "Indonesia": "asia",
    "Philippines": "asia",
    "India": "asia",
    "Sri Lanka": "asia",
    "Bangladesh": "asia",
    "Nepal": "asia",
    "Bhutan": "asia",
    "Pakistan": "asia",
    "Afghanistan": "asia",
    "Kazakhstan": "asia",
    "Uzbekistan": "asia",
    "Turkmenistan": "asia",
    "Kyrgyzstan": "asia",
    "Tajikistan": "asia",
    "Iran": "asia",
    "Iraq": "asia",
    "Israel": "asia",
    "Jordan": "asia",
    "Lebanon": "asia",
    "Syria": "asia",
    "UAE": "asia",
    "Saudi Arabia": "asia",
    "Qatar": "asia",
    "Bahrain": "asia",
    "Kuwait": "asia",
    "Oman": "asia",
    "Yemen": "asia",

    # Ameryki
    "USA": "americas",
    "Canada": "americas",
    "Mexico": "americas",
    "Brazil": "americas",
    "Argentina": "americas",
    "Chile": "americas",
    "Colombia": "americas",
    "Peru": "americas",
    "Ecuador": "americas",
    "Bolivia": "americas",
    "Paraguay": "americas",
    "Uruguay": "americas",
    "Venezuela": "americas",
    "Guyana": "americas",
    "Suriname": "americas",
    "French Guiana": "americas",
    "Guatemala": "americas",
    "El Salvador": "americas",
    "Honduras": "americas",
    "Nicaragua": "americas",
    "Costa Rica": "americas",
    "Panama": "americas",
    "Cuba": "americas",
    "Jamaica": "americas",
    "Haiti": "americas",
    "Dominican Republic": "americas",
    "Puerto Rico": "americas",
    "Bahamas": "americas",
    "Trinidad and Tobago": "americas",
    "Grenada": "americas",
    "Saint Lucia": "americas",
    "Dominica": "americas",
    "Saint Kitts and Nevis": "americas",
    "Antigua and Barbuda": "americas",
    "Sint Maarten": "americas",
    "Saint Barthélemy": "americas",
    "Anguilla": "americas",
    "Guadeloupe": "americas",
    "Martinique": "americas",
    "Aruba": "americas",
    "Curaçao": "americas",
    "Bonaire": "americas",
    "Saint Vincent and the Grenadines": "americas",
    "US Virgin Islands": "americas",
    "Guam": "americas",
    "Northern Mariana Islands": "americas",
    "American Samoa": "americas",

    # Afryka
    "Egypt": "africa",
    "Morocco": "africa",
    "Tunisia": "africa",
    "Algeria": "africa",
    "Libya": "africa",
    "Sudan": "africa",
    "Nigeria": "africa",
    "Ghana": "africa",
    "Ivory Coast": "africa",
    "Senegal": "africa",
    "Sierra Leone": "africa",
    "Liberia": "africa",
    "Mali": "africa",
    "Burkina Faso": "africa",
    "Niger": "africa",
    "Benin": "africa",
    "Togo": "africa",
    "Guinea-Bissau": "africa",
    "Guinea": "africa",
    "Cape Verde": "africa",
    "Cameroon": "africa",
    "Chad": "africa",
    "Central African Republic": "africa",
    "Gabon": "africa",
    "Republic of the Congo": "africa",
    "DR Congo": "africa",
    "Kenya": "africa",
    "Tanzania": "africa",
    "Uganda": "africa",
    "Rwanda": "africa",
    "Burundi": "africa",
    "Ethiopia": "africa",
    "Eritrea": "africa",
    "Djibouti": "africa",
    "Somalia": "africa",
    "South Africa": "africa",
    "Namibia": "africa",
    "Botswana": "africa",
    "Zimbabwe": "africa",
    "Zambia": "africa",
    "Mozambique": "africa",
    "Angola": "africa",
    "Madagascar": "africa",
    "Mauritius": "africa",
    "Réunion": "africa",
    "Seychelles": "africa",

    # Oceania
    "Australia": "oceania",
    "New Zealand": "oceania",
    "Fiji": "oceania",
    "French Polynesia": "oceania",
    "New Caledonia": "oceania",
    "Vanuatu": "oceania",
    "Solomon Islands": "oceania",
    "Papua New Guinea": "oceania",
    "Tonga": "oceania",
    "Samoa": "oceania",
    "Cook Islands": "oceania",
}

# ---------------------------------------------------------------------------
# Funkcje ładowania i parsowania lotnisk
# ---------------------------------------------------------------------------


def parse_airports_file(filepath: str) -> list[dict[str, str]]:
    """Parsuje plik tekstowy z lotniskami i wyodrębnia kody IATA, nazwy i kraje.

    Format oczekiwany (każda linia):
        123. [ABC] Nazwa Lotniska - Kraj

    Args:
        filepath: Ścieżka do pliku tekstowego z lotniskami.

    Returns:
        Lista słowników z kluczami: 'code', 'name', 'country'.
    """
    airports: list[dict[str, str]] = []
    pattern = re.compile(r'\[([A-Z]{3,4})\]')

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                match = pattern.search(line)
                if not match:
                    continue

                code = match.group(1)

                # Wyodrębnienie nazwy (tekst między ']' a ostatnim '-')
                after_bracket = line[match.end():].strip()
                parts = after_bracket.rsplit(" - ", maxsplit=1)

                if len(parts) == 2:
                    name = parts[0].strip()
                    country = parts[1].strip()
                else:
                    name = after_bracket
                    country = "Unknown"

                airports.append({
                    "code": code,
                    "name": name,
                    "country": country,
                })

    except FileNotFoundError:
        logger.error(f"Nie znaleziono pliku z lotniskami: {filepath}")
    except Exception as e:
        logger.error(f"Błąd podczas parsowania pliku lotnisk: {e}")

    logger.info(f"Sparsowano {len(airports)} lotnisk z pliku {filepath}")
    return airports


def load_airports() -> list[dict[str, str]]:
    """Ładuje listę lotnisk z pliku JSON lub generuje ją z pliku tekstowego.

    Jeśli plik data/airports.json istnieje, ładuje go bezpośrednio.
    W przeciwnym razie parsuje plik tekstowy z lotniskami i zapisuje
    wynik do JSON na przyszłość.

    Returns:
        Lista słowników z danymi lotnisk (code, name, country).
    """
    json_path = DATA_DIR / "airports.json"
    txt_path = PROJECT_ROOT / "najczestsze_lotniska_swiata.txt"

    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                airports: list[dict[str, str]] = json.load(f)
            logger.info(f"Załadowano {len(airports)} lotnisk z {json_path}")
            return airports
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Błąd odczytu {json_path}, generuję ponownie: {e}")

    # Generowanie z pliku tekstowego
    logger.info(f"Plik {json_path} nie istnieje, generuję z {txt_path}")
    airports = parse_airports_file(str(txt_path))

    if airports:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(airports, f, ensure_ascii=False, indent=2)
            logger.info(f"Zapisano {len(airports)} lotnisk do {json_path}")
        except IOError as e:
            logger.error(f"Nie udało się zapisać pliku JSON: {e}")

    return airports


def get_destination_airports() -> list[dict[str, str]]:
    """Zwraca listę lotnisk docelowych (wszystkie poza polskimi).

    Filtruje lotniska, których kraj to 'Poland', pozostawiając
    tylko zagraniczne lotniska jako potencjalne cele podróży.

    Returns:
        Lista słowników lotnisk spoza Polski.
    """
    all_airports = load_airports()
    polish_codes = set(POLISH_AIRPORTS)

    destinations = [
        airport for airport in all_airports
        if airport["code"] not in polish_codes
    ]

    logger.info(
        f"Lotniska docelowe: {len(destinations)} "
        f"(z {len(all_airports)} łącznie, pominięto polskie)"
    )
    return destinations
