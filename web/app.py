from flask import Flask, render_template, jsonify, request
import random
import uuid
import os
from core.database import get_points, set_points, add_points, add_history
from web.config import FINAL_MULTIPLIER, PORT
from web.utils import parse_bet, format_value

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev_key_change_me")

active_games = {}
user_sessions = {}

@app.route("/")
def index():
    return "✅ サーバー稼働中 — /mines からゲームへ"

@app.route("/create-session", methods=["POST"])
def create_session():
    data = request.json
    user_id = str(data.get("user_id"))
    token = str(uuid.uuid4())
    user_sessions[token] = user_id
    return jsonify({"success": True, "session_url": f"/mines?token={token}"})

@app.route("/mines")
def mines_page():
    token = request.args.get("token")
    if not token or token not in user_sessions:
        return "❌ 無効なリンク — Discordから再度ボタンを押してください", 400
    return render_template("mines.html", token=token)

@app.route("/api/start", methods=["POST"])
def game_start():
    data = request.json
    token = data.get("token")
    if token not in user_sessions:
        return jsonify({"error": "セッション無効"}), 400
    user_id = user_sessions[token]
    bombs = int(data.get("bombs", 5))
    bet_str = data.get("bet", "100")

    balance = get_points(user_id)
    bet_value = parse_bet(bet_str, balance)

    if bet_value is None or bet_value <= 0 or bet_value > balance:
        return jsonify({"error": "ポイントが足りないか金額が不正です"}), 400
    if not (1 <= bombs <= 24):
        return jsonify({"error": "爆弾数は1～24にしてください"}), 400

    grid = [False] * 25
    for pos in random.sample(range(25), bombs):
        grid[pos] = True

    active_games[user_id] = {
        "bombs": bombs, "bet": bet_value, "grid": grid,
        "opened": [False]*25, "opened_count": 0,
        "multiplier": 1.0, "game_over": False
    }

    set_points(user_id, balance - bet_value)
    return jsonify({"success": True, "balance": get_points(user_id)})

@app.route("/api/open", methods=["POST"])
def open_cell():
    data = request.json
    token = data.get("token")
    idx = int(data.get("index"))
    if token not in user_sessions:
        return jsonify({"error": "セッション無効"}), 400
    user_id = user_sessions[token]
    if user_id not in active_games:
        return jsonify({"error": "ゲームなし"}), 404
    g = active_games[user_id]

    if g["game_over"] or g["opened"][idx]:
        return jsonify({"error": "無効な操作"}), 400
    g["opened"][idx] = True

    if g["grid"][idx]:
        g["game_over"] = True
        all_bombs = [i for i, b in enumerate(g["grid"]) if b]
        del active_games[user_id]
        return jsonify({"result": "lose", "balance": get_points(user_id), "bombs": all_bombs})

    g["opened_count"] += 1
    safe = 25 - g["bombs"]
    if g["opened_count"] >= safe:
        g["multiplier"] = FINAL_MULTIPLIER[g["bombs"]]
        win = int(g["bet"] * g["multiplier"])
        add_points(user_id, win)
        add_history({
            "user_id": user_id, "result": "win", "multiplier": g["multiplier"],
            "amount": win, "time": __import__("datetime").datetime.now().isoformat()
        })
        del active_games[user_id]
        return jsonify({"result": "win", "multiplier": g["multiplier"], "amount": win, "balance": get_points(user_id)})
    else:
        ratio = g["opened_count"] / safe
        g["multiplier"] = round(1.0 + (FINAL_MULTIPLIER[g["bombs"]] - 1.0) * ratio ** 2.2, 2)
        return jsonify({"result": "continue", "multiplier": g["multiplier"]})

@app.route("/api/cashout", methods=["POST"])
def cashout():
    data = request.json
    token = data.get("token")
    if token not in user_sessions:
        return jsonify({"error": "セッション無効"}), 400
    user_id = user_sessions[token]
    if user_id not in active_games:
        return jsonify({"error": "ゲームなし"}), 404
    g = active_games[user_id]
    if g["opened_count"] == 0:
        return jsonify({"error": "1マス以上開けてください"}), 400

    g["game_over"] = True
    win = int(g["bet"] * g["multiplier"])
    add_points(user_id, win)
    add_history({
        "user_id": user_id, "result": "cashout", "multiplier": g["multiplier"],
        "amount": win, "time": __import__("datetime").datetime.now().isoformat()
    })
    del active_games[user_id]
    return jsonify({"result": "cashout", "multiplier": g["multiplier"], "amount": win, "balance": get_points(user_id)})

@app.route("/api/balance", methods=["POST"])
def balance():
    data = request.json
    token = data.get("token")
    if token not in user_sessions:
        return jsonify({"error": "無効"}), 400
    return jsonify({"balance": get_points(user_sessions[token])})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
