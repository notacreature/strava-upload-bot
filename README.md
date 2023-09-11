## Strava Upload Bot
Strava Upload Bot – это Telegram-бот, который позволяет загружать файлы в формате `.fit`, `.tcx` или `.gpx` в социальную сеть Strava. Бот полезен, если по какой-то причине ваше фитнес-приложение не синхронизируется со Strava автоматически.

### Как пользоваться
Чтобы воспользоваться ботом, перейдите в Telegram по адресу [t.me/StravaUploadActivityBot](https://t.me/StravaUploadActivityBot) и нажмите **START** или введите команду `/start`. Бот попросит вас авторизоваться в Strava и предоставить ему доступ к вашему аккаунту. После этого вы сможете отправлять боту файлы в формате `.fit`, `.tcx` или `.gpx`, а он будет публиковать их в Strava в качестве активности.

### Используемые библиотеки Python
Для создания бота использованы следующие библиотеки или модули Python:
* python-telegram-bot
* python requests
* tinydb

### Ограничения или особенности
Бот имеет следующие ограничения или особенности:
* Бот может загружать активность с пользовательским названием
* Бот не поддерживает загрузку видео или фото
* Бот не проверяет корректность или целостность файлов, которые ему отправляют
* Бот не гарантирует безопасность или конфиденциальность ваших данных

### Лицензия или правила использования
Бот является открытым проектом и распространяется под лицензией MIT. Вы можете свободно использовать, изменять и распространять бота при условии, что вы указываете авторство и ссылку на исходный код. Исходный код бота доступен на GitHub – [notacreature/strava_upload_bot](https://github.com/notacreature/strava-upload-bot).
