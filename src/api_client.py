import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote
import requests

logger = logging.getLogger(__name__)

class RapidApiKiwiClient:
    """Klient API Kiwi.com przez RapidAPI do wyszukiwania lotów."""

    def __init__(self, api_key: str) -> None:
        """Inicjalizacja klienta.
        
        Args:
            api_key: Klucz API do RapidAPI.
        """
        self.api_key = api_key
        self.host = "kiwi-com-flights-api.p.rapidapi.com"
        self.base_url = f"https://{self.host}/api/v1"
        self._request_count: int = 0
        logger.info("Klient RapidAPI Kiwi zainicjalizowany pomyślnie")

    def _get_headers(self) -> dict:
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
            "Content-Type": "application/json"
        }

    def _make_request_with_retry(self, endpoint: str, max_retries: int = 3, **params) -> Optional[dict]:
        """Wykonaj zapytanie API z obsługą retry i rate limiting."""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(max_retries):
            try:
                self._request_count += 1
                logger.debug(f"Zapytanie RapidAPI #{self._request_count} (próba {attempt + 1}/{max_retries}) do {endpoint}")
                
                response = requests.get(url, headers=self._get_headers(), params=params, timeout=15)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    logger.warning(f"Rate limit (429) z RapidAPI (próba {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    logger.warning(f"Błąd RapidAPI: status={response.status_code}, odpowiedź={response.text}")
                    if response.status_code >= 500 and attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None

            except requests.RequestException as e:
                logger.error(f"Błąd połączenia z RapidAPI: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue

        return None

    def search_flights(
        self,
        origin: str,
        destination: str,
        date_from: str,
        date_to: Optional[str] = None,
        max_price: Optional[int] = None,
        currency: str = 'PLN',
    ) -> list[dict]:
        """Wyszukaj loty na konkretnej trasie."""
        params = {
            'source': origin,
            'destination': destination,
            'departure_date': date_from,
            'adults': 1,
            'currency': currency,
            'limit': 50
        }
        
        endpoint = "/flights/search-roundtrip" if date_to else "/flights/search-oneway"
        if date_to:
            params['return_date'] = date_to
            
        logger.info(
            f"Wyszukiwanie lotów: {origin} → {destination}, "
            f"data: {date_from}, max cena: {max_price} {currency}"
        )
            
        data = self._make_request_with_retry(endpoint, **params)
        
        results = []
        if not data:
            return results
            
        # Zależnie od odpowiedzi, Kiwi może zwracać wyniki w data['data']
        items = []
        if isinstance(data, dict) and 'data' in data:
            items = data['data']
        elif isinstance(data, dict) and 'flights' in data:
            items = data['flights']
            
        for item in items:
            try:
                price = float(item.get('price', 0))
                if max_price and price > max_price:
                    continue
                    
                results.append({
                    'price': price,
                    'currency': currency,
                    'departure_date': item.get('local_departure', ''),
                    'arrival_date': item.get('local_arrival', ''),
                    'airline': item.get('airlines', [''])[0] if item.get('airlines') else '',
                    'origin': origin,
                    'destination': destination,
                    'duration': item.get('fly_duration', ''),
                    'stops': len(item.get('route', [])) - 1 if item.get('route') else 0,
                    'booking_link': item.get('deep_link', self._generate_booking_link(origin, destination, date_from))
                })
            except Exception as e:
                logger.warning(f"Błąd parsowania oferty lotu: {e}")
                
        logger.info(f"Znaleziono {len(results)} ofert lotów na trasie {origin} → {destination}")
        return results

    def get_inspiration(
        self,
        origin: str,
        max_price: Optional[int] = None,
        currency: str = 'PLN',
    ) -> list[dict]:
        """Najtańsze destynacje z danego lotniska przez price-map."""
        # Szukamy od jutra do 90 dni w przód
        start_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        
        params = {
            'source': origin,
            'currency': currency,
            'start_date': start_date,
            'end_date': end_date
        }
        
        logger.info(
            f"Wyszukiwanie inspiracji (price-map) z lotniska {origin}, "
            f"max cena: {max_price} {currency}"
        )
        
        data = self._make_request_with_retry("/flights/price-map", **params)
        
        # Diagnostyka — loguj surową odpowiedź API
        if data:
            keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
            logger.info(f"[DEBUG] Odpowiedź API price-map klucze: {keys}")
            # Loguj próbkę danych (pierwsze 500 znaków)
            import json
            sample = json.dumps(data, ensure_ascii=False)[:500]
            logger.info(f"[DEBUG] Próbka odpowiedzi: {sample}")
        else:
            logger.warning(f"[DEBUG] API price-map zwróciło None/pustą odpowiedź dla {origin}")
        
        results = []
        if not data or not isinstance(data, dict):
            logger.info(f"Znaleziono {len(results)} inspiracji z lotniska {origin}")
            return results
        
        # Sprawdź różne możliwe struktury odpowiedzi
        items = []
        if 'entries' in data:
            items = data['entries']
        elif 'data' in data:
            items = data['data'] if isinstance(data['data'], list) else []
        elif 'results' in data:
            items = data['results'] if isinstance(data['results'], list) else []
        elif 'flights' in data:
            items = data['flights'] if isinstance(data['flights'], list) else []
        
        logger.info(f"[DEBUG] Znaleziono {len(items)} elementów w odpowiedzi price-map")
        
        for item in items:
            try:
                # Obsłuż różne formaty odpowiedzi
                if isinstance(item, dict):
                    dest_info = item.get('destination', {})
                    if isinstance(dest_info, dict):
                        dest_code = dest_info.get('code', '') or dest_info.get('iata', '') or dest_info.get('name', '')
                    elif isinstance(dest_info, str):
                        dest_code = dest_info
                    else:
                        dest_code = ''
                    
                    price = float(item.get('price', 0))
                else:
                    continue
                    
                if not dest_code or not price or price <= 0:
                    continue
                if max_price and price > max_price:
                    continue
                    
                results.append({
                    'destination': dest_code,
                    'departure_date': start_date,
                    'return_date': '',
                    'price': price,
                    'currency': currency,
                    'origin': origin,
                    'booking_link': self._generate_booking_link(origin, dest_code, start_date),
                })
            except Exception as e:
                logger.warning(f"Błąd parsowania price-map: {e}")
                    
        # Jeśli price-map nie dał wyników, spróbuj search-oneway dla popularnych destynacji
        if not results:
            logger.info(f"[FALLBACK] Price-map pusty dla {origin}, próbuję search-oneway dla popularnych destynacji...")
            popular_destinations = ['LON', 'BCN', 'PAR', 'ROM', 'BER', 'AMS', 'PRG', 'BUD', 'VIE', 'MIL']
            for dest in popular_destinations:
                try:
                    fb_params = {
                        'source': origin,
                        'destination': dest,
                        'departure_date': start_date,
                        'adults': 1,
                        'currency': currency,
                        'limit': 5
                    }
                    fb_data = self._make_request_with_retry("/flights/search-oneway", **fb_params)
                    if fb_data:
                        fb_items = []
                        if isinstance(fb_data, dict):
                            if 'data' in fb_data:
                                fb_items = fb_data['data'] if isinstance(fb_data['data'], list) else []
                            elif 'flights' in fb_data:
                                fb_items = fb_data['flights'] if isinstance(fb_data['flights'], list) else []
                            elif 'results' in fb_data:
                                fb_items = fb_data['results'] if isinstance(fb_data['results'], list) else []
                        
                        if fb_items:
                            logger.info(f"[FALLBACK] Znaleziono {len(fb_items)} lotów {origin} → {dest}")
                            # Loguj próbkę pierwszego elementu
                            import json
                            logger.info(f"[FALLBACK DEBUG] Próbka elementu: {json.dumps(fb_items[0], ensure_ascii=False)[:300]}")
                        
                        for fb_item in fb_items[:3]:
                            try:
                                price = float(fb_item.get('price', 0))
                                if price <= 0:
                                    continue
                                results.append({
                                    'destination': dest,
                                    'departure_date': fb_item.get('local_departure', start_date)[:10],
                                    'return_date': '',
                                    'price': price,
                                    'currency': currency,
                                    'origin': origin,
                                    'booking_link': fb_item.get('deep_link', self._generate_booking_link(origin, dest, start_date)),
                                })
                            except Exception as e:
                                logger.warning(f"Błąd parsowania fallback: {e}")
                except Exception as e:
                    logger.warning(f"Błąd fallback search {origin}→{dest}: {e}")
                    
        logger.info(f"Znaleziono {len(results)} inspiracji z lotniska {origin}")
        return results

    def get_cheapest_dates(self, origin: str, destination: str) -> list[dict]:
        """Puste — rzadko używane w Kiwi, obsłużone w głównym wyszukiwaniu."""
        return []

    def _generate_booking_link(self, origin: str, destination: str, date: str) -> str:
        """Generuj link do Kiwi.com."""
        date_clean = date[:10] if len(date) > 10 else date
        return f"https://www.kiwi.com/deep?from={quote(origin)}&to={quote(destination)}&departure={quote(date_clean)}"

    @property
    def request_count(self) -> int:
        """Zwróć liczbę wykonanych zapytań API."""
        return self._request_count
