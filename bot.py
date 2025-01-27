import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import BotCommand, Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import Command
from asyncio import run
import psycopg2
import pandas as pd
import django
from asgiref.sync import sync_to_async

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from base.models import Company

BOT_TOKEN = "7769778979:AAFNG8nuj0m2rbWbJFHz8Jb2-FHS_Bv5qIc"
DB_CONFIG = {"dbname": "avtolider", "user": "postgres", "password": "8505", "host": "localhost", "port": "5432"}

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

months = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

keyboards = {
    "main": ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Регистрация")]],
        resize_keyboard=True
    ),
    "months": ReplyKeyboardMarkup(
        keyboard=[ 
            [KeyboardButton(text=m) for m in months[i:i+3]] for i in range(0, 12, 3)
        ] + [[KeyboardButton(text="Главное меню")]],
        resize_keyboard=True
    ),
    "registration_complete": ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Накладные")],
            [
                KeyboardButton(text="📊Акт Сверка (СУМ)"),
                KeyboardButton(text="📊Акт Сверка (USD)"),
                KeyboardButton(text="☎️Контакты")
            ],
            [KeyboardButton(text="📜О компании")]
        ],
        resize_keyboard=True
    ),
    "request_contact": ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True
    ),
}

async def export_to_excel(month_name):
    try:
        logging.info(f"Exporting data for month: {month_name}")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        month_index = months.index(month_name) + 1
        cursor.execute(
            "SELECT * FROM base_product WHERE EXTRACT(MONTH FROM created_at) = %s",
            [month_index]
        )
        data = cursor.fetchall()
        cursor.close()
        conn.close()

        if data:
            df = pd.DataFrame(data, columns=["ID", "Description", "Amount", "Price", "CreatedAt", "Month", "TotalAmount"])
            
            if "CreatedAt" in df.columns:
                df["CreatedAt"] = pd.to_datetime(df["CreatedAt"]).dt.tz_localize(None)

            file_path = f"накладные_{month_name.lower()}.xlsx"
            df.to_excel(file_path, index=False)
            logging.info(f"Data exported successfully: {file_path}")
            return file_path
        logging.warning("No data found for the selected month.")
        return None
    except Exception as e:
        logging.error(f"Error exporting data: {e}")
        return None


def normalize_phone_number(phone_number):
    phone_number = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if phone_number.startswith("998"):
        phone_number = "+" + phone_number
    elif not phone_number.startswith("+998"):
        phone_number = "+998" + phone_number.lstrip("5789")
    return phone_number


@sync_to_async
def check_company(phone_number, telegram_id):
    logging.info(f"Checking company for phone number: {phone_number}")

    try:
        company = Company.objects.get(phone_number=phone_number)
        company.telegram_id = telegram_id
        company.save()
        logging.info(f"Telegram ID updated for company: {company.name}")
        return company
    except Company.DoesNotExist:
        logging.warning(f"Company with phone number {phone_number} not found.")
        return None



async def menu_handler(message: Message):
    logging.info(f"Menu handler triggered with text: {message.text}")
    if message.text == "Регистрация":
        await message.answer("Пожалуйста, отправьте свой номер телефона.", reply_markup=keyboards["request_contact"])
    elif message.text == "Накладные":
        await message.answer("Выберите месяц:", reply_markup=keyboards["months"])
    elif message.text == "Главное меню":
        await message.answer("Выберите действие:", reply_markup=keyboards["registration_complete"])

async def handle_contact(message: Message):
    if message.contact:
        phone_number = normalize_phone_number(message.contact.phone_number)
        logging.info(f"Received phone number: {phone_number}")

        company = await check_company(phone_number, message.from_user.id)

        if company:
            await message.answer(
                f"Ваш номер {phone_number} успешно зарегистрирован. Добро пожаловать!",
                reply_markup=keyboards["registration_complete"]
            )
        else:
            await message.answer(
                "Ваш номер телефона не найден в базе данных. Пожалуйста, свяжитесь с администрацией."
            )


async def month_handler(message: Message):
    logging.info(f"Month handler triggered with text: {message.text}")
    file_path = await export_to_excel(message.text)
    if file_path:
        await message.answer_document(document=FSInputFile(file_path))
        os.remove(file_path)
    else:
        await message.reply("Произошла ошибка при экспорте данных или данные отсутствуют.")

async def help_handler(message: Message):
    logging.info("Help command triggered.")
    await message.answer(
        "Это бот для регистрации и экспорта данных.\n"
        "Доступные команды:\n"
        "/start - Запустить бота\n"
        "/help - Получить помощь\n"
        "Вы также можете использовать кнопки для взаимодействия."
    )

async def start():
    logging.info("Starting bot...")
    await bot.set_my_commands([ 
        BotCommand(command="/start", description="Запустить бота"), 
        BotCommand(command="/help", description="Помощь!"), 
    ])

    dp.message.register(
        lambda msg: msg.answer("Добро пожаловать!", reply_markup=keyboards["main"]),
        Command("start")
    )
    dp.message.register(help_handler, Command("help"))
    dp.message.register(menu_handler, F.text.in_(["Накладные", "Главное меню", "Регистрация"]))
    dp.message.register(handle_contact, F.contact)
    dp.message.register(month_handler, F.text.in_(months))

    await dp.start_polling(bot)

if __name__ == "__main__":
    run(start())
