import re, os, json, gspread, uuid
from aiogram import types, BaseMiddleware
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from email_validator import validate_email, EmailNotValidError
from dotenv import load_dotenv

load_dotenv()

ADMIN_USERS = json.loads(os.getenv("ADMIN_USERS"))
GSHEET_KEY_ID = os.getenv("GSHEET_KEY_ID")
gSheet_credentials = json.loads(os.getenv("GSHEET_CREDENTIALS"))


class AccessControlMiddleware(BaseMiddleware):
    def __init__(self, allowed_users):
        super().__init__()
        self.allowed_users = allowed_users

    async def __call__(self, handler, event: types.Message, data):
        if event.from_user.id not in self.allowed_users:
            print(
                f"Unauthorized access denied for {event.from_user.username} with ID of: {event.from_user.id}"
            )
            await event.answer(f"You are not authorized to use this bot.")
            return
        return await handler(event, data)

class NewBooking(StatesGroup):
    user_id = State()
    facility = State()
    date = State()
    start_time = State()
    end_time = State()
    time_period = State()
    email = State()
    name = State()
    contact_number = State()
    confirmation = State()

class BroadcastMessage(StatesGroup):
    user_id = State()
    message = State()
    confirmation = State()

class ViewBooking(StatesGroup):
    user_id = State()
    email = State()

class CancelBooking(StatesGroup):
    user_id = State()
    email = State()
    booking_to_cancel = State()

def is_valid_time_format(time_str):
    if len(time_str) != 4:
        return None
    try:
        hours = int(time_str[:2])
        minutes = int(time_str[2:])
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return True
        else:
            return False
    except ValueError:
        return False

def is_valid_contact_number(contact_number):
    if re.match(r"^[3689]\d{7}$", contact_number):
        return True
    else:
        return False

def is_valid_email(email):
    try:
        # Validate.
        v = validate_email(email)
        # Replace with normalized form.
        email = v["email"]
        return True
    except EmailNotValidError as e:
        # Email is not valid, exception message is human-readable
        print(str(e))
        return False

async def send_booking_data_to_sheet(data):
    gc = gspread.service_account_from_dict(gSheet_credentials)
    sh = gc.open_by_key(GSHEET_KEY_ID)
    worksheet = sh.worksheet("Booking_Details")
    new_booking = [str(uuid.uuid4()), data['facility'], data['date'].strftime("%m/%d/%Y"), data['start_time'].strftime("%H:%M"),
                   data['end_time'].strftime("%H:%M"), data['time_period'],  data['email'], data['name'], data['contact_number']]
    worksheet.append_row(new_booking, value_input_option="USER_ENTERED")
    print(new_booking)

async def reply_keyboard(message, text, buttons, one_time=True):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=btn) for btn in row] for row in buttons],
        resize_keyboard=True,
        one_time_keyboard=one_time
    )
    await message.reply(text, reply_markup=keyboard)

async def admin_menu(message):
    await reply_keyboard(message, "Welcome Admin! What would you like to do?", [
        ["New Booking"],
        ["View Booking"],
        ["Broadcast Message"]
    ])

async def user_menu(message):
    await reply_keyboard(message, "What would you like to do?", [
        ["New Booking"],
        ["View Booking"]
    ])

def print_summary(data):
    day_of_week = data["date"].strftime("%A")
    date = data['date'].strftime("%d/%m/%Y")
    return (
            f"Booking Details\n"
            f"================\n"
            f"Facility: {data['facility']}\n"
            f"Date: {date} ({day_of_week})\n"
            f"Start time: {data['start_time']}\n"
            f"End time: {data['end_time']}\n"
            f"Email: {data['email']}\n"
            f"Name: {data['name']}\n"
            f"Contact Number: {data['contact_number']}\n"
    )

def is_admin(user_id):
    for key in ADMIN_USERS.keys():
        key = int(key)
        if user_id == key:
            return True
    return False

def get_admin_id_username(user_id):
    for key, value in ADMIN_USERS.items():
        key = int(key)
        if user_id == key:
            admin_id = key
            admin_name = value
    return admin_id, admin_name

def all_admin_id():
    admin_id_list = []
    for key in ADMIN_USERS.keys():
        admin_id_list.append(int(key))
    return admin_id_list




