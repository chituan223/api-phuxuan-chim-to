from flask import Flask, jsonify
import requests
import time
from collections import deque
import threading
import math

app = Flask(__name__)

# =========================================================
# 💡 Bộ nhớ tạm để lưu lịch sử & độ chính xác
# =========================================================
history = deque(maxlen=50)
results = deque(maxlen=50)
confidence_log = deque(maxlen=50)


# =========================================================
# 🧠 Thuật toán AI Pentter Real v7.3 (chuẩn thật)
# =========================================================
def algo_pentter_v73(history, results, confidence_log):
    if len(history) < 6:
        return "Tài", 55

    last10 = history[-10:]
    count_tai = last10.count("Tài")
    count_xiu = last10.count("Xỉu")
    mean_total = sum(results[-min(10, len(results)):]) / max(1, len(results))

    # 1️⃣ Phân tích cầu bệt mạnh
    if all(x == "Tài" for x in last10[-4:]):
        return "Tài", 88 + (count_tai - count_xiu) * 0.5
    if all(x == "Xỉu" for x in last10[-4:]):
        return "Xỉu", 88 + (count_xiu - count_tai) * 0.5

    # 2️⃣ Cầu xen kẽ
    flips = sum(1 for i in range(1, len(last10)) if last10[i] != last10[i - 1])
    if flips >= 6:
        next_guess = "Tài" if history[-1] == "Xỉu" else "Xỉu"
        return next_guess, 76 + math.sin(flips) * 5

    # 3️⃣ Phân tích chu kỳ tổng
    if mean_total >= 12:
        return "Tài", 82
    elif mean_total <= 8:
        return "Xỉu", 82

    # 4️⃣ Độ tin cậy điều chỉnh theo độ lệch trung bình
    diff = abs(count_tai - count_xiu)
    conf = 65 + diff * 2 + (flips % 3) * 3
    if conf > 91: conf = 91
    if conf < 61: conf = 61

    # 5️⃣ Xu hướng theo kết quả gần nhất
    trend = "Tài" if sum(results[-3:]) / 3 > 10.5 else "Xỉu"
    return trend, conf


# =========================================================
# 🔍 Lấy dữ liệu thật từ API (MD5)
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
# ♻️ Luồng cập nhật dữ liệu thật liên tục
# =========================================================
def background_updater():
    last_phien = None
    while True:
        result = get_taixiu_data()
        if result:
            phien, dice, tong = result
            if phien != last_phien:
                ket_qua = "Tài" if tong >= 11 else "Xỉu"
                history.append(ket_qua)
                results.append(tong)

                du_doan_moi, tin_cay = algo_pentter_v73(history, results, confidence_log)
                confidence_log.append(tin_cay > 70)

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
# 🌐 API thật /api/taixiumd5
# =========================================================
@app.route("/api/taixiumd5", methods=["GET"])
def taixiumd5():
    if 'last_result' in globals():
        return jsonify(last_result)
    else:
        return jsonify({"status": "Đang cập nhật dữ liệu, vui lòng đợi 5s..."})


# =========================================================
# 🚀 Chạy Flask + Thread cập nhật
# =========================================================
if __name__ == "__main__":
    threading.Thread(target=background_updater, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
