import os

from dotenv import load_dotenv
from fastapi import FastAPI

from template.util.logger import get_logger

# 新增：加载.env文件（必须放在最前面）
load_dotenv()

app = FastAPI(title="程序员面试题智能体", version="1.0.0")
logger = get_logger("interview_api")

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8001))  # 转成整数，默认8000


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("template.ui.api:app", host="0.0.0.0", port=8001, reload=True)
