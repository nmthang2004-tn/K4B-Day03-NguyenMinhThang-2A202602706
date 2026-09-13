"""Web demo không phụ thuộc framework cho Trợ lý Quản lý Chi tiêu ReAct."""

import json
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app import load_test_cases, run_react_agent, save_waterfall_trace
from mcp_server import MCPFinanceServer
from providers import get_llm_provider


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
PROJECT_DIR = BASE_DIR.parent
TRACE_PATH = PROJECT_DIR / "docs" / "trace_waterfall.json"


class DemoState:
    """Giữ provider, MCP server và lịch sử trong suốt phiên demo web."""

    def __init__(self):
        self.provider = get_llm_provider()
        self.mcp_server = MCPFinanceServer()
        self.history = []

    def ask(self, query: str) -> dict:
        logs = run_react_agent(query, self.provider, self.mcp_server)
        final = next(
            (event.get("output", "") for event in reversed(logs)
             if event.get("action_type") == "FINAL_ANSWER"),
            "Chưa có phản hồi cuối cùng.",
        )
        result = {"query": query, "answer": final, "trace": logs}
        self.history.append(result)
        return result


STATE = DemoState()


class DemoHandler(SimpleHTTPRequestHandler):
    """Phục vụ UI tĩnh cùng một API JSON rất nhỏ cho buổi demo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format, *args):
        # Giữ terminal gọn; các log ReAct quan trọng đã do app.py in ra.
        return

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/health":
            return self._json({
                "provider": STATE.provider.__class__.__name__,
                "model": getattr(STATE.provider, "model_name", "Offline Mock"),
                "mcp_server": STATE.mcp_server.server_name,
                "tool_count": len(STATE.mcp_server.list_tools()),
            })
        if route == "/api/test-cases":
            return self._json({"items": load_test_cases()})
        if route == "/api/history":
            return self._json({"items": STATE.history[-12:]})
        if route == "/api/saved-trace":
            if not TRACE_PATH.exists():
                return self._json({"items": []})
            try:
                return self._json({"items": json.loads(TRACE_PATH.read_text(encoding="utf-8"))})
            except json.JSONDecodeError:
                return self._json({"items": []})
        if route in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        route = urlparse(self.path).path
        if route not in ("/api/chat", "/api/run-test"):
            return self._json({"error": "Không tìm thấy API endpoint."}, HTTPStatus.NOT_FOUND)

        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return self._json({"error": "Dữ liệu gửi lên không hợp lệ."}, HTTPStatus.BAD_REQUEST)

        query = str(data.get("query", "")).strip()
        if not query:
            return self._json({"error": "Hãy nhập một câu hỏi để Agent xử lý."}, HTTPStatus.BAD_REQUEST)

        try:
            result = STATE.ask(query)
            # Lưu lần chạy gần nhất để có thể mở JSON trace khi thuyết trình.
            save_waterfall_trace(result["trace"])
            return self._json(result)
        except Exception as exc:  # Không để một lỗi provider làm dừng web server.
            return self._json({"error": f"Agent gặp lỗi: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def run(host: str = "127.0.0.1", port: int = 8000):
    """Khởi chạy UI tại http://127.0.0.1:8000."""
    server = ThreadingHTTPServer((host, port), DemoHandler)
    print("=" * 62)
    print("💳 FINANCE REACT AGENT — WEB DEMO")
    print(f"🌐 Mở trình duyệt: http://{host}:{port}")
    print("⌨️  Nhấn Ctrl+C để dừng server.")
    print("=" * 62)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Đã dừng Web Demo.")
    finally:
        server.server_close()


if __name__ == "__main__":
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    requested_port = int(os.getenv("WEB_DEMO_PORT", "8000"))
    run(port=requested_port)
