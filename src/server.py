# TODO Баг: что будет, если при регистрации не прожать галочку?

import os, configparser, requests
from http import server
from socketserver import BaseServer, TCPServer
from tinydb import TinyDB, Query

config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))


# Создаем класс обработчика запросов, наследуя от SimpleHTTPRequestHandler
class ParamsHTTPRequestHandler(server.SimpleHTTPRequestHandler):
    # Переопределяем метод do_GET() на парсинг входящего url
    def do_GET(self):
        path = self.path
        incoming_params = {}
        url = config["Telegram"]["BOT_URL"]
        if "?" in path:
            path, query = path.split("?", 1)
            for pair in query.split("&"):
                key, value = pair.split("=", 1)
                incoming_params[key] = value
        self.send_response(301)
        self.send_header("Location", url)
        self.end_headers()

        # Сохраняем параметры в хранилище
        user_db = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
        user_query = Query()
        user_db.upsert({"user_id": incoming_params["user_id"], "auth_code": incoming_params["code"]}, user_query["user_id"] == incoming_params["user_id"])

        # Отвечаем в чат об успехе
        url = (f"https://api.telegram.org/bot{config['Telegram']['BOT_TOKEN']}/sendMessage")
        params = {
            "chat_id": incoming_params["user_id"],
            "text": "🤖 Отлично! Теперь я могу загружать активность в Strava.\nПришлите мне файл `.fit`, `.tcx` или `.gpx` и я его опубликую.",
            "parse_mode": "Markdown",
        }
        requests.post(url, params=params)


# Создаем и запускаем TCPServer
port = int(config["Server"]["PORT"])
tcp_server = TCPServer(("", port), ParamsHTTPRequestHandler)
BaseServer.serve_forever(tcp_server)