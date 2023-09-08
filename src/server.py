import os, configparser, requests
from http import server
from socketserver import BaseServer, TCPServer
from tinydb import TinyDB, Query

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))
TOKEN = CONFIG["Telegram"]["BOT_TOKEN"]
BOT_URL = CONFIG["Telegram"]["BOT_URL"]
PORT = CONFIG["Server"]["PORT"]
USER_QUERY = Query()
USER_DB = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))


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

        # Создаём пользователя с полученными параметрами
        USER_DB.upsert(
            {
                "user_id": str(incoming_params["user_id"]),
                "scope": str(incoming_params["scope"]),
                "auth_code": str(incoming_params["code"]),
                "refresh_token": "",
                "favorites": [],
            },
            USER_QUERY["user_id"] == incoming_params["user_id"],
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
