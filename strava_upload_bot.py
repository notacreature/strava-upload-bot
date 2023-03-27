import requests, time

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = '5976143199:AAHUSdb47E-MCiPwTs1WSGym-5fs2BsmfAo'
STRAVA_CLIENT_ID = '104425'
STRAVA_CLIENT_SECRET = '4a4733df7d14ce6b5e6dcc30b0610ad10e555c70'
GET_CODE_URL = f'http://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}&response_type=code&approval_prompt=force&scope=activity:write&redirect_uri=https://t.me/StravaUploadActivityBot'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot=bot)


#Обработка /start, /help; Вывод информационного сообщения
@dp.message_handler(commands=['start', 'help'])
async def welcome(message: types.Message):
    inline_button = InlineKeyboardButton(text="Strava", url=GET_CODE_URL)
    inline_keyboard = InlineKeyboardMarkup().add(inline_button)
    await message.reply('Для получения кода авторизации, перейди в Strava', reply_markup=inline_keyboard)


#Обмен кода на токен; ПЕРЕДЕЛАТЬ НА РЕГИСТРАЦИЮ ПРИЛОЖЕНИЯ
@dp.message_handler(content_types=types.ContentType.TEXT)
async def welcome(message: types.Message):
    code = message.text
    url = f'https://www.strava.com/api/v3/oauth/token?client_id={STRAVA_CLIENT_ID}&client_secret={STRAVA_CLIENT_SECRET}&code={code}&grant_type=authorization_code'
    response = requests.post(url)
    await message.reply(response.json()['refresh_token'])


#Загрузка активности в Strava
@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def connect_strava(message: types.Message):
    file_id = message.document.file_id
    file_name = message.document.file_name
    file_data = await bot.get_file(file_id)
    file_url = await file_data.get_url()

    #Явно задаём токен обновления; ПЕРЕДЕЛАТЬ НА ПОЛУЧЕНИЕ ТОКЕНА ИЗ ХРАНИЛИЩА
    refresh_token = message.caption

    #Получение файла от API Telegram
    open(file_name, 'wb').write(requests.get(file_url).content)
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
        'file': open(file_name, 'rb')
        }
    response = requests.get(url, params=params, headers=headers, files=files)
    upload_id = response.json()['id']

    #Проверка статуса загрузки
    time.sleep(30)
    url = f'https://www.strava.com/api/v3/uploads/{upload_id}'
    headers = {
        'Authorization': f'Bearer {bearer}'
    }
    response = requests.post(url, headers=headers)
    await message.reply(response.json()['status'])


if __name__ == '__main__':
    executor.start_polling(dp)