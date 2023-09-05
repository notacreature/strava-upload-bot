import os, configparser, requests
from http import server
from socketserver import BaseServer, TCPServer
from tinydb import TinyDB, Query

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))
BOT_URL = CONFIG["Telegram"]["BOT_URL"]
TOKEN = CONFIG["Telegram"]["BOT_TOKEN"]
PORT = CONFIG["Server"]["PORT"]


# Создаем класс обработчика запросов, наследуя от SimpleHTTPRequestHandler
class ParamsHTTPRequestHandler(server.SimpleHTTPRequestHandler):
    # Переопределяем метод do_GET() на парсинг входящего url
    def do_GET(self):
        path = self.path
        incoming_params = {}
        url = BOT_URL
        if "?" in path:
            path, query = path.split("?", 1)
            for pair in query.split("&"):
                key, value = pair.split("=", 1)
                incoming_params[key] = value
        self.send_response(301)
        self.send_header("Location", url)
        self.end_headers()

        # Сохраняем параметры в хранилище
        user_db = TinyDB(
            os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json")
        )
        user_query = Query()
        user_db.upsert(
            {
                "user_id": incoming_params["user_id"],
                "scope": incoming_params["scope"],
                "auth_code": incoming_params["code"],
                "favorites": [],
            },
            user_query["user_id"] == incoming_params["user_id"],
        )

        # Отвечаем в чат об успехе
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        params = {
            "chat_id": incoming_params["user_id"],
            "text": "🤖 Отлично! Теперь я могу загружать вашу активность в Strava.\nПришлите мне файл `.fit`, `.tcx` или `.gpx` и я его опубликую.",
            "parse_mode": "Markdown",
        }
        requests.post(url, params=params)


# Создаем и запускаем TCPServer
tcp_server = TCPServer(("", int(PORT)), ParamsHTTPRequestHandler)
BaseServer.serve_forever(tcp_server)
