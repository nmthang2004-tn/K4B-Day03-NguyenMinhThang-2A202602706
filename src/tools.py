"""
TOOL DEFINITIONS & EXECUTION BACKEND
Chủ đề: Trợ lý Quản lý Chi tiêu Cá nhân.
3 Native Tools: expense_database_tool, budget_calculator, budget_checker.
"""

import json
from typing import Any, Dict, Optional

# ==============================================================================
# 1. TOOL SCHEMAS — CHUẨN JSON SCHEMA
# ==============================================================================

TOOLS_SCHEMA = [
    # Tool mẫu học vụ: chỉ giữ để tham khảo JSON Schema, không đăng ký trong TOOL_ROUTER.
    {
        "name": "academic_query",
        "description": "[MẪU KHÔNG SỬ DỤNG] Tra cứu hồ sơ học vụ bằng mã sinh viên.",
        "parameters": {
            "type": "object",
            "properties": {
                "student_id": {
                    "type": "string",
                    "description": "Mã sinh viên, ví dụ: SV2026001.",
                }
            },
            "required": ["student_id"],
        },
    },
    {
        "name": "expense_database_tool",
        "description": "Thêm, tra cứu, cập nhật hoặc xóa các giao dịch chi tiêu cá nhân theo thời gian thực.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "update", "delete"],
                    "description": "Thao tác cần thực hiện với dữ liệu giao dịch.",
                },
                "amount": {
                    "type": "number",
                    "description": "Số tiền giao dịch, đơn vị VND.",
                },
                "category": {
                    "type": "string",
                    "description": "Danh mục chi tiêu (Groceries, Dining, Transport, Entertainment).",
                },
                "description": {
                    "type": "string",
                    "description": "Mô tả ngắn gọn về giao dịch.",
                },
                "date": {
                    "type": "string",
                    "description": "Ngày phát sinh giao dịch theo định dạng YYYY-MM-DD.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "budget_calculator",
        "description": "Tính tổng chi tiêu, ngân sách còn lại và tỷ lệ sử dụng ngân sách theo khoảng thời gian.",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["sum_expenses", "remaining_budget", "budget_usage_percentage"],
                    "description": "Phép tính cần thực hiện trên dữ liệu chi tiêu.",
                },
                "category": {
                    "type": "string",
                    "description": "Danh mục chi tiêu cần tính toán.",
                },
                "period": {
                    "type": "string",
                    "enum": ["day", "week", "month"],
                    "description": "Khoảng thời gian cần thống kê.",
                },
                "budget_limit": {
                    "type": "number",
                    "description": "Hạn mức ngân sách đặt trước bằng VND.",
                },
            },
            "required": ["operation", "period"],
        },
    },
    {
        "name": "budget_checker",
        "description": "Kiểm tra trạng thái ngân sách theo danh mục và phát hiện nguy cơ vượt hạn mức chi tiêu.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Danh mục chi tiêu cần kiểm tra.",
                },
                "period": {
                    "type": "string",
                    "enum": ["week", "month"],
                    "description": "Chu kỳ ngân sách cần đánh giá.",
                },
                "warning_threshold": {
                    "type": "number",
                    "description": "Ngưỡng cảnh báo, ví dụ 0.8 tương đương 80%.",
                },
            },
            "required": ["category", "period"],
        },
    },
]

# ==============================================================================
# 2. MÔ PHỎNG DỮ LIỆU & HÀM THỰC THI TOOL (EXECUTION LAYER)
# ==============================================================================

EXPENSE_LEDGER = [
    {"transaction_id": "TX-001", "amount": 320000, "category": "Groceries", "description": "Siêu thị"},
    {"transaction_id": "TX-002", "amount": 85000, "category": "Transport", "description": "Đổ xăng"},
]

CATEGORY_MONTHLY_BUDGET = {
    "Groceries": 3_000_000,
    "Dining": 2_000_000,
    "Transport": 1_500_000,
    "Entertainment": 1_000_000,
}


def execute_expense_database(
    action: str,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    description: Optional[str] = "",
    date: Optional[str] = None,
) -> str:
    """Thực thi thao tác trên sổ chi tiêu mẫu."""
    if action == "list":
        return json.dumps({"status": "SUCCESS", "data": EXPENSE_LEDGER}, ensure_ascii=False)

    if action == "add":
        if not amount or not category:
            return json.dumps(
                {"status": "VALIDATION_ERROR", "message": "Cần nhập amount và category khi thêm giao dịch."},
                ensure_ascii=False,
            )
        new_tx = {
            "transaction_id": f"TX-{len(EXPENSE_LEDGER) + 1:03d}",
            "amount": float(amount),
            "category": category,
            "description": description or "",
            "date": date,
        }
        EXPENSE_LEDGER.append(new_tx)
        return json.dumps({"status": "SUCCESS", "transaction": new_tx}, ensure_ascii=False)

    return json.dumps(
        {"status": "NOT_SUPPORTED", "message": f"Chức năng '{action}' chưa được hỗ trợ."},
        ensure_ascii=False,
    )


def execute_budget_calculator(
    operation: str,
    period: str,
    category: Optional[str] = None,
    budget_limit: Optional[float] = None,
) -> str:
    """Tính toán ngân sách."""
    matched = [tx for tx in EXPENSE_LEDGER if not category or tx.get("category") == category]
    total = sum(tx["amount"] for tx in matched)
    limit = budget_limit or CATEGORY_MONTHLY_BUDGET.get(category or "Groceries", 0)

    if operation == "sum_expenses":
        return json.dumps({"status": "SUCCESS", "total": total}, ensure_ascii=False)
    if operation == "remaining_budget":
        return json.dumps({"status": "SUCCESS", "limit": limit, "remaining": max(limit - total, 0)}, ensure_ascii=False)
    if operation == "budget_usage_percentage":
        return json.dumps(
            {"status": "SUCCESS", "used": total, "limit": limit, "percentage": round(total / limit * 100, 2) if limit else 0},
            ensure_ascii=False,
        )
    return json.dumps({"status": "NOT_SUPPORTED", "message": f"Phép tính '{operation}' chưa hỗ trợ."}, ensure_ascii=False)


def execute_budget_checker(category: str, period: str, warning_threshold: float = 0.8) -> str:
    """Kiểm tra ngưỡng cảnh báo ngân sách."""
    total = sum(tx["amount"] for tx in EXPENSE_LEDGER if tx.get("category") == category)
    limit = CATEGORY_MONTHLY_BUDGET.get(category, 0)
    percentage = round(total / limit * 100, 2) if limit else 0

    status = "SAFE"
    suggestion = "Ngân sách ổn định, tiếp tục duy trì chi tiêu hợp lý."
    if percentage >= 100:
        status = "OVER_BUDGET"
        suggestion = f"Danh mục {category} đã vượt ngân sách ({percentage}%). Nên tạm hoãn chi tiêu không cần thiết."
    elif percentage >= warning_threshold * 100:
        status = "WARNING"
        suggestion = f"Danh mục {category} đã sử dụng {percentage}% ngân sách. Hãy hạn chế chi thêm."

    return json.dumps({
        "status": "SUCCESS", "category": category, "period": period,
        "used": total, "limit": limit, "percentage": percentage,
        "alert_status": status, "suggestion": suggestion,
    }, ensure_ascii=False)


# ==============================================================================
# 3. TOOL ROUTER & DISPATCHER
# ==============================================================================

TOOL_ROUTER: Dict[str, Any] = {
    "expense_database_tool": execute_expense_database,
    "budget_calculator": execute_budget_calculator,
    "budget_checker": execute_budget_checker,
}


def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Hàm trung chuyển thực thi tool"""
    if tool_name not in TOOL_ROUTER:
        return json.dumps(
            {"status": "UNKNOWN_TOOL", "error": f"Tool '{tool_name}' không tồn tại."},
            ensure_ascii=False,
        )
    try:
        return TOOL_ROUTER[tool_name](**arguments)
    except TypeError as exc:
        return json.dumps({"status": "EXECUTION_ERROR", "error": f"Sai tham số: {exc}"}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"status": "EXECUTION_ERROR", "error": str(exc)}, ensure_ascii=False)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 62)
    print("KIEM THU PYTHON DISPATCHER - QUAN LY CHI TIEU CA NHAN")
    print("=" * 62)
    names = [t["name"] for t in TOOLS_SCHEMA]
    print(f"Da dang ky thanh cong {len(names)} Native Tools trong TOOLS_SCHEMA: {', '.join(names)}")
    result = json.loads(dispatch_tool_call(
        "expense_database_tool",
        {"action": "add", "amount": 90000, "category": "Transport", "description": "Do xang"},
    ))
    print(f"Ket qua goi thu expense_database_tool: Status {result.get('status')}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
