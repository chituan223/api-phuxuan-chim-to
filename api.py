from flask import Flask, jsonify
import requests
import time
from collections import deque
import threading
import json
import statistics

# --- Cấu hình ứng dụng và biến toàn cục ---
app = Flask(__name__)
# Địa chỉ API thật (giả định đây là nguồn dữ liệu chuẩn)
TAIXIU_API_URL = "https://1.bot/GetNewLottery/LT_TaixiuMD5"

# =========================================================
# 💾 Bộ nhớ & Logging Nâng cao
# =========================================================
HISTORY_MAXLEN = 500
history = deque(maxlen=HISTORY_MAXLEN)    # Chứa "Tài" / "Xỉu"
totals = deque(maxlen=HISTORY_MAXLEN)     # Chứa tổng xúc xắc (int)

# Log hiệu suất: Lưu True/False cho mỗi mô hình sau mỗi phiên
model_win_log = {
    # 8 Mô hình Chiến lược VIP Pro
    "MARKOV_TREND": deque(maxlen=50),
    "FIBO_SWING": deque(maxlen=50),
    "EXPONENTIAL_MOMENTUM": deque(maxlen=50),
    "TOTAL_Z_SCORE": deque(maxlen=50),
    "PARABOLIC_CYCLE": deque(maxlen=50),
    "ANTI_STREAK": deque(maxlen=50),
    "ALTERNATING_PATTERN": deque(maxlen=50),
    "AVERAGE_REGRESSION": deque(maxlen=50),
}
# Lưu trữ TẤT CẢ dự đoán của các mô hình con trong phiên K (để đánh giá trong phiên K+1)
last_predictions = {} 

# Kết quả dự đoán cuối cùng
last_result = {"status": "Đang khởi động Hệ thống VIP Pro 8.0..."}

# --- Helper Functions ---
def safe_list(seq):
    """Đảm bảo trả về list từ deque, hoặc list rỗng nếu không tồn tại."""
    return list(seq) if seq is not None else []

def get_model_accuracy(model_name):
    """Tính tỷ lệ thắng trong 10 phiên gần nhất cho mô hình cụ thể (dùng làm trọng số động)."""
    log = model_win_log.get(model_name, deque(maxlen=1))
    recent_log = list(log)[-10:] # Chỉ xét 10 phiên gần nhất
    return recent_log.count(True) / max(len(recent_log), 1)

# =========================================================
# 🧠 CÁC MÔ HÌNH PHÂN TÍCH NÂNG CAO (8 Chiến lược VIP Pro)
# =========================================================
# Tất cả mô hình đều nhận (history, totals) và trả về {"du_doan": "Tài"/"Xỉu", "do_tin_cay": float}

# 1️⃣ MARKOV_TREND: Phân tích xác suất chuyển trạng thái (A -> B)
def model_markov_trend(history, totals, model_name="MARKOV_TREND"):
    h = safe_list(history)
    if len(h) < 10:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}

    last_state = h[-1]
    
    # Xây dựng ma trận chuyển tiếp (Transition Matrix) trên 50 phiên gần nhất
    transitions = {"Tài": {"Tài": 0, "Xỉu": 0}, "Xỉu": {"Tài": 0, "Xỉu": 0}}
    
    data_slice = h[-50:] 
    for i in range(len(data_slice) - 1):
        transitions[data_slice[i]][data_slice[i+1]] += 1

    total_outcomes = sum(transitions[last_state].values())
    if total_outcomes == 0:
        return {"du_doan": last_state, "do_tin_cay": 60.0}

    prob_T = transitions[last_state]["Tài"] / total_outcomes
    prob_X = transitions[last_state]["Xỉu"] / total_outcomes

    pred = "Tài" if prob_T > prob_X else "Xỉu"
    confidence_base = max(prob_T, prob_X) * 100
    
    # Trọng số Động: Cân bằng với hiệu suất lịch sử của mô hình này
    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.7) + (acc * 30)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 2️⃣ FIBO_SWING: Tìm kiếm chuỗi bệt/đảo dựa trên chuỗi Fibonacci (1, 2, 3, 5, 8...)
def model_fibo_swing(history, totals, model_name="FIBO_SWING"):
    h = safe_list(history)
    if len(h) < 5:
        return {"du_doan": "Xỉu", "do_tin_cay": 50.0}

    # Tìm chuỗi bệt hiện tại
    current_trend = h[-1]
    streak_count = 0
    for result in reversed(h):
        if result == current_trend:
            streak_count += 1
        else:
            break
            
    fibo = [1, 2, 3, 5, 8]
    
    if streak_count in fibo and streak_count >= 3:
        # Nếu đang ở ngưỡng Fibo 3, 5, 8 -> dự đoán tiếp tục bệt (mạnh)
        pred = current_trend
        confidence_base = 88.0
    elif streak_count > 8:
        # Nếu bệt quá dài (vượt Fibo mạnh) -> dự đoán đảo chiều (Anti-Fibo)
        pred = "Xỉu" if current_trend == "Tài" else "Tài"
        confidence_base = 75.0
    else:
        # Nếu không có xu hướng Fibo rõ ràng
        pred = "Xỉu" if h[-1] == "Tài" else "Tài" # dự đoán 1-1
        confidence_base = 60.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.8) + (acc * 20)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 3️⃣ EXPONENTIAL_MOMENTUM: Trọng số lũy thừa (Gần nhất quan trọng GẤP ĐÔI)
def model_exponential_momentum(history, totals, model_name="EXPONENTIAL_MOMENTUM"):
    h = safe_list(history)
    if len(h) < 8:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
        
    last8 = h[-8:]
    weighted_score = 0
    
    # Trọng số lũy thừa: 1, 2, 4, 8, 16, 32, 64, 128 (từ cũ nhất đến mới nhất)
    for i, result in enumerate(last8):
        weight = 2**i
        if result == "Tài":
            weighted_score += weight
        else:
            weighted_score -= weight
            
    pred = "Tài" if weighted_score > 0 else "Xỉu"
    
    max_score = sum([2**i for i in range(8)]) # 255
    score_ratio = abs(weighted_score) / max_score
    confidence_base = 60 + score_ratio * 35 # 60% đến 95%

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.8) + (acc * 20)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 4️⃣ TOTAL_Z_SCORE: Phân tích độ lệch chuẩn so với giá trị trung bình (10.5)
def model_total_z_score(history, totals, model_name="TOTAL_Z_SCORE"):
    t = safe_list(totals)
    h = safe_list(history)
    if len(t) < 30:
        return {"du_doan": h[-1] if h else "Tài", "do_tin_cay": 50.0}
        
    last30_totals = t[-30:]
    try:
        avg_sum = statistics.mean(last30_totals)
        std_dev = statistics.stdev(last30_totals)
    except statistics.StatisticsError:
        return {"du_doan": h[-1] if h else "Tài", "do_tin_cay": 50.0}

    if std_dev < 1.0: # Biến động quá thấp
        # Dự đoán Bùng nổ (Breakout)
        pred = "Xỉu" if h[-1] == "Tài" else "Tài"
        confidence_base = 78.0
    elif std_dev > 3.5: # Biến động quá cao
        # Dự đoán Quay về Trung bình (Regression to Mean)
        pred = "Tài" if avg_sum < 10.5 else "Xỉu"
        confidence_base = 70.0
    else:
        # Dự đoán theo xu hướng lệch hiện tại
        z_score = (t[-1] - 10.5) / std_dev
        if z_score > 1.0: # Đang lệch mạnh về Tài
            pred = "Tài"
            confidence_base = 65.0
        elif z_score < -1.0: # Đang lệch mạnh về Xỉu
            pred = "Xỉu"
            confidence_base = 65.0
        else:
            # Gần trung bình, dự đoán theo kết quả cuối cùng
            pred = h[-1]
            confidence_base = 58.0
            
    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.8) + (acc * 20)
    
    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 5️⃣ PARABOLIC_CYCLE: Phát hiện chu kỳ tăng/giảm tốc của cầu
def model_parabolic_cycle(history, totals, model_name="PARABOLIC_CYCLE"):
    h = safe_list(history)
    if len(h) < 15:
        return {"du_doan": "Xỉu", "do_tin_cay": 50.0}

    # Tính toán "độ dốc" (số lần thắng liên tiếp gần đây)
    def get_slope(results):
        score = 0
        for i, r in enumerate(results):
            if r == "Tài": score += (i + 1)
            else: score -= (i + 1)
        return score

    # Xét 5 phiên gần nhất
    slope_short = get_slope(h[-5:])
    
    # Xét 10 phiên gần nhất (đã trừ 5 phiên ngắn hạn)
    slope_long = get_slope(h[-10:])
    
    # Phát hiện sự tăng tốc xu hướng (Parabolic move)
    if slope_short > 0 and slope_long > 0 and slope_short > (slope_long / 2):
        # Tăng tốc mạnh về Tài -> Dự đoán tiếp tục Tài
        pred = "Tài"
        confidence_base = 82.0
    elif slope_short < 0 and slope_long < 0 and slope_short < (slope_long / 2):
        # Tăng tốc mạnh về Xỉu -> Dự đoán tiếp tục Xỉu
        pred = "Xỉu"
        confidence_base = 82.0
    else:
        # Không có tăng tốc rõ rệt, dự đoán đảo chiều nhẹ
        pred = "Xỉu" if h[-1] == "Tài" else "Tài"
        confidence_base = 60.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.8) + (acc * 20)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 6️⃣ ANTI_STREAK: Phản công khi bệt quá dài (tìm điểm gãy cầu)
def model_anti_streak(history, totals, model_name="ANTI_STREAK"):
    h = safe_list(history)
    if len(h) < 10:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}

    current_trend = h[-1]
    long_streak = 0
    for result in reversed(h):
        if result == current_trend:
            long_streak += 1
        else:
            break
            
    # Nếu bệt quá 6 -> dự đoán đảo chiều
    if long_streak >= 6:
        pred = "Xỉu" if current_trend == "Tài" else "Tài"
        confidence_base = 92.0 # Độ tin cậy cao vì đây là chiến lược "gãy cầu"
    else:
        # Nếu không bệt dài, theo đuôi ngắn hạn
        pred = current_trend
        confidence_base = 55.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.8) + (acc * 20)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 7️⃣ ALTERNATING_PATTERN: Phát hiện cầu 1-1, 2-2, 3-3...
def model_alternating_pattern(history, totals, model_name="ALTERNATING_PATTERN"):
    h = safe_list(history)
    if len(h) < 6:
        return {"du_doan": h[-1] if h else "Xỉu", "do_tin_cay": 50.0}

    # Phân tích 6 phiên cuối
    last6 = h[-6:]
    
    # 1-1 pattern (T, X, T, X, T, X)
    if last6 == ["Tài", "Xỉu", "Tài", "Xỉu", "Tài", "Xỉu"][-len(last6):] or \
       last6 == ["Xỉu", "Tài", "Xỉu", "Tài", "Xỉu", "Tài"][-len(last6):]:
        pred = "Xỉu" if h[-1] == "Tài" else "Tài"
        confidence_base = 85.0
    
    # 2-2 pattern (T, T, X, X, T, T)
    elif len(h) >= 4 and h[-1] == h[-2] and h[-3] == h[-4] and h[-1] != h[-3]:
        pred = h[-1] # Dự đoán tiếp tục 2-2 (ví dụ: T, T, X, X, T, T -> dự đoán T)
        confidence_base = 75.0
        
    else:
        pred = h[-1]
        confidence_base = 50.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.8) + (acc * 20)
    
    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 8️⃣ AVERAGE_REGRESSION: Dự đoán quay về trung bình (Mean Reversion)
def model_average_regression(history, totals, model_name="AVERAGE_REGRESSION"):
    t = safe_list(totals)
    if len(t) < 20:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
        
    last20_totals = t[-20:]
    avg_20 = statistics.mean(last20_totals)
    
    # Nếu trung bình đang quá xa 10.5 (trung tâm)
    if avg_20 > 11.5:
        # Đang lệch mạnh về Tài -> Dự đoán Xỉu để kéo về trung bình
        pred = "Xỉu"
        confidence_base = 80.0
    elif avg_20 < 9.5:
        # Đang lệch mạnh về Xỉu -> Dự đoán Tài để kéo về trung bình
        pred = "Tài"
        confidence_base = 80.0
    else:
        # Đã gần trung bình, dự đoán theo xu hướng ngắn hạn (Momentum)
        pred = history[-1]
        confidence_base = 60.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.8) + (acc * 20)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# =========================================================
# 🔧 Danh sách & Công cụ Tổng hợp (Consensus Engine 8.0)
# =========================================================
MODELS = {
    "MARKOV_TREND": model_markov_trend,
    "FIBO_SWING": model_fibo_swing,
    "EXPONENTIAL_MOMENTUM": model_exponential_momentum,
    "TOTAL_Z_SCORE": model_total_z_score,
    "PARABOLIC_CYCLE": model_parabolic_cycle,
    "ANTI_STREAK": model_anti_streak,
    "ALTERNATING_PATTERN": model_alternating_pattern,
    "AVERAGE_REGRESSION": model_average_regression,
}

def run_consensus_engine():
    """
    Chạy tất cả 8 mô hình và tính toán dự đoán cuối cùng dựa trên Trọng số Động.
    Trọng số = Độ tin cậy của mô hình * Tỷ lệ thắng lịch sử gần nhất của mô hình đó.
    """
    global last_predictions
    results_raw = []
    
    # 1. Chạy TẤT CẢ mô hình con
    for name, algo in MODELS.items():
        try:
            out = algo(history, totals)
            out['source'] = name
            results_raw.append(out)
        except Exception as e:
            print(f"[ERROR] Mô hình {name} lỗi: {e}")
            results_raw.append({"du_doan": "Tài", "do_tin_cay": 50.0, "source": name})
            
    if not results_raw:
        return {"du_doan": "Tài", "do_tin_cay": 50.0, "source": "Fallback"}

    # 2. Hệ thống Chấm điểm & Trọng số Động
    final_score = {"Tài": 0.0, "Xỉu": 0.0}
    
    # Lưu dự đoán thô (raw predictions) để đánh giá trong phiên sau
    current_predictions = {} 
    
    for res in results_raw:
        pred = res['du_doan']
        confidence = res['do_tin_cay'] / 100.0 
        
        # Lấy Tỷ lệ thắng gần nhất (Accuracy) làm Trọng số Điều chỉnh
        acc_weight = get_model_accuracy(res['source'])
        
        # Trọng số Động = (Confidence * 0.7) + (Accuracy * 0.3)
        dynamic_weight = (confidence * 0.7) + (acc_weight * 0.3)
        
        final_score[pred] += dynamic_weight 
        
        # Lưu trữ dự đoán hiện tại
        current_predictions[res['source']] = {"du_doan": pred, "do_tin_cay": res['do_tin_cay']}
        
    last_predictions = current_predictions # Cập nhật biến toàn cục

    # 3. Kết luận Consensus
    if final_score["Tài"] > final_score["Xỉu"]:
        final_pred = "Tài"
    elif final_score["Xỉu"] > final_score["Tài"]:
        final_pred = "Xỉu"
    else:
        # Nếu hòa điểm, chọn theo kết quả gần nhất
        final_pred = history[-1] if history else "Tài"
        
    # 4. Tính toán Độ tin cậy Cuối cùng
    total_score = final_score["Tài"] + final_score["Xỉu"]
    winning_score = final_score[final_pred]
    
    final_confidence = (winning_score / max(total_score, 0.01)) * 100
    
    # 5. Tìm mô hình đóng góp nhiều nhất (theo Trọng số Động)
    best_source = max(results_raw, key=lambda x: (x.get("do_tin_cay", 0) * (get_model_accuracy(x['source']) or 1.0))).get('source', 'Consensus')


    return {
        "du_doan": final_pred,
        "do_tin_cay": round(min(final_confidence, 99.0), 1),
        "source": best_source
    }

# =========================================================
# 🔍 Lấy dữ liệu thật từ API
# =========================================================
def get_taixiu_data():
    """Lấy dữ liệu thật từ API, không giả lập, không random."""
    for _ in range(3):
        try:
            res = requests.get(TAIXIU_API_URL, timeout=6)
            data = res.json()
            info = data.get("data")
            
            # Xử lý cấu trúc trả về
            if isinstance(info, list):
                info = info[0] if info else None
            
            if not info:
                time.sleep(1)
                continue

            phien = info.get("Expect", int(time.time()))
            opencode = info.get("OpenCode", "1,2,3")
            
            # Phân tích OpenCode
            parts = [p.strip() for p in str(opencode).split(",") if p.strip().isdigit()]
            if len(parts) >= 3:
                dice = [int(parts[0]), int(parts[1]), int(parts[2])]
            else:
                # Không đủ dữ liệu xúc xắc thật
                continue  
                
            tong = sum(dice)
            return phien, dice, tong
            
        except Exception as e:
            print(f"[API ERROR] Không lấy được dữ liệu: {e}")
            time.sleep(2)
    return None

# =========================================================
# ♻️ Background updater (chạy liên tục)
# =========================================================
def background_updater():
    global last_result, last_predictions
    last_phien = None
    
    print("[INIT] Bắt đầu background updater...")
    
    while True:
        data = get_taixiu_data()
        
        if not data:
            last_result["status"] = f"Lỗi: Không kết nối được API TaiXiu. Thử lại sau {int(time.time())}."
            time.sleep(5)
            continue
            
        phien, dice, tong = data
        ket_qua = "Tài" if tong >= 11 else "Xỉu"
        
        # Chỉ xử lý khi có phiên mới
        if phien != last_phien:
            
            # --- 1. Đánh giá độ chính xác của Phiên TRƯỚC (K) ---
            if last_phien is not None and last_predictions and history:
                print(f"[LOG] Đánh giá độ chính xác cho phiên {last_phien} (KQ: {history[-1]})")
                
                # Kiểm tra dự đoán của từng mô hình con trong phiên trước
                for model_name, pred_data in last_predictions.items():
                    predicted_outcome = pred_data.get("du_doan")
                    actual_outcome = history[-1]
                    
                    is_win = (predicted_outcome == actual_outcome)
                    
                    if model_name in model_win_log:
                         model_win_log[model_name].append(is_win)
                    
            # --- 2. Cập nhật lịch sử với kết quả phiên MỚI (đã ra) ---
            # Chỉ cập nhật lịch sử nếu có kết quả mới và lịch sử chưa có kết quả này (tránh lặp)
            if not history or history[-1] != ket_qua or totals[-1] != tong:
                 history.append(ket_qua)
                 totals.append(tong)
            
            # --- 3. Chạy Engine Consensus (Dự đoán cho phiên TIẾP THEO) ---
            prediction_output = run_consensus_engine()

            # --- 4. Cập nhật kết quả cuối cùng ---
            last_result = {
                "Phiên": phien,
                "Xúc xắc": dice,
                "Tổng": tong,
                "Kết quả thật": ket_qua,
                "Dự đoán Phiên K+1": prediction_output["du_doan"],
                "Độ tin cậy Tổng hợp": f"{prediction_output['do_tin_cay']}%",
                "Nguồn Thuật toán Chính": prediction_output['source'],
                "status": "Cập nhật thành công ✅ (VIP Pro Active)"
            }

            print(f"[OK] Phiên {phien} | KQ: {ket_qua} ({tong}) | Dự đoán K+1: {prediction_output['du_doan']} ({prediction_output['do_tin_cay']}%)")
            last_phien = phien

        time.sleep(3) # Cập nhật sau mỗi 3 giây

# =========================================================
# 🌐 API endpoint (Trả về dự đoán mới nhất)
# =========================================================
@app.route("/api/taixiumd5", methods=["GET"])
def api_taixiu():
    """Trả về kết quả dự đoán Tai Xiu VIP Pro mới nhất."""
    
    # Thêm thông tin lịch sử ngắn gọn và độ chính xác hiện tại
    response_data = last_result.copy()
    
    # Chuẩn bị lịch sử để hiển thị
    recent_history = safe_list(history)[-10:]
    response_data["Lịch sử 10 phiên"] = recent_history
    
    # Tính độ chính xác tổng hợp của Consensus Engine (Tính bằng trung bình của tất cả mô hình)
    total_accuracy = 0
    model_count = 0
    for name in MODELS.keys():
        total_accuracy += get_model_accuracy(name)
        model_count += 1
        
    accuracy = (total_accuracy / max(model_count, 1)) * 100
    
    response_data["Tỷ lệ thắng Tổng hợp (10 phiên gần nhất)"] = f"{round(accuracy, 1)}%"
    
    # Thêm chi tiết độ chính xác của từng mô hình (để người dùng theo dõi và tin tưởng)
    model_accuracies = {}
    for name in MODELS.keys():
        model_accuracies[name] = f"{round(get_model_accuracy(name) * 100, 1)}%"
        
    response_data["Chi tiết Hiệu suất Mô hình"] = model_accuracies
    
    return jsonify(response_data)

# =========================================================
# 🚀 Chạy Flask server
# =========================================================
if __name__ == "__main__":
    # Chạy Background Updater trong một luồng riêng biệt
    threading.Thread(target=background_updater, daemon=True).start()
    
    # Khởi động Flask Server
    app.run(host="0.0.0.0", port=5000)
