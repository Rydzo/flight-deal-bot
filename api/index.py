import os
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Dodaj katalog główny projektu do ścieżki, aby poprawnie importować moduły z src
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.telegram_bot import TelegramBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_webhook")

# Leniwa inicjalizacja instancji bota w celu przyspieszenia startu funkcji bezserwerowej
_bot_instance = None

def get_bot():
    global _bot_instance
    if _bot_instance is None:
        # Inicjalizacja bota (wczyta zmienne środowiskowe z systemu)
        _bot_instance = TelegramBot()
    return _bot_instance

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Odbiera aktualizacje od Telegram API (Webhook)."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            update = json.loads(post_data.decode('utf-8'))
            logger.info(f"Otrzymano update przez webhook: {update}")
            
            message = update.get("message")
            if message:
                bot = get_bot()
                bot.process_message(message)
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Błąd w webhooku: {e}", exc_info=True)
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_GET(self):
        """Wyświetla stronę statusową z instrukcją podpięcia webhooka."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        html = """
        <!DOCTYPE html>
        <html>
            <head>
                <meta charset="utf-8">
                <title>✈️ Flight Deal Bot Webhook</title>
                <style>
                    body {
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        text-align: center;
                        background-color: #0f172a;
                        color: #f8fafc;
                        padding: 50px;
                    }
                    .container {
                        max-width: 650px;
                        margin: 0 auto;
                        background: #1e293b;
                        padding: 40px;
                        border-radius: 12px;
                        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
                        border: 1px solid #334155;
                    }
                    h1 {
                        color: #38bdf8;
                        margin-bottom: 20px;
                    }
                    .status {
                        display: inline-block;
                        background: #10b981;
                        color: white;
                        padding: 6px 12px;
                        border-radius: 20px;
                        font-weight: bold;
                        font-size: 0.9em;
                        margin-bottom: 20px;
                    }
                    code {
                        background: #0f172a;
                        padding: 12px;
                        display: block;
                        max-width: 100%;
                        margin: 20px 0;
                        word-break: break-all;
                        border-radius: 6px;
                        color: #f472b6;
                        border: 1px solid #1e293b;
                        text-align: left;
                        font-family: monospace;
                    }
                    p {
                        line-height: 1.6;
                        color: #cbd5e1;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✈️ Flight Deal Bot Webhook</h1>
                    <div class="status">🟢 Webhook Aktywny</div>
                    <p>Serwer bezserwerowy (Serverless) działa poprawnie i jest gotowy na odbiór powiadomień z Telegrama w czasie rzeczywistym!</p>
                    <hr style="border-color: #334155; margin: 30px 0;"/>
                    <h3 style="text-align: left; color: #cbd5e1;">Jak połączyć webhook ze swoim botem?</h3>
                    <p style="text-align: left;">Skopiuj poniższy link, zastąp <code>&lt;TWÓJ_TOKEN_BOTA&gt;</code> tokenem od BotFather, a <code>&lt;TWOJA_DOMENA_VERCEL&gt;</code> adresem tej aplikacji na Vercel (np. <code>moja-apka.vercel.app</code>), po czym wklej go do paska wyszukiwarki internetowej i wciśnij Enter:</p>
                    <code>
                    https://api.telegram.org/bot&lt;TWÓJ_TOKEN_BOTA&gt;/setWebhook?url=https://&lt;TWOJA_DOMENA_VERCEL&gt;/
                    </code>
                    <p style="text-align: left; font-size: 0.85em; color: #94a3b8; margin-top: 20px;">
                        💡 <i>Wskazówka: Po poprawnym wywołaniu powinieneś zobaczyć komunikat {"ok":true,"result":true,"description":"Webhook was set"}. Od tej pory bot będzie odpowiadał na wiadomości natychmiast!</i>
                    </p>
                </div>
            </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))
