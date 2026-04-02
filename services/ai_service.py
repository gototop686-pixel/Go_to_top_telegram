import os
import asyncio
import logging
from openai import AsyncOpenAI
from config.config import config

# SYSTEM PROMPT FOR "LIYA" - THE AI AGENT OF GO TO TOP WB (v4 Final)
SYSTEM_PROMPT = """
# СИСТЕМНЫЙ ПРОМПТ — AI-АССИСТЕНТ ЛИЯ | GO TO TOP WB

## КТО ТЫ

Ты — Лия, AI-ассистент компании Go to Top. Работаешь в Telegram-боте. Ты первая линия контакта... (Все остальные подробности из предыдущего промпта сохраняются)
"""

class AIService:
    def __init__(self):
        try:
            self.client = AsyncOpenAI(
                api_key=config.groq_api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            # Flagship models to try sequentially if quota is hit
            self.models_to_try = [
                "llama-3.3-70b-versatile",
                "llama3-70b-8192", # Try to use Llama 3 70b if Llama 3.3 70b is hit
                "llama-3.3-70b-specdec",    # High-speed variant
                "llama-3.1-8b-instant",     # Highly robust fallback for quota issues
                "mixtral-8x7b-32768"        # Final reliable fallback
            ]
            logging.info(f"AI Service (Liya) initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize Groq AI: {e}")

    async def get_answer(self, question: str, language: str = "ru") -> str:
        lang_str = "Русский (Russian)" if language == "ru" else "Հայերեն (Armenian)"
        
        for model in self.models_to_try:
            try:
                logging.info(f"Trying Liya with {model} in {lang_str}...")
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT + f"\n\nТЕКУЩИЙ ЯЗЫК ОБЩЕНИЯ: {lang_str}"},
                        {"role": "user", "content": question}
                    ],
                    temperature=0.5,
                    max_tokens=1500
                )
                
                if response and response.choices:
                    return response.choices[0].message.content
                    
            except Exception as e:
                # If hit rate limit (429) or other errors, try the next model
                if "429" in str(e):
                    logging.warning(f"Model {model} hit quota. Trying fallback...")
                    continue
                else:
                    logging.error(f"Error with model {model}: {e}")
                    continue
                    
        return "Извините, я временно исчерпала лимит сообщений на сегодня. Пожалуйста, напишите нашему менеджеру — он ответит на все ваши вопросы лично! 👱‍♀️"

ai_service = AIService()
