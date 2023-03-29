from http import server
from socketserver import BaseServer, TCPServer
from tinydb import TinyDB, Query

#Определяем порт, на котором будет работать сервер
PORT = 8000
BOT_URL = 'https://t.me/StravaUploadActivityBot'

#Создаем свой класс обработчика запросов, наследуя от SimpleHTTPRequestHandler
class MyHTTPRequestHandler(server.SimpleHTTPRequestHandler):
    #Переопределяем метод do_GET()
    def do_GET(self):
        #Получаем путь и параметры запроса
        path = self.path
        params = {}
        if "?" in path:
            path, query = path.split("?", 1)
            for pair in query.split("&"):
                key, value = pair.split("=", 1)
                params[key] = value
        
        self.send_response(301)
        self.send_header('Location', BOT_URL)
        self.end_headers()
       
        #Сохраняем параметры в хранилище
        db = TinyDB('userdata.json')
        db.insert({'user_id': params['user_id'], 'auth_code': params['code']})
        
#Создаем объект сервера, используя класс TCPServer из модуля socketserver
my_server = TCPServer(("", PORT), MyHTTPRequestHandler)

#Выводим информацию о запуске сервера
print(f"HTTP server running on port {PORT}")

#Запускаем бесконечный цикл обработки запросов
BaseServer.serve_forever(my_server)