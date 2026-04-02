import os
import asyncio
import logging
from openai import AsyncOpenAI
from config.config import config

# Comprehensive Multi-language Knowledge Base based on official company scripts
KNOWLEDGE_BASE_RU = """
КОМПАНИЯ: GO TO TOP WB
СУТЬ: Сервис продвижения на Wildberries через безопасные методы.

ПРОЦЕСС (ЭТАПЫ):
1. Запрос -> 2. Данные -> 3. Расчет и PDF -> 4. Оплата -> 5. Группа WhatsApp -> 6. ТЗ -> 7. Запуск -> 8. Склад и доставка.

ПРАВИЛА (SCRIPT):
- Тон: Теплый и бизнес-ориентированный.
- Гарантии: Не гарантируем ТОП, но гарантируем БЕЗОПАСНОСТЬ (имитация живого клиента).
- Механика: Конфиденциальна.
- Оплата: Р/С +6%, Карта +2%, Cash Out 0%, Telcell/Idram 0%.
"""

KNOWLEDGE_BASE_AM = """
ԸՆԿԵՐՈՒԹՅՈՒՆ: GO TO TOP WB

ԳՈՐԾԸՆԹԱՑԻ ՓՈՒԼԵՐԸ:
1. Հարցում -> 2. Տվյալների հավաքագրում -> 3. Հաշվարկ և PDF -> 4. Վճարում -> 5. WhatsApp խումբ -> 6. ՏԱ -> 7. Գործարկում -> 8. Պահեստ և առաքում:

ՊԱՇՏՈՆԱԿԱՆ ՍԿՐԻՊՏՆԵՐ:
- Ողջույն: "Բարև ձեզ 👋 Շնորհակալություն դիմելու համար:"
- Անվտանգություն: "Մենք իմիտացնում ենք իրական գնորդի վարքագիծը (զամբյուղ, դադարներ): WB-ն չի տարբերում մեր գնումները իրականից:"
- Երաշխիք: "Կոնկրետ դիրքերի TOP-ի երաշխիքներ չենք տալիս, բայց ապահովում ենք անվտանգ առաջխաղացում:"
"""

class AIService:
    def __init__(self):
        try:
            # GROQ CLOUD Integration (using the latest flagship models)
            self.client = AsyncOpenAI(
                api_key=config.groq_api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            # Flagship fast models for Groq (2026 lineup)
            self.models_to_try = [
                "llama-3.1-70b-versatile",
                "llama3-70b-8192", 
                "mixtral-8x7b-32768"
            ]
            self.model_name = self.models_to_try[0]
            logging.info(f"AI Service (Groq) initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize Groq AI: {e}")

    async def get_answer(self, question: str, language: str = "ru") -> str:
        kb = KNOWLEDGE_BASE_RU if language == "ru" else KNOWLEDGE_BASE_AM
        
        system_prompt = f"""
        Ты — элитный эксперт и бизнес-консультант компании GO TO TOP (Wildberries promotion). 
        Твое общение должно быть на высочайшем профессиональном уровне, теплым и деловым. 
        Ты — мощный ИИ на базе Groq, обеспечиваешь мгновенную и глубокую аналитику.

        Язык общения: {language if language != 'am' else 'Հայերեն (Armenian)'}.

        БАЗА ЗНАНИЙ (ОФИЦИАЛЬНЫЕ СКРИПТЫ):
        {kb}

        ИНСТРУКЦИИ:
        1. БЕЗ ПРИВЕТСТВИЙ: Сразу к сути. Никаких "Barev/Здравствуйте" в начале.
        2. СТИЛЬ: Используй эмодзи (🚀, 📈, 🛡️, 💎) и списки.
        3. ПОДРОБНОСТЬ: Давай глубокие, развернутые ответы. Если вопрос на армянском (հայերեն) — используй безупречную грамматику и будь детальным.
        4. ДОВЕРИЕ: Подчеркивай безопасность наших методов.
        5. ВОРОНКА: В конце ответа предлагай сделать расчет или задать еще вопрос.

        Вопрос пользователя: {question}
        """
        
        for model in self.models_to_try:
            try:
                logging.info(f"Asking Groq using {model}...")
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a professional business consultant for GO TO TOP (Wildberries Promotion)."},
                        {"role": "user", "content": system_prompt}
                    ],
                    temperature=0.4,
                    max_tokens=1500
                )
                
                if response and response.choices:
                    if self.model_name != model:
                        self.model_name = model
                    return response.choices[0].message.content
                    
            except Exception as e:
                err_text = str(e)
                logging.warning(f"Model {model} failed on Groq: {err_text}")
                continue
        
        return "Извините, система Groq временно недоступна. Пожалуйста, обратитесь к менеджеру напрямую."

ai_service = AIService()
