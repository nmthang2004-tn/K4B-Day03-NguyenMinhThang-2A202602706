"""
CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
Chủ đề: Trợ lý Quản lý Chi tiêu Cá nhân.
"""

import json
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp_server import MCPFinanceServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_AGENT_SYSTEM_PROMPT,
    MAX_ITERATIONS,
)
from providers import get_llm_provider

load_dotenv()


def load_test_cases():
    """Tải danh sách test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG]: Chưa thấy 'config/test_cases.json'. Đang dùng mẫu.\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list):
    """Ghi Waterfall Trace Log ra file docs/trace_waterfall.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, "trace_waterfall.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [TRACE]: Đã lưu {len(trace_data)} sự kiện tại '{trace_path}'!")


def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot Baseline (Cấp 2) – không gọi Tool"""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot phản hồi:\n{response}")


def _synth_observation(obs_data: dict) -> str:
    """Tổng hợp Final Answer từ kết quả Observation của finance tools."""
    status = obs_data.get("status")

    if status == "SUCCESS":
        # expense_database_tool trả về giao dịch vừa thêm
        if "transaction" in obs_data:
            tx = obs_data["transaction"]
            amt = f"{tx['amount']:,.0f}".replace(",", ".")
            return (
                f"Đã ghi nhận giao dịch chi tiêu: {tx['description']} – "
                f"{tx['category']} – {amt}đ (Mã GD: {tx['transaction_id']})."
            )

        # expense_database_tool — list
        if "data" in obs_data:
            data = obs_data["data"]
            if not data:
                return "Chưa có giao dịch chi tiêu nào được ghi nhận."
            lines = ["Danh sách giao dịch hiện có:"]
            total = 0
            for tx in data:
                amt = tx.get("amount", 0)
                total += amt
                lines.append(
                    f"  • {tx.get('transaction_id', 'N/A')}: "
                    f"{tx.get('description', '')} – {tx.get('category', '')} – "
                    f"{amt:,.0f}đ".replace(",", ".")
                )
            lines.append(f"Tổng cộng: {total:,.0f}đ".replace(",", "."))
            return "\n".join(lines)

        # budget_calculator — sum_expenses
        if "total" in obs_data:
            total = obs_data["total"]
            cat = obs_data.get("category", "tất cả")
            return f"Tổng chi tiêu [{cat}]: {total:,.0f}đ".replace(",", ".")

        # budget_calculator — remaining_budget
        if "remaining" in obs_data and "limit" in obs_data:
            cat = obs_data.get("category", "tất cả")
            return (
                f"Ngân sách [{cat}]: "
                f"Đã dùng {obs_data.get('used', 0):,.0f}đ / "
                f"Hạn mức {obs_data['limit']:,.0f}đ – "
                f"Còn lại {obs_data['remaining']:,.0f}đ".replace(",", ".")
            )

        # budget_checker
        if "alert_status" in obs_data:
            pct = obs_data.get("percentage", 0)
            alert = obs_data["alert_status"]
            icon = {"SAFE": "✅", "WARNING": "⚠️", "OVER_BUDGET": "🚨"}.get(alert, "ℹ️")
            return (
                f"{icon} Ngân sách [{obs_data['category']}] tháng này: "
                f"{pct}% đã dùng ({obs_data['used']:,.0f}đ / "
                f"{obs_data['limit']:,.0f}đ)\n"
                f"   → {obs_data.get('suggestion', '')}".replace(",", ".")
            )

        # fallback
        if "message" in obs_data:
            return obs_data["message"]
        return json.dumps(obs_data, ensure_ascii=False)

    if status == "NOT_FOUND":
        return obs_data.get("message", "Không tìm thấy dữ liệu yêu cầu.")
    if status == "VALIDATION_ERROR":
        return obs_data.get("message", "Thiếu thông tin bắt buộc để thực thi thao tác.")
    return f"Phản hồi từ công cụ: {json.dumps(obs_data, ensure_ascii=False)}"


def run_react_agent(user_query: str, provider, mcp_server: MCPFinanceServer) -> list:
    """
    [REACT AGENT LOOP] Thought -> Action -> Observation
    Trả về danh sách trace log của phiên thực thi.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    step = 0
    trace_logs: list[dict] = []
    tools_list = mcp_server.list_tools()

    while step < MAX_ITERATIONS:
        step += 1
        step_start = time.time()
        print(f"\n--- 🔄 ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")

        llm_response = provider.generate_with_tools(
            user_query, tools_list, system_prompt=REACT_AGENT_SYSTEM_PROMPT
        )
        latency_ms = round((time.time() - step_start) * 1000, 2)

        thought = llm_response.get("thought", "Đang suy luận...")
        print(f"🧠 [Thought]: {thought}")

        # ── Trường hợp 1: LLM trả lời trực tiếp bằng văn bản ──
        if llm_response.get("type") == "text":
            final_content = llm_response.get("content", "")
            print(f"🏁 [Final Answer]: {final_content}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": final_content,
                "llm_model": llm_response.get("model"),
                "latency_ms": latency_ms,
            })
            break

        # ── Trường hợp 2: LLM đề xuất gọi Tool ──
        if llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {})
            print(f"🛠️ [Action]: {tool_name}({json.dumps(arguments, ensure_ascii=False)})")

            mcp_result = mcp_server.call_tool(tool_name, arguments)
            obs_data = mcp_result.get("result", {})

            if not obs_data:
                print("👁️ [Observation]: MCP Server trả về rỗng.")
                final_answer = "Chưa nhận được dữ liệu từ MCP Server. Vui lòng kiểm tra lại cấu hình tool."
            else:
                obs_str = json.dumps(obs_data, ensure_ascii=False)
                print(f"👁️ [Observation]: {obs_str}")
                final_answer = _synth_observation(obs_data)

            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "TOOL_EXECUTION",
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "llm_model": llm_response.get("model"),
                "latency_ms": latency_ms,
            })

            print(f"🧠 [Thought]: Đã nhận dữ liệu từ MCP Server. Tổng hợp kết quả.")
            print(f"🏁 [Final Answer]: {final_answer}")

            trace_logs.append({
                "step": step + 1,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": "Tổng hợp kết quả từ MCP Server.",
                "output": final_answer,
                "latency_ms": 10.0,
            })
            break

    return trace_logs


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 62)
    print("💰 TRỢ LÝ QUẢN LÝ CHI TIÊU CÁ NHÂN – REACT AGENT")
    print("=" * 62)

    provider = get_llm_provider()
    mcp_server = MCPFinanceServer()

    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server:   {mcp_server.server_name}\n")

    tests = load_test_cases()
    print(f"✅ Đã tải {len(tests)} Test Cases.\n")

    # ── Interactive ──
    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với Trợ lý Chi tiêu:")
        print("💡 Gợi ý:")
        print("   • 'Hôm nay mình đi siêu thị hết 850.000đ, ghi sổ giúp mình'")
        print("   • 'Tháng này mình đã tiêu bao nhiêu cho ăn uống?'")
        print("   • 'Ngân sách ăn uống tháng này còn bao nhiêu?'")
        print("   • Gõ 'exit' để thoát.\n")
        while True:
            try:
                user_input = input("👤 Bạn hỏi: ").strip()
                if not user_input or user_input.lower() in ("exit", "quit"):
                    print("👋 Tạm biệt!")
                    break
                logs = run_react_agent(user_input, provider, mcp_server)
                save_waterfall_trace(logs)
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát.")
                break

    # ── Test Suite ──
    elif "--all" in sys.argv:
        print("🚀 [TEST SUITE] Chạy toàn bộ Test Cases:")
        completed = 0
        todo_count = 0
        all_traces = []

        for tc in tests:
            print(f"\n{'=' * 50}")
            print(f"🧪 [{tc['id']}] Loại: {tc['type']} | Phức tạp: {tc['complexity']}")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")

            if tc["question"].strip().startswith("TODO"):
                print(f"⏸️  TODO – chưa điền câu hỏi.")
                todo_count += 1
            else:
                logs = run_react_agent(tc["question"], provider, mcp_server)
                all_traces.extend(logs)
                completed += 1

        print(f"\n{'=' * 50}")
        print(f"📊 Kết quả: {completed}/{len(tests)} đã chạy | {todo_count} TODO")
        if all_traces:
            save_waterfall_trace(all_traces)

    # ── Demo mặc định ──
    else:
        print("ℹ️ Cách dùng:")
        print("  python src/app.py --interactive    # Chat trực tiếp")
        print("  python src/app.py --all            # Chạy toàn bộ test cases\n")

        sample = next((tc["question"] for tc in tests if not tc["question"].startswith("TODO")), None)
        if sample:
            print(f"--- 🏁 DEMO: {sample} ---")
            logs = run_react_agent(sample, provider, mcp_server)
            save_waterfall_trace(logs)
