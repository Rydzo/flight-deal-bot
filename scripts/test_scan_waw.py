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
    load_airports,
    CURRENCY,
)
from src.api_client import RapidApiKiwiClient
from src.price_analyzer import PriceAnalyzer
from src.notifier import TelegramNotifier

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_scanner")

def run_test_scan():
    load_dotenv()
    
    api_client = RapidApiKiwiClient(api_key=os.environ["RAPIDAPI_KEY"])
    history_path = DATA_DIR / "price_history.json"
    analyzer = PriceAnalyzer(history_path)
    
    # Używamy tylko pierwszej 5 popularnych destynacji do szybkiego testu
    api_client.POPULAR_DESTINATIONS = ['LON', 'BCN', 'PAR', 'ROM', 'MIL']
    
    all_airports = load_airports()
    airports_dict = {a["code"]: a for a in all_airports}
    
    origin = 'WAW'
    logger.info(f"Running test scan from {origin} to: {api_client.POPULAR_DESTINATIONS}")
    
    flights = api_client.get_inspiration(origin=origin, currency=CURRENCY)
    logger.info(f"Fetched {len(flights)} flights from {origin}")
    
    for flight in flights:
        dest_code = flight.get("destination", "")
        price = flight.get("price", 0)
        
        airport_info = airports_dict.get(dest_code, {})
        country = airport_info.get("country", "Unknown")
        airport_name = airport_info.get("name", dest_code)
        
        route_key = f"{origin}-{dest_code}"
        
        is_bugged, reason, avg_price = analyzer.is_bugged_flight(
            current_price=price,
            route_key=route_key,
            country=country,
        )
        
        departure_date = flight.get("departure_date", "")
        analyzer.add_price(route_key, price, departure_date, country)
        
        logger.info(f"Processed: {route_key} -> {price} PLN (avg: {avg_price}, is_bugged: {is_bugged})")
        
        if is_bugged:
            logger.info(f"🔥 BUG DETECTED: {reason}")
            
    analyzer.save_history()
    logger.info("Done!")

if __name__ == "__main__":
    run_test_scan()
