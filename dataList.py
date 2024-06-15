from aiogram import types

facility_list = [
    "Multi-Purpose Hall",
    "Basketball Court",
    "Football Field",
    "Swimming Pool"
]

commands = [
    types.BotCommand(command="/start", description="Start the bot"),
    types.BotCommand(command="/new_booking", description="Create new booking"),
    types.BotCommand(command="/view_booking", description="View your booking"),
    types.BotCommand(command="/cancel_booking", description="Cancel your booking"),
    types.BotCommand(command="/help", description="Get help"),
    types.BotCommand(command="/about", description="About the bot"),
    types.BotCommand(command="/end", description="End the bot")
]