import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote
import requests

logger = logging.getLogger(__name__)

class RapidApiKiwiClient:
    """Klient API Kiwi.com przez RapidAPI do wyszukiwania lotów."""

    # Popularne destynacje europejskie do skanowania (kody IATA)
    POPULAR_DESTINATIONS = [
        # Europa Zachodnia
        'LON', 'BCN', 'PAR', 'ROM', 'MIL', 'AMS', 'BER', 'BRU', 'VIE', 'PRG',
        'BUD', 'LIS', 'MAD', 'DUB', 'CPH', 'ATH', 'ZRH', 'OSL', 'HEL', 'STO',
        # Europa Wschodnia / Bałkany
        'IST', 'SOF', 'BUH', 'ZAG', 'BEG', 'TIV', 'SKP',
        # Popularne turystyczne
        'PMI', 'AGP', 'TFS', 'LPA', 'FAO', 'NAP', 'SPU', 'DBV', 'CFU', 'RHO',
        'HER', 'SKG', 'GVA', 'NCE', 'MRS',
        # Daleki zasięg
        'JFK', 'BKK', 'NRT', 'DXB', 'DOH', 'TLV', 'CMB', 'DEL', 'SIN',
        'KUL', 'HKT', 'BAH', 'CAI', 'CAS', 'RAK', 'SSH',
    ]

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
                    logger.warning(f"Błąd RapidAPI: status={response.status_code}, odpowiedź={response.text[:200]}")
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

    def _parse_itinerary(self, item: dict, origin: str, currency: str) -> Optional[dict]:
        """Parsuj pojedynczy element 'itinerary' z odpowiedzi Kiwi API.
        
        Kiwi RapidAPI zwraca loty w formacie z 'sectors' lub 'outbound'/'inbound'.
        """
        try:
            # Cena
            price_info = item.get('price', {})
            if isinstance(price_info, dict):
                price = float(price_info.get('amount', 0))
            else:
                price = float(price_info) if price_info else 0
            
            if price <= 0:
                return None

            # Destynacja i data
            dest_code = ''
            departure_date = ''
            return_date = ''
            airline = ''
            booking_link = ''
            
            # Format 1: outbound / inbound (nowszy format Kiwi RapidAPI)
            outbound = item.get('outbound')
            if outbound and isinstance(outbound, dict):
                segments = outbound.get('segments', [])
                if segments:
                    last_seg = segments[-1]
                    dest_code = last_seg.get('destination', {}).get('station', {}).get('code', '')
                    
                    first_seg = segments[0]
                    departure_date = first_seg.get('source', {}).get('local_time', '')[:10]
                    
                    carrier = first_seg.get('carrier', {})
                    if isinstance(carrier, dict):
                        airline = carrier.get('name', '') or carrier.get('code', '')
            
            inbound = item.get('inbound')
            if inbound and isinstance(inbound, dict):
                in_segments = inbound.get('segments', [])
                if in_segments:
                    return_date = in_segments[0].get('source', {}).get('local_time', '')[:10]

            # Format 2: sectors (starszy format)
            if not dest_code:
                sectors = item.get('sectors', [])
                if sectors and isinstance(sectors, list):
                    first_sector = sectors[0]
                    arrival = first_sector.get('arrival', {})
                    departure = first_sector.get('departure', {})
                    
                    # Kod destynacji
                    arr_city = arrival.get('city', {})
                    if isinstance(arr_city, dict):
                        dest_code = arr_city.get('code', '') or arr_city.get('iata', '')
                    arr_station = arrival.get('station', {})
                    if not dest_code and isinstance(arr_station, dict):
                        dest_code = arr_station.get('code', '')
                    
                    # Data wylotu
                    departure_date = first_sector.get('departure_time', '')[:10]
                    
                    # Linia lotnicza
                    carrier = first_sector.get('carrier', {})
                    if isinstance(carrier, dict):
                        airline = carrier.get('name', '') or carrier.get('code', '')
            
            # Fallback - spróbuj odczytać destynację z innych pól
            if not dest_code:
                # Niektóre endpointy mogą mieć flat structure
                dest_code = item.get('destination', '') or item.get('flyTo', '')
            
            if not dest_code:
                return None
            
            # Booking link
            # W nowym formacie link może być w booking_options
            booking_options = item.get('booking_options', [])
            if booking_options and isinstance(booking_options, list):
                booking_link = booking_options[0].get('booking_url', '')
                
            if not booking_link:
                booking_link = item.get('deep_link', '') or item.get('booking_link', '')
                
            if not booking_link:
                booking_link = self._generate_booking_link(origin, dest_code, departure_date)

            return {
                'destination': dest_code,
                'departure_date': departure_date,
                'return_date': return_date,
                'price': price,
                'currency': currency,
                'origin': origin,
                'airline': airline,
                'booking_link': booking_link,
            }
        except Exception as e:
            logger.warning(f"Błąd parsowania itinerary: {e}")
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
        """Wyszukaj loty na konkretnej trasie przez search-oneway."""
        params = {
            'source': origin,
            'destination': destination,
            'departure_date': date_from,
            'adults': 1,
            'currency': currency,
            'limit': 20
        }
        
        endpoint = "/flights/search-roundtrip" if date_to else "/flights/search-oneway"
        if date_to:
            params['return_date'] = date_to
            
        logger.info(
            f"Wyszukiwanie lotów: {origin} -> {destination}, "
            f"data: {date_from}, max cena: {max_price} {currency}"
        )
            
        data = self._make_request_with_retry(endpoint, **params)
        
        results = []
        if not data or not isinstance(data, dict):
            return results
        
        # Kiwi RapidAPI zwraca dane w kluczu 'itineraries'
        itineraries = data.get('itineraries', [])
        
        for item in itineraries:
            parsed = self._parse_itinerary(item, origin, currency)
            if parsed:
                if max_price and parsed['price'] > max_price:
                    continue
                # Nadpisz destynację na podaną (bo wiemy na pewno)
                parsed['destination'] = destination
                results.append(parsed)
                
        logger.info(f"Znaleziono {len(results)} ofert lotów na trasie {origin} -> {destination}")
        return results

    def get_inspiration(
        self,
        origin: str,
        max_price: Optional[int] = None,
        currency: str = 'PLN',
    ) -> list[dict]:
        """Najtańsze destynacje z danego lotniska.
        
        Używa search-oneway do popularnych destynacji, bo endpoint
        price-map w Kiwi RapidAPI nie zwraca wyników dla polskich lotnisk.
        """
        start_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        
        logger.info(
            f"Skanowanie tanich lotów z {origin}, "
            f"max cena: {max_price} {currency}, "
            f"destynacji do sprawdzenia: {len(self.POPULAR_DESTINATIONS)}"
        )
        
        results = []
        
        for dest in self.POPULAR_DESTINATIONS:
            try:
                params = {
                    'source': origin,
                    'destination': dest,
                    'departure_date': start_date,
                    'adults': 1,
                    'currency': currency,
                    'limit': 3  # Tylko najtańsze 3 oferty na trasę
                }
                
                data = self._make_request_with_retry(
                    "/flights/search-oneway", max_retries=3, **params
                )
                
                if not data or not isinstance(data, dict):
                    time.sleep(1.0)
                    continue
                
                itineraries = data.get('itineraries', [])
                
                for item in itineraries:
                    parsed = self._parse_itinerary(item, origin, currency)
                    if not parsed:
                        continue
                    
                    # Nadpisz destynację (mamy pewność)
                    parsed['destination'] = dest
                    
                    if max_price and parsed['price'] > max_price:
                        continue
                    
                    results.append(parsed)
                
                if itineraries:
                    cheapest = min(
                        (float(it.get('price', {}).get('amount', 99999)) 
                         if isinstance(it.get('price'), dict) 
                         else 99999 for it in itineraries),
                        default=99999
                    )
                    logger.info(f"  {origin} -> {dest}: {len(itineraries)} lotów, najtańszy {cheapest:.0f} PLN")
                
                # Stała pauza między zapytaniami, aby szanować rate limit darmowego planu RapidAPI
                time.sleep(1.2)
                    
            except Exception as e:
                logger.warning(f"Błąd skanowania {origin} -> {dest}: {e}")
                continue
        
        logger.info(f"Znaleziono łącznie {len(results)} ofert z {origin}")
        return results

    def get_cheapest_dates(self, origin: str, destination: str) -> list[dict]:
        """Puste — obsłużone w głównym wyszukiwaniu."""
        return []

    def _generate_booking_link(self, origin: str, destination: str, date: str) -> str:
        """Generuj link do Google Flights (bardziej uniwersalny)."""
        date_clean = date[:10] if len(date) > 10 else date
        return (
            f"https://www.google.com/travel/flights?"
            f"q=Flights+from+{quote(origin)}+to+{quote(destination)}+on+{quote(date_clean)}"
        )

    @property
    def request_count(self) -> int:
        """Zwróć liczbę wykonanych zapytań API."""
        return self._request_count


class TequilaKiwiClient:
    """Klient oficjalnego API Kiwi.com (Tequila) do bezpośredniego wyszukiwania lotów."""

    # Te same popularne destynacje co w RapidAPI
    POPULAR_DESTINATIONS = RapidApiKiwiClient.POPULAR_DESTINATIONS

    def __init__(self, api_key: str) -> None:
        """Inicjalizacja klienta Kiwi Tequila."""
        self.api_key = api_key
        self.base_url = "https://api.tequila.kiwi.com/v2"
        self._request_count = 0
        logger.info("Oficjalny klient Kiwi Tequila API zainicjalizowany pomyślnie")

    def _get_headers(self) -> dict:
        return {
            "apikey": self.api_key,
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json"
        }

    def _make_request_with_retry(self, endpoint: str, max_retries: int = 3, **params) -> Optional[dict]:
        """Wykonaj zapytanie API z obsługą retry i rate limiting."""
        url = f"{self.base_url}{endpoint}"
        for attempt in range(max_retries):
            try:
                self._request_count += 1
                logger.debug(f"Zapytanie Tequila #{self._request_count} (próba {attempt + 1}/{max_retries}) do {endpoint}")
                response = requests.get(url, headers=self._get_headers(), params=params, timeout=15)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    logger.warning(f"Rate limit (429) z Tequila API (próba {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                else:
                    logger.warning(f"Błąd Tequila API: status={response.status_code}, odpowiedź={response.text[:200]}")
                    if response.status_code >= 500 and attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None
            except requests.RequestException as e:
                logger.error(f"Błąd połączenia z Tequila API: {e}")
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
        """Wyszukaj loty do konkretnej destynacji."""
        # W Tequila format daty to dd/mm/yyyy (np. 04/06/2026)
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            d_from = date_from

        params = {
            'fly_from': origin,
            'fly_to': destination,
            'date_from': d_from,
            'curr': currency,
            'adults': 1,
            'limit': 20
        }

        if date_to:
            try:
                d_to = datetime.strptime(date_to, "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                d_to = date_to
            params['return_from'] = d_to
            params['return_to'] = d_to

        endpoint = "/search"
        logger.info(f"Wyszukiwanie lotów Tequila: {origin} -> {destination}, data: {d_from}")

        data = self._make_request_with_retry(endpoint, **params)
        results = []
        if not data or not isinstance(data, dict):
            return results

        flights_data = data.get('data', [])
        for item in flights_data:
            price = float(item.get('price', 0))
            if max_price and price > max_price:
                continue

            local_dep = item.get('local_departure', '')
            departure_date = local_dep[:10] if local_dep else date_from

            airlines = [r.get('airline', '') for r in item.get('route', []) if r.get('airline')]
            airline = airlines[0] if airlines else ''

            results.append({
                'destination': destination,
                'departure_date': departure_date,
                'return_date': date_to or '',
                'price': price,
                'currency': currency,
                'origin': origin,
                'airline': airline,
                'booking_link': item.get('deep_link', ''),
            })

        logger.info(f"Znaleziono {len(results)} ofert lotów Tequila na trasie {origin} -> {destination}")
        return results

    def get_inspiration(
        self,
        origin: str,
        max_price: Optional[int] = None,
        currency: str = 'PLN',
    ) -> list[dict]:
        """Skanuje tanie loty z danego lotniska do WSZYSTKICH popularnych destynacji w JEDNYM zapytaniu!"""
        # Data za 14 dni
        start_dt = datetime.now() + timedelta(days=14)
        date_from_str = start_dt.strftime("%d/%m/%Y")
        
        # Łączym destynacje po przecinku
        destinations_str = ",".join(self.POPULAR_DESTINATIONS)
        
        logger.info(
            f"Skanowanie tanich lotów Tequila z {origin} do {len(self.POPULAR_DESTINATIONS)} destynacji w JEDNYM zapytaniu!"
        )
        
        params = {
            'fly_from': origin,
            'fly_to': destinations_str,
            'date_from': date_from_str,
            'curr': currency,
            'adults': 1,
            'one_for_city': 1,
            'limit': 200
        }
        
        data = self._make_request_with_retry("/search", **params)
        results = []
        if not data or not isinstance(data, dict):
            return results
            
        flights_data = data.get('data', [])
        logger.info(f"Odebrano {len(flights_data)} wyników z Tequila API")
        
        for item in flights_data:
            dest_code = item.get('flyTo', '')
            price = float(item.get('price', 0))
            
            if not dest_code or price <= 0:
                continue
                
            if max_price and price > max_price:
                continue
                
            local_dep = item.get('local_departure', '')
            departure_date = local_dep[:10] if local_dep else ''
            
            airlines = [r.get('airline', '') for r in item.get('route', []) if r.get('airline')]
            airline = airlines[0] if airlines else ''
            
            results.append({
                'destination': dest_code,
                'departure_date': departure_date,
                'return_date': '',
                'price': price,
                'currency': currency,
                'origin': origin,
                'airline': airline,
                'booking_link': item.get('deep_link', ''),
            })
            
        if results:
            cheapest = min(results, key=lambda x: x['price'])
            logger.info(f"  Najtańszy lot z {origin}: {cheapest['destination']} za {cheapest['price']:.0f} {currency}")
            
        return results

    def get_cheapest_dates(self, origin: str, destination: str) -> list[dict]:
        """Puste — obsłużone w wyszukiwaniu."""
        return []

    @property
    def request_count(self) -> int:
        """Zwróć liczbę wykonanych zapytań API."""
        return self._request_count

