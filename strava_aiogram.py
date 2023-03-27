#import telegram
#
#from telegram import InlineKeyboardButton, InlineKeyboardMarkup
#
#BOT_TOKEN = ''
#STRAVA_CLIENT_ID = '104425'
#STRAVA_CLIENT_SECRET = '4a4733df7d14ce6b5e6dcc30b0610ad10e555c70'
#GET_CODE_URL = f'http://www.strava.com/oauth/authorize?client_id={STRAVA_CLIENT_ID}&response_type=code&approval_prompt=force&scope=activity:write&redirect_uri=https://t.me/StravaUploadActivityBot'
#
#bot = telegram.Bot(BOT_TOKEN)
#inline_button_strava = InlineKeyboardButton("Перейти к Strava", url=GET_CODE_URL)
#inline_keyboard = InlineKeyboardMarkup(inline_button_strava)
#access_token=''
#refresh_token = ''
#
##Ссылка на Strava
#@bot.message_handler(commands=['start', 'help'])
#async def welcome(message: telegram.Message):
#    #await message.reply('Для использования бота, разрешите загружать файлы в Strava от вашего имени', reply_markup=keyboard_inline) #То же самое, но с реплаем на команду
#    await bot.send_message('Для использования бота, разрешите загружать файлы в Strava от вашего имени', reply_markup=inline_keyboard)
#
## Обмен кода на токен
#@bot.message_handler(commands=['reg'])
#async def get_token(message: telegram.Message)
#    code = message.text
#    url = f'https://www.strava.com/api/v3/oauth/token?client_id={STRAVA_CLIENT_ID}&client_secret={STRAVA_CLIENT_SECRET}&code={code}&grant_type=authorization_code'
#    response = requests.post(url)
#    refresh_token = response.json()['refresh_token']
#    await message.answer(code)
#    
#@bot.message_handler(content_types=telegram.Message.document)
#async def upload_activity(message: types.Message):
#    user_id = message.from_user.id
#    file_id = message.document.file_id
#    file_name = message.document.file_name
#    file_data = await bot.get_file(file_id)
#    file_url = await file_data.get_url()
#
#    # Обновление токена
#    #url = f'https://www.strava.com/api/v3/oauth/token?client_id={STRAVA_CLIENT_ID}&client_secret={STRAVA_CLIENT_SECRET}&code={code}&grant_type=authorization_code'
#    #response = requests.post(url)
#    #bearer = response.json()['access_token']
#
#    # Получение файла от API Telegram
#    open(file_name, 'wb').write(requests.get(file_url).content)
#    time.sleep(15)
#    
#    # Загрузка файла в Strava
#    url = 'https://www.strava.com/api/v3/uploads?name=api_test&data_type=gpx&activity_type=run'
#    payload = {'activity': open(file_name, 'rb')}
#    response = requests.post(url, headers={'Authorization': f'Bearer {bearer}'}, files=payload)
#
#    await bot.send_message(user_id, response.text)
#
#if __name__ == '__main__':
#    executor.start_polling(dp)