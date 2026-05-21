import json
import logging
import random
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Maksymalna liczba wpisów cenowych na trasę
PRICE_HISTORY_MAX_ENTRIES: int = 100

# Maksymalny wiek wpisu cenowego w dniach
PRICE_HISTORY_MAX_AGE_DAYS: int = 90

# Mapowanie krajów na regiony
REGION_COUNTRIES: dict[str, list[str]] = {
    'europe_short': [
        'Germany', 'Czech Republic', 'Slovakia', 'Austria', 'Hungary',
        'Lithuania', 'Latvia', 'Estonia', 'Denmark', 'Sweden', 'Netherlands',
        'Belgium', 'Luxembourg',
    ],
    'europe_long': [
        'Spain', 'Portugal', 'Italy', 'Greece', 'UK', 'Ireland', 'France',
        'Norway', 'Finland', 'Iceland', 'Turkey', 'Cyprus', 'Romania',
        'Bulgaria', 'Croatia', 'Serbia', 'Montenegro', 'Albania',
        'North Macedonia', 'Bosnia and Herzegovina', 'Slovenia',
        'Moldova', 'Ukraine', 'Belarus', 'Russia', 'Switzerland',
    ],
    'asia': [
        'Japan', 'China', 'South Korea', 'Thailand', 'Vietnam', 'Indonesia',
        'Malaysia', 'Singapore', 'Philippines', 'India', 'Sri Lanka', 'Nepal',
        'Cambodia', 'Laos', 'Myanmar', 'Bangladesh', 'Pakistan', 'Mongolia',
        'Taiwan', 'Hong Kong', 'Macau', 'Bhutan', 'Afghanistan',
        'Iran', 'Iraq', 'Israel', 'Jordan', 'Lebanon', 'Syria',
        'Saudi Arabia', 'UAE', 'Qatar', 'Bahrain', 'Kuwait', 'Oman', 'Yemen',
        'Kazakhstan', 'Uzbekistan', 'Turkmenistan', 'Kyrgyzstan', 'Tajikistan',
    ],
    'americas': [
        'USA', 'Canada', 'Mexico', 'Brazil', 'Argentina', 'Chile', 'Colombia',
        'Peru', 'Ecuador', 'Bolivia', 'Paraguay', 'Uruguay', 'Venezuela',
        'Guatemala', 'Costa Rica', 'Panama', 'Cuba', 'Jamaica',
        'Dominican Republic', 'Puerto Rico', 'Haiti', 'Honduras',
        'El Salvador', 'Nicaragua', 'Bahamas', 'Guyana', 'Suriname',
        'French Guiana', 'Trinidad and Tobago', 'Barbados',
    ],
    'africa': [
        'Egypt', 'Morocco', 'Tunisia', 'Algeria', 'Libya', 'South Africa',
        'Kenya', 'Tanzania', 'Ethiopia', 'Nigeria', 'Ghana', 'Senegal',
        'Ivory Coast', 'Cameroon', 'Angola', 'Mozambique', 'Madagascar',
        'Mauritius', 'Seychelles', 'Rwanda', 'Uganda', 'DR Congo', 'Sudan',
        'Zambia', 'Zimbabwe', 'Botswana', 'Namibia',
    ],
    'oceania': [
        'Australia', 'New Zealand', 'Fiji', 'French Polynesia',
        'New Caledonia', 'Papua New Guinea', 'Vanuatu', 'Samoa',
        'Tonga', 'Cook Islands', 'Solomon Islands',
    ],
}

# Absolutne progi cenowe na region (PLN, lot w jedną stronę)
ABSOLUTE_THRESHOLDS: dict[str, int] = {
    'europe_short': 30,
    'europe_long': 80,
    'asia': 400,
    'americas': 600,
    'africa': 350,
    'oceania': 800,
}

# Procentowy próg zniżki uznawany za "zbugowaną" cenę
BUG_THRESHOLD_PERCENT: int = 40


class PriceAnalyzer:
    """Analizator cen lotów i detektor okazji cenowych (bugów)."""

    def __init__(self, history_path: Path) -> None:
        """Inicjalizacja analizatora cen.

        Args:
            history_path: Ścieżka do pliku JSON z historią cen.
        """
        self.history_path = history_path
        self.history: dict = self._load_history()
        self._deals_found: list[dict] = []
        logger.info(f"Analizator cen zainicjalizowany, plik historii: {history_path}")

    def _load_history(self) -> dict:
        """Załaduj historię cen z pliku JSON.

        Returns:
            Słownik z historią cen lub domyślna struktura jeśli plik nie istnieje.
        """
        if self.history_path.exists():
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(
                    f"Załadowano historię cen: "
                    f"{len(data.get('routes', {}))} tras"
                )
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Błąd odczytu historii cen: {e}")
                logger.info("Tworzę nową historię cen")

        return {
            'routes': {},
            'deals': [],
            'last_scan': None,
            'total_scans': 0,
        }

    def save_history(self) -> None:
        """Zapisz historię cen do pliku JSON."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            logger.debug(f"Zapisano historię cen do {self.history_path}")
        except IOError as e:
            logger.error(f"Błąd zapisu historii cen: {e}")

    def get_region(self, country: str) -> str:
        """Określ region na podstawie kraju.

        Args:
            country: Nazwa kraju (po angielsku).

        Returns:
            Nazwa regionu lub 'unknown' jeśli kraj nie został znaleziony.
        """
        for region, countries in REGION_COUNTRIES.items():
            if country in countries:
                return region
        logger.debug(f"Nie znaleziono regionu dla kraju: {country}")
        return 'unknown'

    def add_price(self, route_key: str, price: float, date: str) -> None:
        """Dodaj cenę do historii.

        Args:
            route_key: Klucz trasy w formacie 'WAW-NRT'.
            price: Cena lotu.
            date: Data wylotu w formacie 'YYYY-MM-DD'.
        """
        now = datetime.now().isoformat()

        if route_key not in self.history['routes']:
            self.history['routes'][route_key] = {
                'prices': [],
                'country': None,
            }

        route_data = self.history['routes'][route_key]

        # Dodaj nowy wpis cenowy
        route_data['prices'].append({
            'price': price,
            'date': date,
            'recorded_at': now,
        })

        # Usuń wpisy starsze niż PRICE_HISTORY_MAX_AGE_DAYS
        cutoff = datetime.now() - timedelta(days=PRICE_HISTORY_MAX_AGE_DAYS)
        route_data['prices'] = [
            entry for entry in route_data['prices']
            if self._parse_recorded_at(entry.get('recorded_at', '')) >= cutoff
        ]

        # Ogranicz liczbę wpisów do PRICE_HISTORY_MAX_ENTRIES
        if len(route_data['prices']) > PRICE_HISTORY_MAX_ENTRIES:
            route_data['prices'] = route_data['prices'][-PRICE_HISTORY_MAX_ENTRIES:]

        logger.debug(
            f"Dodano cenę {price} PLN dla trasy {route_key} "
            f"(łącznie {len(route_data['prices'])} wpisów)"
        )

    def _parse_recorded_at(self, recorded_at: str) -> datetime:
        """Parsuj datę zapisu wpisu cenowego.

        Args:
            recorded_at: Data w formacie ISO.

        Returns:
            Obiekt datetime lub minimalna data w przypadku błędu.
        """
        try:
            return datetime.fromisoformat(recorded_at)
        except (ValueError, TypeError):
            return datetime.min

    def is_bugged_flight(
        self,
        current_price: float,
        route_key: str,
        country: str,
    ) -> tuple[bool, Optional[str], Optional[float]]:
        """Sprawdź czy lot jest 'zbugowany' (nienormalnie tani).

        Stosuje trzy metody detekcji:
        1. Próg absolutny — cena poniżej minimum dla regionu.
        2. Próg procentowy — zniżka >=40% od średniej (wymaga >=3 wpisów).
        3. Outlier statystyczny — poniżej mean - 2*std (wymaga >=5 wpisów).

        Args:
            current_price: Aktualna cena lotu.
            route_key: Klucz trasy w formacie 'WAW-NRT'.
            country: Nazwa kraju docelowego (po angielsku).

        Returns:
            Krotka (czy_zbugowany, powód, średnia_cena).
        """
        # Aktualizuj informację o kraju dla trasy
        if route_key in self.history['routes']:
            self.history['routes'][route_key]['country'] = country

        # 1. Sprawdź próg absolutny wg regionu
        region = self.get_region(country)
        threshold = ABSOLUTE_THRESHOLDS.get(region)

        if threshold is not None and current_price <= threshold:
            reason = (
                f"Cena {current_price} PLN jest poniżej progu absolutnego "
                f"dla regionu '{region}' ({threshold} PLN)"
            )
            logger.info(f"🐛 Zbugowany lot (absolutny): {route_key} — {reason}")
            avg_price = self.get_average_price(route_key)
            self._record_deal(route_key, current_price, avg_price, reason)
            return True, reason, avg_price

        # Pobierz historię cen dla trasy
        route_data = self.history.get('routes', {}).get(route_key, {})
        prices = [entry['price'] for entry in route_data.get('prices', [])]

        # 2. Sprawdź próg procentowy (wymaga >=3 wpisów)
        if len(prices) >= 3:
            avg_price = statistics.mean(prices)

            if avg_price > 0:
                discount_pct = ((avg_price - current_price) / avg_price) * 100

                if discount_pct >= BUG_THRESHOLD_PERCENT:
                    reason = (
                        f"Cena {current_price} PLN to {discount_pct:.1f}% zniżki "
                        f"od średniej {avg_price:.0f} PLN (próg: {BUG_THRESHOLD_PERCENT}%)"
                    )
                    logger.info(f"🐛 Zbugowany lot (procentowy): {route_key} — {reason}")
                    self._record_deal(route_key, current_price, avg_price, reason)
                    return True, reason, avg_price

        # 3. Sprawdź outlier statystyczny (wymaga >=5 wpisów)
        if len(prices) >= 5:
            avg_price = statistics.mean(prices)
            std_dev = statistics.stdev(prices)
            outlier_threshold = avg_price - 2 * std_dev

            if current_price < outlier_threshold and std_dev > 0:
                reason = (
                    f"Cena {current_price} PLN jest outlierem statystycznym — "
                    f"poniżej progu {outlier_threshold:.0f} PLN "
                    f"(średnia: {avg_price:.0f}, odchylenie: {std_dev:.0f})"
                )
                logger.info(f"🐛 Zbugowany lot (statystyczny): {route_key} — {reason}")
                self._record_deal(route_key, current_price, avg_price, reason)
                return True, reason, avg_price

        # Lot nie jest zbugowany
        avg_price = self.get_average_price(route_key)
        return False, None, avg_price

    def _record_deal(
        self,
        route_key: str,
        price: float,
        avg_price: Optional[float],
        reason: str,
    ) -> None:
        """Zapisz znalezioną okazję (zbugowany lot) do historii.

        Args:
            route_key: Klucz trasy.
            price: Cena okazji.
            avg_price: Średnia cena historyczna.
            reason: Powód uznania za okazję.
        """
        now = datetime.now().isoformat()
        discount_pct = 0.0
        if avg_price and avg_price > 0:
            discount_pct = ((avg_price - price) / avg_price) * 100

        deal: dict = {
            'route': route_key,
            'price': price,
            'avg_price': avg_price,
            'discount_pct': round(discount_pct, 1),
            'found_at': now,
            'reason': reason,
        }

        self.history['deals'].append(deal)
        self._deals_found.append(deal)
        logger.info(f"Zapisano okazję: {route_key} za {price} PLN ({discount_pct:.1f}% zniżki)")

    def get_average_price(self, route_key: str) -> Optional[float]:
        """Pobierz średnią cenę dla trasy.

        Args:
            route_key: Klucz trasy w formacie 'WAW-NRT'.

        Returns:
            Średnia cena lub None jeśli brak danych.
        """
        route_data = self.history.get('routes', {}).get(route_key, {})
        prices = [entry['price'] for entry in route_data.get('prices', [])]

        if not prices:
            return None

        return statistics.mean(prices)

    def get_stats(self) -> dict:
        """Statystyki bazy danych cen.

        Returns:
            Słownik ze statystykami: total_routes, total_prices, deals_found_today.
        """
        routes = self.history.get('routes', {})
        total_routes = len(routes)
        total_prices = sum(
            len(route_data.get('prices', []))
            for route_data in routes.values()
        )

        # Policz okazje znalezione dzisiaj
        today = datetime.now().date().isoformat()
        deals_found_today = sum(
            1 for deal in self.history.get('deals', [])
            if deal.get('found_at', '').startswith(today)
        )

        return {
            'total_routes': total_routes,
            'total_prices': total_prices,
            'deals_found_today': deals_found_today,
            'total_deals': len(self.history.get('deals', [])),
            'total_scans': self.history.get('total_scans', 0),
            'last_scan': self.history.get('last_scan'),
        }

    def get_random_flight(self) -> Optional[dict]:
        """Pobierz losowy lot z historii (do komendy /test).

        Returns:
            Słownik z informacjami o losowym locie lub None jeśli brak danych.
        """
        routes = self.history.get('routes', {})

        if not routes:
            logger.debug("Brak tras w historii — nie mogę wylosować lotu")
            return None

        route_key = random.choice(list(routes.keys()))
        route_data = routes[route_key]
        prices = route_data.get('prices', [])

        if not prices:
            return None

        latest_entry = prices[-1]

        return {
            'route': route_key,
            'price': latest_entry['price'],
            'date': latest_entry.get('date', ''),
            'country': route_data.get('country', 'Unknown'),
            'avg_price': self.get_average_price(route_key),
            'total_entries': len(prices),
        }

    def get_recent_deals(self, limit: int = 5) -> list[dict]:
        """Pobierz ostatnie znalezione zbugowane loty.

        Args:
            limit: Maksymalna liczba wyników (domyślnie 5).

        Returns:
            Lista ostatnich okazji posortowanych od najnowszych.
        """
        deals = self.history.get('deals', [])

        # Sortuj po dacie znalezienia (od najnowszych)
        sorted_deals = sorted(
            deals,
            key=lambda d: d.get('found_at', ''),
            reverse=True,
        )

        return sorted_deals[:limit]

    def cleanup_old_entries(self) -> int:
        """Usuń stare wpisy z historii (starsze niż 90 dni).

        Czyści zarówno wpisy cenowe jak i stare okazje.
        
        Returns:
            Liczba usuniętych wpisów cenowych.
        """
        cutoff = datetime.now() - timedelta(days=PRICE_HISTORY_MAX_AGE_DAYS)
        removed_prices = 0
        empty_routes: list[str] = []

        for route_key, route_data in self.history.get('routes', {}).items():
            original_count = len(route_data.get('prices', []))

            route_data['prices'] = [
                entry for entry in route_data.get('prices', [])
                if self._parse_recorded_at(entry.get('recorded_at', '')) >= cutoff
            ]

            removed = original_count - len(route_data['prices'])
            removed_prices += removed

            if not route_data['prices']:
                empty_routes.append(route_key)

        # Usuń puste trasy
        for route_key in empty_routes:
            del self.history['routes'][route_key]

        # Usuń stare okazje
        original_deals = len(self.history.get('deals', []))
        self.history['deals'] = [
            deal for deal in self.history.get('deals', [])
            if self._parse_recorded_at(deal.get('found_at', '')) >= cutoff
        ]
        removed_deals = original_deals - len(self.history['deals'])

        logger.info(
            f"Wyczyszczono historię: usunięto {removed_prices} wpisów cenowych, "
            f"{len(empty_routes)} pustych tras i {removed_deals} starych okazji"
        )
        
        return removed_prices

        if removed_prices > 0 or empty_routes or removed_deals:
            self.save_history()
