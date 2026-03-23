import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatOpenAI

from langchain_community.llms import Tongyi
from langchain_community.llms.ollama import Ollama
from template.util.logger import get_logger

load_dotenv()
logger = get_logger("model_factory")

def create_llm():
    """
    多模型工厂：根据 MODEL_TYPE 自动创建对应 LLM
    支持：openai / qwen(通义) / wenxin(文心) / xinghuo(星火) / ollama
    """
    model_type = os.getenv("MODEL_TYPE", "openai").lower()
    logger.info(f"当前使用模型类型: {model_type}")

    # ===================== OpenAI =====================
    if model_type == "openai":
        return ChatOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            temperature=0.1,
        )

    # ===================== 通义千问 =====================
    elif model_type == "qwen":
        return Tongyi(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model_name=os.getenv("QWEN_MODEL", "qwen-turbo"),
            temperature=0.1,
        )

    # # ===================== 文心一言 =====================
    # elif model_type == "wenxin":
    #     return QianfanFan(
    #         api_key=os.getenv("QIANFAN_API_KEY"),
    #         secret_key=os.getenv("QIANFAN_SECRET_KEY"),
    #         model=os.getenv("QIANFAN_MODEL", "ERNIE-4.0-8K"),
    #         temperature=0.1,
    #     )
    #
    # # ===================== 讯飞星火 =====================
    # elif model_type == "xinghuo":
    #     return Spark(
    #         app_id=os.getenv("SPARK_APP_ID"),
    #         api_key=os.getenv("SPARK_API_KEY"),
    #         api_secret=os.getenv("SPARK_API_SECRET"),
    #         model=os.getenv("SPARK_MODEL", "generalv3"),
    #         temperature=0.1,
    #     )

    # ===================== Ollama 本地模型 =====================
    elif model_type == "ollama":
        return Ollama(
            model=os.getenv("OLLAMA_MODEL", "llama3"),
            format="json",
            temperature=0.1,
        )

    else:
        raise ValueError(f"不支持的模型类型: {model_type}")


# import os
# from dotenv import load_dotenv
# from langchain_community.llms.ollama import Ollama
#
# load_dotenv()
#
# # 初始化 Ollama 模型
# ollama_model_name = os.getenv("OLLAMA_MODEL", "gpt-oss:20b-cloud")
# ollama = Ollama(model=ollama_model_name, temperature=0.1)
#
# # 测试调用
# try:
#     prompt = "Hello Ollama, 你能回应我吗？"
#     response = ollama(prompt)
#     print("Ollama 返回结果:", response)
#     print("✅ Ollama 连接成功！")
# except Exception as e:
#     print("❌ Ollama 连接失败:", str(e))
