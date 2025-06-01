import os
import requests
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# 从环境变量获取 Telegram Bot Token
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("请设置 BOT_TOKEN 环境变量。")

# ScriptBlox API 配置
BASE_URL = "https://scriptblox.com/api/script/search"
DETAIL_URL = "https://scriptblox.com/api/script/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# 每页显示的结果数量
RESULTS_PER_PAGE = 5

# 存储用户的搜索状态
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("你好！使用 /search <关键词> 来搜索脚本~")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("请输入搜索关键词，例如：/search jailbreak")
        return

    query = ' '.join(args).strip()
    user_id = update.effective_user.id
    user_states[user_id] = {
        "query": query,
        "page": 1,
        "results": [],
    }

    await send_search_results(update, context, user_id)

async def send_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    state = user_states.get(user_id)
    if not state:
        return

    params = {
        "q": state["query"],
        "page": state["page"],
        "max": RESULTS_PER_PAGE,
    }

    try:
        response = requests.get(BASE_URL, headers=HEADERS, params=params)
        response.raise_for_status()
        scripts = response.json().get("result", {}).get("scripts", [])
    except Exception as e:
        await context.bot.send_message(chat_id=user_id, text=f"搜索失败：{e}")
        return

    if not scripts:
        await context.bot.send_message(chat_id=user_id, text="未找到相关脚本。")
        return

    state["results"] = scripts

    message_text = f"🔍 搜索关键词：{state['query']}\n📄 第 {state['page']} 页结果："
    keyboard = []

    for idx, script in enumerate(scripts, start=1):
        title = script.get("title", "无标题")
        message_text += f"\n{idx}. {title}"

    # 页码切换和序号按钮分两排
    nav_buttons = []
    if state["page"] > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data="prev_page"))
    # 1-5脚本序号按钮
    number_buttons = [InlineKeyboardButton(str(i), callback_data=f"detail_{i}") for i in range(1, len(scripts)+1)]
    nav_buttons.append(InlineKeyboardButton("➡️ 下一页", callback_data="next_page"))

    keyboard.append(nav_buttons[:1])      # 上一页按钮单独一排（如果有）
    keyboard.append(number_buttons)       # 脚本序号一排
    keyboard.append(nav_buttons[1:])      # 下一页按钮单独一排

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=message_text, reply_markup=reply_markup)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id)

    if not state:
        await query.edit_message_text(text="请先使用 /search 命令进行搜索。")
        return

    data = query.data

    if data == "next_page":
        state["page"] += 1
        await send_search_results(update, context, user_id)
    elif data == "prev_page":
        if state["page"] > 1:
            state["page"] -= 1
            await send_search_results(update, context, user_id)
    elif data.startswith("detail_"):
        idx = int(data.split("_")[1]) - 1
        scripts = state.get("results", [])
        if 0 <= idx < len(scripts):
            script_id = scripts[idx].get("_id")
            if script_id:
                try:
                    res = requests.get(DETAIL_URL + script_id, headers=HEADERS)
                    res.raise_for_status()
                    data = res.json().get("script", {})
                    title = data.get("title", "无标题")
                    author = data.get("owner", {}).get("username", "未知作者")
                    key_required = "是" if data.get("key", False) else "否"
                    description = data.get("description", "无描述")
                    content = data.get("script", "无内容")

                    detail_text = (
                        f"📄 标题：{title}\n"
                        f"👤 作者：{author}\n"
                        f"🔑 需要密钥：{key_required}\n"
                        f"📝 描述：{description}\n\n"
                        f"📜 脚本内容：\n{content}"
                    )

                    await context.bot.send_message(chat_id=user_id, text=detail_text)
                except Exception as e:
                    await context.bot.send_message(chat_id=user_id, text=f"获取详情失败：{e}")
        else:
            await context.bot.send_message(chat_id=user_id, text="无效的脚本序号。")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()

if __name__ == "__main__":
    main()
