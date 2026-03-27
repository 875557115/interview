import json
import os
import traceback
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate

from ..llm.client import llm, logger


# ====================== 1. 纯手动实现JSON文本存储（保证数据完整性） ======================
class LightweightChatHistory:
    """纯手动实现轻量级JSON存储，不依赖LangChain历史组件"""
    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.history_dir = "./lightweight_dialogue_history"
        self.file_path = f"{self.history_dir}/{user_id}/{session_id}.json"
        # 初始化目录和文件
        os.makedirs(f"{self.history_dir}/{user_id}", exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({"user_messages": [], "ai_messages": []}, f, ensure_ascii=False, indent=2)

    def add_user_message(self, message: str):
        """追加用户提问（核心：保证历史不丢失）"""
        with open(self.file_path, "r+", encoding="utf-8") as f:
            data = json.load(f)
            # 去重：如果最后一条提问和当前一致，不重复存储
            if data["user_messages"] and data["user_messages"][-1]["content"] == message:
                return
            data["user_messages"].append({
                "content": message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()

    def add_ai_message(self, message: str):
        """追加AI回复（意图结果）"""
        with open(self.file_path, "r+", encoding="utf-8") as f:
            data = json.load(f)
            # 去重：如果最后一条提问和当前一致，不重复存储
            if data["ai_messages"] and data["ai_messages"][-1]["content"] == message:
                return
            data["ai_messages"].append({
                "content": message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()

    def get_all_user_messages(self) -> list:
        """获取所有用户提问（保证完整性）"""
        with open(self.file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [msg["content"] for msg in data["user_messages"]]

    def get_history_text(self) -> str:
        """拼接历史文本（用于Prompt）"""
        user_msgs = self.get_all_user_messages()
        if not user_msgs:
            return "无"
        return "\n".join([f"历史提问{idx+1}：{msg}" for idx, msg in enumerate(user_msgs)])

    def get_file_content(self) -> dict:
        """读取并返回文件的完整内容（核心新增方法）"""
        if not os.path.exists(self.file_path):
            logger.warning(f"历史文件不存在：{self.file_path}")
            return {"error": "文件不存在", "content": None}

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            return {"error": "", "content": content}
        except json.JSONDecodeError:
            logger.error(f"文件格式错误（非JSON）：{self.file_path}")
            return {"error": "文件格式错误", "content": None}
        except PermissionError:
            logger.error(f"无权限读取文件：{self.file_path}")
            return {"error": "无读取权限", "content": None}
        except Exception as e:
            logger.error(f"读取文件失败：{e}")
            return {"error": f"读取失败：{str(e)}", "content": None}

    # ====================== 2. LangChain意图识别（仅用Prompt和LLM） ======================
def recognize_intent(history_text: str, current_question: str, openai_api_key: str) -> dict:
    """用LangChain调用大模型识别意图"""
    prompt = ChatPromptTemplate.from_template("""
    结合历史对话识别用户核心意图，**只输出纯净的 JSON 格式**，不要任何额外说明、代码块标记或 markdown 格式。
    输出格式必须严格为：{{"intent": "用户意图", "keywords": ["关键词1", "关键词2"]}}

    历史对话：{history}
    当前提问：{question}
    """)
    chain = prompt | llm
    try:
        response = chain.invoke({"history": history_text, "question": current_question})
        response_text = response.content if hasattr(response, 'content') else str(response)
        try:
            # 去除首尾空白字符（避免格式问题）
            return json.loads(response_text)
        except json.JSONDecodeError:
            # JSON解析失败，直接返回原始字符串
            return response_text
    except Exception as e:
        logger.error("意图识别失败：{},{}", e,traceback.format_exc())
        return {"intent": "未识别", "keywords": []}


# ====================== 3. 完整流程 ======================
def process_question_lightweight(user_id: str, session_id: str, current_question: str, openai_api_key: str):
    try:
        """轻量级流程：纯手动存储+LangChain意图识别"""
        # 1. 初始化/加载历史
        history = LightweightChatHistory(user_id, session_id)
        # 2. 识别意图
        history_text = history.get_history_text()
        intent_result = recognize_intent(history_text, current_question, openai_api_key)
        # 3. 保存当前提问和意图
        history.add_user_message(current_question)
        history.add_ai_message(json.dumps(intent_result, ensure_ascii=False))
        # 4. 读取文件内容（核心修改）
        file_content = history.get_file_content()

        # 4. 返回结果
        return {
            "full_user_history": history.get_all_user_messages(),
            "current_intent": intent_result.get("intent", "未识别"),
            "keywords": intent_result["keywords"],
            "history_file": history.file_path,
            "history_text": history_text  # 直接返回文件内容
        }
    except Exception as e:
        logger.error(f"意图识别失败：{e}", exc_info=True)
        return {"full_user_history": [], "current_intent": "未识别", "keywords": [], "history_file": None}


# ====================== 测试 ======================
if __name__ == "__main__":
    result = process_question_lightweight(
        user_id="user_001",
        session_id="session_001",
        current_question="Python向量库怎么用？",
        openai_api_key="*"
    )

    print(f"历史文件：{result}")
    print(f"完整历史：{result['full_user_history']}")
    print(f"意图：{result['current_intent']}")
