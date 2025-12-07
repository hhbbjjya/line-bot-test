from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "OK", 200

# 一定要有 POST，最好連 GET 也一起開
@app.route("/callback", methods=["GET", "POST"])
def callback():
    print("收到一個請求：", request.method, request.path)
    print("Body:", request.get_data(as_text=True))
    return "OK", 200   # 永遠回 200，讓 LINE 不會抱怨

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
