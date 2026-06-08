import os, json, time, datetime, requests, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "8682336617:AAEex2v172iD0mgrBAP7hdSSB46gHVq6xGk"
SERVER = "https://key-server-ppi9.onrender.com"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")
ADMIN_IDS = os.environ.get("ADMIN_IDS", "835673342").split(",")

def is_admin(update: Update):
    return str(update.effective_user.id) in ADMIN_IDS

def api(path, **kwargs):
    return requests.post(f"{SERVER}{path}", json={"password": ADMIN_PASSWORD, **kwargs}, timeout=10)

def fmt(n):
    """Форматирует число с разделителями: 1234567 → 1 234 567"""
    try:
        return f"{int(n):,}".replace(",", " ")
    except:
        return str(n)

# ── /help ─────────────────────────────────────────────────────────────────────

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    text = (
        "📖 *Справка по командам*\n\n"

        "━━━ 📊 *Статистика* ━━━\n"
        "/stats — статистика всех аккаунтов\n"
        "/stats monitor — только монитор\n"
        "/stats buyer — только байер\n"
        "/stats sellers — только продавцы\n\n"

        "━━━ 🎮 *Управление модом* ━━━\n"
        "/st `<цель>` `<команда>` — отправить команду\n\n"
        "Цели: `monitor`, `buyer`, `seller`, `sellers`, `all`, или ник игрока\n\n"
        "Примеры:\n"
        "`/st sellers start` — запустить всех продавцов\n"
        "`/st sellers stop` — остановить всех продавцов\n"
        "`/st sellers rate 50000` — курс продавцам\n"
        "`/st buyer start` — запустить байера\n"
        "`/st buyer stop` — остановить байера\n"
        "`/st buyer rate 45000` — мин. курс покупки\n"
        "`/st monitor start` — запустить монитор\n"
        "`/st all stop` — остановить всех\n\n"

        "━━━ 💰 *Продажа коинов с байера* ━━━\n"
        "/sell `<количество>` `<курс>` — продать коины с байера\n"
        "Пример: `/sell 500 55000` — продать 500 коинов по 55000\n\n"

        "━━━ 🔑 *Управление ключами* ━━━\n"
        "/add1 `[заметка]` — ключ на 1 день\n"
        "/add7 `[заметка]` — ключ на 7 дней\n"
        "/add30 `[заметка]` — ключ на 30 дней\n"
        "/add `<дни>` `[заметка]` — ключ на N дней\n"
        "/list — список всех ключей\n"
        "/disable `<ключ>` — отключить ключ\n"
        "/reset `<ключ>` — сбросить HWID привязку\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Нет доступа.")
        return
    await update.message.reply_text(
        "🤖 *AutoSell Manager*\n\n"
        "Используй /help для полного списка команд.",
        parse_mode="Markdown"
    )

# ── /stats ────────────────────────────────────────────────────────────────────

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return

    filter_role = ctx.args[0].lower() if ctx.args else None
    # sellers → seller
    if filter_role == "sellers": filter_role = "seller"

    try:
        r = api("/admin/accounts")
        data = r.json()
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return

    if not data:
        await update.message.reply_text("📭 Нет зарегистрированных аккаунтов.")
        return

    role_emoji = {"monitor": "👁", "buyer": "🛒", "seller": "💸"}
    lines = []

    for nick, acc in data.items():
        role = acc.get("role", "?")
        if filter_role and role != filter_role:
            continue

        online = acc.get("online", False)
        last_seen = acc.get("last_seen", 0)
        stats_data = acc.get("stats", {})

        status = "🟢 онлайн" if online else f"🔴 {last_seen}с назад"
        emoji = role_emoji.get(role, "❓")

        line = f"{emoji} *{nick}* [{role}] — {status}\n"

        if stats_data:
            running = stats_data.get("running", False)
            line += f"  {'▶️ запущен' if running else '⏹ остановлен'}\n"

            if role == "seller":
                cycles = stats_data.get("cycles", 0)
                coins = stats_data.get("coins_listed", 0)
                money = stats_data.get("money_sold", 0)
                rate = stats_data.get("rate", 0)
                balance = stats_data.get("balance", -1)
                line += f"  Курс: {fmt(rate)} | Циклов: {cycles}\n"
                line += f"  Коинов: {fmt(coins)} | Монет: {fmt(money)}\n"
                if balance >= 0:
                    line += f"  Баланс: {fmt(balance)} монет\n"

            elif role == "buyer":
                buys = stats_data.get("buys", 0)
                coins = stats_data.get("coins_bought", 0)
                money = stats_data.get("money_spent", 0)
                min_rate = stats_data.get("min_rate", 0)
                line += f"  Мин.курс: {fmt(min_rate)} | Покупок: {buys}\n"
                line += f"  Куплено: {fmt(coins)} коинов | {fmt(money)} монет\n"

            elif role == "monitor":
                signals = stats_data.get("signals", 0)
                line += f"  Сигналов: {signals}\n"

        lines.append(line)

    if not lines:
        await update.message.reply_text("Нет аккаунтов с такой ролью.")
        return

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ── /st — отправить команду в мод ─────────────────────────────────────────────

ROLE_COMMAND_MAP = {
    # /st sellers start → /sell start
    ("seller", "start"):  "/sell start",
    ("seller", "stop"):   "/sell stop",
    # /st buyer start → /autob start
    ("buyer", "start"):   "/autob start",
    ("buyer", "stop"):    "/autob stop",
    ("buyer", "monitor"): "/autob monitor",
    ("buyer", "buyer"):   "/autob buyer",
    # monitor
    ("monitor", "start"): "/autob monitor",
    ("monitor", "stop"):  "/autob stop",
}

async def st_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Использование: `/st <цель> <команда> [аргументы]`\n"
            "Пример: `/st sellers start`\n"
            "Смотри /help для полного списка.",
            parse_mode="Markdown"
        )
        return

    target = ctx.args[0].lower()
    sub = ctx.args[1].lower()
    extra = ctx.args[2] if len(ctx.args) > 2 else None

    # Определяем роль цели для маппинга команд
    role_of_target = None
    if target in ("seller", "sellers"):
        role_of_target = "seller"
    elif target == "buyer":
        role_of_target = "buyer"
    elif target == "monitor":
        role_of_target = "monitor"

    # Строим команду
    if role_of_target and (role_of_target, sub) in ROLE_COMMAND_MAP:
        command = ROLE_COMMAND_MAP[(role_of_target, sub)]
    elif role_of_target == "seller" and sub == "rate" and extra:
        command = f"/sell rate {extra}"
    elif role_of_target == "buyer" and sub == "rate" and extra:
        command = f"/autob rate {extra}"
    elif target == "all" and sub == "stop":
        # Стоп всем — отправим две команды
        try:
            api("/send_command", target="seller", command="/sell stop")
            api("/send_command", target="buyer",  command="/autob stop")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
            return
        await update.message.reply_text("⏹ Команда *stop* отправлена всем аккаунтам.", parse_mode="Markdown")
        return
    else:
        # Прямая передача команды как есть
        command = "/" + " ".join(ctx.args[1:])

    try:
        r = api("/send_command", target=target, command=command)
        result = r.json()
        sent_to = result.get("sent_to", [])
        if sent_to:
            await update.message.reply_text(
                f"✅ Команда `{command}` отправлена:\n" + "\n".join(f"  • {n}" for n in sent_to),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Нет онлайн-аккаунтов с такой ролью/ником.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ── /sell — продать коины с байера ───────────────────────────────────────────

async def sell_coins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Использование: `/sell <количество> <курс>`\n"
            "Пример: `/sell 500 55000` — продать 500 коинов по курсу 55 000",
            parse_mode="Markdown"
        )
        return

    try:
        amount = int(ctx.args[0].replace(" ", ""))
        rate   = int(ctx.args[1].replace(" ", ""))
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Пример: `/sell 500 55000`", parse_mode="Markdown")
        return

    if amount <= 0 or rate <= 0:
        await update.message.reply_text("❌ Количество и курс должны быть больше 0.")
        return

    # Отправляем байеру команду на продажу через автопродажу коинов
    command = f"/autob sellcoins {amount} {rate}"
    try:
        r = api("/send_command", target="buyer", command=command)
        result = r.json()
        sent_to = result.get("sent_to", [])
        if sent_to:
            total = amount * rate
            await update.message.reply_text(
                f"💸 *Продажа коинов запущена*\n\n"
                f"Аккаунт: *{sent_to[0]}*\n"
                f"Коинов: *{fmt(amount)}*\n"
                f"Курс: *{fmt(rate)}* монет/коин\n"
                f"Итого: *{fmt(total)}* монет",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Байер не в сети.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ── /zah — заход на анархию ──────────────────────────────────────────────────

async def zah_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        r = api("/send_command", target="all", command="/zah")
        result = r.json()
        sent_to = result.get("sent_to", [])
        if sent_to:
            await update.message.reply_text(
                "🏰 Команда *зайти на анархию* отправлена:\n" + "\n".join(f"  • {n}" for n in sent_to),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Нет онлайн-аккаунтов.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ── /fpay — перевод монет (только buyer) ─────────────────────────────────────

async def fpay_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text(
            "Использование: `/fpay <ник> <сумма>`\nПример: `/fpay Player123 50000`",
            parse_mode="Markdown"
        )
        return

    nick_target = ctx.args[0]
    amount      = ctx.args[1]

    command = f"/fpay {nick_target} {amount}"
    try:
        r = api("/send_command", target="buyer", command=command)
        result = r.json()
        sent_to = result.get("sent_to", [])
        if sent_to:
            await update.message.reply_text(
                f"💸 Перевод *{amount}* монет → *{nick_target}*\nОтправлено байеру: *{sent_to[0]}*",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Байер не в сети.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ── Ключи (без изменений) ─────────────────────────────────────────────────────

async def add_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE, days: int, note: str = ""):
    if not is_admin(update): return
    r = api("/admin/add", days=days, note=note)
    data = r.json()
    key = data["key"]
    exp = data["expires"]
    await update.message.reply_text(
        f"✅ *Ключ создан на {days} дн.*\n\n"
        f"`{key}`\n\n"
        f"📅 Истекает: *{exp}*\n"
        f"📝 Заметка: {note or '—'}\n\n"
        f"Вводить в игре:\n`/key {key}`",
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
    r = api("/admin/list")
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
        lines.append(
            f"{status} `{k}`\n"
            f"  📅 {exp} (осталось {days_left}д) | HWID: {hwid}"
            + (f" | {note}" if note else "")
        )
    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")

async def disable(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if not ctx.args:
        await update.message.reply_text("Использование: /disable <ключ>")
        return
    key = ctx.args[0].upper()
    r = api("/admin/disable", key=key)
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
    r = api("/admin/reset_hwid", key=key)
    if r.json().get("ok"):
        await update.message.reply_text(f"🔄 HWID сброшен для `{key}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text("Ключ не найден.")

# ── Polling уведомлений о крупных покупках ────────────────────────────────────

async def notify_loop(bot):
    """Каждые 10 сек проверяем уведомления о крупных покупках."""
    while True:
        try:
            r = requests.post(
                f"{SERVER}/admin/notifications",
                json={"password": ADMIN_PASSWORD},
                timeout=10
            )
            notifications = r.json()
            for n in notifications:
                if n.get("type") == "big_buy":
                    nick  = n.get("nick", "?")
                    coins = n.get("coins", 0)
                    rate  = n.get("rate", 0)
                    money = n.get("money", 0)
                    text = (
                        f"🔔 *Крупная покупка!*\n\n"
                        f"👤 Аккаунт: *{nick}*\n"
                        f"🪙 Куплено: *{fmt(coins)} коинов*\n"
                        f"📈 Курс: *{fmt(rate)}* монет/коин\n"
                        f"💰 Потрачено: *{fmt(money)}* монет"
                    )
                    for admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(chat_id=int(admin_id), text=text, parse_mode="Markdown")
                        except Exception:
                            pass
        except Exception:
            pass
        await asyncio.sleep(10)

# ── Запуск ────────────────────────────────────────────────────────────────────

async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start",   start))
    application.add_handler(CommandHandler("help",    help_cmd))
    application.add_handler(CommandHandler("stats",   stats))
    application.add_handler(CommandHandler("st",      st_cmd))
    application.add_handler(CommandHandler("sell",    sell_coins))
    application.add_handler(CommandHandler("add1",    add1))
    application.add_handler(CommandHandler("add7",    add7))
    application.add_handler(CommandHandler("add30",   add30))
    application.add_handler(CommandHandler("add",     add_custom))
    application.add_handler(CommandHandler("list",    list_keys))
    application.add_handler(CommandHandler("disable", disable))
    application.add_handler(CommandHandler("reset",   reset_hwid))
    application.add_handler(CommandHandler("zah",     zah_cmd))
    application.add_handler(CommandHandler("fpay",    fpay_cmd))

    print("Бот запущен!")
    async with application:
        await application.initialize()
        asyncio.create_task(notify_loop(application.bot))
        await application.start()
        await application.updater.start_polling()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
