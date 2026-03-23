from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse

from ..__main__ import app
from ..service.qa_service import search_by_vector, text_vector_fun, text_segment_fun
from ..util.logger import get_logger

# # 新增：加载.env文件（必须放在最前面）
# load_dotenv()
#
# app = FastAPI(title="程序员面试题智能体", version="1.0.0")
logger = get_logger("interview_api")

# 允许前端跨域调用（本地调试场景优先）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API_HOST = os.getenv("API_HOST", "0.0.0.0")
# API_PORT = int(os.getenv("API_PORT", 8001))  # 转成整数，默认8000


# 请求体模型
class QueryRequest(BaseModel):
    query: str
    tech_stack: Optional[str] = None
    top_k: int = 3


class InterviewStartRequest(BaseModel):
    user_id: str
    tech_stack: str
    position: str


class InterviewAnswerRequest(BaseModel):
    user_id: str
    answer: str


@app.get("/", response_class=HTMLResponse)
async def home_page():
    html_path = Path(__file__).with_name("index.html")
    try:
        return html_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"读取前端页面失败：{str(e)}")
        raise HTTPException(status_code=500, detail="前端页面加载失败")


# API接口：检索面试题
@app.post("/ui/retrieve-questions")
async def retrieve_questions_endpoint(request: QueryRequest):
    try:
        return StreamingResponse(search_by_vector(request.query),  # 传入异步生成器
                                 media_type="text/plain"  # 或 application/json，根据返回格式调整)
                                 )
    except Exception as e:
        logger.error(f"检索面试题失败：{str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ui/text-vector")
async def text_vector_endpoint(request: QueryRequest):
    try:
        # 1. 先 await 执行异步函数，拿到最终结果
        await text_vector_fun(request.query)

        # 2. 把结果包装成异步生成器，供 StreamingResponse 消费
        async def vector_generator():
            # 向量化完成后返回提示信息（编码为 bytes）
            yield "向量生成完成".encode("utf-8")

        # 3. 传给 StreamingResponse（无需 async_mode）
        return StreamingResponse(
            vector_generator(),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"存储向量失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"向量生成失败：{str(e)}")

@app.post("/ui/text-wash")
async def text_segment_endpoint(text: str):  # 注意：建议改用Pydantic模型接收参数
    try:

        await text_segment_fun(text)

        async def vector_generator():
            # 向量化完成后返回提示信息（编码为 bytes）
            yield "向量生成完成".encode("utf-8")

        # 3. 传给 StreamingResponse（无需 async_mode）
        return StreamingResponse(
            vector_generator(),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"清洗数据失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"文本清洗失败：{str(e)}")



# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("template.ui.api:app", host="0.0.0.0", port=8001, reload=True)
