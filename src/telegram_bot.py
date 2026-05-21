"""Moduł bota Telegram obsługującego komendy użytkownika."""

import json
import logging
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from src.config import load_airports, DATA_DIR
from src.price_analyzer import PriceAnalyzer
from src.notifier import TelegramNotifier
from src.api_client import RapidApiKiwiClient

logger = logging.getLogger(__name__)


class TelegramBot:
    """Bot Telegram obsługujący komendy użytkownika.

    Bot nasłuchuje wiadomości za pomocą metody getUpdates (polling)
    i reaguje na komendy: /start, /help, test, /search, /deals, /stats.
    """

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(self) -> None:
        """Inicjalizacja bota — wczytanie konfiguracji i zależności."""
        self.token: str = os.environ["TELEGRAM_BOT_TOKEN"]
        self.chat_id: str = os.environ["TELEGRAM_CHAT_ID"]
        self.base_url: str = self.BASE_URL.format(token=self.token)

        self.notifier = TelegramNotifier(self.token, self.chat_id)
        self.analyzer = PriceAnalyzer(DATA_DIR / "price_history.json")

        self.airports: dict[str, dict] = {a["code"]: a for a in load_airports()}

        self.api_client = RapidApiKiwiClient(
            os.environ.get("RAPIDAPI_KEY", "")
        )

        self.last_update_file: Path = DATA_DIR / "last_update_id.txt"

        # Ścieżka do pliku z historią cen
        self.price_history_file: Path = DATA_DIR / "price_history.json"

        # Ścieżka do pliku z ostatnimi zbugowanymi lotami
        self.deals_file: Path = DATA_DIR / "deals_history.json"

    # ------------------------------------------------------------------
    # Zarządzanie offsetem wiadomości
    # ------------------------------------------------------------------

    def get_last_update_id(self) -> int:
        """Pobierz ID ostatniej przetworzonej wiadomości.

        Returns:
            Numer ostatniego przetworzonego update_id lub 0.
        """
        try:
            if self.last_update_file.exists():
                content = self.last_update_file.read_text(encoding="utf-8").strip()
                if content:
                    return int(content)
        except (ValueError, OSError) as exc:
            logger.warning(f"Nie udało się odczytać last_update_id: {exc}")
        return 0

    def save_last_update_id(self, update_id: int) -> None:
        """Zapisz ID ostatniej przetworzonej wiadomości.

        Args:
            update_id: Numer update_id do zapisania.
        """
        try:
            self.last_update_file.parent.mkdir(parents=True, exist_ok=True)
            self.last_update_file.write_text(str(update_id), encoding="utf-8")
            logger.debug(f"Zapisano last_update_id: {update_id}")
        except OSError as exc:
            logger.error(f"Nie udało się zapisać last_update_id: {exc}")

    # ------------------------------------------------------------------
    # Pobieranie wiadomości z Telegram API
    # ------------------------------------------------------------------

    def get_updates(self, offset: Optional[int] = None) -> list:
        """Pobierz nowe wiadomości z Telegram API.

        Args:
            offset: ID od którego pobierać wiadomości (exclusive).

        Returns:
            Lista obiektów Update z Telegram API.
        """
        url = f"{self.base_url}/getUpdates"
        params: dict = {"timeout": 5}
        if offset is not None:
            params["offset"] = offset

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                logger.error(f"Telegram getUpdates błąd: {data.get('description', 'brak opisu')}")
                return []

            updates = data.get("result", [])
            logger.debug(f"Pobrano {len(updates)} nowych wiadomości.")
            return updates

        except requests.exceptions.Timeout:
            logger.warning("Timeout podczas pobierania wiadomości z Telegram.")
            return []
        except requests.exceptions.ConnectionError:
            logger.error("Błąd połączenia z Telegram API (getUpdates).")
            return []
        except requests.exceptions.HTTPError as exc:
            logger.error(f"Błąd HTTP od Telegram API: {exc}")
            return []
        except Exception as exc:
            logger.error(f"Nieoczekiwany błąd podczas getUpdates: {exc}")
            return []

    # ------------------------------------------------------------------
    # Przetwarzanie wiadomości
    # ------------------------------------------------------------------

    def process_message(self, message: dict) -> None:
        """Przetwórz wiadomość i wykonaj komendę.

        Obsługiwane komendy: /start, /help, test, /test, /search <IATA>,
        /deals, /stats.

        Args:
            message: Obiekt Message z Telegram API.
        """
        # Weryfikacja bezpieczeństwa — odpowiadamy tylko na wiadomości z naszego czatu
        chat = message.get("chat", {})
        chat_id_str = str(chat.get("id", ""))

        if chat_id_str != str(self.chat_id):
            logger.warning(
                f"Odrzucono wiadomość z nieautoryzowanego czatu: {chat_id_str}"
            )
            return

        text = message.get("text", "").strip()
        if not text:
            return

        logger.info(f"Otrzymano komendę: '{text}' od chat_id={chat_id_str}")

        # Normalizacja — małe litery do porównań
        text_lower = text.lower()

        if text_lower == "/start":
            self.notifier.send_welcome()

        elif text_lower == "/help":
            self.notifier.send_help()

        elif text_lower in ("test", "/test"):
            self.handle_test()

        elif text_lower.startswith("/search"):
            # Wyciągnij kod IATA z komendy
            parts = text.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                self.notifier.send_message(
                    "⚠️ Podaj kod IATA lotniska, np.:\n<code>/search NRT</code>"
                )
                return
            destination = parts[1].strip().upper()
            if len(destination) != 3 or not destination.isalpha():
                self.notifier.send_message(
                    f"⚠️ <b>{destination}</b> nie wygląda jak prawidłowy kod IATA.\n"
                    f"Kod IATA to 3 litery, np. <code>NRT</code>, <code>BCN</code>."
                )
                return
            self.handle_search(destination)

        elif text_lower == "/deals":
            self.handle_deals()

        elif text_lower == "/stats":
            self.handle_stats()

        else:
            logger.debug(f"Nieznana komenda: '{text}'")
            self.notifier.send_message(
                f"🤔 Nie rozumiem komendy: <code>{text}</code>\n"
                f"Wpisz /help aby zobaczyć dostępne komendy."
            )

    # ------------------------------------------------------------------
    # Obsługa komend
    # ------------------------------------------------------------------

    def handle_test(self) -> None:
        """Komenda test — wyślij losowy lot z bazy danych cen."""
        logger.info("Obsługa komendy: test")

        try:
            flight = self.analyzer.get_random_flight()
            if not flight:
                self.notifier.send_message(
                    "😔 Baza danych cen jest pusta.\nUruchom najpierw skanowanie lotów."
                )
                return

            route_data = self.analyzer.history.get("routes", {}).get(flight["route"], {})
            prices = [p.get("price") for p in route_data.get("prices", [])]

            flight_data = {
                "route": flight["route"],
                "prices": prices,
                "country": flight["country"],
                "last_price": flight["price"],
                "avg_price": flight["avg_price"],
            }

            self.notifier.send_test_flight(flight_data)

        except Exception as exc:
            logger.error(f"Błąd podczas obsługi komendy test: {exc}")
            self.notifier.send_message("❌ Wystąpił błąd podczas pobierania losowego lotu.")

    def handle_search(self, destination: str) -> None:
        """Komenda /search — szukaj lotów do destynacji.

        Przeszukuje loty z polskich lotnisk do podanej destynacji
        za pomocą Amadeus API.

        Args:
            destination: Kod IATA lotniska docelowego (np. NRT).
        """
        logger.info(f"Obsługa komendy: /search {destination}")

        # Polskie lotniska startowe
        polish_airports = ["WAW", "KRK", "GDN", "KTW", "WRO", "POZ", "RZE"]

        self.notifier.send_message(
            f"🔍 Szukam lotów do <b>{destination}</b>...\nTo może chwilę potrwać ⏳"
        )

        results: list[dict] = []

        for origin in polish_airports:
            try:
                flights = self.api_client.search_flights(origin, destination)
                if flights:
                    for flight in flights:
                        flight["origin"] = origin
                        results.append(flight)
            except Exception as exc:
                logger.warning(f"Błąd wyszukiwania {origin}-{destination}: {exc}")
                continue

        # Sortowanie po cenie
        results.sort(key=lambda x: x.get("price", float("inf")))

        self.notifier.send_search_results(results, destination)

    def handle_deals(self) -> None:
        """Komenda /deals — pokaż ostatnie zbugowane loty."""
        logger.info("Obsługa komendy: /deals")

        try:
            # Pobieramy ostatnie 10 okazji bezpośrednio z analizatora cen
            recent_deals = self.analyzer.get_recent_deals(limit=10)

            if not recent_deals:
                self.notifier.send_message(
                    "📭 Nie wykryto jeszcze żadnych zbugowanych lotów.\n"
                    "Bot monitoruje ceny — poczekaj na kolejny skan!"
                )
                return

            if len(recent_deals) == 1:
                self.notifier.send_deal_alert(recent_deals[0])
            else:
                self.notifier.send_batch_deals(recent_deals)

        except Exception as exc:
            logger.error(f"Błąd podczas obsługi komendy /deals: {exc}")
            self.notifier.send_message("❌ Wystąpił błąd podczas pobierania zbugowanych lotów.")

    def handle_stats(self) -> None:
        """Komenda /stats — wyświetl statystyki bazy danych."""
        logger.info("Obsługa komendy: /stats")

        try:
            stats = self.analyzer.get_stats()
            # Dopasowanie klucza do Notifiera
            stats["deals_found_total"] = stats.get("total_deals", 0)
            self.notifier.send_stats(stats)
        except Exception as exc:
            logger.error(f"Błąd podczas obsługi komendy /stats: {exc}")
            self.notifier.send_message("❌ Wystąpił błąd podczas generowania statystyk.")

    # ------------------------------------------------------------------
    # Główna pętla bota
    # ------------------------------------------------------------------

    def run(self, loop: bool = False) -> None:
        """Uruchom bot — sprawdź nowe wiadomości i odpowiedz.

        Pobiera ostatni update_id, sprawdza nowe wiadomości,
        przetwarza każdą z nich i zapisuje nowy update_id.
        """
        import time
        logger.info(f"Uruchamiam bota Telegram (loop={loop})...")

        if loop:
            logger.info("Bot działa w pętli ciągłej (real-time). Wciśnij Ctrl+C, aby zatrzymać.")
            last_id = self.get_last_update_id()
            offset = last_id + 1 if last_id > 0 else None
            
            while True:
                try:
                    updates = self.get_updates(offset=offset)
                    if updates:
                        logger.info(f"Otrzymano {len(updates)} nowych wiadomości do przetworzenia.")
                        for update in updates:
                            update_id = update.get("update_id", 0)
                            message = update.get("message")

                            if message:
                                try:
                                    self.process_message(message)
                                except Exception as exc:
                                    logger.error(f"Błąd przetwarzania wiadomości (update_id={update_id}): {exc}")

                            last_id = max(last_id, update_id)
                            offset = last_id + 1

                        self.save_last_update_id(last_id)
                    
                    time.sleep(2)  # Odpytuj co 2 sekundy w pętli
                except KeyboardInterrupt:
                    logger.info("Zatrzymano bota przez użytkownika.")
                    break
                except Exception as exc:
                    logger.error(f"Błąd w pętli głównej bota: {exc}")
                    time.sleep(5)  # Odczekaj dłużej w przypadku błędu
        else:
            last_id = self.get_last_update_id()
            offset = last_id + 1 if last_id > 0 else None

            logger.info(f"Pobieram wiadomości od offset={offset}")

            updates = self.get_updates(offset=offset)

            if not updates:
                logger.info("Brak nowych wiadomości.")
                return

            logger.info(f"Otrzymano {len(updates)} nowych wiadomości do przetworzenia.")

            for update in updates:
                update_id = update.get("update_id", 0)
                message = update.get("message")

                if message:
                    try:
                        self.process_message(message)
                    except Exception as exc:
                        logger.error(f"Błąd przetwarzania wiadomości (update_id={update_id}): {exc}")

                last_id = max(last_id, update_id)

            self.save_last_update_id(last_id)
            logger.info(f"Przetworzono {len(updates)} wiadomości. Ostatni update_id: {last_id}")


def main() -> None:
    """Punkt wejścia dla telegram bota."""
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    from dotenv import load_dotenv
    load_dotenv()

    # Sprawdź czy pętla jest włączona przez argument lub zmienną środowiskową
    loop = "--loop" in sys.argv or os.environ.get("TELEGRAM_LOOP", "").lower() == "true"

    bot = TelegramBot()
    bot.run(loop=loop)


if __name__ == "__main__":
    main()
