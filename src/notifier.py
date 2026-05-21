"""Moduł wysyłania powiadomień na Telegram o zbugowanych lotach."""

import logging
from datetime import datetime
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Wysyłanie powiadomień o zbugowanych lotach na Telegram."""

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(self, bot_token: str, chat_id: str) -> None:
        """Inicjalizacja notyfikatora Telegram.

        Args:
            bot_token: Token bota Telegram.
            chat_id: ID czatu, na który wysyłane są wiadomości.
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = self.BASE_URL.format(token=bot_token)

    # ------------------------------------------------------------------
    # Metoda bazowa – wysyłanie wiadomości
    # ------------------------------------------------------------------

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Wyślij wiadomość na Telegram.

        Args:
            text: Treść wiadomości (obsługuje HTML).
            parse_mode: Tryb parsowania – domyślnie HTML.

        Returns:
            True jeśli wiadomość została wysłana, False w przeciwnym razie.
        """
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                logger.error(f"Telegram API zwróciło błąd: {data.get('description', 'brak opisu')}")
                return False

            logger.info("Wiadomość wysłana pomyślnie na Telegram.")
            return True

        except requests.exceptions.Timeout:
            logger.error("Timeout podczas wysyłania wiadomości na Telegram.")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Błąd połączenia z Telegram API.")
            return False
        except requests.exceptions.HTTPError as exc:
            logger.error(f"Błąd HTTP od Telegram API: {exc}")
            return False
        except Exception as exc:
            logger.error(f"Nieoczekiwany błąd podczas wysyłania wiadomości: {exc}")
            return False

    # ------------------------------------------------------------------
    # Powiadomienie o zbugowanym locie
    # ------------------------------------------------------------------

    def send_deal_alert(self, deal: dict) -> bool:
        """Wyślij powiadomienie o zbugowanym locie.

        Args:
            deal: Słownik z kluczami: route, origin, destination,
                  destination_name, country, price, avg_price,
                  discount_pct, departure_date, booking_link,
                  found_at, reason.

        Returns:
            True jeśli wysłano pomyślnie.
        """
        price_fmt = f"{deal.get('price', 0):,.0f}".replace(",", " ")
        avg_fmt = f"{deal.get('avg_price', 0):,.0f}".replace(",", " ")
        discount = deal.get("discount_pct", 0)

        # Formatowanie daty wylotu
        departure_raw = deal.get("departure_date", "")
        try:
            dep_date = datetime.strptime(departure_raw, "%Y-%m-%d").strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            dep_date = str(departure_raw)

        # Formatowanie daty wykrycia
        found_raw = deal.get("found_at", "")
        try:
            found_dt = datetime.fromisoformat(found_raw).strftime("%d.%m.%Y %H:%M")
        except (ValueError, TypeError):
            found_dt = str(found_raw)

        dest_label = deal.get("destination_name", deal.get("destination", ""))
        country = deal.get("country", "")
        if country:
            dest_label = f"{dest_label}, {country}"

        booking_link = deal.get("booking_link", "")
        link_html = f'<a href="{booking_link}">Rezerwuj lot!</a>' if booking_link else "brak linku"

        text = (
            f"🔥 <b>ZBUGOWANY LOT!</b> 🔥\n"
            f"\n"
            f"🛫 {deal.get('origin', '???')} ✈️ {deal.get('destination', '???')} ({dest_label})\n"
            f"📅 Data wylotu: <b>{dep_date}</b>\n"
            f"💰 Średnia cena: {avg_fmt} PLN\n"
            f"🔥 Aktualna cena: <b>{price_fmt} PLN</b>\n"
            f"📉 Zniżka: <b>-{abs(discount)}%</b>!\n"
            f"🔗 {link_html}\n"
            f"\n"
            f"⏰ Wykryto: {found_dt}\n"
            f"🤖 Powód: <code>{deal.get('reason', 'UNKNOWN')}</code>"
        )

        logger.info(f"Wysyłam alert o zbugowanym locie: {deal.get('route', '?')}")
        return self.send_message(text)

    # ------------------------------------------------------------------
    # Grupowe powiadomienie o zbugowanych lotach
    # ------------------------------------------------------------------

    def send_batch_deals(self, deals: list) -> bool:
        """Wyślij grupę zbugowanych lotów w jednej wiadomości.

        Aby nie przekroczyć limitu długości wiadomości Telegram,
        wysyłane jest maksymalnie 5 ofert na wiadomość.

        Args:
            deals: Lista słowników z danymi o zbugowanych lotach.

        Returns:
            True jeśli wszystkie wiadomości zostały wysłane pomyślnie.
        """
        if not deals:
            logger.warning("Brak zbugowanych lotów do wysłania.")
            return True

        BATCH_SIZE = 5
        all_ok = True

        for batch_start in range(0, len(deals), BATCH_SIZE):
            batch = deals[batch_start : batch_start + BATCH_SIZE]
            parts: list[str] = []

            for idx, deal in enumerate(batch, start=batch_start + 1):
                price_fmt = f"{deal.get('price', 0):,.0f}".replace(",", " ")
                avg_fmt = f"{deal.get('avg_price', 0):,.0f}".replace(",", " ")
                discount = deal.get("discount_pct", 0)

                departure_raw = deal.get("departure_date", "")
                try:
                    dep_date = datetime.strptime(departure_raw, "%Y-%m-%d").strftime("%d.%m.%Y")
                except (ValueError, TypeError):
                    dep_date = str(departure_raw)

                dest_label = deal.get("destination_name", deal.get("destination", ""))
                country = deal.get("country", "")
                if country:
                    dest_label = f"{dest_label}, {country}"

                booking_link = deal.get("booking_link", "")
                link_html = f'<a href="{booking_link}">Rezerwuj</a>' if booking_link else ""

                part = (
                    f"<b>{idx}.</b> 🛫 {deal.get('origin', '???')} ✈️ {deal.get('destination', '???')} "
                    f"({dest_label})\n"
                    f"   📅 {dep_date}  💰 <b>{price_fmt} PLN</b> (avg {avg_fmt}) "
                    f"📉 -{abs(discount)}%  {link_html}"
                )
                parts.append(part)

            header = f"🔥 <b>ZBUGOWANE LOTY ({batch_start + 1}–{batch_start + len(batch)} z {len(deals)})</b> 🔥\n\n"
            text = header + "\n\n".join(parts)

            logger.info(f"Wysyłam grupę zbugowanych lotów: {batch_start + 1}–{batch_start + len(batch)}")
            if not self.send_message(text):
                all_ok = False

        return all_ok

    # ------------------------------------------------------------------
    # Testowy lot (komenda /test)
    # ------------------------------------------------------------------

    def send_test_flight(self, flight: dict) -> bool:
        """Wyślij testowy lot (komenda /test).

        Args:
            flight: Słownik z kluczami: route, prices (lista),
                    country, last_price, avg_price.

        Returns:
            True jeśli wysłano pomyślnie.
        """
        route = flight.get("route", "???-???")
        parts = route.split("-")
        origin = parts[0] if len(parts) >= 2 else "???"
        destination = parts[1] if len(parts) >= 2 else "???"

        last_price = flight.get("last_price", 0)
        avg_price = flight.get("avg_price", 0)
        country = flight.get("country", "")
        prices = flight.get("prices", [])

        price_fmt = f"{last_price:,.0f}".replace(",", " ")
        avg_fmt = f"{avg_price:,.0f}".replace(",", " ")

        now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

        # Link do Google Flights jako fallback
        search_link = (
            f"https://www.google.com/travel/flights?q=flights+from+{origin}+to+{destination}"
        )

        num_prices = len(prices)

        text = (
            f"🧪 <b>TEST</b> — Losowy lot z bazy:\n"
            f"\n"
            f"🛫 {origin} ✈️ {destination}"
        )
        if country:
            text += f" ({country})"
        text += (
            f"\n"
            f"📅 Sprawdzono: {now_str}\n"
            f"💰 Cena: <b>{price_fmt} PLN</b>\n"
            f"📊 Średnia: {avg_fmt} PLN (z {num_prices} pomiarów)\n"
            f'🔗 <a href="{search_link}">Szukaj lotu</a>'
        )

        logger.info(f"Wysyłam testowy lot: {route}")
        return self.send_message(text)

    # ------------------------------------------------------------------
    # Wyniki wyszukiwania (komenda /search)
    # ------------------------------------------------------------------

    def send_search_results(self, results: list, destination: str) -> bool:
        """Wyślij wyniki wyszukiwania (komenda /search).

        Args:
            results: Lista słowników z wynikami wyszukiwania.
                     Każdy element zawiera: origin, destination, price, airline,
                     departure_date, booking_link.
            destination: Kod IATA destynacji.

        Returns:
            True jeśli wysłano pomyślnie.
        """
        if not results:
            text = (
                f"🔍 <b>Wyniki wyszukiwania: {destination}</b>\n"
                f"\n"
                f"😔 Nie znaleziono lotów do <b>{destination}</b>.\n"
                f"Spróbuj inny kod IATA lub sprawdź później."
            )
            logger.info(f"Brak wyników wyszukiwania dla {destination}")
            return self.send_message(text)

        parts: list[str] = []
        for idx, result in enumerate(results[:10], start=1):
            price_fmt = f"{result.get('price', 0):,.0f}".replace(",", " ")

            departure_raw = result.get("departure_date", "")
            try:
                dep_date = datetime.strptime(departure_raw, "%Y-%m-%d").strftime("%d.%m.%Y")
            except (ValueError, TypeError):
                dep_date = str(departure_raw)

            airline = result.get("airline", "")
            booking_link = result.get("booking_link", "")
            link_html = f' <a href="{booking_link}">Rezerwuj</a>' if booking_link else ""

            part = (
                f"<b>{idx}.</b> 🛫 {result.get('origin', '???')} ✈️ {result.get('destination', destination)}\n"
                f"   📅 {dep_date}  💰 <b>{price_fmt} PLN</b>"
            )
            if airline:
                part += f"  ✈️ {airline}"
            part += link_html

            parts.append(part)

        header = (
            f"🔍 <b>Wyniki wyszukiwania: {destination}</b>\n"
            f"Znaleziono <b>{len(results)}</b> lotów (pokazuję maks. 10):\n\n"
        )
        text = header + "\n\n".join(parts)

        logger.info(f"Wysyłam {len(results)} wyników wyszukiwania dla {destination}")
        return self.send_message(text)

    # ------------------------------------------------------------------
    # Statystyki (komenda /stats)
    # ------------------------------------------------------------------

    def send_stats(self, stats: dict) -> bool:
        """Wyślij statystyki (komenda /stats).

        Args:
            stats: Słownik z kluczami: total_routes, total_prices,
                   deals_found_total, last_scan.

        Returns:
            True jeśli wysłano pomyślnie.
        """
        last_scan_raw = stats.get("last_scan", "")
        try:
            last_scan = datetime.fromisoformat(last_scan_raw).strftime("%d.%m.%Y %H:%M")
        except (ValueError, TypeError):
            last_scan = str(last_scan_raw) if last_scan_raw else "brak danych"

        text = (
            f"📊 <b>Statystyki bazy lotów</b>\n"
            f"\n"
            f"🗺️ Monitorowane trasy: <b>{stats.get('total_routes', 0)}</b>\n"
            f"💾 Zapisanych cen: <b>{stats.get('total_prices', 0)}</b>\n"
            f"🔥 Wykrytych zbugowanych lotów: <b>{stats.get('deals_found_total', 0)}</b>\n"
            f"⏰ Ostatni skan: <b>{last_scan}</b>\n"
            f"\n"
            f"🤖 Bot działa i monitoruje ceny 24/7!"
        )

        logger.info("Wysyłam statystyki bazy lotów.")
        return self.send_message(text)

    # ------------------------------------------------------------------
    # Powitanie (komenda /start)
    # ------------------------------------------------------------------

    def send_welcome(self) -> bool:
        """Wyślij powitanie (komenda /start).

        Returns:
            True jeśli wysłano pomyślnie.
        """
        text = (
            f"👋 <b>Cześć! Jestem botem zbugowanych lotów!</b>\n"
            f"\n"
            f"Monitoruję ceny lotów i powiadomię Cię, gdy znajdę "
            f"nienormalnie tanią ofertę ✈️🔥\n"
            f"\n"
            f"<b>Dostępne komendy:</b>\n"
            f"/help — lista komend\n"
            f"/test — losowy lot z bazy (test połączenia)\n"
            f"/search <code>IATA</code> — szukaj lotów do destynacji\n"
            f"/deals — ostatnie zbugowane loty\n"
            f"/stats — statystyki bazy\n"
            f"\n"
            f"🤖 Zbugowane loty wysyłam automatycznie — nie musisz nic robić!"
        )

        logger.info("Wysyłam wiadomość powitalną.")
        return self.send_message(text)

    # ------------------------------------------------------------------
    # Pomoc (komenda /help)
    # ------------------------------------------------------------------

    def send_help(self) -> bool:
        """Wyślij pomoc (komenda /help).

        Returns:
            True jeśli wysłano pomyślnie.
        """
        text = (
            f"📖 <b>Lista komend:</b>\n"
            f"\n"
            f"🟢 /start — powitanie i opis bota\n"
            f"🟢 /help — ta wiadomość\n"
            f"🧪 /test lub <code>test</code> — losowy lot z bazy\n"
            f"🔍 /search <code>IATA</code> — szukaj lotów, np. <code>/search NRT</code>\n"
            f"🔥 /deals — ostatnie wykryte zbugowane loty\n"
            f"📊 /stats — statystyki monitorowania\n"
            f"\n"
            f"<i>Kody IATA to 3-literowe kody lotnisk, np. NRT (Tokio), "
            f"BCN (Barcelona), JFK (Nowy Jork).</i>"
        )

        logger.info("Wysyłam wiadomość pomocy.")
        return self.send_message(text)
