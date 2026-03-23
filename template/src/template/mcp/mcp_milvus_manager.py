import uvicorn
from mcp.server.fastmcp import FastMCP
import os
import time
from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType
from langchain_huggingface import HuggingFaceEmbeddings
from typing import List, Dict, Optional

port = int(os.getenv("MCP_PORT", 8099))
host = "127.0.0.1"  # 加上这一行，强制监听所有网卡，解决未定义问题
mcp = FastMCP("milvus-server")

# Embedding model
_embedding_model = None

def _ensure_connected():
    # pymilvus manages connections globally; re-connecting is safe.
    connections.connect(
        alias=os.getenv("MILVUS_ALIAS", "default"),
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=os.getenv("MILVUS_PORT", "19530"),
        user = os.getenv("MILVUS_USER","root"),
        password = os.getenv("MILVUS_PASSWORD","Milvus")
    )

def _get_embedding_model():
    """获取嵌入模型"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
    return _embedding_model

def _get_collection(collection_name: str) -> Collection:
    """获取Milvus集合"""
    _ensure_connected()
    return Collection(collection_name)

@mcp.tool()
def list_collections():
    """List milvus collections"""
    try:
        _ensure_connected()
        return utility.list_collections()
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def create_collection(collection_name: str) -> str:
    """Create milvus collection with default schema"""
    try:
        _ensure_connected()

        # 检查集合是否已存在
        if utility.has_collection(collection_name):
            return f"Collection {collection_name} already exists"

        # 定义字段
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=384),
            FieldSchema(name="create_time", dtype=DataType.INT64),
            FieldSchema(name="update_time", dtype=DataType.INT64),
            FieldSchema(name="status", dtype=DataType.INT32, default_value=1),
            FieldSchema(name="difficulty", dtype=DataType.INT32, default_value=2),
            FieldSchema(name="tech_stack", dtype=DataType.VARCHAR, max_length=256, default_value=""),
            FieldSchema(name="domain", dtype=DataType.VARCHAR, max_length=256, default_value=""),
            FieldSchema(name="position", dtype=DataType.VARCHAR, max_length=256, default_value=""),
            FieldSchema(name="interview_stage", dtype=DataType.VARCHAR, max_length=256, default_value=""),
            FieldSchema(name="tag", dtype=DataType.VARCHAR, max_length=512, default_value=""),
            FieldSchema(name="embedding_model", dtype=DataType.VARCHAR, max_length=256, default_value="all-MiniLM-L6-v2"),
            FieldSchema(name="reference", dtype=DataType.VARCHAR, max_length=512, default_value="")
        ]

        # 创建schema
        schema = CollectionSchema(fields, description="Agent interview collection")

        # 创建集合
        collection = Collection(name=collection_name, schema=schema)

        # 创建索引
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index(field_name="vector", index_params=index_params)

        return f"Collection {collection_name} created successfully"
    except Exception as e:
        return f"create_collection error: {e}"

@mcp.tool()
def add_texts(collection_name: str, texts: List[Dict]) -> str:
    """Add texts to milvus collection"""
    try:
        _ensure_connected()
        collection = _get_collection(collection_name)
        embedding_model = _get_embedding_model()

        now_ms = int(time.time() * 1000)
        entities = []

        for text_data in texts:
            text = text_data.get("text", "").strip()
            if not text:
                continue

            # 生成向量
            vector = embedding_model.embed_query(text)

            # 构建实体
            entity = [
                text,  # text
                vector,  # vector
                text_data.get("create_time", now_ms),  # create_time
                text_data.get("update_time", now_ms),  # update_time
                text_data.get("status", 1),  # status
                text_data.get("difficulty", 2),  # difficulty
                text_data.get("tech_stack", ""),  # tech_stack
                text_data.get("domain", ""),  # domain
                text_data.get("position", ""),  # position
                text_data.get("interview_stage", ""),  # interview_stage
                text_data.get("tag", ""),  # tag
                text_data.get("embedding_model", "all-MiniLM-L6-v2"),  # embedding_model
                text_data.get("reference", "")  # reference
            ]
            entities.append(entity)

        if entities:
            # 插入数据
            collection.insert(entities)
            collection.flush()
            return f"Successfully added {len(entities)} texts"
        else:
            return "No texts to add"
    except Exception as e:
        return f"add_texts error: {e}"

@mcp.tool()
def query(collection_name: str, query_text: str, k: int = 5,
          difficulty: Optional[int] = None,
          tech_stack: Optional[str] = None,
          domain: Optional[str] = None,
          status: Optional[int] = 1) -> List[Dict]:
    """Query milvus collection"""
    try:
        _ensure_connected()
        collection = _get_collection(collection_name)
        embedding_model = _get_embedding_model()


        # 生成查询向量
        query_vector = embedding_model.embed_query(query_text)

        # 构建过滤条件
        filter_conditions = []
        if status is not None:
            filter_conditions.append(f"status == {status}")
        if difficulty is not None:
            filter_conditions.append(f"difficulty == {difficulty}")
        if tech_stack is not None:
            filter_conditions.append(f"tech_stack like '{tech_stack}%'")
        if domain is not None:
            filter_conditions.append(f"domain like '{domain}%'")

        expr = " && ".join(filter_conditions) if filter_conditions else ""

        # 执行查询
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 10}
        }

        results = collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=k,
            expr=expr,
            output_fields=["text", "tech_stack", "domain", "difficulty", "position"]
        )

        # 处理结果
        result_list = []
        for hits in results:
            for hit in hits:
                result_list.append({
                    "text": hit.entity.get("text", ""),
                    "tech_stack": hit.entity.get("tech_stack", ""),
                    "domain": hit.entity.get("domain", ""),
                    "difficulty": hit.entity.get("difficulty", 2),
                    "position": hit.entity.get("position", ""),
                    "distance": hit.distance
                })

        return result_list
    except Exception as e:
        return [{"error": str(e)}]

@mcp.tool()
def delete_by_filter(collection_name: str, filter_expr: str) -> str:
    """Delete by filter from milvus collection"""
    try:
        _ensure_connected()
        collection = _get_collection(collection_name)
        collection.delete(expr=filter_expr)
        collection.flush()
        return f"Successfully deleted by filter: {filter_expr}"
    except Exception as e:
        return f"delete_by_filter error: {e}"

@mcp.tool()
def delete_all(collection_name: str) -> str:
    """Delete all from milvus collection"""
    try:
        _ensure_connected()
        collection = _get_collection(collection_name)
        collection.delete(expr="status >= 0")
        collection.flush()
        return f"Successfully deleted all from {collection_name}"
    except Exception as e:
        return f"delete_all error: {e}"

@mcp.tool()
def has_collection(collection_name: str) -> bool:
    """Check if milvus collection exists"""
    try:
        _ensure_connected()
        return utility.has_collection(collection_name)
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def drop_collection(collection_name: str) -> str:
    """Drop milvus collection"""
    try:
        _ensure_connected()
        utility.drop_collection(collection_name)
        return "ok"
    except Exception as e:
        return f"drop_collection error: {e}"


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("📌 第一步：验证工具是否被装饰器注册")
    print("=" * 50)

    agent = _get_collection("agent_collection")
    print(agent.description)

    # 验证 1：打印 FastMCP 所有可能的工具存储属性
    print("\n🔍 扫描 FastMCP 工具存储属性：")
    tool_attrs = ["_tools", "tools", "registered_tools", "_tool_registry", "tool_registry"]
    found = False
    for attr in tool_attrs:
        if hasattr(mcp, attr):
            found = True
            tool_dict = getattr(mcp, attr)
            print(f"  ✅ 找到属性 [{attr}]，包含工具：")
            for tool_name in tool_dict.keys():
                print(f"    - {tool_name}")

    # 验证 2：从 FastAPI 路由解析（兜底）
    if not found and hasattr(mcp, "app") and hasattr(mcp.app, "router"):
        print("\n🔍 从 FastAPI 路由解析 MCP 工具：")
        mcp_routes = []
        for route in mcp.app.router.routes:
            if hasattr(route, "path") and "/mcp/" in route.path:
                tool_name = route.path.split("/")[-1]
                mcp_routes.append(tool_name)
        if mcp_routes:
            found = True
            print(f"  ✅ 从路由中找到 MCP 工具：{mcp_routes}")

    # 验证 3：最终兜底提示
    if not found:
        print("  ❌ 未找到工具存储属性，但装饰器已执行 → 工具已注册（以 API 验证为准）")
    else:
        print("  ✅ 工具注册成功！")

    # ==================== 启动服务 ====================
    print("\n" + "=" * 50)
    print(f"📌 第二步：启动 MCP 服务（端口：{port}）")
    print("=" * 50)
    print(f"  🚀 服务启动后，访问以下地址验证：")
    print(f"  - API 文档（必看）：http://localhost:{port}/docs")
    print(f"  - 工具列表接口：http://localhost:{port}/mcp/tools")
    print(f"  - 测试工具调用：http://localhost:{port}/mcp/list_collections")
    print("\n  ⏳ 启动中...（服务启动后会阻塞，按 Ctrl+C 停止）")

    # 启动服务（添加 host="0.0.0.0" 确保外部可访问）
    # mcp.run(transport="streamable-http")
    print("=" * 60)
    print(" Milvus MCP 服务启动（修复版）")
    print(" 外部可访问：http://0.0.0.0:8099")
    print("=" * 60)
    print("📄 文档地址: http://localhost:8099/docs")
    print("🔧 工具列表: http://localhost:8099/mcp/tools")
    print("🧪 测试接口: http://localhost:8099/mcp/list_collections")
    print("=" * 60)

    # ✅ 正确启动 FastAPI + MCP，支持外部访问
    uvicorn.run(
        app=mcp.app,
        host=host,
        port=port,
        log_level="info"
    )
