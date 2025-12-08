import os
import random
import time
from flask import Flask, request

from linebot import LineBotApi
from linebot.models import TextSendMessage

# ==============================
# 1. 建立 Flask app
# ==============================
app = Flask(__name__)

# ==============================
# 2. LINE 設定（從環境變數讀取）
# ==============================
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")

if CHANNEL_ACCESS_TOKEN:
    line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
    print("✅ 已載入 CHANNEL_ACCESS_TOKEN")
else:
    line_bot_api = None
    print("⚠️ CHANNEL_ACCESS_TOKEN 未設定，無法回覆 LINE 訊息。")

# ==============================
# 3. 使用者「連續預測模式」狀態紀錄
#    key: user_id, value: 最後一次有效觸發時間 (time.time())
# ==============================
user_session_last_trigger = {}
SESSION_TIMEOUT_SEC = 60  # 一分鐘內都算「連續預測模式」

# ==============================
# 4. 判斷輸入是否為 6~12 個「莊/閒/和」
# ==============================
def is_valid_sequence(text: str) -> bool:
    if not (6 <= len(text) <= 12):
        return False
    for ch in text:
        if ch not in ["莊", "閒", "和"]:
            return False
    return True

# ==============================
# 5. 預測邏輯
# ==============================
def generate_prediction():
    

    # 1) 決定預測結果：莊 45%、閒 45%、和 10%
    r = random.random()  # 0.0 ~ 1.0
    if r < 0.45:
        result = "莊"
    elif r < 0.90:
        result = "閒"
    else:
        result = "和"

    # 2) 決定預測機率：50% ~ 98%
    prob = random.randint(50, 98)

    # 3) 根據機率決定建議本金：500 ~ 10000
    min_bet = 500
    max_bet = 10000

    # 線性映射：prob 從 50~98 對應到 500~10000
    bet_float = min_bet + (prob - 50) / (98 - 50) * (max_bet - min_bet)
    # 取整數 & 四捨五入到百元
    bet = int(round(bet_float / 100.0)) * 100
    bet = max(min_bet, min(max_bet, bet))

    return result, prob, bet


# ==============================
# 6. Webhook / 根目錄 (都支援)
# ==============================
@app.route("/", methods=["GET", "POST"])
@app.route("/callback", methods=["GET", "POST"])
def callback():
    # GET 多半是健康檢查或驗證，直接回 200
    if request.method == "GET":
        return "OK", 200

    # LINE Webhook 正式請求 (POST)
    data = request.get_json(silent=True)
    print("📩 收到 LINE webhook JSON：", data)

    if not data or "events" not in data:
        return "OK", 200

    for event in data["events"]:
        if event.get("type") == "message" and event["message"]["type"] == "text":
            user_text = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            # 拿 userId 當作 session key
            user_id = None
            source = event.get("source", {})
            # 可能是 user / group / room，優先拿 userId
            if "userId" in source:
                user_id = source["userId"]
            else:
                # 沒 userId 的話，退而求其次，以 groupId/roomId 當 key
                user_id = source.get("groupId") or source.get("roomId") or "unknown"

            now = time.time()
            last_trigger = user_session_last_trigger.get(user_id, None)

            # 判斷這次輸入是否為「6~12 個莊閒和」
            valid_seq = is_valid_sequence(user_text)

            # 條件 1：這次輸入是合法序列 → 觸發預測 & 更新 session 時間
            # 條件 2：不是合法序列，但在 60 秒內有合法觸發紀錄 → 視為連續預測
            in_session = (
                last_trigger is not None and (now - last_trigger) <= SESSION_TIMEOUT_SEC
            )

            if valid_seq or in_session:
                # 只要符合上面兩種狀況，就給預測
                result, prob, bet = generate_prediction()

                # 更新 session 時間（延長一分鐘窗口）
                user_session_last_trigger[user_id] = now

                reply_text = (
                    "🎲 百家樂智能預測系統\n\n"
                    f"你輸入的內容：{user_text}\n"
                    f"系統預測結果：{result}\n"
                    f"預測勝率：約 {prob}%\n"
                    f"建議本金：約 {bet} 元\n\n"
                    
                )
            else:
                # 不合法，而且不在一分鐘連續預測時間內
                reply_text = "請給我預測結果6-12局"

            # 回覆訊息
            if line_bot_api is not None:
                try:
                    line_bot_api.reply_message(
                        reply_token,
                        TextSendMessage(text=reply_text)
                    )
                except Exception as e:
                    print("❌ 回覆訊息失敗：", e)
            else:
                print("⚠️ 收到訊息但沒有 CHANNEL_ACCESS_TOKEN，無法回覆。內容：", reply_text)

    return "OK", 200


# ==============================
# 7. 本機測試用
# ==============================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

