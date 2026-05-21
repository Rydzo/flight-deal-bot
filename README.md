# ✈️ Flight Deal Bot — Wykrywacz Zbugowanych Lotów

[![Scan Flights](https://github.com/YOUR_USERNAME/flight-deal-bot/actions/workflows/scan_flights.yml/badge.svg)](https://github.com/YOUR_USERNAME/flight-deal-bot/actions/workflows/scan_flights.yml)
[![Telegram Bot](https://github.com/YOUR_USERNAME/flight-deal-bot/actions/workflows/telegram_bot.yml/badge.svg)](https://github.com/YOUR_USERNAME/flight-deal-bot/actions/workflows/telegram_bot.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 🇵🇱 Bot do Telegrama, który automatycznie wyszukuje **"zbugowane" loty** — loty, których cena jest drastycznie niższa niż średnia (np. lot do Japonii za 680 PLN zamiast 2500 PLN). Hostowany za darmo na GitHub Actions.

---

## 📖 Spis treści

- [Jak to działa?](#-jak-to-działa)
- [Funkcje](#-funkcje)
- [Szybki start (5 kroków)](#-szybki-start-5-kroków)
- [Komendy bota](#-komendy-bota)
- [Architektura](#-architektura)
- [Algorytm wykrywania](#-algorytm-wykrywania-zbugowanych-lotów)
- [Konfiguracja](#️-konfiguracja)
- [Uruchamianie lokalne](#-uruchamianie-lokalne)
- [FAQ](#-faq)
- [Licencja](#-licencja)

---

## 🧠 Jak to działa?

```
1. 🕐 Co 6 godzin GitHub Actions uruchamia skaner
2. 🌍 Skaner sprawdza loty z polskich lotnisk (rotacja dzień po dniu)
3. 📡 Amadeus API zwraca najtańsze loty do setek destynacji
4. 📊 Algorytm porównuje ceny z historią i progami absolutnymi
5. 🔥 Jeśli lot jest zbugowany → wysyłamy powiadomienie na Telegram
6. 💾 Aktualizujemy historię cen w repozytorium
```

**Przykład powiadomienia:**

```
🔥 ZBUGOWANY LOT! 🔥

🛫 WAW ✈️ NRT (Tokyo Narita, Japan)
📅 Data wylotu: 15.08.2026
💰 Średnia cena: 2,450 PLN
🔥 Aktualna cena: 680 PLN
📉 Zniżka: -72%!
🔗 Rezerwuj lot!

⏰ Wykryto: 21.05.2026 16:30
```

---

## ✨ Funkcje

| Funkcja | Opis |
|---------|------|
| 🔍 **Automatyczne skanowanie** | Co 6h sprawdza loty z 11 polskich lotnisk |
| 🔥 **Wykrywanie zbugowanych cen** | Algorytm statystyczny + progi absolutne |
| 📱 **Powiadomienia Telegram** | Natychmiastowe alerty o okazjach |
| 🧪 **Komenda `/test`** | Sprawdź czy bot działa |
| 🔎 **Komenda `/search`** | Wyszukaj loty do konkretnej destynacji |
| 📊 **Komenda `/stats`** | Statystyki bazy danych |
| 🌍 **943 lotniska** | Destynacje na całym świecie |
| 💰 **Za darmo** | RapidAPI Kiwi.com (300 zapytań/miesiąc) + GitHub Actions |
| 📈 **Historia cen** | Automatycznie budowana baza porównawcza |

---

## 🚀 Szybki start (5 kroków)

### Krok 1: Stwórz bota Telegram

1. Otwórz Telegram i znajdź **[@BotFather](https://t.me/BotFather)**
2. Wyślij `/newbot`
3. Wybierz nazwę (np. "Flight Deals Bot")
4. Wybierz username (musi kończyć się na `bot`, np. `MojeLotyDeal_bot`)
5. **Zapisz token** który dostaniesz od BotFathera

### Krok 2: Uzyskaj swój Chat ID

1. Napisz do **[@userinfobot](https://t.me/userinfobot)** na Telegramie
2. Bot odpowie Twoim **Chat ID** (numer)
3. **Zapisz ten numer**

### Krok 3: Uzyskaj klucze RapidAPI (Kiwi.com)

1. Załóż konto na **[RapidAPI](https://rapidapi.com/)**
2. Wejdź na stronę API **Kiwi.com Flights API** i zasubskrybuj darmowy plan "Basic" (300 zapytań/miesiąc).
3. **Zapisz** wartość nagłówka `X-RapidAPI-Key` z panelu "Endpoints".

### Krok 4: Sforkuj repozytorium i dodaj sekrety

1. Sforkuj to repozytorium na GitHub
2. Idź do **Settings → Secrets and variables → Actions**
3. Dodaj 4 sekrety:

| Sekret | Wartość |
|--------|---------|
| `RAPIDAPI_KEY` | Twój klucz RapidAPI |
| `TELEGRAM_BOT_TOKEN` | Token od BotFathera |
| `TELEGRAM_CHAT_ID` | Twój Chat ID |

### Krok 5: Uruchom bota!

1. Idź do **Actions** w swoim forku
2. Włącz GitHub Actions (jeśli wyłączone)
3. Uruchom ręcznie **"✈️ Scan Flights"** (przycisk "Run workflow")
4. Napisz `test` do swojego bota na Telegramie
5. **Gotowe!** 🎉 Bot będzie skanować co 6 godzin automatycznie.

---

## 🤖 Komendy bota

| Komenda | Opis |
|---------|------|
| `/start` | Powitanie i instrukcja użycia |
| `test` | 🧪 Wysyła losowy lot z bazy — sprawdź czy bot działa |
| `/search <KOD>` | 🔎 Szukaj lotów do destynacji (np. `/search NRT`) |
| `/deals` | 🔥 Pokaż ostatnie znalezione zbugowane loty |
| `/stats` | 📊 Statystyki: ile tras w bazie, ile bugów |
| `/help` | ℹ️ Lista komend |

> **Uwaga:** Komenda `test` działa zarówno z `/` jak i bez — wystarczy napisać `test`.

---

## 🏗️ Architektura

```
┌──────────────────────────────────────────────┐
│              GitHub Actions                   │
│                                              │
│  ┌─────────────┐     ┌──────────────┐       │
│  │ scan_flights │     │ telegram_bot │       │
│  │  (co 6h)    │     │  (co 5min)   │       │
│  └──────┬──────┘     └──────┬───────┘       │
│         │                    │                │
└─────────┼────────────────────┼────────────────┘
          │                    │
          ▼                    ▼
┌──────────────────────────────────────────────┐
│              Python Modules                   │
│                                              │
│  flight_scanner.py ──→ api_client.py         │
│         │                    │                │
│         ▼                    ▼                │
│  price_analyzer.py    Amadeus API            │
│         │                                    │
│         ▼                                    │
│  notifier.py ──────→ Telegram Bot API        │
│                            │                 │
│  telegram_bot.py ←─────────┘                 │
└──────────────────────────────────────────────┘
          │
          ▼
┌──────────────┐
│    data/     │
│              │
│ airports.json│
│ price_history│
│   .json      │
└──────────────┘
```

### Struktura plików

```
📁 Loty bot/
├── 📁 .github/workflows/
│   ├── scan_flights.yml        # Skanowanie co 6h
│   └── telegram_bot.yml        # Polling komend co 5min
├── 📁 src/
│   ├── __init__.py
│   ├── config.py               # Konfiguracja, lista lotnisk
│   ├── api_client.py           # Klient Amadeus API
│   ├── price_analyzer.py       # Algorytm wykrywania bugów
│   ├── notifier.py             # Powiadomienia Telegram
│   ├── telegram_bot.py         # Obsługa komend
│   └── flight_scanner.py       # Główny skaner
├── 📁 data/
│   ├── airports.json           # 943 lotniska (IATA + nazwa + kraj)
│   └── price_history.json      # Historia cen (auto-generowana)
├── 📁 tests/
│   └── test_price_analyzer.py  # Testy jednostkowe
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md                   # Ten plik
```

---

## 🧮 Algorytm wykrywania zbugowanych lotów

Bot używa **trzech warstw** wykrywania:

### Warstwa 1: Progi absolutne

Jeśli cena lotu jest poniżej progu absolutnego dla regionu, lot jest oznaczany jako zbugowany niezależnie od historii.

| Region | Próg (PLN) | Przykład |
|--------|-----------|----------|
| Europa (krótki dystans) | < 30 PLN | WAW → BER za 15 PLN |
| Europa (długi dystans) | < 80 PLN | WAW → LIS za 50 PLN |
| Azja | < 400 PLN | WAW → BKK za 299 PLN |
| Ameryki | < 600 PLN | WAW → JFK za 450 PLN |
| Afryka | < 350 PLN | WAW → CAI za 200 PLN |
| Oceania | < 800 PLN | WAW → SYD za 600 PLN |

### Warstwa 2: Zniżka procentowa

Jeśli mamy minimum 3 historyczne ceny, sprawdzamy:

```
zniżka = (średnia_cena - aktualna_cena) / średnia_cena × 100%

Jeśli zniżka ≥ 40% → LOT ZBUGOWANY ✅
```

### Warstwa 3: Outlier statystyczny

Jeśli mamy minimum 5 historycznych cen:

```
Jeśli cena < (średnia - 2 × odchylenie_standardowe) → LOT ZBUGOWANY ✅
```

---

## ⚙️ Konfiguracja

### Zmienne środowiskowe

| Zmienna | Opis | Wymagana |
|---------|------|----------|
| `RAPIDAPI_KEY` | Klucz API RapidAPI | ✅ |
| `TELEGRAM_BOT_TOKEN` | Token bota Telegram | ✅ |
| `TELEGRAM_CHAT_ID` | Twój Chat ID na Telegramie | ✅ |

### Stałe (config.py)

| Stała | Wartość | Opis |
|-------|---------|------|
| `BUG_THRESHOLD_PERCENT` | 40 | Min. zniżka % żeby oznaczyć jako bug |
| `SCAN_INTERVAL_HOURS` | 6 | Częstotliwość skanowania |
| `PRICE_HISTORY_MAX_ENTRIES` | 30 | Max wpisów cenowych per trasa |
| `PRICE_HISTORY_MAX_AGE_DAYS` | 90 | Kasowanie starszych wpisów |
| `CURRENCY` | PLN | Waluta cen |
| `DATE_RANGE_MONTHS` | 12 | Zakres dat (od dziś +12 miesięcy) |

### Polskie lotniska wylotowe

Bot skanuje loty z **11 polskich lotnisk** (rotacja dzień po dniu):

| Kod | Lotnisko |
|-----|----------|
| WAW | Warszawa Chopina |
| KRK | Kraków Balice |
| GDN | Gdańsk Wałęsa |
| KTW | Katowice Pyrzowice |
| WRO | Wrocław Kopernika |
| POZ | Poznań Ławica |
| RZE | Rzeszów Jasionka |
| SZZ | Szczecin Goleniów |
| LUZ | Lublin |
| BYG | Bydgoszcz |
| LCJ | Łódź Lublinek |

---

## 💻 Uruchamianie lokalne

### Wymagania

- Python 3.9+
- Konto RapidAPI (darmowy plan Kiwi.com Flights API)
- Bot Telegram (token od BotFathera)

### Instalacja

```bash
# Klonuj repozytorium
git clone https://github.com/YOUR_USERNAME/flight-deal-bot.git
cd flight-deal-bot

# Stwórz wirtualne środowisko (opcjonalnie)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# lub: venv\Scripts\activate  # Windows

# Zainstaluj zależności
pip install -r requirements.txt

# Skopiuj i wypełnij plik .env
cp .env.example .env
# Edytuj .env i wpisz swoje klucze
```

### Uruchomienie skanera

```bash
python -m src.flight_scanner
```

### Uruchomienie bota Telegram

```bash
python -m src.telegram_bot
```

### Uruchomienie testów

```bash
python -m pytest tests/ -v
```

---

## ❓ FAQ

### Ile to kosztuje?

**Nic.** RapidAPI dla Kiwi.com daje 300 darmowych zapytań miesięcznie, a GitHub Actions jest darmowy dla publicznych repozytoriów.

### Jak często bot sprawdza loty?

Co **6 godzin** (4 razy dziennie). Komendy Telegram są sprawdzane co **5 minut**.

### Czy bot sprawdza wszystkie 943 lotniska naraz?

Nie. Używa endpointu **Price Map** z Kiwi, który z jednego zapytania zwraca najtańsze loty do wielu destynacji. Bot rotuje między polskimi lotniskami wylotowymi dzień po dniu.

### Szacunkowe zużycie API?

~120 zapytań/miesiąc przez automatyczny skaner. Pozostaje około 180 zapytań na używanie komendy `/search` w Telegramie.

### Co jeśli GitHub Actions się wyłączy po 60 dniach nieaktywności?

Scheduled workflows wymagają aktywności w repo. Bot automatycznie commituje `price_history.json` co 6h, więc repo jest zawsze aktywne.

### Czy mogę dodać więcej lotnisk wylotowych?

Tak! Edytuj listę `POLISH_AIRPORTS` w `src/config.py`.

### Czy mogę zmienić próg zbugowanego lotu?

Tak! Zmień `BUG_THRESHOLD_PERCENT` w `src/config.py` (domyślnie 40%).

---

## 📊 Zużycie API

| Element | Zapytania/cykl | Cykle/dzień | Zapytania/miesiąc |
|---------|---------------|-------------|-------------------|
| Price Map (Skaner) | 1 | 4 | ~120 |
| Komendy /search | ~1 | zależy | zależy (np. 150) |
| **SUMA** | | | **~270** |
| **Limit RapidAPI** | | | **300** |
| **Zapas** | | | **~30** ✅ |

---

## 🛠️ Technologie

- **Python 3.11** — język programowania
- **Kiwi.com Flights API (RapidAPI)** — dane lotnicze (Search, Price Map)
- **Telegram Bot API** — powiadomienia i komendy
- **GitHub Actions** — hosting (cron jobs)
- **JSON** — baza danych (price_history.json)

---

## 📄 Licencja

MIT License — używaj jak chcesz! Pamiętaj tylko o limitach API Amadeus.

---

## 🤝 Wkład

1. Sforkuj repozytorium
2. Stwórz branch (`git checkout -b feature/moja-funkcja`)
3. Commituj zmiany (`git commit -m 'Dodaj moją funkcję'`)
4. Push (`git push origin feature/moja-funkcja`)
5. Otwórz Pull Request

---

<p align="center">
  Made with ❤️ and ✈️ | Powered by Amadeus API & Telegram
</p>
