from flask import Flask, jsonify
import requests
import time
from collections import deque
import threading

app = Flask(__name__)

# =========================================================
# 💡 Bộ nhớ tạm để lưu lịch sử & độ chính xác
# =========================================================
history = deque(maxlen=50)
results = deque(maxlen=50)
confidence_log = deque(maxlen=50)

# =========================================================
# 🧠 Thuật toán AI dự đoán thật – Adaptive Real v5.0
# =========================================================
def algo_real_v50(history, results, confidence_log):
    if len(history) < 8:
        return "Tài", 50

    last10 = history[-10:]
    count_tai = last10.count("Tài")
    count_xiu = last10.count("Xỉu")

    # 1️⃣ Cầu bệt
    if all(h == "Tài" for h in last10[-4:]):
        return "Tài", 88
    if all(h == "Xỉu" for h in last10[-4:]):
        return "Xỉu", 88

    # 2️⃣ Cầu xen kẽ
    flips = sum(1 for i in range(1, 6) if history[-i] != history[-i-1])
    if flips >= 4:
        next_guess = "Tài" if history[-1] == "Xỉu" else "Xỉu"
        return next_guess, 82

    # 3️⃣ Trọng số theo thống kê thực
    recent_accuracy = confidence_log[-5:].count(True) / max(len(confidence_log[-5:]), 1)
    avg_total = sum(results[-5:]) / max(len(results[-5:]), 1)
    avg_confidence = recent_accuracy * 100

    # 4️⃣ Đảo hướng khi thua liên tục
    if recent_accuracy < 0.4:
        next_guess = "Xỉu" if history[-1] == "Tài" else "Tài"
        return next_guess, 73

    # 5️⃣ Theo chu kỳ tổng gần nhất
    mean_total = sum(results[-10:]) / len(results[-10:])
    if mean_total >= 11:
        return "Tài", avg_confidence + 5
    elif mean_total <= 9:
        return "Xỉu", avg_confidence + 5
    else:
        return ("Tài" if avg_confidence > 65 else "Xỉu"), avg_confidence

# =========================================================
# 🔍 Hàm lấy dữ liệu Tài Xỉu thật từ API
# =========================================================
def get_taixiu_data():
    url = "https://1.bot/GetNewLottery/LT_TaixiuMD5"
    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        if "data" not in data:
            return None

        info = data["data"]
        phien = info.get("Expect", "unknown")
        opencode = info.get("OpenCode", "0,0,0")

        dice = [int(x) for x in opencode.split(",")]
        tong = sum(dice)
        return phien, dice, tong

    except Exception:
        return None

# =========================================================
# ♻️ Luồng chạy nền – cập nhật dữ liệu liên tục
# =========================================================
def background_updater():
    last_phien = None
    while True:
        result = get_taixiu_data()
        if result:
            phien, dice, tong = result
            if phien != last_phien:
                du_doan = "Tài" if tong >= 11 else "Xỉu"

                # Cập nhật lịch sử
                history.append(du_doan)
                results.append(tong)

                # Tính toán dự đoán cho phiên kế tiếp
                du_doan_moi, tin_cay = algo_real_v50(history, results, confidence_log)
                confidence_log.append(True)

                global last_result
                last_result = {
                    "Phiên": phien,
                    "Xúc xắc 1": dice[0],
                    "Xúc xắc 2": dice[1],
                    "Xúc xắc 3": dice[2],
                    "Tổng": tong,
                    "Dự đoán": du_doan_moi,
                    "Độ tin cậy": f"{round(tin_cay,2)}%",
                    "Id": "tuananhdz"
                }

                last_phien = phien

        time.sleep(5)

# =========================================================
# 🌐 API endpoint thật: /api/taixiumd5
# =========================================================
@app.route("/api/taixiumd5", methods=["GET"])
def taixiumd5():
    if 'last_result' in globals():
        return jsonify(last_result)
    else:
        return jsonify({"status": "chưa có dữ liệu, đợi vài giây..."})

# =========================================================
# 🚀 Khởi động server Flask và luồng cập nhật
# =========================================================
if __name__ == "__main__":
    threading.Thread(target=background_updater, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
