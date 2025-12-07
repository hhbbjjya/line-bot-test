import os
import random
from flask import Flask, request
from linebot import LineBotApi
from linebot.models import TextSendMessage

app = Flask(__name__)

# 從環境變數讀取 Channel access token
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")

if CHANNEL_ACCESS_TOKEN:
    line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
    print("✅ 已讀取 CHANNEL_ACCESS_TOKEN")
else:
    line_bot_api = None
    print("⚠️ 環境變數 CHANNEL_ACCESS_TOKEN 未設定，機器人將無法回覆訊息，但 webhook 仍可回 200。")


def generate_prediction():
    
    r = random.random()
    if r < 0.45:
        result = "莊"
    elif r < 0.90:
        result = "閒"
    else:
        result = "和"

    prob = random.randint(50, 98)

    min_prob, max_prob = 50, 98
    min_bet, max_bet = 500, 10000
    scale = (prob - min_prob) / (max_prob - min_prob)
    bet = min_bet + scale * (max_bet - min_bet)
    bet = int(round(bet / 100.0)) * 100

    return result, prob, bet


@app.route("/", methods=["GET"])
def home():
    return "OK", 200


@app.route("/callback", methods=["POST"])
def callback():
    data = request.get_json(silent=True)
    print("📩 收到 LINE webhook JSON：", data)

    if not data or "events" not in data:
        return "OK", 200

    for event in data["events"]:
        if event.get("type") == "message" and event["message"]["type"] == "text":
            user_text = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            if user_text not in ["莊", "閒", "和"]:
                reply_text = "請給我預測結果6-12局"
            else:
                result, prob, bet = generate_prediction()
                reply_text = (
                    "🎲 百家樂預測系統\n\n"
                    f"你輸入的內容：{user_text}\n"
                    f"系統預測結果：{result}\n"
                    f"預測勝率：約 {prob}%\n"
                    f"建議本金：約 {bet} 元\n\n"
                    
                )

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
