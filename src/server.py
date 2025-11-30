import os, configparser, requests, strava
from http import server
from urllib import parse
from socketserver import TCPServer
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


class AuthRequestHandler(server.SimpleHTTPRequestHandler):
    def do_GET(self):
        request = parse.urlparse(self.path)
        query_params = parse.parse_qs(request.query)
        scope = str(query_params["scope"][0])
        code = str(query_params["code"][0])
        user_id = str(query_params["user_id"][0])

        self.send_response(303)
        self.send_header("Location", BOT_URL)
        self.end_headers()

        # Проверка выданных в Strava прав и создание пользователя
        if SCOPE in scope:
            refresh_token = strava.get_refresh_token(CLIENT_ID, CLIENT_SECRET, code)
            USER_DB.upsert(
                {
                    "user_id": user_id,
                    "refresh_token": refresh_token,
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
tcp_server = TCPServer(("", int(PORT)), AuthRequestHandler)
tcp_server.serve_forever()
