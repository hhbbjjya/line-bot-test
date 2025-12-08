import os
import random
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
# 3. 預測邏輯
# ==============================
def generate_prediction():
    """
    回傳：
    - result: "莊" / "閒" / "和"
    - prob:   50~98 (int, 百分比)
    - bet:    500~10000 (int, 建議本金，機率越高越大)
    """

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
# 4. Webhook / 根目錄 (都支援)
# ==============================
@app.route("/", methods=["GET", "POST"])
@app.route("/callback", methods=["GET", "POST"])
def callback():
    # LINE 驗證或 Render 健康檢查可能會用 GET
    if request.method == "GET":
        return "OK", 200

    # LINE 正式送 Webhook 是 POST
    data = request.get_json(silent=True)
    print("📩 收到 LINE webhook JSON：", data)

    if not data or "events" not in data:
        return "OK", 200

    for event in data["events"]:
        if event.get("type") == "message" and event["message"]["type"] == "text":
            user_text = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            # 如果不是輸入「莊 / 閒 / 和」就提示
            if user_text not in ["莊", "閒", "和"]:
                reply_text = "請給我預測結果6-12局"
            else:
                # 輸入正確關鍵字，開始預測
                result, prob, bet = generate_prediction()
                reply_text = (
                    "🎲 百家樂智能預測系統\n\n"
                    f"你輸入的內容：{user_text}\n"
                    f"系統預測結果：{result}\n"
                    f"預測勝率：約 {prob}%\n"
                    f"建議本金：約 {bet} 元\n\n"
                   
                )

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
# 5. 本機測試用
# ==============================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

