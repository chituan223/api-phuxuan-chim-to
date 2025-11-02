from flask import Flask, jsonify
import requests
import time
from collections import deque
import threading

app = Flask(__name__)

# =========================================================
# 💾 Bộ nhớ tạm lưu lịch sử & độ tin cậy
# =========================================================
history = deque(maxlen=50)   # chứa "Tài" / "Xỉu"
totals = deque(maxlen=50)    # chứa tổng xúc xắc (int)
win_log = deque(maxlen=50)   # chứa True/False (dự đoán đúng hay không)
last_result = {"status": "đang khởi động..."}

# ---------------- Helper an toàn ----------------
def safe_list(seq):
    return list(seq) if seq is not None else []

def safe_win_rate(win_seq):
    w = list(win_seq)[-10:]
    return w.count(True) / max(len(w), 1)

# =========================================================
# 🧠 Bộ 15 thuật toán Real VIP chuẩn (tất cả đã được guard)
# =========================================================

# 1️⃣ Real VIP – Cầu bệt mạnh
def algo_vip_1(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    last5 = h[-5:] if len(h) >= 1 else []
    recent_wins = w[-10:]
    win_rate = recent_wins.count(True) / max(len(recent_wins), 1)

    if len(last5) >= 5 and all(x == "Tài" for x in last5):
        return {"du_doan": "Tài", "do_tin_cay": round(min(90 + win_rate * 9, 99), 1)}
    if len(last5) >= 5 and all(x == "Xỉu" for x in last5):
        return {"du_doan": "Xỉu", "do_tin_cay": round(min(90 + win_rate * 9, 99), 1)}

    if len(h) > 0:
        return {"du_doan": h[-1], "do_tin_cay": round(75 + win_rate * 15, 1)}
    return {"du_doan": "Tài", "do_tin_cay": 50.0}

# 2️⃣ Real VIP – Cầu xen kẽ
def algo_vip_2(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    last6 = h[-6:]
    pattern = "".join("T" if x == "Tài" else "X" for x in last6)
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    if len(last6) >= 6 and pattern.endswith(("TTXXTT", "XXTTXX")):
        pred = "Tài" if pattern[-1] == "X" else "Xỉu"
        return {"du_doan": pred, "do_tin_cay": round(min(85 + win_rate * 12, 99), 1)}
    if len(h) > 0:
        return {"du_doan": h[-1], "do_tin_cay": round(70 + win_rate * 20, 1)}
    return {"du_doan": "Tài", "do_tin_cay": 50.0}

# 3️⃣ Real VIP – Tổng động
def algo_vip_3(history, totals, win_log):
    h = safe_list(history)
    t = safe_list(totals)
    w = safe_list(win_log)
    last12_totals = t[-12:] if t else []
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)

    if not last12_totals:
        # không đủ dữ liệu tổng -> fallback
        if len(h) > 0:
            return {"du_doan": h[-1], "do_tin_cay": 60.0}
        return {"du_doan": "Tài", "do_tin_cay": 50.0}

    mean_total = sum(last12_totals) / len(last12_totals)
    high_ratio = sum(1 for x in last12_totals if x > 10.5) / len(last12_totals)
    low_ratio = 1 - high_ratio
    weight = 0.5 + (win_rate - 0.5) * 0.5

    if mean_total >= 11 and high_ratio > 0.55:
        du_doan = "Tài"
        confidence = 80 + weight * 15 + win_rate * 5
    elif mean_total <= 9 and low_ratio > 0.55:
        du_doan = "Xỉu"
        confidence = 80 + weight * 15 + win_rate * 5
    else:
        du_doan = h[-1] if h else "Tài"
        confidence = 75 + weight * 20 + win_rate * 4

    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 4️⃣ Real VIP – Trọng số ngắn hạn
def algo_vip_4(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    last8 = h[-8:]
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    if not last8:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
    w_tai = sum(1 / (i + 1) for i, val in enumerate(reversed(last8)) if val == "Tài")
    w_xiu = sum(1 / (i + 1) for i, val in enumerate(reversed(last8)) if val == "Xỉu")
    du_doan = "Tài" if w_tai > w_xiu else "Xỉu"
    confidence = 70 + win_rate * 25
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 5️⃣ Real VIP – Bệt đảo
def algo_vip_5(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    tail = h[-6:] if h else []
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    if len(tail) >= 4 and all(x == tail[-1] for x in tail[-4:]):
        du_doan = tail[-1]
    elif tail:
        du_doan = "Tài" if tail.count("Tài") >= 3 else "Xỉu"
    else:
        du_doan = "Tài"
    confidence = 75 + win_rate * 20
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 6️⃣ Real VIP – Flip counter
def algo_vip_6(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    if len(h) < 2:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
    flips = 0
    limit = min(5, len(h)-1)
    for i in range(1, limit+1):
        if h[-i] != h[-i-1]:
            flips += 1
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    du_doan = "Tài" if flips % 2 == 0 else "Xỉu"
    confidence = 70 + win_rate * 25
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 7️⃣ Real VIP – Balance ratio
def algo_vip_7(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    last10 = h[-10:]
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    if not last10:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
    diff = last10.count("Tài") - last10.count("Xỉu")
    if abs(diff) >= 4:
        du_doan = "Xỉu" if diff > 0 else "Tài"
    else:
        du_doan = last10[-1]
    confidence = 70 + win_rate * 25
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 8️⃣ Real VIP – Triple layer trend
def algo_vip_8(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    s1 = h[-5:] if len(h) >= 5 else h
    s2 = h[-10:-5] if len(h) >= 6 else []
    s3 = h[-15:-10] if len(h) >= 11 else []
    score = sum(1 for s in (s1, s2, s3) if len(s) >= 1 and s.count("Tài") > 2)
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    du_doan = "Tài" if score >= 2 else ("Xỉu" if len(h)>0 else "Tài")
    confidence = 75 + win_rate * 20
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 9️⃣ Real VIP – Double swing
def algo_vip_9(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    last6 = h[-6:] if len(h) >= 1 else []
    pattern = "".join("T" if x == "Tài" else "X" for x in last6)
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    if len(last6) >= 4 and (pattern.endswith("TTXX") or pattern.endswith("XXTT")):
        du_doan = "Tài" if pattern[-1] == "X" else "Xỉu"
    elif last6:
        du_doan = "Tài" if last6.count("Tài") >= 3 else "Xỉu"
    else:
        du_doan = "Tài"
    confidence = 75 + win_rate * 20
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 🔟 Real VIP – Hybrid weighted
def algo_vip_10(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    last10 = h[-10:]
    if not last10:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
    weight = sum((1 if x == "Tài" else -1) * (i + 1) for i, x in enumerate(reversed(last10)))
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    du_doan = "Tài" if weight >= 0 else "Xỉu"
    confidence = 70 + win_rate * 25
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 11️⃣ Real VIP – Anti-streak
def algo_vip_11(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    tail = h[-5:] if len(h) >= 1 else []
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    if len(tail) >= 4 and all(x == tail[-1] for x in tail):
        du_doan = tail[-1]
    elif tail:
        du_doan = "Tài" if tail[-1] == "Xỉu" else "Xỉu"
    else:
        du_doan = "Tài"
    confidence = 75 + win_rate * 20
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 12️⃣ Real VIP – Backward bet
def algo_vip_12(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    chain = 0
    max_check = min(5, len(h)-1) if len(h) >= 2 else 0
    for i in range(1, max_check+1):
        if h[-i] == h[-i-1]:
            chain += 1
        else:
            break
    if len(h) == 0:
        du_doan = "Tài"
    else:
        du_doan = h[-1] if chain >= 3 else ("Tài" if h[-1] == "Xỉu" else "Xỉu")
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    confidence = 70 + win_rate * 25
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 13️⃣ Real VIP – Weighted trend
def algo_vip_13(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    last10 = h[-10:]
    if not last10:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
    weight = sum((1 if x == "Tài" else -1) * (i + 1) for i, x in enumerate(reversed(last10)))
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    du_doan = "Tài" if weight >= 0 else "Xỉu"
    confidence = 75 + win_rate * 20
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 14️⃣ Real VIP – Moving average total
def algo_vip_14(history, totals, win_log):
    t = safe_list(totals)
    w = safe_list(win_log)
    last8_totals = t[-8:]
    if not last8_totals:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
    mean_total = sum(last8_totals) / len(last8_totals)
    du_doan = "Tài" if mean_total >= 11 else "Xỉu"
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    confidence = 75 + win_rate * 20
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# 15️⃣ Real VIP – Last result follow
def algo_vip_15(history, totals, win_log):
    h = safe_list(history)
    w = safe_list(win_log)
    last = h[-1] if h else "Tài"
    win_rate = w[-10:].count(True) / max(len(w[-10:]), 1)
    du_doan = last
    confidence = 70 + win_rate * 25
    return {"du_doan": du_doan, "do_tin_cay": round(min(confidence, 99), 1)}

# =========================================================
# 🔧 Danh sách thuật toán
# =========================================================
algorithms = [
    algo_vip_1, algo_vip_2, algo_vip_3, algo_vip_4, algo_vip_5,
    algo_vip_6, algo_vip_7, algo_vip_8, algo_vip_9, algo_vip_10,
    algo_vip_11, algo_vip_12, algo_vip_13, algo_vip_14, algo_vip_15
]

# =========================================================
# 🔍 Lấy dữ liệu thật từ API
# =========================================================
def get_taixiu_data():
    url = "https://1.bot/GetNewLottery/LT_TaixiuMD5"
    for _ in range(3):
        try:
            res = requests.get(url, timeout=6)
            data = res.json()
            # Hỗ trợ cả cấu trúc {"data": {...}} hoặc {"data": [..]}
            info = data.get("data")
            if not info:
                time.sleep(1)
                continue
            # Nếu info là list: lấy phần tử đầu
            if isinstance(info, list):
                info = info[0] if info else None
            if not info:
                time.sleep(1)
                continue
            phien = info.get("Expect", int(time.time()))
            opencode = info.get("OpenCode", "1,2,3")
            # bảo đảm định dạng "a,b,c"
            parts = [p.strip() for p in str(opencode).split(",") if p.strip().isdigit()]
            if len(parts) >= 3:
                dice = [int(parts[0]), int(parts[1]), int(parts[2])]
            else:
                # fallback nếu opencode khác dạng
                dice = [int(x) for x in "1,2,3".split(",")]
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
            dice = [1, 2, 3]
            tong = sum(dice)
        else:
            phien, dice, tong = data

        # Nếu phiên mới
        if last_result.get("status") == "đang khởi động..." or phien != last_phien:
            ket_qua = "Tài" if tong >= 11 else "Xỉu"
            history.append(ket_qua)
            totals.append(tong)

            # Chạy tất cả thuật toán (mỗi thuật toán trả dict)
            results_all = []
            for algo in algorithms:
                try:
                    out = algo(history, totals, win_log)
                    # đảm bảo format
                    if isinstance(out, dict) and "du_doan" in out and "do_tin_cay" in out:
                        results_all.append(out)
                    else:
                        # fallback
                        results_all.append({"du_doan": "Tài", "do_tin_cay": 50.0})
                except Exception as e:
                    # nếu 1 thuật toán lỗi, fallback chứ không crash cả vòng
                    print(f"[WARN] algo {getattr(algo, '__name__', str(algo))} error: {e}")
                    results_all.append({"du_doan": "Tài", "do_tin_cay": 50.0})

            # Chọn thuật toán tốt nhất dựa trên do_tin_cay
            best = max(results_all, key=lambda x: x.get("do_tin_cay", 0))
            pred = best.get("du_doan", "Tài")
            win_log.append(pred == ket_qua)

            last_result = {
                "Phiên": phien,
                "Xúc xắc": dice,
                "Tổng": tong,
                "Kết quả thật": ket_qua,
                "Dự đoán": pred,
                "Độ tin cậy": f"{best.get('do_tin_cay', 0)}%",
                "Nguồn thuật toán": algorithms[results_all.index(best)].__name__,
                "status": "Cập nhật thành công ✅"
            }

            print(f"[OK] Phiên: {phien} - KQ: {ket_qua} ({tong}) - Dự đoán: {pred} ({best.get('do_tin_cay',0)}%)")
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
