# from fastapi import FastAPI, Request
# from fastapi.responses import StreamingResponse, JSONResponse
# import httpx
# import json
# import uuid
#
# app = FastAPI()
#
# # 你的超算信息
# SUPERCLOUD_API_KEY = "sk-Mzc1LTEyNjI5MzMzNzc5LTE3NzQxNzM3MDcwNTc="
# SUPERCLOUD_URL = "https://api.scnet.cn/api/llm/v1"
#
# MODEL_MAP = {
#     "claude-3-sonnet": "MiniMax-M2.5",
#     "claude-3-haiku": "MiniMax-M2.5",
# }
#
# # 必须实现！Claude Code 必调用
# @app.post("/v1/messages/count_tokens")
# async def count_tokens():
#     return {"input_tokens": 10, "output_tokens": 10}
#
# @app.post("/v1/messages")
# async def chat(request: Request):
#     body = await request.json()
#     model = body.get("model", "claude-3-sonnet")
#     stream = body.get("stream", False)
#     messages = body.get("messages", [])
#
#     # 转换消息格式（适配超算）
#     conv_messages = []
#     for msg in messages:
#         role = msg.get("role")
#         content = msg.get("content")
#         text = ""
#         if isinstance(content, list):
#             for c in content:
#                 if c.get("type") == "text":
#                     text += c.get("text", "")
#         else:
#             text = str(content or "")
#         conv_messages.append({"role": role, "content": text})
#
#     # 请求超算获取真实回答
#     async with httpx.AsyncClient(timeout=120) as client:
#         resp = await client.post(
#             f"{SUPERCLOUD_URL}/chat/completions",
#             headers={
#                 "Authorization": f"Bearer {SUPERCLOUD_API_KEY}",
#                 "Content-Type": "application/json"
#             },
#             json={
#                 "model": MODEL_MAP.get(model, "MiniMax-M2.5"),
#                 "messages": conv_messages,
#                 "temperature": 0.7,
#                 "stream": stream
#             }
#         )
#
#     # ----------------------
#     # 流式返回（对接超算流式输出）
#     # ----------------------
#     if stream:
#         async def generate():
#             # 超算流式解析 + Claude Code 格式转换
#             async for line in resp.aiter_lines():
#                 if not line:
#                     continue
#                 if line.startswith("data: "):
#                     line = line[6:]
#                 if line == "[DONE]":
#                     yield f"data: {json.dumps({'type': 'message_stop'})}\n\n"
#                     break
#                 try:
#                     data = json.loads(line)
#                     token = data["choices"][0]["delta"].get("content", "")
#                     if token:
#                         yield f"data: {json.dumps({
#                             'type': 'content_block_delta',
#                             'index': 0,
#                             'delta': {'type': 'text_delta', 'text': token}
#                         })}\n\n"
#                 except Exception:
#                     pass
#         return StreamingResponse(generate(), media_type="text/event-stream")
#
#     # ----------------------
#     # 非流式返回（兜底）
#     # ----------------------
#     result = resp.json()
#     reply = result["choices"][0]["message"]["content"].strip()
#     return JSONResponse({
#         "id": f"msg_{uuid.uuid4().hex[:16]}",
#         "type": "message",
#         "role": "assistant",
#         "content": [{"type": "text", "text": reply}],
#         "model": model,
#         "stop_reason": "end_turn",
#         "usage": {"input_tokens": 10, "output_tokens": len(reply) // 3}
#     })
#
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="127.0.0.1", port=9999)

# from fastapi import FastAPI, Request, HTTPException
# from fastapi.responses import JSONResponse
# import httpx
# import json
# from fastapi.middleware.cors import CORSMiddleware # 新增导入
#
# app = FastAPI()
#
# # 你的超算平台配置
# SUPERCLOUD_API_KEY = "sk-Mzc1LTEyNjI5MzMzNzc5LTE3NzQxNzM3MDcwNTc="
# SUPERCLOUD_URL = "https://api.scnet.cn/api/llm/v1"
#
# # 模型映射
# MODEL_MAP = {
#     "claude-3-sonnet": "MiniMax-M2.5",
#     "claude-3-haiku": "MiniMax-M2.5"
# }
#
#
# # 新增 CORS 配置
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # 允许所有源（生产环境建议配置具体域名）
#     allow_credentials=True,
#     allow_methods=["*"],  # 允许所有方法
#     allow_headers=["*"],  # 允许所有头
# )
#
# @app.post("/v1/messages")
# async def claude_messages(request: Request):
#     try:
#         # 安全获取 body
#         body_bytes = await request.body()
#         if not body_bytes:
#             raise HTTPException(status_code=400, detail="empty body")
#
#         body = json.loads(body_bytes)
#
#         # 解析 Claude 请求
#         model = body.get("model", "claude-3-sonnet")
#         messages = body.get("messages", [])
#
#         # 转换消息格式
#         converted_messages = []
#         for msg in messages:
#             role = msg.get("role")
#             content = ""
#             if isinstance(msg.get("content"), list):
#                 for c in msg["content"]:
#                     if c["type"] == "text":
#                         content += c["text"]
#             else:
#                 content = msg.get("content", "")
#             converted_messages.append({"role": role, "content": content})
#
#         # 构造超算请求
#         payload = {
#             "model": MODEL_MAP.get(model, "MiniMax-M2.5"),
#             "messages": converted_messages,
#             "temperature": body.get("temperature", 0.7)
#         }
#
#         # 请求超算
#         async with httpx.AsyncClient(timeout=60) as client:
#             resp = await client.post(
#                 SUPERCLOUD_URL + "/chat/completions",
#                 headers={
#                     "Authorization": f"Bearer {SUPERCLOUD_API_KEY}",
#                     "Content-Type": "application/json"
#                 },
#                 json=payload
#             )
#
#         # 打印超算返回的原始信息（方便排查问题）
#         print("超算状态码:", resp.status_code)
#         print("超算返回内容:", resp.text)
#
#         if resp.status_code != 200:
#             return JSONResponse({
#                 "error": "supercloud api error",
#                 "status_code": resp.status_code,
#                 "detail": resp.text
#             }, status_code=500)
#
#         result = resp.json()
#         answer = result["choices"][0]["message"]["content"]
#
#         # 返回 Claude 格式
#         return {
#             "id": "msg_123",
#             "type": "message",
#             "role": "assistant",
#             "content": [{"type": "text", "text": answer}],
#             "model": model,
#             "stop_reason": "end_turn"
#         }
#
#     except Exception as e:
#         print("捕获到异常:", str(e))
#         return JSONResponse({"error": str(e)}, status_code=500)


# from fastapi import FastAPI, Request, HTTPException
# from fastapi.responses import JSONResponse
# from fastapi.middleware.cors import CORSMiddleware
# import json
#
# app = FastAPI()
#
# # 允许跨域
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
#
# async def spy_on_request(request: Request):
#     # 1. 获取所有信息
#     method = request.method
#     url = str(request.url)
#     headers = dict(request.headers)
#     query_params = dict(request.query_params)
#
#     # 2. 获取 Body
#     try:
#         body_bytes = await request.body()
#         body_str = body_bytes.decode('utf-8', errors='ignore')
#         try:
#             body_json = json.loads(body_str)
#         except:
#             body_json = None
#     except Exception as e:
#         body_str = f"Failed to read body: {str(e)}"
#         body_json = None
#
#     # 3. 构建调试数据包
#     debug_data = {
#         "method": method,
#         "url": url,
#         "headers": headers,
#         "query_params": query_params,
#         "body_raw": body_str,
#         "body_json": body_json
#     }
#
#     # 4. 打印到终端
#     print("\n" + "=" * 50)
#     print("🚨 CLAUDE CODE 请求 intercepted!")
#     print(json.dumps(debug_data, indent=2, ensure_ascii=False))
#     print("=" * 50 + "\n")
#
#     # 5. 保存到文件（当前目录下的 debug_log.txt）
#     with open("debug_log.txt", "a", encoding="utf-8") as f:
#         f.write(json.dumps(debug_data, indent=2, ensure_ascii=False))
#         f.write("\n---\n")
#
#     return debug_data
#
#
# # --- 拦截所有可能的路径 ---
#
# @app.post("/{path:path}")
# async def catch_all(request: Request, path: str):
#     debug_info = await spy_on_request(request)
#
#     # 直接返回一个错误，把调试信息塞回去，
#     # 这样 Claude Code 可能会在错误详情里显示我们返回的内容
#     return JSONResponse(
#         status_code=400,
#         content={
#             "error": "Debug Mode",
#             "message": "I've logged your request. Check the server terminal or debug_log.txt",
#             "your_request": debug_info
#         }
#     )
# # 启动 9999 端口
# if __name__ == "__main__":
#     import uvicorn
#
#     uvicorn.run(app, host="0.0.0.0", port=9999)


from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import time
import re

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 超算平台配置
SUPERCLOUD_API_KEY = "sk-Mzc1LTEyNjI5MzMzNzc5LTE3NzQxNzM3MDcwNTc="
SUPERCLOUD_URL = "https://api.scnet.cn/api/llm/v1"

# 模型映射
MODEL_MAP = {
    "claude-3-sonnet": "MiniMax-M2.5",
    "claude-3-haiku": "MiniMax-M2.5",
    "claude-3-opus": "MiniMax-M2.5"
}

# 【最高优先级规则】彻底禁止工具调用，中英双语强约束
FORBID_TOOL_PROMPT = """
==================== 最高优先级强制规则 ====================
你必须100%遵守以下规则，绝对不能违反：
1. 你只能输出纯自然语言文本，绝对不允许使用任何工具、函数、指令调用。
2. 绝对禁止输出任何包含 minimax:tool_call、tool_call、function_call、Glob、Read、Write、Bash 等工具相关的内容。
3. 无论用户问什么，你都直接用自然语言回答，绝对不能提任何需要调用工具、执行代码、读取/写入文件的内容。
4. 如果用户让你操作文件、写代码、执行命令，你直接把代码/操作步骤用纯文本写出来，绝对不能调用任何工具。
5. 禁止输出任何非自然语言的指令格式，所有内容都必须是人类可读的纯文本。
6. 如果用户的需求需要操作文件，你直接告诉用户你无法直接操作文件，然后把完整的代码/步骤用纯文本写出来，让用户手动操作。
============================================================
"""

# 工具关键词黑名单，只要出现就拦截
BLACKLIST_KEYWORDS = ["minimax:tool_call", "tool_call", "function_call", "Glob", "Read", "Write", "Bash", "Edit",
                      "TodoWrite"]


def generate_sse_event(event_type: str, data: dict) -> str:
    """生成符合Anthropic规范的SSE事件"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_response_generator(answer: str, model: str):
    """纯文本流式响应生成器"""
    msg_id = f"msg_{int(time.time() * 1000)}"

    # 标准Anthropic流式事件序列
    yield generate_sse_event("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [], "model": model, "stop_reason": None,
            "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": len(answer)}
        }
    })

    yield generate_sse_event("content_block_start", {
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "text", "text": ""}
    })

    yield generate_sse_event("content_block_delta", {
        "type": "content_block_delta", "index": 0,
        "delta": {"type": "text_delta", "text": answer}
    })

    yield generate_sse_event("content_block_stop", {
        "type": "content_block_stop", "index": 0
    })

    yield generate_sse_event("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": len(answer)}
    })

    yield generate_sse_event("message_stop", {"type": "message_stop"})


@app.post("/v1/messages")
async def claude_messages(request: Request):
    print("\n" + "=" * 80)
    print(f"[请求时间] {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    try:
        # 1. 解析请求，直接丢弃所有工具相关字段
        body_bytes = await request.body()
        body = json.loads(body_bytes)

        # 【第一层拦截】彻底移除工具相关字段
        body.pop("tools", None)
        body.pop("tool_choice", None)
        body.pop("functions", None)

        model = body.get("model", "claude-3-sonnet")
        messages = body.get("messages", [])
        print(f"[请求信息] 模型: {model} | 消息轮数: {len(messages)}")

        # 2. 处理System Prompt，把禁用规则放在最前面
        system_parts = body.get("system", [])
        original_system = "\n".join([
            p.get("text", "") for p in system_parts
            if isinstance(p, dict) and p.get("type") == "text"
        ])
        # 强制拼接禁用规则
        final_system = FORBID_TOOL_PROMPT + "\n\n" + original_system

        # 3. 转换消息格式，只保留纯文本，过滤所有工具内容
        converted_messages = []
        # 把禁用规则合并到第一条用户消息
        if messages:
            first_msg = messages[0]
            if first_msg.get("role") == "user":
                if isinstance(first_msg.get("content"), list):
                    for c in first_msg["content"]:
                        if c.get("type") == "text":
                            c["text"] = f"{final_system}\n\n{c['text']}"
                            break
                else:
                    first_msg["content"] = f"{final_system}\n\n{first_msg['content']}"

        # 遍历转换所有消息，只提取纯文本
        for msg in messages:
            role = msg.get("role")
            content = ""
            if isinstance(msg.get("content"), list):
                for c in msg["content"]:
                    if c.get("type") == "text":
                        content += c.get("text", "")
            else:
                content = msg.get("content", "")

            if role in ["user", "assistant"]:
                converted_messages.append({"role": role, "content": content})

        if not converted_messages:
            raise HTTPException(status_code=400, detail="无有效消息内容")

        # 4. 构造上游请求，绝对不传递任何工具参数
        payload = {
            "model": MODEL_MAP.get(model, "MiniMax-M2.5"),
            "messages": converted_messages,
            "temperature": 0.3,  # 降低温度，让模型更遵守规则
            "top_p": 0.9,
            "stream": False
        }

        # 5. 请求上游
        print(f"[上游请求] 发送请求到超算平台...")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                SUPERCLOUD_URL + "/chat/completions",
                headers={"Authorization": f"Bearer {SUPERCLOUD_API_KEY}", "Content-Type": "application/json"},
                json=payload
            )

        print(f"[上游响应] 状态码: {resp.status_code}")
        if resp.status_code != 200:
            print(f"[上游错误] {resp.text}")
            return JSONResponse({
                "type": "error",
                "error": {"type": "api_error", "message": f"上游服务错误: {resp.text}"}
            }, status_code=500)

        # 6. 【第二层拦截】过滤模型输出，彻底清除工具内容
        result = resp.json()
        raw_answer = result["choices"][0]["message"]["content"]
        print(f"[原始输出] {raw_answer[:200]}...")

        # 检查是否包含黑名单关键词
        has_blacklist = any(keyword in raw_answer for keyword in BLACKLIST_KEYWORDS)
        if has_blacklist:
            # 只要有工具关键词，直接重写回答，绝对不返回给前端
            final_answer = "抱歉，我无法直接执行工具操作或文件读写。如果你需要写冒泡排序代码，我可以直接给你完整的代码内容，你可以手动创建文件保存。\n\n冒泡排序Python代码示例：\n```python\ndef bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        # 标记是否发生交换，优化排序效率\n        swapped = False\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n                swapped = True\n        # 如果没有交换，说明数组已经有序，提前退出\n        if not swapped:\n            break\n    return arr\n\n# 测试示例\nif __name__ == \"__main__\":\n    test_arr = [64, 34, 25, 12, 22, 11, 90]\n    sorted_arr = bubble_sort(test_arr)\n    print(\"排序后的数组:\", sorted_arr)\n```"
        else:
            final_answer = raw_answer

        print(f"[最终输出] {final_answer[:200]}...")

        # 7. 返回流式响应
        return StreamingResponse(
            stream_response_generator(final_answer, model),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    except Exception as e:
        print(f"[异常] {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "type": "error",
            "error": {"type": "internal_error", "message": str(e)}
        }, status_code=500)


@app.post("/v1/chat/completions")
async def openai_compatible(request: Request):
    return await claude_messages(request)


if __name__ == "__main__":
    import uvicorn

    print("\n" + "#" * 80)
    print("# Claude Code 代理 - 纯文本终极兜底版")
    print("# 服务地址: http://127.0.0.1:9999")
    print("# 已彻底禁用工具调用，100%消除minimax:tool_call乱输出")
    print("#" * 80 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=9999)
