from flask import Flask, jsonify
import requests
import time
from collections import deque
import threading

app = Flask(__name__)

# =========================================================
# 💾 Bộ nhớ tạm lưu lịch sử & độ tin cậy
# =========================================================
history = deque(maxlen=50)
totals = deque(maxlen=50)
win_log = deque(maxlen=50)
last_result = {"status": "đang khởi động..."}  # giữ key 'status'

# =========================================================
# 🧠 Thuật toán VIP
# =========================================================
def algo_vip(history, totals, win_log):
    hist = list(history)
    tot = list(totals)
    wins = list(win_log)
    if len(hist) < 6:
        return {"du_doan": "Tài", "do_tin_cay": 60.0}
    recent_totals = tot[-10:]
    recent_history = hist[-10:]
    recent_wins = wins[-10:]
    mean_total = sum(recent_totals) / len(recent_totals)
    tai_ratio = recent_history.count("Tài") / len(recent_history)
    win_rate = recent_wins.count(True) / max(len(recent_wins), 1)
    du_doan = "Tài" if mean_total > 10.8 or tai_ratio > 0.55 else "Xỉu"
    tin_cay = 60 + (tai_ratio * 20) + (win_rate * 20) + ((mean_total - 10.5) * 5)
    tin_cay = max(60, min(round(tin_cay, 1), 98))
    return {"du_doan": du_doan, "do_tin_cay": tin_cay}

def algo_real_v90R_12(history, totals, win_log):
    hist = list(history)
    wins = list(win_log)[-10:]
    if len(hist) < 2:
        return {"du_doan": "Tài", "do_tin_cay": 70}
    chain = 0
    for i in range(1, min(6, len(hist))):
        if hist[-i] == hist[-i-1]:
            chain += 1
        else:
            break
    du_doan = hist[-1] if chain >= 3 else ("Tài" if hist[-1] == "Xỉu" else "Xỉu")
    confidence = 70 + wins.count(True) / max(len(wins), 1) * 25
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

def algo_real_v90R_13(history, totals, win_log):
    hist = list(history)
    wins = list(win_log)[-10:]
    last7 = hist[-7:] if len(hist) >= 7 else hist
    tai_count = last7.count("Tài")
    xiu_count = last7.count("Xỉu")
    du_doan = "Tài" if tai_count > xiu_count else "Xỉu"
    confidence = 70 + wins.count(True) / max(len(wins), 1) * 25
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

def algo_real_v90R_14(history, totals, win_log):
    tot = list(totals)
    hist = list(history)
    wins = list(win_log)[-10:]
    last10_totals = tot[-10:] if len(tot) >= 10 else tot
    mean_total = sum(last10_totals) / len(last10_totals) if last10_totals else 10.5
    if mean_total >= 11:
        du_doan = "Tài"
    elif mean_total <= 9:
        du_doan = "Xỉu"
    else:
        du_doan = hist[-1] if hist else "Tài"
    confidence = 75 + wins.count(True) / max(len(wins), 1) * 20
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

def algo_real_v90R_15(history, totals, win_log):
    hist = list(history)
    wins = list(win_log)[-10:]
    last12 = hist[-12:] if len(hist) >= 12 else hist
    tai_ratio = last12.count("Tài") / len(last12) if last12 else 0
    xiu_ratio = last12.count("Xỉu") / len(last12) if last12 else 0
    if tai_ratio > 0.6:
        du_doan = "Tài"
    elif xiu_ratio > 0.6:
        du_doan = "Xỉu"
    else:
        du_doan = hist[-1] if hist else "Tài"
    confidence = 75 + wins.count(True) / max(len(wins), 1) * 20
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

algorithms = [algo_vip, algo_real_v90R_12, algo_real_v90R_13, algo_real_v90R_14, algo_real_v90R_15]

# =========================================================
# 🔍 Lấy dữ liệu thật từ API
# =========================================================
def get_taixiu_data():
    url = "https://1.bot/GetNewLottery/LT_TaixiuMD5"
    for _ in range(3):
        try:
            res = requests.get(url, timeout=6)
            data = res.json()
            if "data" in data and data["data"]:
                info = data["data"]
                phien = info.get("Expect", int(time.time()))
                opencode = info.get("OpenCode", "1,2,3")
                dice = [int(x) for x in opencode.split(",")]
                tong = sum(dice)
                return phien, dice, tong
        except Exception:
            time.sleep(2)
    return None

# =========================================================
# ♻️ Background updater
# =========================================================
def background_updater():
    global last_result
    last_phien = None
    while True:
        data = get_taixiu_data()
        if not data:
            phien = int(time.time())
            dice = [1,2,3]
            tong = sum(dice)
        else:
            phien, dice, tong = data

        # check phiên mới hoặc lần đầu
        if last_result.get("status", None) == "đang khởi động..." or phien != last_phien:
            ket_qua = "Tài" if tong >= 11 else "Xỉu"
            history.append(ket_qua)
            totals.append(tong)

            # chọn thuật toán tốt nhất
            results_all = [algo(history, totals, win_log) for algo in algorithms]
            best = max(results_all, key=lambda x: x["do_tin_cay"])
            pred = best["du_doan"]
            # win_log dựa trên dự đoán đúng hay sai
            win_log.append(pred == ket_qua)

            last_result = {
                "Phiên": phien,
                "Xúc xắc": dice,
                "Tổng": tong,
                "Kết quả thật": ket_qua,
                "Dự đoán": pred,
                "Độ tin cậy": f"{best['do_tin_cay']}%",
                "Nguồn thuật toán": algorithms[results_all.index(best)].__name__,
                "status": "Cập nhật thành công ✅"
            }

            print(f"[OK] Phiên: {phien} - KQ: {ket_qua} ({tong}) - Dự đoán: {pred} ({best['do_tin_cay']}%)")
            last_phien = phien

        time.sleep(3)

# =========================================================
# 🌐 API endpoint
# =========================================================
@app.route("/api/taixiumd5", methods=["GET"])
def api_taixiu():
    return jsonify(last_result)

# =========================================================
# 🚀 Chạy Flask server
# =========================================================
if __name__ == "__main__":
    threading.Thread(target=background_updater, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
