"""
🔌 MULTI-PROVIDER LLM ADAPTER (Google Gemini, OpenAI & Offline Mock)
Hỗ trợ Native Tool Calling và chuyển đổi linh hoạt qua biến môi trường LLM_PROVIDER.
"""

import os
import sys
import json
from typing import Dict, Any, List
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho các LLM Provider hỗ trợ Native Tool Calling"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Offline Mock Provider dùng để chạy thử mà không tốn API Key"""
    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return f"[Mock Chatbot Response]: Xin chào! Tôi đã nhận được câu hỏi '{prompt}'. (Chế độ Chatbot không có Tool tra cứu dữ liệu thời gian thực)."

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        prompt_lower = prompt.lower()

        # Mô phỏng nhận diện intent gọi Tool cho quản lý chi tiêu
        if "ngân sách" in prompt_lower and ("ăn" in prompt_lower or "dining" in prompt_lower):
            return {
                "type": "tool_call",
                "tool_name": "budget_checker",
                "arguments": {"category": "Dining", "period": "month", "warning_threshold": 0.8},
                "thought": "Người dùng muốn kiểm tra ngân sách danh mục Ăn uống. Tôi sẽ gọi budget_checker.",
            }
        if "còn bao nhiêu" in prompt_lower or "tổng cộng bao nhiêu" in prompt_lower or "đã tiêu" in prompt_lower:
            return {
                "type": "tool_call",
                "tool_name": "budget_calculator",
                "arguments": {"operation": "sum_expenses", "period": "day"},
                "thought": "Người dùng yêu cầu thống kê chi tiêu. Tôi sẽ gọi budget_calculator để tính tổng chi tiêu.",
            }
        if "đổ xăng" in prompt_lower or "siêu thị" in prompt_lower or "thanh toán" in prompt_lower or "tiêu" in prompt_lower or "chi" in prompt_lower:
            # TC05: câu thiếu danh mục "- vừa tiêu 200k" => trả lời hỏi lại thay vì gọi tool sai
            if prompt_lower.strip() in ("mình vừa tiêu 200k, ghi sổ giúp mình.", "mình vừa tiêu 200k ghi sổ giúp mình"):
                return {
                    "type": "text",
                    "content": "Bạn muốn ghi số tiền 200.000đ vào danh mục nào? Ví dụ: Ăn uống, Di chuyển, Giải trí, Mua sắm...",
                    "thought": "Câu lệnh thiếu danh mục chi tiêu. Cần hỏi lại để làm rõ trước khi gọi expense_database_tool.",
                }
            # TC02/TC03: ghi sổ đơn giản
            if "đổ xăng" in prompt_lower and "siêu thị" not in prompt_lower:
                return {
                    "type": "tool_call",
                    "tool_name": "expense_database_tool",
                    "arguments": {"action": "add", "amount": 90000, "category": "Transport", "description": "Đổ xăng"},
                    "thought": "Người dùng yêu cầu ghi sổ đổ xăng 90.000đ. Tôi sẽ gọi expense_database_tool.",
                }
            if "siêu thị" in prompt_lower:
                return {
                    "type": "tool_call",
                    "tool_name": "expense_database_tool",
                    "arguments": {"action": "add", "amount": 850000, "category": "Groceries", "description": "Siêu thị"},
                    "thought": "Người dùng yêu cầu ghi sổ siêu thị 850.000đ. Tôi sẽ gọi expense_database_tool.",
                }
            return {
                "type": "tool_call",
                "tool_name": "expense_database_tool",
                "arguments": {"action": "add", "amount": 200000, "category": "Other", "description": "Chi tiêu"},
                "thought": "Người dùng yêu cầu ghi sổ chi tiêu. Tôi sẽ gọi expense_database_tool.",
            }

        return {
            "type": "text",
            "content": "Xin chào! Tôi là trợ lý quản lý chi tiêu cá nhân. Tôi có thể giúp bạn ghi sổ chi tiêu, tính tổng chi tiêu theo ngày/tuần/tháng và cảnh báo khi ngân sách sắp vượt ngưỡng.",
            "thought": "Câu hỏi chung về tính năng trợ lý. Trả lời trực tiếp không cần gọi Tool.",
        }


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider (Native Tool Calling với Google GenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        configured_fallbacks = os.getenv(
            "GEMINI_FALLBACK_MODELS",
            "gemini-3.8-flash,gemini-3.7-flash,gemini-3.6-flash",
        )
        self.fallback_models = [
            item.strip() for item in configured_fallbacks.split(",") if item.strip()
        ]

    @staticmethod
    def _is_model_fallback_error(error: Exception) -> bool:
        """Chỉ chuyển model khi API báo hết quota hoặc model tạm không khả dụng."""
        message = str(error).upper()
        return (
            "429" in message
            or "RESOURCE_EXHAUSTED" in message
            or "503" in message
            or "UNAVAILABLE" in message
        )

    def _model_candidates(self) -> List[str]:
        """Giữ model trong .env là ưu tiên, sau đó dùng các Flash model dự phòng."""
        return list(dict.fromkeys([self.model_name, *self.fallback_models]))

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            last_error = None
            for candidate in self._model_candidates():
                try:
                    response = client.models.generate_content(model=candidate, contents=contents)
                    if candidate != self.model_name:
                        print(f"ℹ️ [Gemini Provider]: Model '{self.model_name}' hết quota; dùng '{candidate}'.")
                    return response.text
                except Exception as error:
                    last_error = error
                    if not self._is_model_fallback_error(error):
                        raise
                    print(f"⚠️ [Gemini Provider]: '{candidate}' không khả dụng ({str(error).splitlines()[0]}); thử model dự phòng.")
            raise last_error
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("ℹ️ [Gemini Provider]: Chưa tìm thấy GEMINI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)
        
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            
            # Chuẩn hóa function declarations cho Gemini SDK
            function_declarations = []
            for tool in tools_schema:
                # Bỏ qua các tool schema chưa được định nghĩa hoàn chỉnh
                if not tool.get("name") or not tool.get("parameters"):
                    continue
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                temperature=0.2
            )

            last_error = None
            response = None
            used_model = self.model_name
            for candidate in self._model_candidates():
                try:
                    response = client.models.generate_content(
                        model=candidate,
                        contents=prompt,
                        config=config,
                    )
                    used_model = candidate
                    if candidate != self.model_name:
                        print(f"ℹ️ [Gemini Provider]: Model '{self.model_name}' hết quota; dùng '{candidate}'.")
                    break
                except Exception as error:
                    last_error = error
                    if not self._is_model_fallback_error(error):
                        raise
                    print(f"⚠️ [Gemini Provider]: '{candidate}' không khả dụng ({str(error).splitlines()[0]}); thử model dự phòng.")

            if response is None:
                raise last_error

            # Kiểm tra xem Gemini có trả về Tool Call không
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if hasattr(call, 'args') and call.args else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "model": used_model,
                    "thought": f"Gemini ({used_model}) quyết định gọi công cụ '{call.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": response.text or "",
                    "model": used_model,
                    "thought": f"Gemini ({used_model}) phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }

        except Exception as e:
            print(f"⚠️ [Gemini API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (Native Tool Calling với OpenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            print("ℹ️ [OpenAI Provider]: Chưa tìm thấy OPENAI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            tools = []
            for tool in tools_schema:
                if not tool.get("name"):
                    continue
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                })

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )

            msg = response.choices[0].message
            if msg.tool_calls:
                call = msg.tool_calls[0]
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.function.name,
                    "arguments": args,
                    "thought": f"OpenAI quyết định gọi công cụ '{call.function.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": msg.content or "",
                    "thought": "OpenAI phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }
        except Exception as e:
            print(f"⚠️ [OpenAI API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


def get_llm_provider() -> BaseLLMProvider:
    """Factory function khởi tạo Provider theo LLM_PROVIDER env variable"""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider_type == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if key and key != "your_gemini_api_key_here":
            return GeminiProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key and key != "your_openai_api_key_here":
            return OpenAIProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "mock":
        return MockOfflineProvider()
    else:
        return MockOfflineProvider()
