"""
MCP SERVER MODULE
MCP Server mô phỏng cho Trợ lý Quản lý Chi tiêu Cá nhân.
"""

import json
import sys
from typing import Any, Dict, List

from tools import TOOLS_SCHEMA, dispatch_tool_call

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class MCPFinanceServer:
    """MCP Server tối giản; giữ tên lớp cũ để tương thích với src/app.py."""

    def __init__(self, server_name: str = "personal-finance-mcp-server"):
        self.server_name = server_name
        self.version = "2026.1.0"

    def list_tools(self) -> List[Dict[str, Any]]:
        """Trả về danh sách Native Tool Schemas công bố cho LLM."""
        return TOOLS_SCHEMA

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Thực thi tool qua Dispatcher và đóng gói kết quả theo JSON-RPC 2.0."""
        raw_result = dispatch_tool_call(tool_name, arguments)
        try:
            content = json.loads(raw_result)
        except (TypeError, json.JSONDecodeError) as exc:
            content = {
                "status": "INVALID_TOOL_RESPONSE",
                "error": f"Tool trả về dữ liệu không phải JSON hợp lệ: {exc}",
            }

        return {
            "jsonrpc": "2.0",
            "server": self.server_name,
            "tool": tool_name,
            "result": content,
        }


if __name__ == "__main__":
    print("=" * 62)
    print("KIỂM THỬ MCP SERVER - TRỢ LÝ QUẢN LÝ CHI TIÊU CÁ NHÂN")
    print("=" * 62)

    server = MCPFinanceServer()
    tools = server.list_tools()
    tool_names = [tool["name"] for tool in tools]
    print(f"✅ Khởi tạo MCP Server: {server.server_name} (Version: {server.version})")
    print(f"📦 Số lượng Tools công bố: {len(tools)}")
    print(f"🧰 Tools: {', '.join(tool_names)}")

    test_result = server.call_tool(
        "expense_database_tool",
        {
            "action": "add",
            "amount": 90000,
            "category": "Transport",
            "description": "Đổ xăng",
        },
    )
    result = test_result.get("result", {})
    if test_result.get("jsonrpc") == "2.0" and result.get("status") == "SUCCESS":
        print("✅ [TASK 2.1]: Dispatcher và MCP JSON-RPC hoạt động thành công.")
        print(f"   Kết quả gọi thử expense_database_tool: {json.dumps(result, ensure_ascii=False)}")
    else:
        print(f"❌ [TASK 2.1]: Kiểm thử thất bại: {json.dumps(test_result, ensure_ascii=False)}")
