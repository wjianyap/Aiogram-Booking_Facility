import asyncio, logging, sys, os, gspread, json, uuid
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
from aiogram.filters import Command

from functions import (AccessControlMiddleware, NewBooking, BroadcastMessage, ViewBooking, CancelBooking, is_valid_time_format, is_valid_contact_number, 
                       is_valid_email, reply_keyboard, admin_menu, user_menu, print_summary, is_admin, get_admin_id_username, all_admin_id, send_booking_data_to_sheet)
from dataList import facility_list, commands

load_dotenv()
booking_requests = {}

TOKEN_API = os.getenv("TOKEN_API")
GSHEET_KEY_ID = os.getenv("GSHEET_KEY_ID")
ALLOWED_USERS = json.loads(os.environ['ALLOWED_USERS'])
gSheet_credentials = json.loads(os.getenv("GSHEET_CREDENTIALS"))

bot = Bot(token=TOKEN_API)
dp = Dispatcher()

dp.message.middleware(AccessControlMiddleware(ALLOWED_USERS))

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    if is_admin(message.from_user.id):
        await admin_menu(message)
    else:
        await user_menu(message)

@dp.message(lambda message: "broadcast message" in message.text.lower())
async def broadcast_message_input(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.reply("You are not authorized to broadcast messages.")
        await start_handler(message)
        return
    await state.update_data(user_id=message.from_user.id)
    await state.set_state(BroadcastMessage.message)
    await message.reply("Please enter the message you would like to broadcast to all users") 

@dp.message(BroadcastMessage.message)
async def broadcast_message_confirmation(message: types.Message, state: FSMContext):
    await state.update_data(message=message.text)
    await state.set_state(BroadcastMessage.confirmation)
    await reply_keyboard(message, f"Broadcast message: {message.text}\n\nConfirm broadcast?", [["Yes", "No"]])

@dp.message(lambda message: message.text.lower() == "yes", BroadcastMessage.confirmation)
async def broadcast_message_confirmation_positive(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if is_admin(message.from_user.id):
        for user_id in ALLOWED_USERS:
            admin_name = get_admin_id_username(message.from_user.id)[1]
            await bot.send_message(user_id, f"Broadcasted Message from {admin_name}:\n {data['message']}")
    else:
        await message.reply("You are not authorized to broadcast messages.")
    await state.clear()
    await start_handler(message)

@dp.message(lambda message: "new booking" in message.text.lower())
async def newBooking(message: types.Message, state: FSMContext):
    facility_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=facility) for facility in facility_list[i : i + 3]]
            for i in range(0, len(facility_list), 3)
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await state.update_data(user_id=message.from_user.id)
    await state.set_state(NewBooking.facility)
    await message.reply("Which facility would you like to book?", reply_markup=facility_kb)

@dp.message(NewBooking.facility)
async def newBooking_facility(message: types.Message, state: FSMContext):
    await state.update_data(facility=message.text)
    await state.set_state(NewBooking.date)
    await message.answer("Please select the date of booking",reply_markup=await SimpleCalendar().start_calendar())

@dp.callback_query(SimpleCalendarCallback.filter(), NewBooking.date)
async def newBooking_date(call: CallbackQuery, callback_data: dict, state: FSMContext):
    calendar = SimpleCalendar()
    calendar.set_dates_range(datetime.now() - timedelta(days=1), datetime(2024, 12, 31))
    selected, date = await calendar.process_selection(call, callback_data)
    if selected:
        await state.update_data(date=date)
        await state.set_state(NewBooking.start_time)
        await call.message.reply(f'You selected {date.strftime("%d/%m/%Y")}. \nPlease enter the start time of booking (hhmm)')

@dp.message(NewBooking.start_time)
async def newBooking_startTime(message: types.Message, state: FSMContext):
    data = await state.get_data()
    print(datetime.now().date(), type(datetime.now().date()))
    if is_valid_time_format(message.text):
        data['start_time'] = datetime.strptime(message.text, "%H%M").time()
        if data['date'].date() == datetime.now().date() and data['start_time'] < datetime.now().time():
            await message.reply(f"Invalid time!\n"
                                f"Start time cannot be before the current time. "
                                f"Please enter the start time of booking (hhmm)")
            return

        await state.update_data(start_time=data['start_time'])
        await state.set_state(NewBooking.end_time)
        await message.reply("Please enter the end time of booking (hhmm)")
    else:
        await message.reply("Invalid time format. Please enter the start time of booking (hhmm)")


@dp.message(NewBooking.end_time)
async def newBooking_endTime(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if is_valid_time_format(message.text):
        data['end_time'] = datetime.strptime(message.text, "%H%M").time()
        if data['end_time'] <= data['start_time']:
                await message.reply("End time cannot be before the start time or the same as the start time. Please re-enter the end time.")
                return

        await state.update_data(end_time=data['end_time'])
        await state.update_data(time_period=f"{data['start_time'].strftime("%H:%M")}-{data['end_time'].strftime("%H:%M")}")
        await state.set_state(NewBooking.time_period)
        await state.set_state(NewBooking.email)

        for values in existing_booking[1:]:
            if data["facility"] == values[1] and data['date'].strftime("%m/%d/%Y") == values[2]:
                if data["start_time"] < datetime.strptime(values[4], "%H:%M").time() and data['end_time'] > datetime.strptime(values[3], "%H:%M").time():
                    await message.reply(f"{data['facility']} has been already booked by {values[7]} on {values[2]}, from {values[3]} to {values[4]}. Please select another time slot.")
                    await state.set_state(NewBooking.date)
                    await message.reply("Please select another date or time of booking", reply_markup=await SimpleCalendar().start_calendar())
                    return
        await message.reply("Please enter your email")
    else:
        await message.reply("Invalid time format. Please enter the end time of booking (hhmm)")

@dp.message(NewBooking.email)
async def newBooking_email(message: types.Message, state: FSMContext):
    if is_valid_email(message.text):
        await state.update_data(email=message.text)
        await state.set_state(NewBooking.name)
        await message.reply("Please enter your name")
    else:
        await message.reply("Invalid email. Please enter a valid email") 

@dp.message(NewBooking.name)
async def newBooking_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(NewBooking.contact_number)
    await message.reply("Please enter your contact number (+65)")

@dp.message(NewBooking.contact_number)
async def newBooking_contactNumber(message: types.Message, state: FSMContext):
    if is_valid_contact_number(message.text):
        await state.update_data(contact_number=message.text)
        data = await state.get_data()
        await state.set_state(NewBooking.confirmation)
        await message.reply(print_summary(data)+"\nConfirm booking?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Yes"), KeyboardButton(text="No")]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
    else:
        await message.reply("Invalid contact number. Please enter a valid contact number")

@dp.message(lambda message: message.text.lower() == "yes", NewBooking.confirmation)
async def newBooking_confirmation(message: types.Message, state: FSMContext):
    data = await state.get_data() 
    booking_id = str(uuid.uuid4())
    booking_requests[booking_id] = {"data": data, "processed": False, "message_ids": {}}
    booking_request = (f"New booking request:\n\n"+print_summary(data)+"\n\n")

    if not is_admin(message.from_user.id):
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Approve", callback_data=f"approve_{booking_id}"),
            InlineKeyboardButton(text="Reject", callback_data=f"reject_{booking_id}")],
        ])

        for admin_id in all_admin_id():
            try:
                sent_message = await bot.send_message(admin_id, booking_request, reply_markup=inline_kb)
                booking_requests[booking_id]["message_ids"][admin_id] = sent_message.message_id
            except Exception as e:
                logging.error(f"Error sending message to admin {admin_id}: {e}")

        await message.reply(f"Your booking request has been sent for approval. You will be notified once it is reviewed.\n\n"+print_summary(data))
    else:
        try:
            sent_message = await bot.send_message(data['user_id'], "Your booking request has been approved.")
            await send_booking_data_to_sheet(data)
        except Exception as e:
            logging.error(f"Error sending message to user {data['user_id']}: {e}")  
    
    await state.clear()
    await start_handler(message) 

@dp.callback_query(lambda c: c.data.startswith('approve_'))
async def newBooking_approve(callback_query: CallbackQuery):
    booking_id = callback_query.data.split("_")[1]
    booking_requests[booking_id]["processed"] = True
    await bot.send_message(booking_requests[booking_id]["data"]['user_id'], f"Your booking request has been approved by {get_admin_id_username(callback_query.from_user.id)[1]}.\n\n{print_summary(booking_requests[booking_id]['data'])}")  
    await send_booking_data_to_sheet(booking_requests[booking_id]["data"])

    for admin_id in all_admin_id():
        try:
            await bot.edit_message_reply_markup(admin_id, booking_requests[booking_id]["message_ids"][admin_id])
            await bot.send_message(admin_id, f"Booking request approved by {get_admin_id_username(callback_query.from_user.id)[1]} for {booking_requests[booking_id]['data']['name']}.\n\n{print_summary(booking_requests[booking_id]['data'])}")
        except Exception as e:
            logging.error(f"Error editing message for admin {admin_id}: {e}")

@dp.callback_query(lambda c: c.data.startswith('reject_'))
async def newBooking_reject(callback_query: CallbackQuery):
    booking_id = callback_query.data.split("_")[1]
    booking_requests[booking_id]["processed"] = True
    await bot.send_message(booking_requests[booking_id]["data"]['user_id'], f"Your booking request has been rejected by {get_admin_id_username(callback_query.from_user.id)[1]}.\n\n{print_summary(booking_requests[booking_id]['data'])}")
    for admin_id in all_admin_id():
        try:
            await bot.edit_message_reply_markup(admin_id, booking_requests[booking_id]["message_ids"][admin_id])
            await bot.send_message(admin_id, f"Booking request approved by {get_admin_id_username(callback_query.from_user.id)[1]} for {booking_requests[booking_id]['data']['name']}.\n\n{print_summary(booking_requests[booking_id]['data'])}")
        except Exception as e:
            logging.error(f"Error editing message for admin {admin_id}: {e}")

@dp.message(lambda message: message.text.lower() == "no", NewBooking.confirmation)
async def newBooking_confirmation_negative(message: types.Message, state: FSMContext):
    await state.clear()
    await start_handler(message)

@dp.message(lambda message: "view booking" in message.text.lower())
async def viewBooking_emailInput(message: types.Message, state: FSMContext):
    await state.set_state(ViewBooking.email)
    await message.reply(f'Please enter your email to view your booking')

@dp.message(ViewBooking.email)
async def viewBooking_emailProcessing(message: types.Message, state: FSMContext):
    email = message.text
    if not is_valid_email(email):
        await message.reply("Invalid email. Please enter a valid email")
        return
    
    user_bookings = [row for row in existing_booking[1:] if row[6] == email]  
    if not user_bookings:
        await message.reply("No bookings found for this email.")
    else:
        booking_details = "\n\n".join([
            f"Facility: {row[1]}\nDate: {row[2]}\nStart Time: {row[3]}\nEnd Time: {row[4]}\nEmail: {row[6]}\nName: {row[7]}\nContact Number: {row[8]}"
            for row in user_bookings
        ])
        await message.reply(f"Your bookings:\n\n{booking_details}")
    
    await state.clear()
    await start_handler(message)
    
@dp.message(lambda message: "cancel booking" in message.text.lower())
async def cancelBooking_emailInput(message: types.Message, state: FSMContext):
    await state.set_state(CancelBooking.email)
    await message.reply("Please enter your email to view and cancel your bookings")

@dp.message(CancelBooking.email)
async def cancelBooking_emailProcessing(message: types.Message, state: FSMContext):
    email = message.text
    if not is_valid_email(email):
        await message.reply("Invalid email. Please enter a valid email")
        return
    existing_booking = worksheet.get_all_values()
    user_bookings = [row for row in existing_booking[1:] if row[6] == email]
    if not user_bookings:
        await message.reply("No bookings found for this email.")
        await state.clear()
        await start_handler(message)
        return
    
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"Cancel {row[1]} on {row[2]} from {row[3]} to {row[4]}")]for row in user_bookings],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await state.update_data(email=email)
    await state.set_state(CancelBooking.booking_to_cancel)
    await message.reply("Select a booking to cancel:", reply_markup=cancel_kb)

@dp.message(CancelBooking.booking_to_cancel)
async def cancelBooking_bookingToCancel(message: types.Message, state: FSMContext):
    try:
        selected_booking = message.text.replace("Cancel ", "").split(" on ")
        facility = selected_booking[0]
        date_time = selected_booking[1].split(" from ")
        date = date_time[0]
        start_end_time = date_time[1].split(" to ")
        start_time = start_end_time[0].replace(" ", "")
        end_time = start_end_time[1].replace(" ", "")
    except (IndexError, ValueError):
        await message.reply("Invalid format. Please select a booking to cancel from the list.")
        return

    email = (await state.get_data()).get('email')
    booking_found = False
    
    for i, row in enumerate(existing_booking):
        if (    
            row[1] == facility and row[2] == date and row[3] == start_time and row[4] == end_time and row[6] == email
        ):
            worksheet.delete_rows(i + 1)
            existing_booking.pop(i)
            booking_found = True
            break
    
    if booking_found:
        await message.reply(f"Booking for {facility} on {date} from {start_time} to {end_time} has been cancelled.")
    else:
        await message.reply("Failed to cancel the booking. Please try again.")
    
    await state.clear()
    await start_handler(message)

async def help_handler(message: types.Message):
    await message.answer(f"This is the help handler")

async def about_handler(message: types.Message):
    await message.answer(f"This is the about handler")

async def end_handler(message: types.Message):
    await message.answer(
        f"Ending previous command...\n"
        f"Anything else I can do for you?\n\n"
        f"Please type /start to start again."
    )

async def main() -> None:
    global worksheet, existing_booking
    gc = gspread.service_account_from_dict(gSheet_credentials)
    sh = gc.open_by_key(GSHEET_KEY_ID)
    worksheet = sh.worksheet("Booking_Details")
    existing_booking = worksheet.get_all_values()
    logging.info("Existing bookings fetched and stored in memory")
    dp.message.register(broadcast_message_input, Command(commands=["broadcast_message"]))
    dp.message.register(newBooking, Command(commands=["new_booking"]))
    dp.message.register(viewBooking_emailInput, Command(commands=["view_booking"]))
    dp.message.register(cancelBooking_emailInput, Command(commands=["cancel_booking"]))
    dp.message.register(help_handler, Command(commands=["help"]))
    dp.message.register(about_handler, Command(commands=["about"]))
    dp.message.register(end_handler, Command(commands=["end"]))
    await bot.set_my_commands(commands)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main()) 