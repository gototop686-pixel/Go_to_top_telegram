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
from handlers import common, ai_support, sales_funnel, manager, faq, prices


async def handle_ping(request):
    return web.Response(text="Bot is running!")


async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Start web server FIRST so Render sees the port immediately
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")

    # Now initialize database
    await init_db()
    logging.info("Database initialized")

    # Setup bot
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
    # then AI support, then funnel, then prices
    dp.include_router(manager.router)
    dp.include_router(common.router)
    dp.include_router(faq.router)
    dp.include_router(ai_support.router)
    dp.include_router(sales_funnel.router)
    dp.include_router(prices.router)

    # Clean start: delete old webhook
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Starting polling...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
