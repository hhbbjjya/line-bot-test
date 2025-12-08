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

# 每個使用者累積輸入的牌路字串（包含莊/閒/和）
user_history_seq = {}

# ==============================
# 4. 判斷輸入是否為 6~12 個「莊/閒/和」(啟動預測用)
# ==============================
def is_valid_sequence(text: str) -> bool:
    if not (6 <= len(text) <= 12):
        return False
    for ch in text:
        if ch not in ["莊", "閒", "和"]:
            return False
    return True

# 判斷是否為「至少 1 個字，且每個都是 莊/閒/和」
# 用在已經啟動後，追加輸入用
def is_valid_result_chars(text: str) -> bool:
    if len(text) < 1:
        return False
    for ch in text:
        if ch not in ["莊", "閒", "和"]:
            return False
    return True

# ==============================
# 5-1. 牌路判斷小工具（莊/閒 → B/P）
# ==============================

def _seq_to_history(seq: str):
    """
    把「莊閒和」字串轉成只含 B / P 的歷史：
    '莊' -> 'B'
    '閒' -> 'P'
    '和' -> 略過 (不算進大路)
    """
    history = []
    for ch in seq:
        if ch == "莊":
            history.append("B")
        elif ch == "閒":
            history.append("P")
        # '和' 直接略過
    return history


def _is_long_dragon(history, length=4):
    """
    長龍判斷：最後 length 手都同一邊
    回傳: (bool, side or None)
    """
    if len(history) < length:
        return False, None
    last = history[-1]
    for i in range(1, length + 1):
        if history[-i] != last:
            return False, None
    return True, last


def _is_jump_dragon(history, length=4):
    """
    跳龍判斷：例如 BPBP / PBPB
    """
    if len(history) < length:
        return False
    seq = history[-length:]
    for i in range(1, len(seq)):
        if seq[i] == seq[i - 1]:
            return False
    return True


def _is_symmetric_copy(history, window=4):
    """
    對稱複製：...ABCD | ABCD 或 ...ABCD | DCBA
    """
    if len(history) < window * 2:
        return False
    recent = history[-window:]
    prev = history[-2 * window:-window]
    if recent == prev or recent == prev[::-1]:
        return True
    return False


def _is_just_cut_head(history, min_streak=3):
    """
    斷頭判斷:
    ... X X X Y  (X != Y，且 X 至少連續 min_streak 次)
    回傳: (bool, X, Y)
    """
    if len(history) < min_streak + 1:
        return False, None, None
    last = history[-1]
    prev = history[-2]
    if last == prev:
        return False, None, None

    streak_side = prev
    streak_len = 1
    idx = len(history) - 2
    while idx - 1 >= 0 and history[idx - 1] == streak_side:
        streak_len += 1
        idx -= 1

    if streak_len >= min_streak:
        return True, streak_side, last
    return False, None, None


def _triple_rule_vote(history):
    """
    三式法則: 回傳 { 'B': 分數, 'P': 分數 }
    1. 趨勢式
    2. 節奏式
    3. 壓力式
    """
    score = {"B": 0.0, "P": 0.0}
    n = len(history)
    if n == 0:
        return score

    # 1. 趨勢式：看最近 6 手哪邊多
    window = history[-6:] if n >= 6 else history[:]
    cntB = window.count("B")
    cntP = window.count("P")
    if cntB > cntP:
        score["B"] += 0.8
    elif cntP > cntB:
        score["P"] += 0.8

    # 2. 節奏式：看轉折數
    turns = 0
    for i in range(1, len(window)):
        if window[i] != window[i - 1]:
            turns += 1
    if len(window) >= 3:
        last = window[-1]
        opp = "P" if last == "B" else "B"
        if turns >= len(window) // 2:
            # 轉折多：說是變盤，投給反邊
            score[opp] += 0.6
        else:
            # 轉折少：說是續牌，投給同邊
            score[last] += 0.6

    # 3. 壓力式：看整體莊閒比例
    totalB = history.count("B")
    totalP = history.count("P")
    if totalB > totalP * 1.3:
        score["P"] += 0.6
    elif totalP > totalB * 1.3:
        score["B"] += 0.6

    return score


def _sub_road_check(history):
    """
    副路驗證:
    看最近 4 手的轉折數，來判斷偏續牌還是變盤。
    回傳: (bias_side or None, 描述文字)
    """
    if len(history) < 4:
        return None, "副路資料不足，略過副路驗證。"

    window = history[-4:]
    turns = 0
    for i in range(1, len(window)):
        if window[i] != window[i - 1]:
            turns += 1

    last = window[-1]
    opp = "P" if last == "B" else "B"

    if turns >= 2:
        # 轉折多：偏變盤 → 壓反邊
        return opp, f"副路顯示近期轉折偏多，屬於變盤格局，略偏向 { '莊' if opp == 'B' else '閒' }。"
    else:
        # 轉折少：偏續牌 → 壓同邊
        return last, f"副路顯示近期轉折偏少，屬於續牌格局，略偏向 { '莊' if last == 'B' else '閒' }。"


def _fake_baccarat_by_pattern(history):
    """
    核心牌路分析：
    history: ['B','P','B',...]
    回傳: side('B'/'P'), conf(0.55~0.78), reasons(list[str])
    """
    reasons = []
    score = {"B": 0.0, "P": 0.0}

    if len(history) == 0:
        # 沒資料 → 退回給上層隨機
        return None, None, ["目前沒有有效牌路資料，改用隨機場能預測。"]

    last = history[-1]

    # 1. 長龍
    is_long, dragon_side = _is_long_dragon(history, length=4)
    if is_long:
        score[dragon_side] += 2.0
        reasons.append(f"目前處於{'莊' if dragon_side == 'B' else '閒'}方長龍結構，慣性仍在延續中。")

    # 2. 跳龍
    if _is_jump_dragon(history, length=4):
        opp = "P" if last == "B" else "B"
        score[opp] += 1.2
        reasons.append("最近出現明顯跳龍節奏，依照節奏延伸，下一手偏向反向。")

    # 3. 對稱複製
    if _is_symmetric_copy(history, window=4):
        score[last] += 1.0
        reasons.append("大路呈現對稱複製現象，慣性偏向延續目前結構。")

    # 4. 斷頭
    cut, cut_side, new_side = _is_just_cut_head(history, min_streak=3)
    if cut:
        score[new_side] += 1.3
        reasons.append(
            f"前一段出現{'莊' if cut_side == 'B' else '閒'}方長段被斷頭，"
            f"常見走勢為新方向再拉一小段，偏向{'莊' if new_side == 'B' else '閒'}。"
        )

    # 5. 三式法則
    triple = _triple_rule_vote(history)
    score["B"] += triple["B"]
    score["P"] += triple["P"]
    reasons.append("套用三式法則評估趨勢、節奏與壓力位，整體結構已逐漸偏向單一方向。")

    # 6. 副路驗證
    bias_side, desc = _sub_road_check(history)
    reasons.append(desc)
    if bias_side in ("B", "P"):
        score[bias_side] += 0.9

    # 決定邊
    if score["B"] > score["P"]:
        side = "B"
    elif score["P"] > score["B"]:
        side = "P"
    else:
        side = random.choice(["B", "P"])
        reasons.append("主路與副路訊號拉鋸，採用隨機打點平衡雙方能量。")

    # 根據分差決定信心
    diff = abs(score["B"] - score["P"])
    base_conf = 0.55
    conf = base_conf + min(diff * 0.08, 0.2)  # 最多 +0.2
    conf += (random.random() - 0.5) * 0.05     # 小抖動
    conf = max(0.55, min(conf, 0.78))

    return side, conf, reasons


# ==============================
# 5-2. 預測邏輯（以你的原本設計為主，外加牌路）
# ==============================
def generate_prediction(history_seq: str | None):
    """
    history_seq:
        - 傳入目前「累積」的莊閒和字串（可能超過 12 個）
        - 如果是 None 或無法分析 → 回到原本隨機預測
    回傳: (result_text, prob, bet, detail_text)
    """

    detail_lines = []

    if history_seq is not None:
        history = _seq_to_history(history_seq)
        # 全是「和」或有效莊閒太少 → 視為無效牌路
        if len(history) > 0:
            side, conf, reasons = _fake_baccarat_by_pattern(history)
            if side is not None and conf is not None:
                # 用牌路預測結果
                result = "莊" if side == "B" else "閒"
                prob = int(round(conf * 100))
                prob = max(50, min(98, prob))

                # 用你原本的公式算建議本金
                min_bet = 500
                max_bet = 10000
                bet_float = min_bet + (prob - 50) / (98 - 50) * (max_bet - min_bet)
                bet = int(round(bet_float / 100.0)) * 100
                bet = max(min_bet, min(max_bet, bet))

                detail_lines.extend(reasons)
                detail_text = "📊 牌路分析：\n" + "\n".join(
                    f"{i+1}. {msg}" for i, msg in enumerate(detail_lines)
                )
                detail_text += "\n\n※ 本系統僅供娛樂參考，請勿重壓。"

                return result, prob, bet, detail_text
            else:
                detail_lines.extend(reasons)
        else:
            detail_lines.append("目前有效莊/閒資料過少，無法形成穩定牌路，改用隨機場能預測。")

    # 走到這邊代表：沒有 history_seq 或牌路不可用 → 回到你原本隨機邏輯

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

    bet_float = min_bet + (prob - 50) / (98 - 50) * (max_bet - min_bet)
    bet = int(round(bet_float / 100.0)) * 100
    bet = max(min_bet, min(max_bet, bet))

    if not detail_lines:
        detail_lines.append("目前尚未形成明顯牌路結構，改以隨機場能與機率平衡作為參考。")

    detail_text = "📊 牌路分析：\n" + "\n".join(
        f"{i+1}. {msg}" for i, msg in enumerate(detail_lines)
    )
    detail_text += "\n\n※ 本系統僅供娛樂參考，請勿重壓。"

    return result, prob, bet, detail_text


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

            # 啟動條件：這次輸入是否為「6~12 個莊閒和」
            valid_seq = is_valid_sequence(user_text)
            # 單純結果字串（至少一個字，全是莊閒和）
            valid_result_chars = is_valid_result_chars(user_text)

            # 是否在連續預測模式中
            in_session = (
                last_trigger is not None and (now - last_trigger) <= SESSION_TIMEOUT_SEC
            )

            history_seq = None

            if valid_seq:
                # 第一次觸發或重新觸發：把這次輸入當起點或接在舊的後面
                prev = user_history_seq.get(user_id, "")
                history_seq = prev + user_text
                user_history_seq[user_id] = history_seq
                user_session_last_trigger[user_id] = now

            elif in_session and valid_result_chars:
                # 已在一分鐘內 & 這次輸入是合法結果字串 → 接在之前的後面
                prev = user_history_seq.get(user_id, "")
                history_seq = prev + user_text
                user_history_seq[user_id] = history_seq
                user_session_last_trigger[user_id] = now

            elif in_session:
                # 在 session 內但輸入不是莊閒和 → 仍用目前累積的牌路做一次預測
                history_seq = user_history_seq.get(user_id, None)
                user_session_last_trigger[user_id] = now

            # 判斷要不要預測
            if history_seq is not None:
                # 只要有牌路（不論剛啟動還是接續），就做預測
                result, prob, bet, detail_text = generate_prediction(history_seq)

                # 只顯示最近 30 手給朋友看就好
                show_seq = history_seq[-30:]

                reply_text = (
                    "🎲 百家樂智能預測系統\n\n"
                    f"目前累積牌路（最近 30 手內）：{show_seq}\n\n"
                    f"系統預測結果：{result}\n"
                    f"預測勝率：約 {prob}%\n"
                    f"建議本金：約 {bet} 元\n\n"
                    f"{detail_text}"
                )
            else:
                # 沒有啟動，也不在 session 內
                if valid_result_chars:
                    # 他有輸入莊/閒/和，但不足 6~12 個
                    reply_text = "請先給我 6～12 局的結果，例如：莊閒閒莊莊和閒閒。"
                else:
                    reply_text = "請給我 6～12 局的預測結果，例如：莊閒閒莊莊和閒閒。"

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
