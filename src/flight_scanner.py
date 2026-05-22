"""
Główny skrypt skanujący loty — uruchamiany cyklicznie przez GitHub Actions.

Przepływ:
1. Załaduj konfigurację i historię cen
2. Wybierz polskie lotnisko wylotowe (rotacja)
3. Pobierz najtańsze loty z Amadeus API (Flight Inspiration Search)
4. Porównaj ceny z historią — wykryj zbugowane loty
5. Wyślij powiadomienia na Telegram
6. Zaktualizuj historię cen
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Dodaj katalog główny projektu do ścieżki
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from src.config import (
    DATA_DIR,
    POLISH_AIRPORTS,
    get_today_origin,
    load_airports,
    get_destination_airports,
    CURRENCY,
)
from src.api_client import RapidApiKiwiClient, TequilaKiwiClient
from src.price_analyzer import PriceAnalyzer
from src.notifier import TelegramNotifier

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("flight_scanner")


def run_scan():
    """Główna funkcja skanowania lotów."""
    load_dotenv()

    logger.info("=" * 60)
    logger.info("🛫 START SKANOWANIA LOTÓW")
    logger.info("=" * 60)

    # --- Walidacja zmiennych środowiskowych ---
    tequila_key = os.environ.get("TEQUILA_API_KEY")
    rapid_key = os.environ.get("RAPIDAPI_KEY")
    
    if not tequila_key and not rapid_key:
        logger.error("❌ Brak klucza API! Ustaw TEQUILA_API_KEY lub RAPIDAPI_KEY w pliku .env lub GitHub Secrets.")
        sys.exit(1)
        
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        logger.error(f"❌ Brak zmiennych środowiskowych: {', '.join(missing)}")
        logger.error("Ustaw je w pliku .env lub GitHub Secrets.")
        sys.exit(1)

    # --- Inicjalizacja komponentów ---
    if tequila_key:
        api_client = TequilaKiwiClient(api_key=tequila_key)
    else:
        api_client = RapidApiKiwiClient(api_key=rapid_key)

    history_path = DATA_DIR / "price_history.json"
    analyzer = PriceAnalyzer(history_path)

    notifier = TelegramNotifier(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
    )

    # --- Załaduj listę lotnisk ---
    all_airports = load_airports()
    airports_dict = {a["code"]: a for a in all_airports}
    destination_codes = {a["code"] for a in get_destination_airports()}

    # --- Wybierz dzisiejsze lotniska wylotowe (rotacja, wszystkie lub cały kraj) ---
    scan_poland = os.environ.get("SCAN_POLAND_DIRECT", "true").lower() == "true"
    force_all = os.environ.get("FORCE_ALL_AIRPORTS", "false").lower() == "true"
    
    if scan_poland:
        # Endpoint /deals/cheap-from-country/poland sam obsługuje cały kraj.
        # 'PL' to tylko etykieta — api_client nie używa tego jako parametru.
        today_origins = ["PL"]
        logger.info("📍 Tryb SCAN_POLAND_DIRECT — endpoint country deals skanuje CAŁĄ Polskę automatycznie!")
    elif force_all:
        today_origins = list(POLISH_AIRPORTS)
        logger.info(f"📍 Tryb FORCE_ALL — skanowanie ze WSZYSTKICH lotnisk: {', '.join(today_origins)}")
    else:
        today_origins = [get_today_origin()]
        logger.info(f"📍 Dzisiejsze lotnisko wylotowe (rotacja): {', '.join(today_origins)}")

    # --- Liczniki ---
    total_flights_checked = 0
    bugged_flights_found = []

    # --- Skanowanie lotów ---
    for origin in today_origins:
        logger.info(f"\n{'─' * 40}")
        logger.info(f"🔍 Skanowanie z lotniska: {origin}")

        try:
            # Użyj Flight Inspiration Search — jedno zapytanie, wiele destynacji
            flights = api_client.get_inspiration(origin=origin, currency=CURRENCY)

            if not flights:
                logger.warning(f"⚠️ Brak wyników dla {origin}")
                continue

            logger.info(f"📊 Znaleziono {len(flights)} destynacji z {origin}")

            for flight in flights:
                dest_code = flight.get("destination", "")

                price = flight.get("price", 0)
                if not price or price <= 0:
                    continue

                total_flights_checked += 1

                # Rzeczywiste lotnisko wylotowe (np. WAW) — wyciągnięte
                # z danych lotu przez api_client, nawet gdy origin to lista
                actual_origin = flight.get("origin", origin)

                # Pobierz informacje o lotnisku docelowym (soft lookup)
                airport_info = airports_dict.get(dest_code, {})
                country = airport_info.get("country", "Unknown")
                airport_name = airport_info.get("name", dest_code)

                route_key = f"{actual_origin}-{dest_code}"

                # Sprawdź czy lot jest zbugowany
                is_bugged, reason, avg_price = analyzer.is_bugged_flight(
                    current_price=price,
                    route_key=route_key,
                    country=country,
                )

                # Dodaj cenę do historii (niezależnie czy zbugowany)
                departure_date = flight.get("departure_date", "")
                analyzer.add_price(route_key, price, departure_date, country)

                if is_bugged:
                    discount_pct = 0
                    if avg_price and avg_price > 0:
                        discount_pct = round(
                            (avg_price - price) / avg_price * 100, 1
                        )

                    deal = {
                        "route": route_key,
                        "origin": actual_origin,
                        "destination": dest_code,
                        "destination_name": airport_name,
                        "country": country,
                        "price": price,
                        "avg_price": avg_price or price,
                        "discount_pct": discount_pct,
                        "departure_date": departure_date,
                        "return_date": flight.get("return_date", ""),
                        "booking_link": flight.get("booking_link", ""),
                        "found_at": datetime.now().isoformat(),
                        "reason": reason,
                    }

                    bugged_flights_found.append(deal)
                    analyzer.add_deal(deal)

                    logger.info(
                        f"🔥 ZBUGOWANY LOT! {route_key} — "
                        f"{price} PLN (avg: {avg_price:.0f} PLN, "
                        f"-{discount_pct}%) — {reason}"
                    )

        except Exception as e:
            logger.error(f"❌ Błąd podczas skanowania z {origin}: {e}", exc_info=True)
            continue

    # --- Wyślij powiadomienia ---
    if bugged_flights_found:
        logger.info(f"\n{'=' * 40}")
        logger.info(
            f"🔥 Znaleziono {len(bugged_flights_found)} zbugowanych lotów!"
        )

        if len(bugged_flights_found) <= 3:
            # Wysyłaj pojedyncze powiadomienia
            for deal in bugged_flights_found:
                notifier.send_deal_alert(deal)
        else:
            # Wysyłaj grupowo
            notifier.send_batch_deals(bugged_flights_found)
    else:
        logger.info("\n✅ Brak zbugowanych lotów w tym skanie.")

    # --- Zapisz historię cen ---
    analyzer.save_history()
    logger.info(f"💾 Historia cen zapisana.")

    # --- Wyczyść stare wpisy ---
    cleaned = analyzer.cleanup_old_entries()
    if cleaned > 0:
        analyzer.save_history()
        logger.info(f"🧹 Wyczyszczono {cleaned} starych wpisów.")

    # --- Podsumowanie ---
    logger.info(f"\n{'=' * 60}")
    logger.info(f"📊 PODSUMOWANIE SKANU:")
    logger.info(f"   Lotniska wylotowe: {', '.join(today_origins)}")
    logger.info(f"   Sprawdzonych lotów: {total_flights_checked}")
    logger.info(f"   Zbugowanych lotów: {len(bugged_flights_found)}")
    logger.info(f"   Zapytań API: {api_client.request_count}")

    stats = analyzer.get_stats()
    logger.info(f"   Tras w bazie: {stats['total_routes']}")
    logger.info(f"   Łącznych wpisów cenowych: {stats['total_prices']}")
    logger.info(f"{'=' * 60}")
    logger.info("✅ SKANOWANIE ZAKOŃCZONE\n")


def main():
    """Punkt wejścia."""
    try:
        run_scan()
    except KeyboardInterrupt:
        logger.info("⏹️ Przerwano przez użytkownika.")
    except Exception as e:
        logger.error(f"❌ Krytyczny błąd: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
