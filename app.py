from flask import Flask, request

app = Flask(__name__)

# 不管是 "/" 還是 "/callback"，都接受 GET + POST
@app.route("/", methods=["GET", "POST"])
@app.route("/callback", methods=["GET", "POST"])
def callback():
    print("收到一個請求：", request.method, request.path)
    print("Body:", request.get_data(as_text=True))
    # 永遠回 200，避免 LINE 抱怨
    return "OK", 200

if __name__ == "__main__":
    # Render 會用 gunicorn 啟，不太會跑到這裡，但本機測試也 OK
    app.run(host="0.0.0.0", port=10000)
