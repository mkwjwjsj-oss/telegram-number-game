import os
import random
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# خادم ويب بسيط لتلبية متطلبات Web Service المجاني
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Telegram Number Guessing Bot is alive!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)


MIN_NUM = 1
MAX_NUM = 50
MAX_ATTEMPTS_PER_PLAYER = 6


@dataclass
class GameSession:
    secret_number: int
    player_attempts: Dict[int, int] = field(default_factory=dict)
    player_names: Dict[int, str] = field(default_factory=dict)
    active: bool = True


games: Dict[int, GameSession] = {}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    welcome_text = (
        "أهلاً بك في لعبة **تخمين الأرقام** (من 1 إلى 50)!\n\n"
        "الأوامر المتاحة:\n"
        "• /game — بدء جولة جديدة\n"
        "• /guess <الرقم> — تخمين رقم (مثال: `/guess 25`)\n\n"
        f"لكل لاعب **{MAX_ATTEMPTS_PER_PLAYER} محاولات** في الجولة الواحدة، ويمكن اللعب بشكل فردي أو جماعي."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    secret = random.randint(MIN_NUM, MAX_NUM)
    games[chat_id] = GameSession(secret_number=secret, active=True)

    await update.message.reply_text(
        f"بدأت جولة جديدة! اخترت رقماً سرياً بين **{MIN_NUM}** و **{MAX_NUM}**.\n"
        f"لدى كل لاعب **{MAX_ATTEMPTS_PER_PLAYER} محاولات**.\n"
        "استخدم الأمر `/guess 25` لبدء التخمين.",
        parse_mode="Markdown",
    )


async def guess_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "لاعب"

    session: Optional[GameSession] = games.get(chat_id)
    if not session or not session.active:
        await update.message.reply_text(
            "لا توجد جولة نشطة حالياً. ابدأ واحدة باستخدام `/game`."
        )
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("الاستخدام الصحيح: `/guess 25`", parse_mode="Markdown")
        return

    try:
        guess_val = int(context.args[0])
    except ValueError:
        await update.message.reply_text("يرجى إدخال رقم صحيح فقط، مثل: `/guess 17`", parse_mode="Markdown")
        return

    if guess_val < MIN_NUM or guess_val > MAX_NUM:
        await update.message.reply_text(
            f"الرقم يجب أن يكون بين **{MIN_NUM}** و **{MAX_NUM}**.",
            parse_mode="Markdown",
        )
        return

    used = session.player_attempts.get(user_id, 0)
    if used >= MAX_ATTEMPTS_PER_PLAYER:
        await update.message.reply_text(
            f"عذراً {user_name}، لقد استنفدت محاولاتك ({MAX_ATTEMPTS_PER_PLAYER}) في هذه الجولة."
        )
        return

    used += 1
    session.player_attempts[user_id] = used
    session.player_names[user_id] = user_name
    remaining = MAX_ATTEMPTS_PER_PLAYER - used

    if guess_val == session.secret_number:
        session.active = False
        await update.message.reply_text(
            f"مبروك {user_name}! خمنت الرقم الصحيح **{session.secret_number}** "
            f"في المحاولة رقم **{used}**.\n"
            "لبدء جولة جديدة اكتب `/game`.",
            parse_mode="Markdown",
        )
        return

    hint = "أكبر" if guess_val < session.secret_number else "أصغر"

    all_exhausted = len(session.player_attempts) > 0 and all(
        attempts >= MAX_ATTEMPTS_PER_PLAYER
        for attempts in session.player_attempts.values()
    )

    if all_exhausted:
        session.active = False
        await update.message.reply_text(
            f"تخمينك ({guess_val}) {hint} من الرقم السري، وقد انتهت محاولات جميع اللاعبين!\n"
            f"الرقم الصحيح كان: **{session.secret_number}**.\n"
            "ابدأ جولة جديدة عبر `/game`.",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        f"{user_name}: الرقم السري **{hint}** من **{guess_val}**.\n"
        f"المحاولات المتبقية لك: **{remaining}**",
        parse_mode="Markdown",
    )


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("لم يتم العثور على متغير البيئة BOT_TOKEN.")

    threading.Thread(target=run_web_server, daemon=True).start()

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("guess", guess_command))

    print("Bot and web server are running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
