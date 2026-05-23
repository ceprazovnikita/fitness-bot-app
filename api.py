import os
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import storage

app = Flask(__name__)
CORS(app)

@app.route('/api/get/<int:user_id>')
def get_data(user_id):
    user = storage.get_user(user_id)
    return jsonify({
        "calories_today": user.get("calories_today", 0),
        "calories_target": user.get("calories_target", 2000),
        "water_today": user.get("water_today", 0),
        "meals_today": user.get("meals_today", []),
        "history": user.get("history", []),
    })

@app.route('/api/water', methods=['POST'])
def add_water():
    data = request.json
    storage.add_water(data['user_id'], data['ml'])
    return jsonify({"ok": True})

@app.route('/api/meal', methods=['POST'])
def add_meal():
    data = request.json
    storage.add_meal(data['user_id'], data['meal'], data['calories'],
                    data.get('proteins', 0), data.get('fats', 0), data.get('carbs', 0))
    return jsonify({"ok": True})

@app.route('/api/meal/delete', methods=['POST'])
def delete_meal():
    data = request.json
    user = storage.get_user(data['user_id'])
    meals = user.get('meals_today', [])
    idx = data['index']
    if 0 <= idx < len(meals):
        meal = meals[idx]
        meals.pop(idx)
        storage.update_user(data['user_id'], {
            'meals_today': meals,
            'calories_today': max(0, user['calories_today'] - meal['calories']),
        })
    return jsonify({"ok": True})

def run_api():
    app.run(host='0.0.0.0', port=5000)

def start_api_thread():
    t = threading.Thread(target=run_api, daemon=True)
    t.start()