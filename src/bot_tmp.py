from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✏ Имя", callback_data="NAME"),
            InlineKeyboardButton("✏ Описание", callback_data="DESC"),
            InlineKeyboardButton("✏ Тип", callback_data="TYPE"),
        ],
        [
            InlineKeyboardButton("Посмотреть в Strava", url=f"https://google.com"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        """Активность опубликована 🏆
```
Имя: Evening Workout
Тип: Workout
Время: 480
Дистанция: 1356.4
Описание: t.me/StravaUploadActivityBot
```""",
        constants.ParseMode.MARKDOWN,
        reply_markup=reply_markup,
    )
    return "upload_change"


async def chname_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(query.from_user.id, "🤖 Введи новое имя")
    return "chname_finish"


async def chdesc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(query.from_user.id, "🤖 Введи новое описание")
    return "chdesc_finish"


async def chtype_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("🏊‍♀️ Swim", callback_data="Swim"),
            InlineKeyboardButton("🚴‍♂️ Ride", callback_data="Ride"),
            InlineKeyboardButton("👟 Run", callback_data="Run"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="🤖 Выбери новый тип", reply_markup=reply_markup)
    return "chtype_finish"


async def chname_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✏ Имя", callback_data="NAME"),
            InlineKeyboardButton("✏ Описание", callback_data="DESC"),
            InlineKeyboardButton("✏ Тип", callback_data="TYPE"),
        ],
        [
            InlineKeyboardButton("Посмотреть в Strava", url=f"https://www.strava.com/"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"""Активность обновлена 🏆
```
Имя: {update.message.text}
Тип: Workout
Время: 480
Дистанция: 1356.4
Описание: t.me/StravaUploadActivityBot
```""",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=reply_markup,
    )
    return "upload_change"


async def chdesc_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✏ Имя", callback_data="NAME"),
            InlineKeyboardButton("✏ Описание", callback_data="DESC"),
            InlineKeyboardButton("✏ Тип", callback_data="TYPE"),
        ],
        [
            InlineKeyboardButton("Посмотреть в Strava", url=f"https://google.com"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"""Активность обновлена 🏆
```
Имя: Evening Workout
Тип: Workout
Время: 480
Дистанция: 1356.4
Описание: {update.message.text}
```""",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=reply_markup,
    )
    return "upload_change"


async def chtype_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("✏ Имя", callback_data="NAME"),
            InlineKeyboardButton("✏ Описание", callback_data="DESC"),
            InlineKeyboardButton("✏ Тип", callback_data="TYPE"),
        ],
        [
            InlineKeyboardButton("Посмотреть в Strava", url=f"https://google.com"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"""Активность обновлена 🏆
```
Имя: Evening Workout
Тип: {update.callback_query.data}
Время: 480
Дистанция: 1356.4
Описание: t.me/StravaUploadActivityBot
```""",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=reply_markup,
    )

    return "upload_change"


def main() -> None:
    application = Application.builder().token("5833480161:AAGwy25wrYJT7LAiNCfb-Z6TCnWn8rS9mMU").build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.FileExtension("gpx"), start)],
        states={
            "upload_change": [
                CallbackQueryHandler(chname_start, pattern="NAME"),
                CallbackQueryHandler(chdesc_start, pattern="DESC"),
                CallbackQueryHandler(chtype_start, pattern="TYPE"),
            ],
            "chname_finish": [MessageHandler(filters.TEXT, chname_finish)],
            "chdesc_finish": [MessageHandler(filters.TEXT, chdesc_finish)],
            "chtype_finish": [CallbackQueryHandler(chtype_finish, pattern=".*")],
        },
        fallbacks=[MessageHandler(filters.Document.FileExtension("gpx"), start)],
    )

    application.add_handler(conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
