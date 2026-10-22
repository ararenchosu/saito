from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import random
import aiohttp
import os
from core.database import get_points, set_points, add_points, add_history
from web.config import (
    FINAL_MULTIPLIER, PORT, SITE_URL,
    DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI, DISCORD_SCOPE
)
from web.utils import parse_bet, format_value

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change_this_to_random_string")
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True

active_games = {}

# ===== ヘルパー：ログイン確認 =====
def get_current_user():
    return session.get("user_id")

# ===== トップページ =====
@app.route("/")
def index():
    user_id = get_current_user()
    return render_template("index.html", user_id=user_id)

# ===== Discordログイン =====
@app.route("/login")
def login():
    if not DISCORD_CLIENT_ID:
        return "⚠️ 管理者がOAuth設定を完了していません", 500
    discord_auth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={DISCORD_SCOPE}"
    )
    return redirect(discord_auth_url)

# ===== コールバック =====
@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "❌ 認証コードが見つかりません", 400

    # トークン取得
    import requests
    token_res = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_REDIRECT_URI,
        }
    )
    if token_res.status_code != 200:
        return "❌ トークン取得に失敗しました", 400
    token_data = token_res.json()
    access_token = token_data.get("access_token")

    # ユーザー情報取得
    user_res = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if user_res.status_code != 200:
        return "❌ ユーザー情報取得に失敗しました", 400
    user_data = user_res.json()
    user_id = str(user_data["id"])

    # セッションに保存
    session["user_id"] = user_id
    session["username"] = user_data.get("username", "Unknown")

    return redirect(url_for("mines_page"))

# ===== ログアウト =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ===== マインスページ =====
@app.route("/mines")
def mines_page():
    user_id = get_current_user()
    if not user_id:
        return redirect(url_for("login"))
    return render_template("mines.html", user_id=user_id)

# ===== ランキング =====
@app.route("/ranking")
def ranking():
    from core.database import load_all
    data = load_all()
    users = data.get("points", {})
    sorted_users = sorted(users.items(), key=lambda x: x[1], reverse=True)[:50]
    return render_template("ranking.html", rankings=sorted_users)

# ===== マイページ =====
@app.route("/profile")
def profile():
    user_id = get_current_user()
    if not user_id:
        return redirect(url_for("login"))
    balance = get_points(user_id)
    return render_template("profile.html", balance=balance, username=session.get("username"))

# ===== API：残高 =====
@app.route("/api/balance", methods=["POST"])
def api_balance():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "ログインが必要です"}), 401
    return jsonify({"balance": get_points(user_id)})

# ===== API：ゲーム開始 =====
@app.route("/api/start", methods=["POST"])
def game_start():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "ログインが必要です"}), 401
    data = request.json
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

# ===== API：マス開く =====
@app.route("/api/open", methods=["POST"])
def open_cell():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "ログインが必要です"}), 401
    if user_id not in active_games:
        return jsonify({"error": "ゲームが見つかりません"}), 404
    g = active_games[user_id]
    idx = int(request.json.get("index"))

    if g["game_over"] or g["opened"][idx]:
        return jsonify({"error": "無効な操作です"}), 400
    g["opened"][idx] = True

    if g["grid"][idx]:
        g["game_over"] = True
        all_bombs = [i for i, b in enumerate(g["grid"]) if b]
        del active_games[user_id]
        return jsonify({
            "result": "lose",
            "balance": get_points(user_id),
            "bombs": all_bombs
        })

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
        return jsonify({
            "result": "win", "multiplier": g["multiplier"],
            "amount": win, "balance": get_points(user_id)
        })
    else:
        ratio = g["opened_count"] / safe
        g["multiplier"] = round(1.0 + (FINAL_MULTIPLIER[g["bombs"]] - 1.0) * ratio ** 2.2, 2)
        return jsonify({"result": "continue", "multiplier": g["multiplier"]})

# ===== API：回収 =====
@app.route("/api/cashout", methods=["POST"])
def cashout():
    user_id = get_current_user()
    if not user_id:
        return jsonify({"error": "ログインが必要です"}), 401
    if user_id not in active_games:
        return jsonify({"error": "ゲームが見つかりません"}), 404
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
    return jsonify({
        "result": "cashout", "multiplier": g["multiplier"],
        "amount": win, "balance": get_points(user_id)
    })

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
