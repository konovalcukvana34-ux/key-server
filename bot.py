import os, json, time, datetime, requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8682336617:AAEex2v172iD0mgrBAP7hdSSB46gHVq6xGk"
SERVER = "https://web-production-24b86.up.railway.app"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")
ADMIN_IDS = os.environ.get("ADMIN_IDS", "835673342").split(",")  # твой Telegram ID

def is_admin(update: Update):
    return str(update.effective_user.id) in ADMIN_IDS

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    await update.message.reply_text(
        "🔑 *AutoSell Key Manager*\n\n"
        "Команды:\n"
        "/add1 — ключ на 1 день\n"
        "/add7 — ключ на 7 дней\n"
        "/add30 — ключ на 30 дней\n"
        "/add <дни> <заметка> — ключ на N дней\n"
        "/list — список всех ключей\n"
        "/disable <ключ> — отключить ключ\n"
        "/reset <ключ> — сбросить HWID\n",
        parse_mode="Markdown"
    )

async def add_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE, days: int, note: str = ""):
    if not is_admin(update): return
    r = requests.post(f"{SERVER}/admin/add", json={
        "password": ADMIN_PASSWORD, "days": days, "note": note
    })
    data = r.json()
    key = data["key"]
    exp = data["expires"]
    await update.message.reply_text(
        f"✅ *Ключ создан на {days} дн.*\n\n"
        f"`{key}`\n\n"
        f"📅 Истекает: *{exp}*\n"
        f"📝 Заметка: {note or '—'}\n\n"
        f"Покупатель вводит в игре:\n`/key {key}`",
        parse_mode="Markdown"
    )

async def add1(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = " ".join(ctx.args) if ctx.args else ""
    await add_key(update, ctx, 1, note)

async def add7(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = " ".join(ctx.args) if ctx.args else ""
    await add_key(update, ctx, 7, note)

async def add30(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    note = " ".join(ctx.args) if ctx.args else ""
    await add_key(update, ctx, 30, note)

async def add_custom(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Использование: /add <дни> <заметка>")
        return
    days = int(ctx.args[0])
    note = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else ""
    await add_key(update, ctx, days, note)

async def list_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    r = requests.post(f"{SERVER}/admin/list", json={"password": ADMIN_PASSWORD})
    keys = r.json()
    if not keys:
        await update.message.reply_text("Ключей нет.")
        return
    lines = []
    for k, v in keys.items():
        status = "✅" if v.get("active") else "❌"
        days_left = v.get("days_left", 0)
        exp = v.get("expires_str", "?")
        hwid = "привязан" if v.get("hwid") else "свободен"
        note = v.get("note", "")
        lines.append(f"{status} `{k}`\n  📅 {exp} (осталось {days_left}д) | HWID: {hwid}" + (f" | {note}" if note else ""))
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

async def disable(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not ctx.args:
        await update.message.reply_text("Использование: /disable <ключ>")
        return
    key = ctx.args[0].upper()
    r = requests.post(f"{SERVER}/admin/disable", json={"password": ADMIN_PASSWORD, "key": key})
    if r.json().get("ok"):
        await update.message.reply_text(f"❌ Ключ `{key}` отключён.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Ключ не найден.")

async def reset_hwid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not ctx.args:
        await update.message.reply_text("Использование: /reset <ключ>")
        return
    key = ctx.args[0].upper()
    r = requests.post(f"{SERVER}/admin/reset_hwid", json={"password": ADMIN_PASSWORD, "key": key})
    if r.json().get("ok"):
        await update.message.reply_text(f"🔄 HWID сброшен для `{key}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Ключ не найден.")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add1", add1))
app.add_handler(CommandHandler("add7", add7))
app.add_handler(CommandHandler("add30", add30))
app.add_handler(CommandHandler("add", add_custom))
app.add_handler(CommandHandler("list", list_keys))
app.add_handler(CommandHandler("disable", disable))
app.add_handler(CommandHandler("reset", reset_hwid))

print("Бот запущен!")
app.run_polling()
