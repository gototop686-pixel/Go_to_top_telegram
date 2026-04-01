import os
import asyncio
import logging
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperty

from config.config import config
from database.models import init_db
from middlewares.i18n import I18nMiddleware
from handlers import common, ai_support, sales_funnel

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def main():
    # Initialize database
    await init_db()
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperty(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Register middleware
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())

    # Register routers
    dp.include_router(common.router)
    dp.include_router(sales_funnel.router)
    dp.include_router(ai_support.router)

    # Logging
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Start polling in background
    polling_task = asyncio.create_task(dp.start_polling(bot))

    # Setup aiohttp web server for Render health checks
    app = web.Application()
    app.router.add_get("/", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render provides 'PORT' automatically
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    logging.info(f"Starting web server on port {port}")
    await site.start()

    # Wait for polling to finish (lifetime of bot)
    await polling_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
