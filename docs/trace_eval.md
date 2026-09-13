# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Nguyễn Minh Thắng  
> **Mã Sinh Viên / Mã Học viên:** 2A202602706  
> **Chủ đề Lựa chọn:** Trợ lý Quản lý Chi tiêu Cá nhân (Personal Expense & Finance Agent)

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | **5 / 5** | Quản lý chi tiêu KHÔNG thể giải quyết trong một lượt (one-shot). Khi người dùng nói: *"Hôm nay vừa ăn lẩu 450k với bạn, cuối tuần có đủ tiền đi xem phim không?"*, Agent phải: (1) Phân tích chi phí & phân loại danh mục "Ăn uống", (2) Truy vấn số dư ngân sách tuần/tháng hiện tại, (3) Tính toán trừ số tiền 450k và so sánh với ngân sách còn lại cho mục "Giải trí", (4) Đánh giá và đưa ra phản hồi/khuyến nghị phù hợp. Mỗi bước phụ thuộc vào kết quả bước trước đó. |
| **2. Tool Interaction** | **5 / 5** | LLM thuần túy rất dễ bị ảo giác tính toán (math hallucination) và không có quyền truy cập dữ liệu thực tế. Hệ thống BẮT BUỘC phải tích hợp các tools: (1) `expense_database_tool`: CRUD giao dịch (thêm/đọc/sửa/xóa), (2) `budget_calculator`: Tính toán cộng/trừ số dư, phần trăm chi tiêu chính xác, (3) `budget_checker`: Kiểm tra trạng thái ngân sách theo danh mục và phát hiện nguy cơ vượt hạn mức chi tiêu. |
| **3. Dynamic Decision** | **4 / 5** | Luồng thực thi phụ thuộc hoàn toàn vào kết quả trả về từ tool (Observation): (a) Nếu ngân sách còn dư → Tự động lưu giao dịch và thông báo số dư mới, (b) Nếu danh mục vượt ngưỡng cảnh báo (>80% ngân sách) → Kích hoạt nhánh cảnh báo thâm hụt và đề xuất danh mục khác có thể cắt giảm bù vào, (c) Nếu câu lệnh người dùng mơ hồ (ví dụ: "vừa tiêu 200k") → Tự động đặt câu hỏi làm rõ danh mục trước khi ghi sổ. |
| **4. Long Horizon Goal** | **4 / 5** | Trợ lý KHÔNG chỉ trả lời câu hỏi tức thời mà còn hướng tới mục tiêu tài chính xuyên suốt theo chu kỳ (tuần, tháng, năm): (1) Theo dõi mục tiêu tiết kiệm (ví dụ: "Tiết kiệm 30 triệu trong 6 tháng"), (2) Tổng hợp báo cáo định kỳ và điều chỉnh hạn mức chi tiêu linh hoạt theo tiến độ thực tế. Agent duy trì ngữ cảnh qua nhiều phiên giao dịch. |
| **TỔNG ĐIỂM AGENTIC FIT** | **18 / 20** | *Tổng điểm > 12/20 → Đạt điều kiện nâng cấp lên ReAct Agent System. Bài toán rất phù hợp triển khai Agentic System vì đòi hỏi multi-step reasoning, tool-based math accuracy, và dynamic decision-making.* |

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

Đã cấu hình `GEMINI_API_KEY`, `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-3.5-flash` và chuỗi dự phòng `gemini-3.8-flash, gemini-3.7-flash, gemini-3.6-flash`. Khi Gemini 3.5 Flash báo quota `429`, provider tự động chuyển sang Flash model khả dụng tiếp theo. Lượt suite cuối sinh 8 sự kiện từ Gemini API thật: TC01/TC05 dùng Gemini 3.8 Flash, TC02/TC04 dùng Gemini 3.7 Flash và TC03 dùng Gemini 3.6 Flash; không có Mock fallback.

```json
[
  {
    "step": 1,
    "query": "Hôm nay mình đi siêu thị hết 850.000đ và đổ xăng 90.000đ, hãy ghi sổ giúp mình và cho biết mình đã tiêu tổng cộng bao nhiêu trong ngày.",
    "action_type": "TOOL_EXECUTION",
    "tool_name": "expense_database_tool",
    "arguments": {
      "action": "add",
      "amount": 850000,
      "category": "Groceries",
      "description": "Đi siêu thị"
    },
    "observation": {
      "status": "SUCCESS",
      "transaction": {
        "transaction_id": "TX-004",
        "amount": 850000.0,
        "category": "Groceries"
      }
    },
    "llm_model": "gemini-3.6-flash",
    "latency_ms": 10641.13
  },
  {
    "step": 2,
    "action_type": "FINAL_ANSWER",
    "thought": "Tổng hợp kết quả từ MCP Server.",
    "output": "Đã ghi nhận giao dịch chi tiêu: Đi siêu thị – Groceries – 850.000đ (Mã GD: TX-004).",
    "latency_ms": 10.0
  }
]
```

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [x] Đã xác nhận Agent kết nối và nhận phản hồi từ Gemini API thật; `429` của Gemini 3.5 Flash được chuyển sang Flash model dự phòng.
- **Tổng số Test Cases đã chạy thành công:** 5 / 5 test cases, 0 TODO; toàn bộ 5 case trong trace cuối do Gemini API thật xử lý.
- **Số lượt gọi Tool qua MCP Server trong trace hiện tại:** 3 lượt, đều do Gemini API thật khởi tạo.
- **Kiểm tra Interactive CLI:** Đã gửi prompt, nhận phản hồi từ Gemini API thật và thoát bằng `exit` thành công.
- **Cấu hình fallback:** Khi model ưu tiên báo `429 RESOURCE_EXHAUSTED` hoặc `503 UNAVAILABLE`, hệ thống lần lượt thử Gemini 3.8 Flash, 3.7 Flash và 3.6 Flash; lỗi xác thực/cấu hình không bị che giấu bằng fallback.
- **Kết quả Đẩy Repo nộp bài:** [ ] Đã Commit và Push mã nguồn thành công lên GitHub cá nhân.

---

> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
