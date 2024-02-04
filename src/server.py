import os, configparser, requests
from http import server
from socketserver import BaseServer, TCPServer
from tinydb import TinyDB, Query
from dictionary import TEXT, URL

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))
BOT_URL = CONFIG["Telegram"]["BOT_URL"]
SCOPE = CONFIG["Strava"]["SCOPE"]
USER_DB = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
USER_QUERY = Query()
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

        # Если scope соответствуют требуемым – добавляем пользователя в БД; если нет, сообщаем в чат об ошибке.
        if SCOPE in str(incoming_params["scope"]):
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

            url = URL["bot"].format(TOKEN)
            params = {
                "chat_id": str(incoming_params["user_id"]),
                "text": TEXT["reply_authorized"],
                "parse_mode": "Markdown",
            }
            requests.post(url, params=params)

        else:
            url = URL["bot"].format(TOKEN)
            params = {
                "chat_id": str(incoming_params["user_id"]),
                "text": TEXT["reply_scope"],
                "parse_mode": "Markdown",
            }
            requests.post(url, params=params)


# Создаем и запускаем TCPServer
tcp_server = TCPServer(("", int(PORT)), ParamsHTTPRequestHandler)
BaseServer.serve_forever(tcp_server)
