import logging, requests, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

BOT_TOKEN = '5976143199:AAHUSdb47E-MCiPwTs1WSGym-5fs2BsmfAo'
STRAVA_CLIENT_ID = '104425'
STRAVA_CLIENT_SECRET = '4a4733df7d14ce6b5e6dcc30b0610ad10e555c70'
GET_CODE_URL = f'http://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}&response_type=code&approval_prompt=force&scope=activity:write&redirect_uri=https://t.me/StravaUploadActivityBot'

#Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

#Обработка /start, /help; Вывод информационного сообщения
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inline_button = InlineKeyboardButton("Перейти к Strava", url=GET_CODE_URL)
    inline_keyboard= InlineKeyboardMarkup( [[inline_button]] )
    await update.message.reply_text('Для использования бота, разрешите загружать файлы в Strava от вашего имени', reply_markup=inline_keyboard)

#Обмен кода на токен; ПЕРЕДЕЛАТЬ НА РЕГИСТРАЦИЮ ПРИЛОЖЕНИЯ
async def get_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text
    url = f'https://www.strava.com/api/v3/oauth/token?client_id={STRAVA_CLIENT_ID}&client_secret={STRAVA_CLIENT_SECRET}&code={code}&grant_type=authorization_code'
    response = requests.post(url)
    await update.message.reply_text(response.json()['refresh_token'])

#Загрузка активности в Strava
async def upload_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_id = update.message.document.file_id
    file_name = update.message.document.file_name
    file_data = await context.bot.get_file(file_id)

    #Явно задаём токен обновления; ПЕРЕДЕЛАТЬ НА ПОЛУЧЕНИЕ ТОКЕНА ИЗ ХРАНИЛИЩА
    refresh_token = update.message.caption

    #Получение файла от API Telegram
    open(file_name, 'wb').write(requests.get(file_data.file_path).content)
    time.sleep(20)#Как еще можно дождаться конца скачивания файла?
    
    #Обновление токена
    url = f'https://www.strava.com/api/v3/oauth/token?client_id={STRAVA_CLIENT_ID}&client_secret={STRAVA_CLIENT_SECRET}&grant_type=refresh_token&refresh_token={refresh_token}'
    response = requests.post(url)
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
        'activity': open(file_name, 'rb')
        }
    response = requests.post(url, params=params, headers=headers, files=files)

    #Проверка статуса загрузки
    upload_id = response.json()['id']
    url = f'https://www.strava.com/api/v3/uploads/{upload_id}'
    headers = {
        'Authorization': f'Bearer {bearer}'
    }
    response = requests.post(url, headers=headers)
    await update.message.reply_text(response.json()['status'])

def main() -> None:   
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', info))
    application.add_handler(CommandHandler('help', info))
    application.add_handler(MessageHandler(filters.TEXT, get_token))
    application.add_handler(MessageHandler(filters.ATTACHMENT, upload_activity))

    application.run_polling()
    
if __name__ == "__main__":
    main()