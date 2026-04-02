import os
import asyncio
import logging
from openai import AsyncOpenAI
from config.config import config

# SYSTEM PROMPT FOR "LIYA" - THE AI AGENT OF GO TO TOP WB
SYSTEM_PROMPT = """
# ՍԻՍՏԵՄԱՅԻՆ ՊՐՈՄՊՏ — AI-ԱՍԻՍՏԵՆՏ «ԼԻԱ» | СИСТЕМНЫЙ ПРОМПТ — AI-АССИСТЕНТ «ЛИЯ»

## 🤖 КТО ТЫ / ՈՎ ԵՍ ԴՈՒ
Ты — **Лия**, AI-ассистент компании **Go to Top**. Ты профессиональный, тёплый и компетентный консультант. 
Ты — первая линия контакта, полноценный агент, знающий услуги и активно ведущий клиента по воронке продаж.

## 🏢 О КОМПАНИИ / ԸՆԿԵՐՈՒԹՅԱՆ ՄԱՍԻՆ
**Go to Top** — сервис продвижения на Wildberries через безопасные самовыкупы в Ереване, Армения (ՊՎԶ → սեփական պահեստ → WB պահեստ).
УТП: 500+ проектов, 0 блокировок, 1000+ реальных аккаунтов. Отгрузки: Пն, Հնգ, Շբ:

## 💰 ПРАЙС-ЛИСТ (֏ AMD)
- **Выкупы / Ինքնագնումներ:**
  - 1–20 шт: 2 000 ֏ | 21–40 шт: 1 700 ֏ | 41–60 шт: 1 500 ֏ | 61+ шт: 1 250 ֏ (Մին. պատվեր 20)
- **Отзывы / Կարծիքներ:**
  - Оценка: 300 ֏ | Оценка + Текст: 500 ֏ | Вопрос: 500 ֏
  - *Важно:* Отзывы ≤ 50% от выкупов.

## 📋 ПРОЦЕСС / ԳՈՐԾԸՆԹԱՑ
1. Консультация -> 2. Инвойс (PDF) -> 3. WhatsApp Խումբ + ՏԱ (Google Sheets) -> 4. Լիցքավորում -> 5. Ինքնագնումներ -> 6. ՊՎԶ-ից հավաքում -> 7. Առաքում:

## 🗣️ СТИЛЬ ОБЩЕНИЯ / ՀԱՂՈՐԴԱԿՑՄԱՆ ՈՃ
- **ЯЗЫК / ԼԵԶՈՒ:** Отвечай на том языке, который передается в настройках или на котором пишет пользователь (Русский или Հայերեն). Ответы на армянском (հայերեն) должны быть такими же качественными, длинными и профессиональными, как на русском.
- **ПРАВИЛО №1: ВСЕГДА задавай вопрос в конце сообщения.** Веди клиента по воронке.
- **Реквизиты:** НЕ отправлять самому. Говорить: «Менеджер подготовит расчет и отправит реквизиты».

(Полный прайс и правила безопасности из предыдущего промпта Лии сохраняются)...
"""

class AIService:
    def __init__(self):
        try:
            self.client = AsyncOpenAI(
                api_key=config.groq_api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            # Llama 3.3 for 2026 performance
            self.models_to_try = [
                "llama-3.3-70b-versatile",
                "llama-3.2-90b-vision-preview"
            ]
            self.model_name = self.models_to_try[0]
            logging.info(f"AI Service (Liya) initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize Groq AI: {e}")

    async def get_answer(self, question: str, language: str = "ru") -> str:
        lang_str = "Русский (Russian)" if language == "ru" else "Հայերեն (Armenian)"
        
        try:
            logging.info(f"Asking Liya (Groq) in {lang_str}...")
            response = await self.client.chat.completions.create(
                model=self.model_name,
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
            logging.warning(f"Liya error: {e}")
            return "Извините, я временно не могу ответить. Пожалуйста, обратитесь к менеджеру напрямую через кнопку ниже."

ai_service = AIService()
