# Wildberries Promotion Bot (MV)

This is a production-ready Telegram bot for a Wildberries promotion service with an integrated AI support system and a structured sales funnel.

## 🚀 Key Features

1.  **AI Q&A Support**: Answers user questions based on the service knowledge base using Google Gemini (1.5-flash).
2.  **Sales Funnel**: Structured data collection (Name, Article, Quantity) for calculations.
3.  **Multilingual Support**: Supports Russian (🇷🇺) and Armenian (🇦🇲).
4.  **Manager Integration**: Automatically hands off calculation requests and direct support requests to the manager.
5.  **Persistence**: Uses SQLAlchemy with PostgreSQL (Supabase) for long-term data storage.

## ⚙️ Configuration

1.  Clone this repository to your hosting or local machine.
2.  Create a `.env` file based on `.env.example`:
    ```env
    BOT_TOKEN=your_telegram_bot_token
    MANAGER_ID=your_telegram_user_id
    GEMINI_API_KEY=your_google_gemini_api_key
    DATABASE_URL=your_postgres_link
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## 🛠️ Deployment on Render.com (Web Service)

Render is the recommended choice. The bot is optimized to run as a **Web Service** (not Background Worker) to use the free tier effectively.

1.  **New Web Service**:
    *   Connect your repository.
    *   **Runtime**: `Python 3`.
    *   **Build Command**: `pip install -r requirements.txt`.
    *   **Start Command**: `python bot.py`.
2.  **Environment Variables**:
    *   `BOT_TOKEN`: Your Telegram Bot Token.
    *   `MANAGER_ID`: Your Telegram ID (to receive notifications).
    *   `GEMINI_API_KEY`: Your Google Gemini API Key.
    *   `DATABASE_URL`: Your Supabase/PostgreSQL connection string.
3.  **Automatic DB Driver**: 
    *   The bot automatically handles standard `postgres://` or `postgresql://` links. 
    *   It will prepend `+asyncpg` for you, making it compatible with async SQLAlchemy.
4.  **Health Checks**:
    *   The bot starts a small HTTP server on the port provided by Render (captured via `$PORT`).
    *   You can set the health check path to `/` in the Render dashboard.
    *   **Anti-Sleep**: If the bot is on a free tier, it will sleep after 15 minutes of inactivity. Use a free service like [cron-job.org](https://cron-job.org) to ping your Render URL every 10-14 minutes to keep it "always-on".

## 🧠 Customizing Knowledge Base

To update what the AI knows:
1. Open `services/ai_service.py`.
2. Edit the `KNOWLEDGE_BASE` string.
3. Commit and push to GitHub. Render will redeploy automatically.

---
Developed for **Go to Top WB** - High-performance Telegram Sales & Support Bot.
