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
totals = deque(maxlen=50)
win_log = deque(maxlen=50)

# =========================================================
# 🧠 10 thuật toán Real AI Logic (v81R → v90R)
# =========================================================

def algo_v81R(history, totals, win_log):
    if len(history) < 6:
        return {"du_doan": "Tài", "do_tin_cay": 65.0}
    mean_total = sum(totals[-6:]) / len(totals[-6:])
    win_rate = win_log[-8:].count(True) / max(len(win_log[-8:]), 1)
    du_doan = "Tài" if mean_total > 10.8 else "Xỉu"
    tin_cay = 60 + (win_rate * 35)
    return {"du_doan": du_doan, "do_tin_cay": round(tin_cay, 1)}

def algo_v82R(history, totals, win_log):
    if len(history) < 6:
        return {"du_doan": "Tài", "do_tin_cay": 60.0}
    last5 = history[-5:]
    mean_total = sum(totals[-8:]) / len(totals[-8:])
    flips = sum(1 for i in range(1, len(last5)) if last5[i] != last5[i-1])
    stable = 1 - flips / 4
    du_doan = "Tài" if mean_total > 10.8 else "Xỉu"
    tin_cay = 60 + (stable * 35)
    return {"du_doan": du_doan, "do_tin_cay": round(tin_cay, 1)}

def algo_v83R(history, totals, win_log):
    if len(history) < 8:
        return {"du_doan": "Xỉu", "do_tin_cay": 68.0}
    mean_total = sum(totals[-10:]) / len(totals[-10:])
    tai_ratio = sum(t > 10.5 for t in totals[-10:]) / len(totals[-10:])
    win_rate = win_log[-10:].count(True) / max(len(win_log[-10:]), 1)
    du_doan = "Tài" if tai_ratio > 0.55 else "Xỉu"
    tin_cay = 70 + (win_rate * 25)
    return {"du_doan": du_doan, "do_tin_cay": round(tin_cay, 1)}

def algo_v84R(history, totals, win_log):
    if len(history) < 5:
        return {"du_doan": "Tài", "do_tin_cay": 63.0}
    count_tai = history[-6:].count("Tài")
    mean_total = sum(totals[-6:]) / len(totals[-6:])
    du_doan = "Tài" if (count_tai >= 4 or mean_total >= 11) else "Xỉu"
    tin_cay = 65 + abs(11 - mean_total) * 4
    return {"du_doan": du_doan, "do_tin_cay": round(min(tin_cay, 96.0), 1)}

def algo_v85R(history, totals, win_log):
    if len(history) < 10:
        return {"du_doan": "Xỉu", "do_tin_cay": 64.0}
    flips = sum(1 for i in range(1, 6) if history[-i] != history[-i-1])
    mean_total = sum(totals[-8:]) / len(totals[-8:])
    du_doan = "Tài" if flips <= 1 and mean_total >= 10.8 else "Xỉu"
    tin_cay = 70 + (1 - (flips / 5)) * 25
    return {"du_doan": du_doan, "do_tin_cay": round(tin_cay, 1)}

def algo_v86R(history, totals, win_log):
    if len(history) < 7:
        return {"du_doan": "Tài", "do_tin_cay": 62.0}
    mean_total = sum(totals[-7:]) / len(totals[-7:])
    std_total = (sum((x - mean_total) ** 2 for x in totals[-7:]) / 7) ** 0.5
    du_doan = "Tài" if mean_total > 10.7 else "Xỉu"
    tin_cay = 68 + (2.5 - std_total) * 12
    return {"du_doan": du_doan, "do_tin_cay": round(max(min(tin_cay, 95), 60), 1)}

def algo_v87R(history, totals, win_log):
    if len(history) < 6:
        return {"du_doan": "Xỉu", "do_tin_cay": 61.0}
    mean_total = sum(totals[-9:]) / len(totals[-9:])
    ratio_tai = sum(t > 10.5 for t in totals[-9:]) / len(totals[-9:])
    du_doan = "Tài" if ratio_tai >= 0.6 else "Xỉu"
    tin_cay = 70 + (abs(mean_total - 10.5) * 6)
    return {"du_doan": du_doan, "do_tin_cay": round(tin_cay, 1)}

def algo_v88R(history, totals, win_log):
    if len(history) < 8:
        return {"du_doan": "Tài", "do_tin_cay": 65.0}
    recent = history[-6:]
    tai_dom = recent.count("Tài") / 6
    mean_total = sum(totals[-6:]) / len(totals[-6:])
    du_doan = "Tài" if tai_dom > 0.55 or mean_total >= 10.9 else "Xỉu"
    tin_cay = 70 + (tai_dom * 25)
    return {"du_doan": du_doan, "do_tin_cay": round(tin_cay, 1)}

def algo_v89R(history, totals, win_log):
    if len(history) < 8:
        return {"du_doan": "Xỉu", "do_tin_cay": 63.0}
    tai_seq = sum(1 for h in history[-5:] if h == "Tài")
    mean_total = sum(totals[-8:]) / len(totals[-8:])
    du_doan = "Tài" if (tai_seq >= 3 or mean_total >= 10.8) else "Xỉu"
    tin_cay = 68 + (tai_seq * 5)
    return {"du_doan": du_doan, "do_tin_cay": round(min(tin_cay, 96.0), 1)}

def algo_v90R(history, totals, win_log):
    if len(history) < 9:
        return {"du_doan": "Tài", "do_tin_cay": 60.0}
    mean_total = sum(totals[-9:]) / len(totals[-9:])
    win_rate = win_log[-10:].count(True) / max(len(win_log[-10:]), 1)
    du_doan = "Tài" if (mean_total > 10.6 and win_rate >= 0.5) else "Xỉu"
    tin_cay = 70 + (win_rate * 25)
    return {"du_doan": du_doan, "do_tin_cay": round(tin_cay, 1)}

# Danh sách 10 thuật toán
algorithms = [
    algo_v81R, algo_v82R, algo_v83R, algo_v84R, algo_v85R,
    algo_v86R, algo_v87R, algo_v88R, algo_v89R, algo_v90R
]

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
                ket_qua = "Tài" if tong >= 11 else "Xỉu"

                # Lưu dữ liệu thật
                history.append(ket_qua)
                totals.append(tong)
                win_log.append(True)

                # Chạy 10 thuật toán → chọn cái có độ tin cậy cao nhất
                results_all = []
                for algo in algorithms:
                    out = algo(history, totals, win_log)
                    out["algo_name"] = algo.__name__
                    results_all.append(out)

                best = max(results_all, key=lambda x: x["do_tin_cay"])

                global last_result
                last_result = {
                    "Phiên": phien,
                    "Xúc xắc": dice,
                    "Tổng": tong,
                    "Kết quả thật": ket_qua,
                    "Dự đoán": best["du_doan"],
                    "Độ tin cậy": f"{best['do_tin_cay']}%",
                    "Nguồn thuật toán": best["algo_name"],
                    "Id": "tuananhdz"
                }

                last_phien = phien

        time.sleep(5)

# =========================================================
# 🌐 API endpoint: /api/taixiumd5
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
