import os
import asyncio
import logging
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config.config import config
from database.models import init_db
from middlewares.i18n import I18nMiddleware
from handlers import common, ai_support, sales_funnel, manager, faq


async def handle_ping(request):
    return web.Response(text="Bot is running!")


async def main():
    await init_db()
    
    # No default parse_mode — AI sends plain text
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties()
    )
    dp = Dispatcher()

    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())

    # Order matters: manager first (handles ManagerChat state),
    # then common (/start, language, menu buttons),
    # then FAQ (static Armenian + AI redirect for Russian),
    # then AI support, then funnel
    dp.include_router(manager.router)
    dp.include_router(common.router)
    dp.include_router(faq.router)
    dp.include_router(ai_support.router)
    dp.include_router(sales_funnel.router)

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Health check endpoint for Render
    app = web.Application()
    app.router.add_get("/", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    logging.info(f"Starting web server on port {port}")
    await site.start()

    # Clean start: delete old webhook
    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
