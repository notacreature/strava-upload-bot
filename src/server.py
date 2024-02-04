import os, configparser, requests, strava
from http import server
from socketserver import BaseServer, TCPServer
from tinydb import TinyDB, Query
from dictionary import TEXT, URL

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))
BOT_URL = CONFIG["Telegram"]["BOT_URL"]
SCOPE = CONFIG["Strava"]["SCOPE"]
CLIENT_ID = CONFIG["Strava"]["CLIENT_ID"]
CLIENT_SECRET = CONFIG["Strava"]["CLIENT_SECRET"]
USER_DB = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
USER_QUERY = Query()
TOKEN = CONFIG["Telegram"]["BOT_TOKEN"]
PORT = CONFIG["Server"]["PORT"]


class ParamsHTTPRequestHandler(server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path
        incoming_params = {}
        if "?" in path:
            path, query = path.split("?", 1)
            for pair in query.split("&"):
                key, value = pair.split("=", 1)
                incoming_params[key] = value
        user_id = str(incoming_params["user_id"])
        code = str(incoming_params["code"])

        self.send_response(301)
        self.send_header("Location", BOT_URL)
        self.end_headers()

        # Проверка выданных в Strava прав и создание пользователя
        if SCOPE in str(incoming_params["scope"]):
            refresh_token = strava.get_refresh_token(user_id, CLIENT_ID, CLIENT_SECRET, code)
            USER_DB.upsert(
                {
                    "user_id": user_id,
                    "refresh_token": refresh_token,
                    "favorites": [],
                },
                USER_QUERY["user_id"] == user_id,
            )

            url = URL["bot"].format(TOKEN)
            params = {
                "chat_id": user_id,
                "text": TEXT["reply_authorized"],
                "parse_mode": "Markdown",
            }
            requests.post(url, params=params)
        else:
            url = URL["bot"].format(TOKEN)
            params = {
                "chat_id": user_id,
                "text": TEXT["reply_scope"],
                "parse_mode": "Markdown",
            }
            requests.post(url, params=params)


# Старт сервера
tcp_server = TCPServer(("", int(PORT)), ParamsHTTPRequestHandler)
BaseServer.serve_forever(tcp_server)
