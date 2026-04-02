import os
import asyncio
import logging
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config.config import config
from database.models import init_db
from middlewares.i18n import I18nMiddleware
from handlers import common, ai_support, sales_funnel, manager

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    # Initialize database
    await init_db()
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Register middleware
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())

    # Register routers (order matters!)
    dp.include_router(manager.router)
    dp.include_router(common.router)
    dp.include_router(ai_support.router)
    dp.include_router(sales_funnel.router)

    # Logging
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Setup aiohttp web server for Render health checks (health check endpoint)
    app = web.Application()
    app.router.add_get("/", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render provides 'PORT' automatically
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    logging.info(f"Starting web server on port {port}")
    await site.start()

    # CRITICAL: Delete any old webhook and clear pending updates to avoid Conflict Errors 
    # when Render performs a rolling update (old instance still running).
    await bot.delete_webhook(drop_pending_updates=True)

    # Start polling
    # This call is blocking, it will keep the bot alive
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
