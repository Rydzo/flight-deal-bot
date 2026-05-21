"""
Testy jednostkowe dla modułu price_analyzer.

Testuje algorytm wykrywania zbugowanych lotów:
- Progi absolutne per region
- Zniżka procentowa (≥40%)
- Outlier statystyczny (mean - 2*std)
- Zarządzanie historią cen
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Dodaj ścieżkę projektu
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.price_analyzer import PriceAnalyzer


class TestPriceAnalyzer:
    """Testy analizatora cen."""

    def setup_method(self):
        """Przygotuj tymczasowy plik historii przed każdym testem."""
        self.temp_dir = tempfile.mkdtemp()
        self.history_path = Path(self.temp_dir) / "price_history.json"
        # Stwórz pusty plik historii
        with open(self.history_path, "w") as f:
            json.dump({}, f)
        self.analyzer = PriceAnalyzer(self.history_path)

    def teardown_method(self):
        """Wyczyść po teście."""
        if self.history_path.exists():
            os.remove(self.history_path)
        os.rmdir(self.temp_dir)

    # --- Testy progów absolutnych ---

    def test_absolute_threshold_europe_short(self):
        """Lot w Europie za 15 PLN powinien być zbugowany."""
        is_bugged, reason, avg = self.analyzer.is_bugged_flight(
            current_price=15.0, route_key="WAW-BER", country="Germany"
        )
        assert is_bugged is True
        assert "progu absolutnego" in reason

    def test_absolute_threshold_europe_long(self):
        """Lot w Europie (daleki) za 50 PLN powinien być zbugowany."""
        is_bugged, reason, avg = self.analyzer.is_bugged_flight(
            current_price=50.0, route_key="WAW-LIS", country="Portugal"
        )
        assert is_bugged is True
        assert "progu absolutnego" in reason

    def test_absolute_threshold_asia(self):
        """Lot do Azji za 300 PLN powinien być zbugowany."""
        is_bugged, reason, avg = self.analyzer.is_bugged_flight(
            current_price=300.0, route_key="WAW-NRT", country="Japan"
        )
        assert is_bugged is True
        assert "progu absolutnego" in reason

    def test_absolute_threshold_americas(self):
        """Lot do Ameryk za 500 PLN powinien być zbugowany."""
        is_bugged, reason, avg = self.analyzer.is_bugged_flight(
            current_price=500.0, route_key="WAW-JFK", country="USA"
        )
        assert is_bugged is True
        assert "progu absolutnego" in reason

    def test_absolute_threshold_oceania(self):
        """Lot do Oceanii za 600 PLN powinien być zbugowany."""
        is_bugged, reason, avg = self.analyzer.is_bugged_flight(
            current_price=600.0, route_key="WAW-SYD", country="Australia"
        )
        assert is_bugged is True
        assert "progu absolutnego" in reason

    def test_normal_price_not_bugged(self):
        """Normalny lot nie powinien być zbugowany."""
        is_bugged, reason, avg = self.analyzer.is_bugged_flight(
            current_price=2500.0, route_key="WAW-NRT", country="Japan"
        )
        assert is_bugged is False
        assert reason is None

    # --- Testy zniżki procentowej ---

    def test_discount_40_percent(self):
        """Lot z 40% zniżką powinien być zbugowany."""
        # Dodaj historyczne ceny
        for i in range(5):
            self.analyzer.add_price("WAW-BCN", 1000.0 + i * 50, f"2026-0{i+1}-15", "Spain")
        self.analyzer.save_history()

        # Średnia: ~1100 PLN, cena 600 PLN = ~45% zniżka
        is_bugged, reason, avg = self.analyzer.is_bugged_flight(
            current_price=600.0, route_key="WAW-BCN", country="Spain"
        )
        assert is_bugged is True
        assert "zniżki" in reason

    def test_discount_below_threshold(self):
        """Lot z 20% zniżką NIE powinien być zbugowany."""
        for i in range(5):
            self.analyzer.add_price("WAW-BCN", 1000.0, f"2026-0{i+1}-15", "Spain")
        self.analyzer.save_history()

        # Średnia: 1000 PLN, cena 850 PLN = 15% zniżka
        is_bugged, reason, avg = self.analyzer.is_bugged_flight(
            current_price=850.0, route_key="WAW-BCN", country="Spain"
        )
        assert is_bugged is False

    # --- Testy outlieru statystycznego ---

    def test_statistical_outlier(self):
        """Lot poniżej mean-2*std powinien być zbugowany."""
        # Ceny: 2000, 2100, 2050, 1950, 2000 → mean≈2020, std≈55
        prices = [2000, 2100, 2050, 1950, 2000]
        for i, p in enumerate(prices):
            self.analyzer.add_price("WAW-NRT", p, f"2026-0{i+1}-15", "Japan")
        self.analyzer.save_history()

        # Cena 1800 jest poniżej 2020 - 2*55 = 1910 → outlier
        is_bugged, reason, avg = self.analyzer.is_bugged_flight(
            current_price=1800.0, route_key="WAW-NRT", country="Japan"
        )
        assert is_bugged is True

    # --- Testy zarządzania historią ---

    def test_add_price(self):
        """Dodawanie cen do historii."""
        self.analyzer.add_price("WAW-BCN", 500.0, "2026-06-15", "Spain")
        self.analyzer.add_price("WAW-BCN", 550.0, "2026-07-15", "Spain")
        self.analyzer.save_history()

        avg = self.analyzer.get_average_price("WAW-BCN")
        assert avg == 525.0

    def test_get_stats(self):
        """Sprawdzenie statystyk."""
        self.analyzer.add_price("WAW-BCN", 500.0, "2026-06-15", "Spain")
        self.analyzer.add_price("WAW-NRT", 2000.0, "2026-06-15", "Japan")
        self.analyzer.save_history()

        stats = self.analyzer.get_stats()
        assert stats["total_routes"] == 2
        assert stats["total_prices"] == 2

    def test_get_region(self):
        """Sprawdzenie mapowania regionów."""
        assert self.analyzer.get_region("Germany") == "europe_short"
        assert self.analyzer.get_region("Spain") == "europe_long"
        assert self.analyzer.get_region("Japan") == "asia"
        assert self.analyzer.get_region("USA") == "americas"
        assert self.analyzer.get_region("Australia") == "oceania"
        assert self.analyzer.get_region("Egypt") == "africa"

    def test_random_flight(self):
        """Losowy lot z bazy."""
        self.analyzer.add_price("WAW-BCN", 500.0, "2026-06-15", "Spain")
        self.analyzer.save_history()

        flight = self.analyzer.get_random_flight()
        assert flight is not None
        assert "route" in flight

    def test_empty_history_random(self):
        """Losowy lot z pustej bazy powinien zwrócić None."""
        flight = self.analyzer.get_random_flight()
        assert flight is None

    def test_max_entries_per_route(self):
        """Historia nie powinna przekraczać max wpisów per trasa."""
        for i in range(40):
            self.analyzer.add_price("WAW-BCN", 500.0 + i, f"2026-01-{i+1:02d}", "Spain")
        self.analyzer.save_history()

        route_data = self.analyzer.history.get("routes", {}).get("WAW-BCN", {})
        prices = route_data.get("prices", [])
        assert len(prices) <= 30  # PRICE_HISTORY_MAX_ENTRIES


# Uruchomienie testów
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
