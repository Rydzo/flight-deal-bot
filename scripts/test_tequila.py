import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from src.api_client import TequilaKiwiClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_tequila")

def run_test():
    api_key = os.environ.get("TEQUILA_API_KEY", "")
    if not api_key:
        logger.error("❌ Brak TEQUILA_API_KEY w pliku .env!")
        logger.info("Zarejestruj się za darmo na https://tequila.kiwi.com/, pobierz klucz i dodaj TEQUILA_API_KEY=twój_klucz do pliku .env.")
        return
        
    client = TequilaKiwiClient(api_key=api_key)
    
    # 1. Test search_flights
    logger.info("--- TEST 1: Wyszukiwanie konkretnej trasy (WAW -> BCN) ---")
    try:
        flights = client.search_flights(origin="WAW", destination="BCN", date_from="2026-06-04", limit=2)
        logger.info(f"Pomyślnie odebrano {len(flights)} ofert!")
        for f in flights[:2]:
            logger.info(f"  Lot: {f['origin']} -> {f['destination']} za {f['price']} {f['currency']} ({f['airline']}) - link: {f['booking_link'][:50]}...")
    except Exception as e:
        logger.error(f"Błąd wyszukiwania trasy: {e}", exc_info=True)

    # 2. Test get_inspiration (Optymalizacja comma-separated)
    logger.info("\n--- TEST 2: Skanowanie tanich destynacji (Inspiration - Comma-separated) ---")
    try:
        # Ograniczamy na potrzeby testu do 5 destynacji
        client.POPULAR_DESTINATIONS = ['LON', 'BCN', 'PAR', 'ROM', 'MIL']
        results = client.get_inspiration(origin="WAW")
        logger.info(f"Pomyślnie odebrano {len(results)} ofert dla różnych destynacji w JEDNYM zapytaniu! 🎉")
        for f in results[:5]:
            logger.info(f"  Oferta: {f['origin']} -> {f['destination']} za {f['price']} {f['currency']} ({f['airline']})")
    except Exception as e:
        logger.error(f"Błąd skanowania zbiorczego: {e}", exc_info=True)

if __name__ == "__main__":
    run_test()
