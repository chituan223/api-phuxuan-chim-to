from flask import Flask, jsonify
import requests
import time
from collections import deque
import threading

app = Flask(__name__)

# =========================================================
# 💡 Bộ nhớ tạm để lưu lịch sử & độ chính xác
# =========================================================
history = deque(maxlen=200)   # lưu kết quả ("Tài"/"Xỉu") theo thứ tự cũ->mới
totals = deque(maxlen=200)    # lưu tổng xúc xắc tương ứng
win_log = deque(maxlen=200)   # lưu True/False: dự đoán trước đó có trúng không

# Lưu dự đoán gần nhất để so sánh với phiên tiếp theo
last_prediction = None        # dạng {"du_doan": "Tài"/"Xỉu", "do_tin_cay": 85.0}
last_phien_seen = None

# =========================================================
# 🧠 Thuật toán Luck8 Real AI Logic v8.0R (No Random)
# =========================================================
def algo_real_v80R(history, totals, win_log):
    """
    Trả về dict {"du_doan": "Tài"/"Xỉu", "do_tin_cay": float}
    Confidence được điều chỉnh động theo win_rate và tín hiệu chuỗi.
    """
    # bảo đảm có ít nhất dữ liệu tối thiểu
    if len(history) < 6 or len(totals) < 6:
        # tạm confidence ngẫu nhiên trong khoảng 45-65 thay vì cố định 70
        return {"du_doan": "Tài", "do_tin_cay": 55.0}

    last10 = list(history)[-10:]
    last5 = list(history)[-5:]
    # tính win_rate gần đây (dựa trên win_log)
    recent_wins = list(win_log)[-10:]
    win_rate = recent_wins.count(True) / max(len(recent_wins), 1)

    # 1) Cầu bệt mạnh -> confidence rất cao
    if len(last5) == 5 and all(h == "Tài" for h in last5):
        return {"du_doan": "Tài", "do_tin_cay": min(95.0, 75.0 + win_rate * 20)}
    if len(last5) == 5 and all(h == "Xỉu" for h in last5):
        return {"du_doan": "Xỉu", "do_tin_cay": min(95.0, 75.0 + win_rate * 20)}

    # 2) Cầu xen kẽ (flips)
    flips = sum(1 for i in range(1, min(len(history), 6)) if history[-i] != history[-i-1])
    if flips >= 4:
        pred = "Tài" if history[-1] == "Xỉu" else "Xỉu"
        return {"du_doan": pred, "do_tin_cay": min(92.0, 68.0 + win_rate * 24)}

    # 3) Phân tích tổng (totals)
    last_totals = list(totals)[-8:]
    mean_total = sum(last_totals) / max(len(last_totals), 1)
    high_ratio = sum(1 for t in last_totals if t >= 11) / max(len(last_totals), 1)

    # 4) Logic chính kết hợp win_rate + mean_total
    if mean_total >= 11 and high_ratio > 0.55:
        do_tin = 65.0 + win_rate * 30.0  # dao động theo win_rate
        return {"du_doan": "Tài", "do_tin_cay": round(min(do_tin, 99.0), 1)}
    if mean_total <= 9 and (1 - high_ratio) > 0.55:
        do_tin = 65.0 + win_rate * 30.0
        return {"du_doan": "Xỉu", "do_tin_cay": round(min(do_tin, 99.0), 1)}

    # 5) Khi không rõ ràng: dựa trên win_rate và cân bằng chuỗi
    recent_bias = last10.count("Tài") - last10.count("Xỉu")
    if win_rate >= 0.6:
        # nếu win_rate tốt -> giữ hướng vừa thắng
        prefer = history[-1]
        base = 58.0 + win_rate * 30.0
        conf = round(min(max(base + recent_bias * 2, 1.0), 99.0), 1)
        return {"du_doan": prefer, "do_tin_cay": conf}
    else:
        # nghi ngờ -> đảo hướng nhẹ
        prefer = "Xỉu" if history[-1] == "Tài" else "Tài"
        base = 52.0 + win_rate * 30.0
        conf = round(min(max(base - abs(recent_bias) * 2, 1.0), 98.0), 1)
        return {"du_doan": prefer, "do_tin_cay": conf}

# =========================================================
# 🔍 Hàm lấy dữ liệu Tài Xỉu thật từ API
# =========================================================
def get_taixiu_data():
    url = "https://1.bot/GetNewLottery/LT_TaixiuMD5"
    try:
        res = requests.get(url, timeout=6)
        data = res.json()
        if not data or "data" not in data:
            return None

        info = data["data"]
        phien = info.get("Expect", "unknown")
        opencode = info.get("OpenCode", "0,0,0")
        # phuc truong: đôi khi opencode có spaces -> strip
        dice = [int(x.strip()) for x in opencode.split(",")]
        tong = sum(dice)
        return phien, dice, tong
    except Exception as e:
        # không raise để luồng tiếp tục chạy
        print("Lỗi khi gọi API dữ liệu:", e)
        return None

# =========================================================
# ♻️ Luồng chạy nền – cập nhật dữ liệu liên tục
# =========================================================
def background_updater():
    global last_prediction, last_phien_seen
    last_phien_seen = None
    last_prediction = None

    while True:
        data = get_taixiu_data()
        if data:
            phien, dice, tong = data
            ket_qua = "Tài" if tong >= 11 else "Xỉu"

            # nếu là phiên mới (chưa xử lý)
            if phien != last_phien_seen:
                # 1) Nếu trước đó có 1 dự đoán, đánh giá nó (so sánh với kết quả hiện tại)
                if last_prediction is not None:
                    prev_pred = last_prediction.get("du_doan")
                    was_win = (prev_pred == ket_qua)
                    win_log.append(was_win)
                    print(f"[ĐÁNH GIÁ] Phiên {phien}: kết quả={ket_qua} | dự đoán trước đó={prev_pred} -> {'WIN' if was_win else 'LOSE'}")
                else:
                    # chưa có dự đoán trước đó -> không append
                    print(f"[MỚI] Phiên {phien}: kết quả={ket_qua} (chưa có dự đoán cũ để đánh giá)")

                # 2) Cập nhật lịch sử kết quả hiện tại
                history.append(ket_qua)
                totals.append(tong)

                # 3) Tính dự đoán cho phiên **tiếp theo**
                du_doan_data = algo_real_v80R(list(history), list(totals), list(win_log))

                # lưu dự đoán này để so sánh khi có phiên mới vào sau
                last_prediction = {"du_doan": du_doan_data["du_doan"], "do_tin_cay": du_doan_data["do_tin_cay"]}

                # 4) Lưu last_result để trả về API
                global last_result
                last_result = {
                    "Phiên": phien,
                    "Xúc xắc 1": dice[0],
                    "Xúc xắc 2": dice[1],
                    "Xúc xắc 3": dice[2],
                    "Tổng": tong,
                    "Kết quả": ket_qua,
                    "Dự đoán_tiếp_theo": du_doan_data["du_doan"],
                    "Độ_tin_cậy": f"{du_doan_data['do_tin_cay']}%",
                    "Id": "tuananhdz"
                }

                # 5) In log rõ ràng để debug / chạy trên Pydroid3
                print("------------------------------------------------------------")
                print(f"[NEW] Phiên {phien} | Dice={dice} | Tổng={tong} | KQ={ket_qua}")
                print(f"[PRED] Dự đoán cho phiên kế: {du_doan_data['du_doan']} ({du_doan_data['do_tin_cay']}%)")
                print(f"[STATS] history_len={len(history)} totals_len={len(totals)} winrate_recent={round(sum(win_log[-10:]) / max(len(win_log[-10:]),1),3) if win_log else 'N/A'}")
                print("------------------------------------------------------------")

                last_phien_seen = phien

        # chờ 5s trước lần gọi tiếp theo
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
    # start background poller
    threading.Thread(target=background_updater, daemon=True).start()
    print("Khởi động server... truy cập: http://0.0.0.0:5000/api/taixiumd5")
    app.run(host="0.0.0.0", port=5000)
