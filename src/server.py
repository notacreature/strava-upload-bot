import os, configparser
from http import server
from socketserver import BaseServer, TCPServer
from tinydb import TinyDB, Query

path = os.path.join(os.path.dirname(__file__), '..', 'settings.ini')
config = configparser.ConfigParser()
config.read(path)

#Создаем свой класс обработчика запросов, наследуя от SimpleHTTPRequestHandler
class MyHTTPRequestHandler(server.SimpleHTTPRequestHandler):
    #Переопределяем метод do_GET()
    def do_GET(self):
        #Получаем путь и параметры запроса
        path = self.path
        params = {}
        url = config['Telegram']['BOT_URL']
        if "?" in path:
            path, query = path.split("?", 1)
            for pair in query.split("&"):
                key, value = pair.split("=", 1)
                params[key] = value
        
        self.send_response(301)
        self.send_header('Location', url)
        self.end_headers()
        
        #TODO Баг: если база пуста, вызов if возвращает ошибку, потому что в ней нет ключа 'user_id'
        #Сохраняем параметры в хранилище
        path = os.path.join(os.path.dirname(__file__), '..', 'storage/userdata.json')
        db = TinyDB(path)
        user = Query()
        if db.contains(user['user_id'] == params['user_id']):
            db.update({'auth_code': params['code']}, user['user_id'] == params['user_id'])
        else:
            db.insert({'user_id': params['user_id'], 'auth_code': params['code']})

#Создаем объект сервера, используя класс TCPServer из модуля socketserver
port = int(config['Server']['PORT'])
my_server = TCPServer(("", port), MyHTTPRequestHandler)

#Выводим информацию о запуске сервера
print(f"HTTP server running on port {port}")

#Запускаем бесконечный цикл обработки запросов
BaseServer.serve_forever(my_server)