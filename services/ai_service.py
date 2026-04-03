import asyncio
import logging
import re
import json
import os
from collections import defaultdict
from openai import AsyncOpenAI
from config.config import config


# ============================================================
# PROMPT BLOCK SYSTEM — loads only needed blocks per message
# ============================================================

# Find project root directory (where bot.py is)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)

PROMPTS_DIR = os.path.join(_PROJECT_ROOT, "prompts")
FULL_PROMPT_PATH = os.path.join(_THIS_DIR, "system_prompt.md")


def load_prompt_block(filename: str) -> str:
    """Load a prompt block from the prompts/ directory."""
    try:
        path = os.path.join(PROMPTS_DIR, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        logging.warning(f"Failed to load block {filename}: {e}")
    return ""


def load_full_prompt() -> str:
    """Load the full prompt as fallback."""
    try:
        if os.path.exists(FULL_PROMPT_PATH):
            with open(FULL_PROMPT_PATH, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        logging.warning(f"Failed to load full prompt: {e}")
    return "Ты — Лия, AI-ассистент Go to Top. Помогаешь с продвижением на Wildberries. Отвечай кратко, по делу."


# Pre-load all blocks at startup
BLOCKS = {
    "base": load_prompt_block("base.txt"),
    "greeting": load_prompt_block("greeting.txt"),
    "how_we_work": load_prompt_block("how_we_work.txt"),
    "pricing": load_prompt_block("pricing.txt"),
    "data_collection": load_prompt_block("data_collection.txt"),
    "existing_client": load_prompt_block("existing_client.txt"),
    "objections": load_prompt_block("objections.txt"),
    "faq": load_prompt_block("faq.txt"),
    "confidential": load_prompt_block("confidential.txt"),
    "escalation": load_prompt_block("escalation.txt"),
}

# Full prompt fallback
FULL_PROMPT = load_full_prompt()

# Use block system only if base block loaded successfully
USE_BLOCKS = bool(BLOCKS.get("base"))

logging.info(f"Prompt system: {'BLOCKS' if USE_BLOCKS else 'FULL'} mode")


# ============================================================
# CATEGORY MAPPING — which blocks to load per category
# ============================================================

CATEGORY_BLOCKS = {
    "GREETING":          ["base", "greeting"],
    "HOW_WE_WORK":       ["base", "how_we_work"],
    "PRICING":           ["base", "pricing"],
    "DATA_COLLECTION":   ["base", "data_collection", "pricing"],
    "CALCULATION":       ["base", "data_collection", "pricing"],  # Same as DATA_COLLECTION
    "EXISTING_CLIENT":   ["base", "existing_client"],
    "OBJECTION":         ["base", "objections"],
    "FAQ":               ["base", "faq"],
    "REVIEWS":           ["base", "faq", "pricing"],
    "KEYWORD_ACTIVATION":["base", "how_we_work", "faq"],
    "STRATEGY":          ["base", "objections"],
    "CONFIDENTIAL":      ["base", "confidential"],
    "ESCALATION":        ["base", "escalation"],
    "OFFTOPIC":          ["base"],
}


# ============================================================
# ROUTER PROMPT — tiny, classifies messages cheaply
# ============================================================

ROUTER_PROMPT = """Ты классификатор сообщений для бота Go to Top (самовыкупы Wildberries).
Определи категорию. Ответь ОДНИМ словом:
GREETING, HOW_WE_WORK, PRICING, DATA_COLLECTION, CALCULATION, EXISTING_CLIENT, OBJECTION, FAQ, REVIEWS, KEYWORD_ACTIVATION, STRATEGY, CONFIDENTIAL, ESCALATION, OFFTOPIC

Правила:
- Приветствие, /start, первое сообщение → GREETING
- Цены, стоимость, сколько стоит (без конкретных чисел/заказа) → PRICING
- Отправка данных (имя, артикул, ключи, числа) → DATA_COLLECTION
- Хочу заказать, мне нужно X выкупов, оформить заказ, сделать заказ, оставить заявку, закажу, давай начнём, готов заказать → DATA_COLLECTION
- Расчёт, посчитайте, рассчитайте → DATA_COLLECTION
- Я ваш клиент, статус, допвыкупы → EXISTING_CLIENT
- Дорого, не верю, гарантия, блогер → OBJECTION
- Вопрос (блокировка, сроки, отгрузка, валюта) → FAQ
- Отзывы → REVIEWS
- Ключевое слово, кластер, активация → KEYWORD_ACTIVATION
- Стратегия, план продвижения → STRATEGY
- Как делаете, какой софт, механика → CONFIDENTIAL
- Грубость, возврат, реквизиты, юрист → ESCALATION
- Не по теме → OFFTOPIC

ВАЖНО: Если клиент хочет заказать, купить, оформить, или называет конкретные числа выкупов/отзывов — это ВСЕГДА DATA_COLLECTION, даже если он ещё не отправил форму.

Сообщение: """


# ============================================================
# CONVERSATION HISTORY
# ============================================================

class ConversationHistory:
    def __init__(self, max_messages: int = 12):
        self.histories = defaultdict(list)
        self.max_messages = max_messages

    def add_user_message(self, user_id: int, message: str):
        self.histories[user_id].append({"role": "user", "content": message})
        self._trim(user_id)

    def add_assistant_message(self, user_id: int, message: str):
        self.histories[user_id].append({"role": "assistant", "content": message})
        self._trim(user_id)

    def get_messages(self, user_id: int) -> list:
        return list(self.histories[user_id])

    def clear(self, user_id: int):
        self.histories[user_id] = []

    def _trim(self, user_id: int):
        if len(self.histories[user_id]) > self.max_messages:
            self.histories[user_id] = self.histories[user_id][-self.max_messages:]


# ============================================================
# LEAD DETECTION
# ============================================================

def parse_lead_ready(response: str):
    match = re.search(r'\[LEAD_READY\](.*?)\[/LEAD_READY\]', response, re.DOTALL)
    if match:
        clean = response[:match.start()].strip()
        try:
            data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            data = {"raw": match.group(1).strip()}
        return clean, data
    return response, None


# ============================================================
# AI SERVICE
# ============================================================

class AIService:
    def __init__(self):
        self.keys = config.groq_keys
        self.clients = [
            AsyncOpenAI(api_key=k, base_url="https://api.groq.com/openai/v1")
            for k in self.keys
        ]

        # Main model for responses
        self.main_models = [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
        ]

        # Small fast model for routing
        self.router_model = "llama-3.1-8b-instant"

        self.conversation = ConversationHistory(max_messages=12)

        logging.info(
            f"AI Service initialized: {len(self.keys)} keys, "
            f"prompt mode: {'BLOCKS' if USE_BLOCKS else 'FULL'}"
        )

    async def _classify_message(self, message: str, client) -> str:
        """Classify message into category using small fast model (~100 tokens)."""
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.router_model,
                    messages=[
                        {"role": "user", "content": ROUTER_PROMPT + message}
                    ],
                    temperature=0,
                    max_tokens=20
                ),
                timeout=10.0
            )
            if response and response.choices:
                category = response.choices[0].message.content.strip().upper()
                # Clean: take first word only
                category = category.split()[0] if category else "FAQ"
                if category in CATEGORY_BLOCKS:
                    return category
        except Exception as e:
            logging.warning(f"Router failed: {e}")

        return "FAQ"  # Safe default

    def _build_prompt(self, category: str) -> str:
        """Build prompt from blocks based on category."""
        if not USE_BLOCKS:
            return FULL_PROMPT

        block_names = CATEGORY_BLOCKS.get(category, ["base", "faq"])
        parts = []
        for name in block_names:
            block = BLOCKS.get(name, "")
            if block:
                parts.append(block)

        return "\n\n---\n\n".join(parts)

    async def _translate(self, text: str, direction: str, client) -> str:
        """Translate text using the fast model.
        direction: 'am_to_ru' or 'ru_to_am'
        
        For am_to_ru: handles Armenian script, Latin transliteration, and mixed text.
        For ru_to_am: translates Russian to Armenian script.
        
        Returns original text on failure (safe fallback).
        """
        if direction == "am_to_ru":
            system_msg = (
                "Ты переводчик. Переведи текст на русский язык. "
                "Текст может быть на армянском (армянскими буквами), на армянском латинскими буквами (транслит), "
                "или на смешанном языке. Переведи всё на русский. "
                "Имена, артикулы, числа, URL — оставь без изменений. "
                "Отвечай ТОЛЬКО переводом, без пояснений."
            )
        else:  # ru_to_am
            system_msg = (
                "Ты переводчик. Переведи текст на армянский язык (армянскими буквами). "
                "Сохрани форматирование, эмодзи, переносы строк. "
                "Имена, артикулы, числа, URL, технические термины (Wildberries, WB, Go to Top) — оставь без изменений. "
                "Цены в драмах (֏) оставь как есть. "
                "Отвечай ТОЛЬКО переводом, без пояснений."
            )

        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.router_model,  # Fast small model for translation
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": text}
                    ],
                    temperature=0.2,
                    max_tokens=2000
                ),
                timeout=15.0
            )
            if response and response.choices:
                translated = response.choices[0].message.content.strip()
                if translated:
                    logging.info(f"Translate {direction}: '{text[:40]}...' -> '{translated[:40]}...'")
                    return translated
        except Exception as e:
            logging.warning(f"Translation {direction} failed: {e}")

        return text  # Fallback: return original

    async def get_answer(self, question: str, language: str = "ru", user_id: int = 0) -> str:
        is_armenian = (language == "am")

        # ============================================================
        # ARMENIAN PIPELINE: translate input to Russian first
        # This gives much better AI quality since prompts are in Russian
        # ============================================================
        working_question = question
        if is_armenian and self.clients:
            working_question = await self._translate(question, "am_to_ru", self.clients[0])
            logging.info(f"Armenian input translated: '{question[:50]}' -> '{working_question[:50]}'")

        # Add RUSSIAN version to history (AI always thinks in Russian)
        self.conversation.add_user_message(user_id, working_question)

        # Step 1: Route message (cheap, ~100 tokens) — always in Russian now
        category = "FAQ"
        if USE_BLOCKS and self.clients:
            category = await self._classify_message(working_question, self.clients[0])
            logging.info(f"Router: '{working_question[:50]}...' -> {category}")

        # Step 2: Build minimal prompt
        prompt = self._build_prompt(category)
        prompt = prompt.replace("{manager_id}", str(config.manager_id))

        # Step 3: Build messages — ALWAYS Russian for the AI
        messages = [
            {"role": "system", "content": prompt + "\n\nТЕКУЩИЙ ЯЗЫК: Русский (Russian)"}
        ]
        messages.extend(self.conversation.get_messages(user_id))

        # Step 4: Get response (with timeout and fallback)
        russian_answer = None
        for i, client in enumerate(self.clients):
            for model in self.main_models:
                try:
                    response = await asyncio.wait_for(
                        client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=0.5,
                            max_tokens=1500
                        ),
                        timeout=30.0
                    )

                    if response and response.choices:
                        answer = response.choices[0].message.content
                        clean_answer, lead_data = parse_lead_ready(answer)
                        # Store RUSSIAN answer in history
                        self.conversation.add_assistant_message(user_id, clean_answer)

                        if lead_data:
                            russian_answer = f"{clean_answer}\n[LEAD_DATA]{json.dumps(lead_data, ensure_ascii=False)}[/LEAD_DATA]"
                        else:
                            russian_answer = clean_answer
                        break  # Got answer, exit model loop

                except asyncio.TimeoutError:
                    logging.warning(f"Timeout: Key {i+1}, Model {model}")
                    continue
                except Exception as e:
                    msg = str(e).lower()
                    if "429" in msg or "413" in msg:
                        logging.warning(f"Rate limit: Key {i+1}, Model {model}")
                        break
                    elif "decommissioned" in msg:
                        continue
                    else:
                        logging.error(f"Error: Key {i+1}, Model {model}: {e}")
                        continue

            if russian_answer:
                break  # Got answer, exit client loop

        if not russian_answer:
            fallback_ru = "Извините, я временно не могу ответить. Обратитесь к менеджеру через кнопку ниже 👱‍♀️"
            if is_armenian and self.clients:
                return await self._translate(fallback_ru, "ru_to_am", self.clients[0])
            return fallback_ru

        # ============================================================
        # ARMENIAN PIPELINE: translate AI response back to Armenian
        # ============================================================
        if is_armenian and self.clients:
            # Don't translate [LEAD_DATA] tags — extract, translate text, re-attach
            lead_match = re.search(r'\[LEAD_DATA\].*?\[/LEAD_DATA\]', russian_answer, re.DOTALL)
            if lead_match:
                text_part = russian_answer[:lead_match.start()].strip()
                lead_tag = lead_match.group(0)
                translated_text = await self._translate(text_part, "ru_to_am", self.clients[0])
                return f"{translated_text}\n{lead_tag}"
            else:
                return await self._translate(russian_answer, "ru_to_am", self.clients[0])

        return russian_answer

    async def translate_to_russian(self, text: str) -> str:
        """Public method: translate Armenian/transliterated text to Russian.
        Used by handlers to run trigger detection on Russian text.
        Returns original text if translation fails or no clients available."""
        if not self.clients:
            return text
        return await self._translate(text, "am_to_ru", self.clients[0])

    async def translate_to_armenian(self, text: str) -> str:
        """Public method: translate Russian text to Armenian.
        Used by handlers to translate bot messages for Armenian users."""
        if not self.clients:
            return text
        return await self._translate(text, "ru_to_am", self.clients[0])

    def clear_history(self, user_id: int):
        self.conversation.clear(user_id)


ai_service = AIService()
