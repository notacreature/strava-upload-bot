# TODO заменить строки в callback_data на структурированные, "data:чётотам" и/или "action:чётотам" (внимательно для regexp и chtype)
# TODO объединить refresh и пейджинг
# TODO привести к общему виду обновление данных в context.user_data
# TODO абстрагировать inline_keyboard для пейджинга

import os, requests, configparser, strava
from tinydb import TinyDB, Query
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    constants,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from dictionary import TEXT, URL

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), "..", "settings.ini"))
TOKEN = CONFIG["Telegram"]["BOT_TOKEN"]
CLIENT_ID = CONFIG["Strava"]["CLIENT_ID"]
CLIENT_SECRET = CONFIG["Strava"]["CLIENT_SECRET"]
SCOPE = CONFIG["Strava"]["SCOPE"]
REDIRECT_URL = CONFIG["Server"]["URL"]
USER_DB = TinyDB(os.path.join(os.path.dirname(__file__), "..", "storage", "userdata.json"))
USER_QUERY = Query()
PER_PAGE = 4


class KeyboardFormatter:
    @staticmethod
    def format_activity_data(format: str, url: str, activity: dict) -> str:
        activity_link = url.format(activity["id"])
        return format.format(
            activity["name"], activity["sport_type"], activity["moving_time"], activity["distance"], activity["gear"], activity["description"], activity_link
        )

    @staticmethod
    def format_edit_keyboard(keys: dict) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(keys["key_change_name"], callback_data="Chname"),
                    InlineKeyboardButton(keys["key_change_desc"], callback_data="Chdesc"),
                ],
                [
                    InlineKeyboardButton(keys["key_change_type"], callback_data="Chtype"),
                    InlineKeyboardButton(keys["key_change_gear"], callback_data="Chgear"),
                ],
                [
                    InlineKeyboardButton(keys["key_activities"], callback_data="List"),
                ],
            ]
        )

    @staticmethod
    def format_type_keyboard(keys: dict) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(keys["key_swim"], callback_data="Swim"),
                    InlineKeyboardButton(keys["key_ride"], callback_data="Ride"),
                    InlineKeyboardButton(keys["key_run"], callback_data="Run"),
                ]
            ]
        )

    @staticmethod
    def format_list_keyboard(keys: dict, activity_list: list) -> InlineKeyboardMarkup:
        inline_keys = [
            [
                InlineKeyboardButton(keys["key_prev"], callback_data="PrevPage"),
                InlineKeyboardButton(keys["key_refresh"], callback_data="Refresh"),
                InlineKeyboardButton(keys["key_next"], callback_data="NextPage"),
            ]
        ]
        for activity in activity_list:
            inline_keys.insert(-1, [InlineKeyboardButton(TEXT["key_activity"].format(activity["name"], activity["date"]), callback_data=activity["id"])])
        return InlineKeyboardMarkup(inline_keys)


# /start; регистрация
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    inline_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(TEXT["key_auth"], url=URL["auth"].format(CLIENT_ID, SCOPE, REDIRECT_URL, user_id)),
            ]
        ]
    )
    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            TEXT["reply_start"],
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            TEXT["reply_restart"],
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
        return ConversationHandler.END


# /delete; удаление данных пользователя из userdata.json
async def delete_user_data_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            TEXT["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            TEXT["reply_delete_dialog"],
            constants.ParseMode.MARKDOWN,
        )
        return "delete_dialog"


async def delete_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    access_token = await strava.get_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    await strava.deauthorize(access_token)
    USER_DB.remove(USER_QUERY["user_id"] == user_id)
    await update.message.reply_text(
        TEXT["reply_deleted"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Список последних тренировок
async def show_activities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        user_id = str(update.message.from_user.id)
    elif update.callback_query:
        user_id = str(update.callback_query.from_user.id)

    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await context.bot.send_message(
            user_id,
            TEXT["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    access_token = await strava.get_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    context.user_data["access_token"] = access_token
    page = context.user_data["page"] = 1
    activity_list = await strava.get_activities(access_token, page, PER_PAGE)

    inline_keys = [
        [
            InlineKeyboardButton(TEXT["key_prev"], callback_data="PrevPage"),
            InlineKeyboardButton(TEXT["key_refresh"], callback_data="Refresh"),
            InlineKeyboardButton(TEXT["key_next"], callback_data="NextPage"),
        ]
    ]
    for activity in activity_list:
        inline_keys.insert(-1, [InlineKeyboardButton(TEXT["key_activity"].format(activity["name"], activity["date"]), callback_data=activity["id"])])
    inline_keyboard = InlineKeyboardMarkup(inline_keys)

    if update.message:
        await update.message.reply_text(
            TEXT["reply_activities_shown"],
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            TEXT["reply_activities_shown"],
            constants.ParseMode.MARKDOWN,
            reply_markup=inline_keyboard,
        )

    return "activities_shown"


async def refresh_activities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    access_token = context.user_data["access_token"]
    page = context.user_data["page"]
    activity_list = await strava.get_activities(access_token, page, PER_PAGE)

    # зачем здесь дублирование вывода клавиатуры?
    # await update.callback_query.edit_message_reply_markup(reply_markup=None)
    await update.callback_query.edit_message_reply_markup(reply_markup=KeyboardFormatter.format_list_keyboard(activity_list, TEXT))
    return "activities_shown"


async def show_next_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    access_token = context.user_data["access_token"]
    page = context.user_data["page"]
    page = context.user_data["page"] = page + 1
    activity_list = await strava.get_activities(access_token, page, PER_PAGE)

    inline_keys = [
        [
            InlineKeyboardButton(TEXT["key_prev"], callback_data="PrevPage"),
            InlineKeyboardButton(TEXT["key_refresh"], callback_data="Refresh"),
            InlineKeyboardButton(TEXT["key_next"], callback_data="NextPage"),
        ]
    ]
    for activity in activity_list:
        inline_keys.insert(-1, [InlineKeyboardButton(TEXT["key_activity"].format(activity["name"], activity["date"]), callback_data=activity["id"])])
    inline_keyboard = InlineKeyboardMarkup(inline_keys)

    await update.callback_query.edit_message_reply_markup(reply_markup=None)
    await update.callback_query.edit_message_reply_markup(reply_markup=inline_keyboard)
    return "activities_shown"


async def show_prev_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    access_token = context.user_data["access_token"]
    page = context.user_data["page"]
    page = context.user_data["page"] = page - 1 if page > 1 else 1
    activity_list = await strava.get_activities(access_token, page, PER_PAGE)

    inline_keys = [
        [
            InlineKeyboardButton(TEXT["key_prev"], callback_data="PrevPage"),
            InlineKeyboardButton(TEXT["key_refresh"], callback_data="Refresh"),
            InlineKeyboardButton(TEXT["key_next"], callback_data="NextPage"),
        ]
    ]
    for activity in activity_list:
        inline_keys.insert(-1, [InlineKeyboardButton(TEXT["key_activity"].format(activity["name"], activity["date"]), callback_data=activity["id"])])
    inline_keyboard = InlineKeyboardMarkup(inline_keys)

    await update.callback_query.edit_message_reply_markup(reply_markup=None)
    await update.callback_query.edit_message_reply_markup(reply_markup=inline_keyboard)
    return "activities_shown"


async def show_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    activity_id = update.callback_query.data
    context.user_data["activity_id"] = activity_id
    access_token = context.user_data["access_token"]
    activity = await strava.get_activity(access_token, activity_id)

    await update.callback_query.edit_message_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_shown"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


# Публикация тренировки
async def upload_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)

    if not strava.user_exists(user_id, USER_DB, USER_QUERY):
        await update.message.reply_text(
            TEXT["reply_unknown"],
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    refresh_token = USER_DB.get(USER_QUERY["user_id"] == user_id)["refresh_token"]
    access_token = await strava.get_access_token(user_id, CLIENT_ID, CLIENT_SECRET, refresh_token, USER_DB, USER_QUERY)
    context.user_data["access_token"] = access_token
    name = update.message.caption
    data_type = str.split(update.message.document.file_name, ".")[-1]
    file_data = await context.bot.get_file(update.message.document.file_id)
    file = requests.get(file_data.file_path).content
    upload_id = await strava.post_activity(access_token, name, data_type, file)
    upload = await strava.get_upload(upload_id, access_token)

    activity_id = upload["activity_id"]
    context.user_data["activity_id"] = activity_id
    if activity_id:
        activity = await strava.get_activity(access_token, activity_id)

        await update.message.reply_text(
            KeyboardFormatter.format_activity_data(TEXT["reply_activity_uploaded"], URL["activity"], activity),
            constants.ParseMode.MARKDOWN,
            reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
        )
        return "activity_shown"
    else:
        await update.message.reply_text(
            TEXT["reply_error"].format(str(upload["error"])),
            constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END


# Редактирование тренировки
async def change_name_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = str(update.callback_query.from_user.id)
    await context.bot.send_message(
        user_id,
        TEXT["reply_change_name"],
        constants.ParseMode.MARKDOWN,
    )
    return "change_name_dialog"


async def change_desc_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = str(update.callback_query.from_user.id)
    await context.bot.send_message(
        user_id,
        TEXT["reply_change_desc"],
        constants.ParseMode.MARKDOWN,
    )
    return "change_desc_dialog"


async def change_type_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    await update.callback_query.edit_message_text(
        TEXT["reply_change_type"],
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_type_keyboard(TEXT),
    )
    return "change_type_dialog"


async def change_gear_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    access_token = context.user_data["access_token"]
    gear_list = await strava.get_gear(access_token)
    inline_keys = []
    for gear in gear_list:
        inline_keys.append(
            [
                InlineKeyboardButton(f"{gear['type']} {gear['name']}", callback_data=gear["id"]),
            ]
        )
    inline_keyboard = InlineKeyboardMarkup(inline_keys)
    await update.callback_query.edit_message_text(
        TEXT["reply_change_gear"],
        constants.ParseMode.MARKDOWN,
        reply_markup=inline_keyboard,
    )
    return "change_gear_dialog"


async def change_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    name = update.message.text
    await strava.update_activity(access_token, activity_id, name=name)
    activity = await strava.get_activity(access_token, activity_id)

    await update.message.reply_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_updated"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


async def change_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    description = update.message.text
    await strava.update_activity(access_token, activity_id, description=description)
    activity = await strava.get_activity(access_token, activity_id)

    await update.message.reply_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_updated"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


async def change_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    sport_type = update.callback_query.data
    await strava.update_activity(access_token, activity_id, sport_type=sport_type)
    activity = await strava.get_activity(access_token, activity_id)

    await update.callback_query.edit_message_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_updated"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


async def change_gear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    access_token = context.user_data["access_token"]
    activity_id = context.user_data["activity_id"]
    gear_id = update.callback_query.data
    await strava.update_activity(access_token, activity_id, gear_id=gear_id)
    activity = await strava.get_activity(access_token, activity_id)

    await update.callback_query.edit_message_text(
        KeyboardFormatter.format_activity_data(TEXT["reply_activity_updated"], URL["activity"], activity),
        constants.ParseMode.MARKDOWN,
        reply_markup=KeyboardFormatter.format_edit_keyboard(TEXT),
    )
    return "activity_shown"


# /help; справка
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        TEXT["reply_help"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# /cancel; отмена диалога ConversationHandler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        TEXT["reply_canceled"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Обработка прочих сообщений
async def other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        TEXT["reply_other"],
        constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


def main():
    application = ApplicationBuilder().token(TOKEN).build()

    delete_entry = CommandHandler("delete", delete_user_data_dialog)
    list_entry = CommandHandler("activities", show_activities)
    file_entry = MessageHandler(
        filters.Document.FileExtension("fit") | filters.Document.FileExtension("tcx") | filters.Document.FileExtension("gpx"), upload_activity
    )
    cancel_fallback = CommandHandler("cancel", cancel)
    start_reply = CommandHandler("start", start)
    help_reply = CommandHandler("help", help)
    other_reply = MessageHandler(
        ~filters.COMMAND & ~filters.Document.FileExtension("fit") & ~filters.Document.FileExtension("tcx") & ~filters.Document.FileExtension("gpx"), other
    )

    activity_dialog = ConversationHandler(
        entry_points=[
            list_entry,
            file_entry,
        ],
        states={
            "activities_shown": [
                CallbackQueryHandler(show_activity, pattern="^\\d+$"),
                CallbackQueryHandler(refresh_activities, pattern="Refresh"),
                CallbackQueryHandler(show_next_page, pattern="NextPage"),
                CallbackQueryHandler(show_prev_page, pattern="PrevPage"),
            ],
            "activity_shown": [
                CallbackQueryHandler(show_activities, pattern="List"),
                CallbackQueryHandler(change_name_dialog, pattern="Chname"),
                CallbackQueryHandler(change_desc_dialog, pattern="Chdesc"),
                CallbackQueryHandler(change_type_dialog, pattern="Chtype"),
                CallbackQueryHandler(change_gear_dialog, pattern="Chgear"),
            ],
            "change_name_dialog": [MessageHandler(~filters.COMMAND & filters.TEXT, change_name)],
            "change_desc_dialog": [MessageHandler(~filters.COMMAND & filters.TEXT, change_desc)],
            "change_type_dialog": [CallbackQueryHandler(change_type, pattern="Swim|Ride|Run")],
            "change_gear_dialog": [CallbackQueryHandler(change_gear, pattern="^\\w\\d+$")],
        },
        fallbacks=[
            cancel_fallback,
            list_entry,
            file_entry,
            delete_entry,
        ],
    )

    delete_dialog = ConversationHandler(
        entry_points=[
            delete_entry,
        ],
        states={
            "delete_dialog": [CommandHandler("delete", delete_user_data)],
        },
        fallbacks=[
            cancel_fallback,
            list_entry,
            file_entry,
            delete_entry,
        ],
    )

    application.add_handlers(
        [
            activity_dialog,
            delete_dialog,
            start_reply,
            help_reply,
            other_reply,
        ]
    )

    application.run_polling()


if __name__ == "__main__":
    main()
