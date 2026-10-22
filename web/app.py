from flask import Flask, render_template, request, jsonify, session
import os
import json
import uuid

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change_this_to_secure_key")

# データファイル
DATA_FILE = "points_data.json"

# ファイル読み込み
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ファイル保存
def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ユーザーID取得（簡易セッション）
def get_user_id():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())
    return session["user_id"]

# ===== トップページ =====
@app.route("/")
def index():
    return render_template("index.html")

# ===== マインズページ =====
@app.route("/mines")
def mines():
    return render_template("mines.html")

# ===== 残高取得API =====
@app.route("/api/balance", methods=["POST"])
def api_balance():
    uid = get_user_id()
    data = load_data()
    balance = data.get(uid, {}).get("balance", 0.0)
    return jsonify({"balance": balance})

# ===== 入金API =====
@app.route("/api/deposit", methods=["POST"])
def api_deposit():
    req = request.get_json()
    amount = float(req.get("amount", 0))
    
    if amount <= 0:
        return jsonify({"success": False, "error": "正しい金額を入力してください"})
    
    uid = get_user_id()
    data = load_data()
    
    if uid not in data:
        data[uid] = {"balance": 0.0}
    
    data[uid]["balance"] += amount
    save_data(data)
    
    return jsonify({
        "success": True,
        "new_balance": data[uid]["balance"]
    })

# ===== マインズ：ゲーム開始 =====
@app.route("/api/start", methods=["POST"])
def api_start():
    req = request.get_json()
    bombs = int(req.get("bombs", 1))
    bet = float(req.get("bet", 0))
    
    uid = get_user_id()
    data = load_data()
    balance = data.get(uid, {}).get("balance", 0.0)
    
    if bet <= 0:
        return jsonify({"error": "ベット額を入力してください"})
    if balance < bet:
        return jsonify({"error": "残高が足りません"})
    
    # ベット額を一時的に引く
    data[uid]["balance"] -= bet
    
    # 爆弾位置をランダム選択
    import random
    all_cells = list(range(25))
    bomb_positions = random.sample(all_cells, bombs)
    
    # ゲーム状態をセッションに保存
    session["mines_game"] = {
        "bet": bet,
        "bombs": bomb_positions,
        "opened": [],
        "active": True
    }
    
    save_data(data)
    return jsonify({"success": True})

# ===== マインズ：マスを開く =====
@app.route("/api/open", methods=["POST"])
def api_open():
    req = request.get_json()
    idx = int(req.get("index", 0))
    
    game = session.get("mines_game")
    if not game or not game.get("active"):
        return jsonify({"error": "ゲームが開始されていません"})
    
    if idx in game["opened"]:
        return jsonify({"result": "already"})
    
    game["opened"].append(idx)
    
    # 爆弾だった → 負け
    if idx in game["bombs"]:
        game["active"] = False
        session["mines_game"] = game
        return jsonify({"result": "lose", "bombs": game["bombs"]})
    
    # 宝石だった
    safe_count = 25 - len(game["bombs"])
    opened_safe = len(game["opened"])
    if opened_safe == safe_count:
        # 全部開いた → 勝ち
        game["active"] = False
        bet = game["bet"]
        mult = 1.0
        for i in range(opened_safe):
            mult *= 25 / (25 - i)
        win_amount = bet * mult
        
        uid = get_user_id()
        data = load_data()
        data[uid]["balance"] += win_amount
        save_data(data)
        
        session["mines_game"] = game
        return jsonify({"result": "win", "multiplier": round(mult, 2)})
    
    session["mines_game"] = game
    return jsonify({"result": "ok"})

# ===== マインズ：回収 =====
@app.route("/api/cashout", methods=["POST"])
def api_cashout():
    game = session.get("mines_game")
    if not game or not game.get("active"):
        return jsonify({"error": "ゲームがありません"})
    
    opened_safe = len(game["opened"])
    bet = game["bet"]
    mult = 1.0
    for i in range(opened_safe):
        mult *= 25 / (25 - i)
    win_amount = bet * mult
    
    uid = get_user_id()
    data = load_data()
    data[uid]["balance"] += win_amount
    save_data(data)
    
    game["active"] = False
    session["mines_game"] = game
    return jsonify({"success": True, "amount": win_amount, "multiplier": round(mult, 2)})

if __name__ == "__main__":
    app.run(debug=True)
