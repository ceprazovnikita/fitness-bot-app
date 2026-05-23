import os
import json
import base64
import logging
from groq import Groq

log = logging.getLogger(__name__)


def get_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def transcribe_audio(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        transcription = get_client().audio.transcriptions.create(
            file=f,
            model="whisper-large-v3",
            language="ru",
        )
    return transcription.text


def analyze_calories(text: str) -> dict:
    response = get_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты диетолог. Пользователь описывает что он съел. "
                    "Оцени калорийность. "
                    "Отвечай ТОЛЬКО в формате JSON без markdown:\n"
                    '{"calories": 350, "description": "Тарелка овсянки с молоком", "proteins": 12, "fats": 8, "carbs": 45}'
                ),
            },
            {"role": "user", "content": f"Я съел: {text}"},
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def analyze_calories_from_photo(image_path: str) -> dict:
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    ext = image_path.split(".")[-1].lower()
    media_type = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"

    response = get_client().chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}"
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Ты диетолог. Определи что за еда на фото и рассчитай калории. "
                            "Отвечай ТОЛЬКО в формате JSON без markdown:\n"
                            '{"calories": 350, "description": "Тарелка овсянки с молоком", "proteins": 12, "fats": 8, "carbs": 45}'
                        ),
                    },
                ],
            }
        ],
        temperature=0.3,
        timeout=60,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def get_daily_advice(meals: list, calories_today: int, calories_target: int) -> str:
    remaining = calories_target - calories_today

    if not meals:
        prompt = (
            f"Составь полный план питания на день на {calories_target} ккал. "
            f"Дай 3-4 приёма пищи с конкретными блюдами и калориями каждого. "
            f"Отвечай на русском языке."
        )
    else:
        meals_text = "\n".join([f"- {m['meal']} ({m['calories']} ккал)" for m in meals])
        if remaining <= 0:
            prompt = (
                f"Человек уже съел:\n{meals_text}\n\n"
                f"Итого: {calories_today} ккал, норма {calories_target} ккал. "
                f"Норма уже достигнута или превышена. "
                f"Дай совет как провести остаток дня в плане питания. Отвечай на русском."
            )
        else:
            prompt = (
                f"Человек уже съел сегодня:\n{meals_text}\n\n"
                f"Итого: {calories_today} ккал из {calories_target} ккал. "
                f"Осталось: {remaining} ккал. "
                f"Предложи конкретные блюда которые можно съесть на оставшиеся {remaining} ккал. "
                f"Дай 2-3 варианта с указанием калорий. Отвечай на русском."
            )

    response = get_client().chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Ты дружелюбный диетолог. Давай короткие практичные советы на русском языке."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def calculate_bmi(weight: float, height: float) -> dict:
    bmi = weight / ((height / 100) ** 2)

    if bmi < 18.5:
        category = "Недостаточный вес"
    elif bmi < 25:
        category = "Норма"
    elif bmi < 30:
        category = "Избыточный вес"
    else:
        category = "Ожирение"

    calories_target = int(10 * weight + 6.25 * height - 5 * 30 + 200)

    return {
        "bmi": round(bmi, 1),
        "category": category,
        "calories_target": calories_target,
    }