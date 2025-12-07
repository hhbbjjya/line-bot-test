from flask import Flask, request
from linebot import LineBotApi
from linebot.models import TextSendMessage
import random

app = Flask(__name__)

# 換成你自己的 Channel access token
CHANNEL_ACCESS_TOKEN = "rCnR+rTlXzoSYgSNm0YMNuCWudA9uxY3gDaX421tCP7x5zQZnDUj4U+lkdBPf+q7qqnQ7V9972B7ehjV+F6wpynJVY5k0xsdm1F4ISmI75GYBnkq7Fam5G1+v1LB5L6KGzjcqe8YCowwvIIe6LnbtQdB04t89/1O/w1cDnyilFU="

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)


@app.route("/", methods=["GET"])
def index():
    return "OK"


@app.route("/callback", methods=["POST"])
def callback():
    data = request.get_json()
    print("收到 LINE webhook JSON：", data)

    # 沒有 events 就直接回 OK，避免錯誤
    if not data or "events" not in data:
        return "OK"

    for event in data["events"]:
        # 只處理文字訊息
        if event.get("type") == "message" and event["message"]["type"] == "text":
            user_text = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            # 判斷要回什麼
            if user_text == "預測":
                result = random_prediction()
                prob = random.randint(60, 90)
                bet = random.randint(1000, 5000)

                reply = (
                    f"🎲 假百家樂模擬結果\n\n"
                    f"預測結果：{result}\n"
                    f"通關機率：約 {prob}%\n"
                    f"建議下注：{bet} 元\n\n"
                    f"（純展示用，沒有任何真實準確性）"
                )
            else:
                reply = "輸入「預測」來看看假百家樂模擬結果 😎"

            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text=reply)
            )

    # 一律回 200，避免 LINE 說 400
    return "OK"


def random_prediction():
    """讓『和』的機率比較低，莊／閒比較常出"""
    r = random.random()
    if r < 0.47:
        return "莊"
    elif r < 0.94:
        return "閒"
    else:
        return "和"


if __name__ == "__main__":
    app.run(port=5000)
