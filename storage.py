import json
import os
from threading import Lock
from datetime import date

FILE = "users.json"
_lock = Lock()


def load_all() -> dict:
    if not os.path.exists(FILE):
        return {}
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_all(data: dict):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user(chat_id: int) -> dict:
    data = load_all()
    key = str(chat_id)
    today = str(date.today())
    if key not in data:
        data[key] = {
            "weight": None,
            "height": None,
            "calories_target": 2000,
            "meals_today": [],
            "calories_today": 0,
            "water_today": 0,
            "last_date": today,
            "history": [],
        }
        save_all(data)
    else:
        # Сброс данных если новый день
        if data[key].get("last_date") != today:
            yesterday = {
                "date": data[key].get("last_date"),
                "calories": data[key].get("calories_today", 0),
                "water": data[key].get("water_today", 0),
                "meals": data[key].get("meals_today", []),
            }
            history = data[key].get("history", [])
            history.append(yesterday)
            if len(history) > 7:
                history = history[-7:]
            data[key]["history"] = history
            data[key]["meals_today"] = []
            data[key]["calories_today"] = 0
            data[key]["water_today"] = 0
            data[key]["last_date"] = today
            save_all(data)
    return data[key]


def update_user(chat_id: int, fields: dict):
    with _lock:
        data = load_all()
        key = str(chat_id)
        if key not in data:
            get_user(chat_id)
            data = load_all()
        data[key].update(fields)
        save_all(data)


def add_meal(chat_id: int, meal: str, calories: int, proteins: int = 0, fats: int = 0, carbs: int = 0):
    with _lock:
        data = load_all()
        key = str(chat_id)
        if key not in data:
            get_user(chat_id)
            data = load_all()
        data[key]["meals_today"].append({
            "meal": meal,
            "calories": calories,
            "proteins": proteins,
            "fats": fats,
            "carbs": carbs,
        })
        data[key]["calories_today"] += calories
        save_all(data)


def add_water(chat_id: int, ml: int):
    with _lock:
        data = load_all()
        key = str(chat_id)
        if key not in data:
            get_user(chat_id)
            data = load_all()
        data[key]["water_today"] = data[key].get("water_today", 0) + ml
        save_all(data)


def reset_today(chat_id: int):
    update_user(chat_id, {
        "meals_today": [],
        "calories_today": 0,
        "water_today": 0,
    })