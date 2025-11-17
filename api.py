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
history = deque(maxlen=HISTORY_MAXLEN)      # Chứa "Tài" / "Xỉu"
totals = deque(maxlen=HISTORY_MAXLEN)       # Chứa tổng xúc xắc (int)

# Log hiệu suất: Lưu True/False cho mỗi mô hình sau mỗi phiên (Xét 50 phiên gần nhất)
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
last_result = {"status": "Đang khởi động Hệ thống VIP Pro 8.1 (MVT Core)..."}

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
# (Các mô hình 1, 2, 3, 5, 6, 7, 8 được giữ nguyên hoặc điều chỉnh nhẹ trọng số)
# =========================================================

# 1️⃣ MARKOV_TREND: Phân tích xác suất chuyển trạng thái (Giữ nguyên)
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
    
    acc = get_model_accuracy(model_name)
    # Điều chỉnh: Trọng số Acc/Confidence = 35/65
    confidence = (confidence_base * 0.65) + (acc * 35)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 2️⃣ FIBO_SWING: Tìm kiếm chuỗi bệt/đảo dựa trên chuỗi Fibonacci (Giữ nguyên)
def model_fibo_swing(history, totals, model_name="FIBO_SWING"):
    h = safe_list(history)
    if len(h) < 5:
        return {"du_doan": "Xỉu", "do_tin_cay": 50.0}

    current_trend = h[-1]
    streak_count = 0
    for result in reversed(h):
        if result == current_trend:
            streak_count += 1
        else:
            break
            
    fibo = [1, 2, 3, 5, 8]
    
    if streak_count in fibo and streak_count >= 3:
        pred = current_trend
        confidence_base = 88.0
    elif streak_count > 8:
        pred = "Xỉu" if current_trend == "Tài" else "Tài"
        confidence_base = 75.0
    else:
        pred = "Xỉu" if h[-1] == "Tài" else "Tài"
        confidence_base = 60.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.7) + (acc * 30)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 3️⃣ EXPONENTIAL_MOMENTUM: Trọng số lũy thừa (Giữ nguyên)
def model_exponential_momentum(history, totals, model_name="EXPONENTIAL_MOMENTUM"):
    h = safe_list(history)
    if len(h) < 8:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
        
    last8 = h[-8:]
    weighted_score = 0
    
    for i, result in enumerate(last8):
        weight = 2**i
        if result == "Tài":
            weighted_score += weight
        else:
            weighted_score -= weight
            
    pred = "Tài" if weighted_score > 0 else "Xỉu"
    
    max_score = sum([2**i for i in range(8)]) # 255
    score_ratio = abs(weighted_score) / max_score
    confidence_base = 60 + score_ratio * 35 

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.7) + (acc * 30)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 4️⃣ TOTAL_Z_SCORE: Cải tiến Lõi - Bắt điểm cực trị (High-Confidence Entry)
def model_total_z_score(history, totals, model_name="TOTAL_Z_SCORE"):
    t = safe_list(totals)
    h = safe_list(history)
    if len(t) < 30:
        return {"du_doan": h[-1] if h else "Tài", "do_tin_cay": 50.0}
        
    last30_totals = t[-30:]
    try:
        # avg_sum = statistics.mean(last30_totals) # Không cần dùng avg_sum
        std_dev = statistics.stdev(last30_totals)
    except statistics.StatisticsError:
        return {"du_doan": h[-1] if h else "Tài", "do_tin_cay": 50.0}

    if std_dev < 1.0: # Biến động quá thấp (Hẹp) -> Sắp bùng nổ
        pred = "Xỉu" if h[-1] == "Tài" else "Tài"
        confidence_base = 78.0
    else:
        # Tính Z-Score cho phiên cuối cùng (So với trung tâm 10.5)
        z_score = (t[-1] - 10.5) / std_dev
        
        # BẮT ĐIỂM CỰC TRỊ: Nếu Z-Score > +/- 2.0 (Ngoài 2 độ lệch chuẩn)
        if z_score > 2.0: # Lệch mạnh về Tài
            pred = "Xỉu" # Dự đoán đảo chiều về Xỉu
            confidence_base = 90.0 # Độ tin cậy rất cao
        elif z_score < -2.0: # Lệch mạnh về Xỉu
            pred = "Tài" # Dự đoán đảo chiều về Tài
            confidence_base = 90.0
        else:
            # Nếu gần trung bình, theo đuôi xu hướng ngắn hạn gần nhất
            pred = h[-1]
            confidence_base = 58.0
            
    acc = get_model_accuracy(model_name)
    # Tăng ảnh hưởng của Acc cho mô hình cực trị
    confidence = (confidence_base * 0.6) + (acc * 40)
    
    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.9), 1)}

# 5️⃣ PARABOLIC_CYCLE: Phát hiện chu kỳ tăng/giảm tốc của cầu (Giữ nguyên)
def model_parabolic_cycle(history, totals, model_name="PARABOLIC_CYCLE"):
    h = safe_list(history)
    if len(h) < 15:
        return {"du_doan": "Xỉu", "do_tin_cay": 50.0}

    def get_slope(results):
        score = 0
        for i, r in enumerate(results):
            if r == "Tài": score += (i + 1)
            else: score -= (i + 1)
        return score

    slope_short = get_slope(h[-5:])
    slope_long = get_slope(h[-10:])
    
    if slope_short > 0 and slope_long > 0 and slope_short > (slope_long / 2):
        pred = "Tài"
        confidence_base = 82.0
    elif slope_short < 0 and slope_long < 0 and slope_short < (slope_long / 2):
        pred = "Xỉu"
        confidence_base = 82.0
    else:
        pred = "Xỉu" if h[-1] == "Tài" else "Tài"
        confidence_base = 60.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.7) + (acc * 30)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 6️⃣ ANTI_STREAK: Phản công khi bệt quá dài (tìm điểm gãy cầu) (Giữ nguyên)
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
            
    if long_streak >= 6:
        pred = "Xỉu" if current_trend == "Tài" else "Tài"
        confidence_base = 92.0 
    else:
        pred = current_trend
        confidence_base = 55.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.7) + (acc * 30)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 7️⃣ ALTERNATING_PATTERN: Phát hiện cầu 1-1, 2-2, 3-3... (Giữ nguyên)
def model_alternating_pattern(history, totals, model_name="ALTERNATING_PATTERN"):
    h = safe_list(history)
    if len(h) < 6:
        return {"du_doan": h[-1] if h else "Xỉu", "do_tin_cay": 50.0}

    last6 = h[-6:]
    
    # 1-1 pattern
    if last6 == ["Tài", "Xỉu", "Tài", "Xỉu", "Tài", "Xỉu"][-len(last6):] or \
       last6 == ["Xỉu", "Tài", "Xỉu", "Tài", "Xỉu", "Tài"][-len(last6):]:
        pred = "Xỉu" if h[-1] == "Tài" else "Tài"
        confidence_base = 85.0
    
    # 2-2 pattern
    elif len(h) >= 4 and h[-1] == h[-2] and h[-3] == h[-4] and h[-1] != h[-3]:
        pred = h[-1] 
        confidence_base = 75.0
        
    else:
        pred = h[-1]
        confidence_base = 50.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.7) + (acc * 30)
    
    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# 8️⃣ AVERAGE_REGRESSION: Dự đoán quay về trung bình (Mean Reversion) (Giữ nguyên)
def model_average_regression(history, totals, model_name="AVERAGE_REGRESSION"):
    t = safe_list(totals)
    if len(t) < 20:
        return {"du_doan": "Tài", "do_tin_cay": 50.0}
        
    last20_totals = t[-20:]
    avg_20 = statistics.mean(last20_totals)
    
    if avg_20 > 11.5:
        pred = "Xỉu"
        confidence_base = 80.0
    elif avg_20 < 9.5:
        pred = "Tài"
        confidence_base = 80.0
    else:
        pred = history[-1]
        confidence_base = 60.0

    acc = get_model_accuracy(model_name)
    confidence = (confidence_base * 0.7) + (acc * 30)

    return {"du_doan": pred, "do_tin_cay": round(min(confidence, 99.0), 1)}

# =========================================================
# 🔧 Danh sách & Công cụ Tổng hợp (Consensus Engine 8.1 - MVT CORE)
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

# Định nghĩa các Vector (Kiến trúc MVT)
MVT_VECTORS = {
    # Mô hình theo đuổi xu hướng
    "TREND": ["MARKOV_TREND", "EXPONENTIAL_MOMENTUM", "FIBO_SWING"],
    # Mô hình dự đoán đảo chiều/quay về trung bình
    "REVERSION": ["ANTI_STREAK", "AVERAGE_REGRESSION", "TOTAL_Z_SCORE"],
    # Mô hình tìm kiếm mẫu hình
    "PATTERN": ["ALTERNATING_PATTERN", "PARABOLIC_CYCLE"],
}

def run_consensus_engine():
    """
    Chạy tất cả 8 mô hình và tính toán dự đoán cuối cùng dựa trên Trọng số Động MVT.
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
            # print(f"[ERROR] Mô hình {name} lỗi: {e}") 
            results_raw.append({"du_doan": "Tài", "do_tin_cay": 50.0, "source": name})
            
    if not results_raw:
        return {"du_doan": "Tài", "do_tin_cay": 50.0, "source": "Fallback"}

    # 2. Tính Trọng số Động và Lưu trữ dự đoán hiện tại
    weighted_results = {}
    current_predictions = {}
    
    for res in results_raw:
        confidence = res['do_tin_cay'] / 100.0
        acc_weight = get_model_accuracy(res['source'])
        
        # Cải tiến: Trọng số Động = (Confidence * 0.6) + (Accuracy * 0.4)
        dynamic_weight = (confidence * 0.6) + (acc_weight * 0.4)
        
        weighted_results[res['source']] = {
            "du_doan": res['du_doan'], 
            "weight": dynamic_weight
        }
        current_predictions[res['source']] = {"du_doan": res['du_doan'], "do_tin_cay": res['do_tin_cay']}
        
    last_predictions = current_predictions

    # 3. Tính điểm MVT (Multi-Vector Trend) và xác định Vector mạnh nhất
    vector_scores = {"TREND": 0.0, "REVERSION": 0.0, "PATTERN": 0.0}
    vector_counts = {"TREND": 0, "REVERSION": 0, "PATTERN": 0}
    
    for v_name, v_models in MVT_VECTORS.items():
        for m_name in v_models:
            if m_name in weighted_results:
                # Cộng điểm trọng số của mô hình vào Vector
                vector_scores[v_name] += weighted_results[m_name]['weight']
                vector_counts[v_name] += 1
    
    # Lấy điểm trung bình của Vector
    for v_name in vector_scores:
        vector_scores[v_name] = vector_scores[v_name] / max(vector_counts[v_name], 1)
        
    best_vector = max(vector_scores, key=vector_scores.get) # Vector chiến thắng
    
    # 4. Tính toán Điểm Tổng hợp Cuối cùng (Ưu tiên Vector mạnh nhất)
    final_score = {"Tài": 0.0, "Xỉu": 0.0}
    
    for name, data in weighted_results.items():
        weight_multiplier = 1.0
        
        # Kiểm tra mô hình thuộc Vector mạnh nhất
        is_best_vector = False
        for v_name, v_models in MVT_VECTORS.items():
            if name in v_models and v_name == best_vector:
                is_best_vector = True
                break
                
        if is_best_vector:
            weight_multiplier = 1.5 # Ưu tiên 50% cho mô hình thuộc Vector mạnh nhất
            
        final_score[data['du_doan']] += data['weight'] * weight_multiplier

    # 5. Kết luận Consensus
    if final_score["Tài"] > final_score["Xỉu"]:
        final_pred = "Tài"
    elif final_score["Xỉu"] > final_score["Tài"]:
        final_pred = "Xỉu"
    else:
        final_pred = history[-1] if history else "Tài" # Nếu hòa điểm, chọn theo kết quả gần nhất
            
    # 6. Tính toán Độ tin cậy Cuối cùng
    total_score = final_score["Tài"] + final_score["Xỉu"]
    winning_score = final_score[final_pred]
    
    final_confidence = (winning_score / max(total_score, 0.01)) * 100
    
    # 7. Tìm mô hình đóng góp nhiều nhất
    best_source = max(results_raw, key=lambda x: (x.get("do_tin_cay", 0) * (get_model_accuracy(x['source']) or 0.5))).get('source', 'MVT Consensus')


    return {
        "du_doan": final_pred,
        "do_tin_cay": round(min(final_confidence, 99.9), 1),
        "source": best_source,
        "best_vector": best_vector
    }

# =========================================================
# 🔍 Lấy dữ liệu thật từ API (Giữ nguyên)
# =========================================================
def get_taixiu_data():
    """Lấy dữ liệu thật từ API, không giả lập, không random."""
    for _ in range(3):
        try:
            # Gửi yêu cầu với header cần thiết (Nếu API yêu cầu, hiện tại không có nên giữ nguyên)
            res = requests.get(TAIXIU_API_URL, timeout=6)
            data = res.json()
            info = data.get("data")
            
            if isinstance(info, list):
                info = info[0] if info else None
            
            if not info:
                time.sleep(1)
                continue

            phien = info.get("Expect", int(time.time()))
            opencode = info.get("OpenCode", "1,2,3")
            
            parts = [p.strip() for p in str(opencode).split(",") if p.strip().isdigit()]
            if len(parts) >= 3:
                dice = [int(parts[0]), int(parts[1]), int(parts[2])]
            else:
                continue
                
            tong = sum(dice)
            return phien, dice, tong
            
        except Exception as e:
            # print(f"[API ERROR] Không lấy được dữ liệu: {e}") 
            time.sleep(2)
    return None

# =========================================================
# ♻️ Background updater (chạy liên tục) (Giữ nguyên logic chính)
# =========================================================
def background_updater():
    global last_result, last_predictions
    last_phien = None
    
    print("[INIT] Bắt đầu background updater (MVT Core Active)...")
    
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
                # print(f"[LOG] Đánh giá độ chính xác cho phiên {last_phien} (KQ: {history[-1]})")
                
                for model_name, pred_data in last_predictions.items():
                    predicted_outcome = pred_data.get("du_doan")
                    actual_outcome = history[-1]
                    
                    is_win = (predicted_outcome == actual_outcome)
                    
                    if model_name in model_win_log:
                          model_win_log[model_name].append(is_win)
                          
            # --- 2. Cập nhật lịch sử với kết quả phiên MỚI (đã ra) ---
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
                "Chiến lược MVT Chủ đạo": prediction_output['best_vector'],
                "status": "Cập nhật thành công ✅ (VIP Pro Active)"
            }

            print(f"[OK] Phiên {phien} | KQ: {ket_qua} ({tong}) | Dự đoán K+1: {prediction_output['du_doan']} ({prediction_output['do_tin_cay']}%) | Vector: {prediction_output['best_vector']}")
            last_phien = phien

        time.sleep(3) # Cập nhật sau mỗi 3 giây

# =========================================================
# 🌐 API endpoint (Trả về dự đoán mới nhất) (Cập nhật thông tin MVT)
# =========================================================
@app.route("/api/taixiumd5", methods=["GET"])
def api_taixiu():
    """Trả về kết quả dự đoán Tai Xiu VIP Pro mới nhất."""
    
    response_data = last_result.copy()
    
    # Chuẩn bị lịch sử để hiển thị
    recent_history = safe_list(history)[-10:]
    response_data["Lịch sử 10 phiên"] = recent_history
    
    # Tính độ chính xác tổng hợp của Consensus Engine
    total_accuracy = 0
    model_count = 0
    for name in MODELS.keys():
        total_accuracy += get_model_accuracy(name)
        model_count += 1
        
    accuracy = (total_accuracy / max(model_count, 1)) * 100
    
    response_data["Tỷ lệ thắng Tổng hợp (10 phiên gần nhất)"] = f"{round(accuracy, 1)}%"
    
    # Thêm chi tiết độ chính xác của từng mô hình
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
    app.run(host="0.0.0.0", port=5000, debug=False)
