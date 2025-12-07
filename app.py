import os
import random
from flask import Flask, request, abort
from linebot import LineBotApi
from linebot.models import TextSendMessage

app = Flask(__name__)

# 從環境變數讀取 Channel access token
CHANNEL_ACCESS_TOKEN = os.environ.get("RgcqUiBN6XtqJl0PZco4wa2dIJl+Abbqkz9fKrWmp0NbkAaINWBDMoTzwksD31lqqqnQ7V9972B7ehjV+F6wpynJVY5k0xsdm1F4ISmI75F370gf/JHao7wT+NUyMrdL8Mjpu4earKLX4son+Far4AdB04t89/1O/w1cDnyilFU=")

if not CHANNEL_ACCESS_TOKEN:
    # 如果沒有設定，啟動時直接印警告，方便你在 Render log 看到
    print("⚠️ 環境變數 CHANNEL_ACCESS_TOKEN 未設定，請到 Render 後台加入。")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)


def generate_prediction():
    
    # 1. 決定預測結果
    r = random.random()  # 0.0 ~ 1.0
    if r < 0.45:
        result = "莊"
    elif r < 0.90:
        result = "閒"
    else:
        result = "和"

    # 2. 預測機率（%）
    prob = random.randint(50, 98)

    # 3. 依機率決定本金（線性映射）
    min_prob, max_prob = 50, 98
    min_bet, max_bet = 500, 10000

    scale = (prob - min_prob) / (max_prob - min_prob)  # 0 ~ 1
    bet = min_bet + scale * (max_bet - min_bet)

    # 讓金額看起來比較整，取到最接近百元
    bet = int(round(bet / 100.0)) * 100

    return result, prob, bet


@app.route("/", methods=["GET"])
def home():
    # 給 Render / 人類健康檢查用
    return "OK", 200


@app.route("/callback", methods=["POST"])
def callback():
    # LINE Webhook 進來會打這裡（POST）
    try:
        data = request.get_json()
    except Exception as e:
        print("❌ 無法解析 JSON：", e)
        return "Bad Request", 400

    print("📩 收到 LINE webhook JSON：", data)

    # LINE 會送一個物件，裡面有 events 陣列
    if not data or "events" not in data:
        return "OK", 200

    for event in data["events"]:
        # 只處理文字訊息
        if event.get("type") == "message" and event["message"]["type"] == "text":
            user_text = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            # 規則：
            # 1) 如果輸入不是「莊 / 閒 / 和」
            #    → 回「請給我預測結果6-12局」
            if user_text not in ["莊", "閒", "和"]:
                reply_text = "請給我預測結果6-12局"

            # 2) 如果輸入是「莊 / 閒 / 和」
            #    → 產生隨機預測結果
            else:
                result, prob, bet = generate_prediction()
                reply_text = (
                    "🎲 百家樂預測系統\n\n"
                    f"你輸入的內容：{user_text}\n"
                    f"系統預測結果：{result}\n"
                    f"預測勝率：約 {prob}%\n"
                    f"建議本金：約 {bet} 元\n\n"
                   
                )

            try:
                line_bot_api.reply_message(
                    reply_token,
                    TextSendMessage(text=reply_text)
                )
            except Exception as e:
                # 就算回覆失敗，也不要讓 webhook 變成 500，避免 LINE 說錯
                print("❌ 回覆訊息失敗：", e)

    # 很重要：一定要回 200，讓 LINE 知道 webhook 處理成功
    return "OK", 200


if __name__ == "__main__":
    # 本機測試用，Render 上會用 gunicorn 啟動
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

