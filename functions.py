import re
from aiogram import types, BaseMiddleware
from aiogram.fsm.state import State, StatesGroup
from email_validator import validate_email, EmailNotValidError

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
    
class Booking(StatesGroup):
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
    email_for_view = State()
    email_for_cancel = State()
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

def print_summary(data):
    day_of_week = data["date"].strftime("%A")
    return (
            f"Booking Details\n"
            f"================\n"
            f"Facility: {data['facility']}\n"
            f"Date: {data["date"].strftime("%d/%m/%Y")} ({day_of_week})\n"
            f"Start time: {data['start_time']}\n"
            f"End time: {data['end_time']}\n"
            f"Email: {data['email']}\n"
            f"Name: {data['name']}\n"
            f"Contact Number: {data['contact_number']}\n"
    )
