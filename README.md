# Wildberries Promotion Bot (MV)

This is a production-ready Telegram bot for a Wildberries promotion service with an integrated AI support system and a structured sales funnel.

## 🚀 Key Features

1.  **AI Q&A Support**: Answers user questions based on the service knowledge base using Google Gemini.
2.  **Sales Funnel**: Structured data collection (Name, Article, Quantity) for calculations.
3.  **Multilingual Support**: Supports Russian (🇷🇺) and Armenian (🇦🇲).
4.  **Manager Integration**: Automatically hands off calculation requests and direct support requests to the manager.
5.  **Analytics**: Tracks user interactions and funnel drop-off via SQLite.

## ⚙️ Configuration

1.  Clone this repository to your hosting or local machine.
2.  Create a `.env` file based on `.env.example`:
    ```env
    BOT_TOKEN=your_telegram_bot_token
    MANAGER_ID=your_telegram_user_id
    GEMINI_API_KEY=your_google_gemini_api_key
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## 🛠️ Deployment on Render.com

Render is a great free hosting choice for this lightweight bot.

1.  **GitHub Repo**: Push your code to a private GitHub repository.
2.  **New Web Service**:
    *   Connect your repository.
    *   **Environment**: `Python3`.
    *   **Build Command**: `pip install -r requirements.txt`.
    *   **Start Command**: `python bot.py`.
3.  **Environment Variables**: Add your keys from the `.env` file to Render's Dashboard.
4.  **Database (Supabase / PostgreSQL)**:
    *   The bot uses **SQLAlchemy**, supporting both SQLite and PostgreSQL.
    *   On Render's free tier, local SQLite data is lost on every deploy. 
    *   **To use Supabase (recommended)**:
        1. Get your **Direct Connection String** from Supabase (Settings -> Database).
        2. Set the `DATABASE_URL` environment variable on Render:
           `postgresql+asyncpg://user:password@host:port/dbname`
        3. The bot will automatically switch to PostgreSQL and maintain your data persistently.

## 🧠 Customizing Knowledge Base

To update the information the AI uses to answer questions:
1. Open `services/ai_service.py`.
2. Edit the `KNOWLEDGE_BASE` string with your website content or sales scripts.

---
Developed as a lightweight, scalable solution for Telegram lead generation.
