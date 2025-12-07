@app.route("/", methods=["GET", "POST"])
@app.route("/callback", methods=["GET", "POST"])
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
                    "（純隨機模擬，娛樂用，沒有任何真實準確性）"
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
