import requests, time, asyncio, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from tinydb import TinyDB, Query

BOT_TOKEN = '5976143199:AAHUSdb47E-MCiPwTs1WSGym-5fs2BsmfAo'
STRAVA_CLIENT_ID = '104425'
STRAVA_CLIENT_SECRET = '4a4733df7d14ce6b5e6dcc30b0610ad10e555c70'
REDIRECT_URL = 'http://localhost:8000/'


#Обработка /start, /help; Вывод информационного сообщения
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    inline_button = InlineKeyboardButton("Перейти к Strava", url=f'http://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}&response_type=code&scope=activity:write&redirect_uri={REDIRECT_URL}?user_id={user_id}')
    inline_keyboard= InlineKeyboardMarkup( [[inline_button]] )
    await update.message.reply_text(f'Для использования бота, разрешите загружать файлы в Strava от вашего имени', reply_markup=inline_keyboard)


#Загрузка активности в Strava
async def upload_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    file_id = update.message.document.file_id
    file_name = update.message.document.file_name
    file_data = await context.bot.get_file(file_id)
    db = TinyDB('userdata.json')
    user = Query()
    
    #Получение файла от API Telegram
    open(f'storage/{file_name}', 'wb').write(requests.get(file_data.file_path).content)
    time.sleep(20)#Как еще можно дождаться конца скачивания файла?
    
    #Попытка получить refresh_token из БД; при неуспехе получаем от API и добавляем текущему пользователю в БД
    try:
        refresh_token = db.search(user.user_id == user_id)[0]['refresh_token']
    except (IndexError, KeyError):
        code = db.search(user['user_id'] == user_id)[0]['auth_code']
        url = f'https://www.strava.com/api/v3/oauth/token'
        params = {
            'client_id': f'{STRAVA_CLIENT_ID}',
            'client_secret': f'{STRAVA_CLIENT_SECRET}',
            'grant_type': 'authorization_code',
            'code': f'{code}'
            }
        response = requests.post(url, params=params)
        refresh_token = response.json()['refresh_token']
        db.update({'refresh_token': refresh_token}, user['user_id'] == user_id)
    
    #Обновление токена
    url = f'https://www.strava.com/api/v3/oauth/token'
    params = {
        'client_id': f'{STRAVA_CLIENT_ID}',
        'client_secret': f'{STRAVA_CLIENT_SECRET}',
        'grant_type': 'refresh_token',
        'refresh_token': f'{refresh_token}'
        }
    response = requests.post(url, params=params)
    bearer = response.json()['access_token']
    
    #Загрузка файла в Strava
    url = 'https://www.strava.com/api/v3/uploads'
    params = {
        'name': 'telegram_bot_test',
        'data_type': 'gpx',
        'activity_type': 'run'
        }
    headers = {
        'Authorization': f'Bearer {bearer}'
    }
    files = {
        'file': open(f'storage/{file_name}', 'rb')
        }
    response = requests.post(url, params=params, headers=headers, files=files)
    upload_id = response.json()['id_str']
    
    #Проверка статуса загрузки
    time.sleep(30)
    url = f'https://www.strava.com/api/v3/uploads/{upload_id}'
    headers = {
        'Authorization': f'Bearer {bearer}'
    }
    response = requests.get(url, headers=headers)
    await update.message.reply_text(response.json()['status'])

    try:
        os.remove(f'storage/{file_name}')
    except:
        pass


def main() -> None:   
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', info))
    application.add_handler(CommandHandler('help', info))
    application.add_handler(MessageHandler(filters.ATTACHMENT, upload_activity))

    application.run_polling()
    
    
if __name__ == "__main__":
    main()