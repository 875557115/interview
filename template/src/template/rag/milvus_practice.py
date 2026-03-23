import time
from typing import List, Dict, Optional
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_milvus import Milvus
from template.util.logger import get_logger



log = get_logger(__name__)


@dataclass
class MilvusInterviewEntity:
    """对应 Milvus agent_collection 的实体类"""
    # 核心业务字段（必填）
    text: str  # 题干原文
    embedding_model: str = "all-MiniLM-L6-v2"  # 固定模型名

    # 可选字段（带默认值）
    vector: Optional[List[float]] = None  # 384维向量（自动生成）
    create_time: Optional[int] = None  # 创建时间戳（毫秒）
    update_time: Optional[int] = None  # 更新时间戳（毫秒）
    status: int = 1  # 状态：1=上线，0=下线
    difficulty: int = 2  # 难度：1=简单 2=中等 3=困难 4=专家
    tech_stack: str = ""  # 技术栈
    domain: str = ""  # 技术领域
    position: str = ""  # 岗位
    interview_stage: str = ""  # 面试阶段
    tag: str = ""  # 标签（逗号分隔）
    reference: str = ""  # 参考链接

    def __post_init__(self):
        """初始化后自动补全时间戳"""
        now_ms = int(time.time() * 1000)
        if self.create_time is None:
            self.create_time = now_ms
        if self.update_time is None:
            self.update_time = now_ms

    def to_metadata_dict(self) -> Dict:
        """转换为 LangChain Document 的 metadata 字典格式"""
        return {
            "create_time": self.create_time,
            "update_time": self.update_time,
            "status": self.status,
            "difficulty": self.difficulty,
            "tech_stack": self.tech_stack,
            "domain": self.domain,
            "position": self.position,
            "interview_stage": self.interview_stage,
            "tag": self.tag,
            "embedding_model": self.embedding_model,
            "reference": self.reference
        }

    def generate_vector(self, embedding_model):
        """自动生成384维向量（HuggingFaceEmbeddings）"""
        if self.vector is None:
            self.vector = embedding_model.embed_query(self.text)
        return self.vector


class AgentVectorDB:
    """智能体专用向量数据库封装（适配HuggingFaceEmbeddings）"""

    def __init__(
        self,
        host: str = "localhost",
        port: str = "19530",
        user: str = "root",
        password: str = "Milvus",
        collection_name: str = "agent_collection",
        model_name: str = "all-MiniLM-L6-v2"
    ):
        """
        初始化向量数据库
        :param host: Milvus 主机地址
        :param port: Milvus 端口
        :param user: Milvus 用户名
        :param password: Milvus 密码
        :param collection_name: 集合名称
        :param model_name: HuggingFace嵌入模型名（默认all-MiniLM-L6-v2）
        """
        # 1. 初始化HuggingFaceEmbeddings（核心！）
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},  # 指定CPU运行（无GPU时）
            encode_kwargs={"normalize_embeddings": True}  # 归一化提升检索精度
        )
        print(f"✅ HuggingFace模型初始化成功（{model_name}）")

        # 2. 初始化Milvus连接
        self.vector_db = Milvus(
            embedding_function=self.embedding_model,
            connection_args={
                "host": host,
                "port": port,
                "user": user,
                "password": password
            },
            collection_name=collection_name,
            auto_id=True,  # 自动生成主键
            text_field="text",  # 文本字段名
            vector_field="vector"  # 384维向量字段名
        )
        print(f"✅ Milvus 连接成功（集合：{collection_name}）")

    def add_texts(self, entities: List[MilvusInterviewEntity]) -> None:
        """插入实体到Milvus（自动生成384维向量）"""
        if not entities:
            print("⚠️ 没有需要插入的实体")
            return

        docs = []
        for entity in entities:
            # 自动生成384维向量
            entity.generate_vector(self.embedding_model)
            # 构建Document
            doc = Document(
                page_content=entity.text,
                metadata=entity.to_metadata_dict()
            )
            docs.append(doc)

        # 插入到Milvus
        self.vector_db.add_documents(docs)
        log.info(f"✅ 成功插入 {len(docs)} 条数据（384维向量）")

    def query(
        self,
        text: str,
        k: int = 5,
        difficulty: Optional[int] = None,
        tech_stack: Optional[str] = None,
        domain: Optional[str] = None,
        status: Optional[int] = 1
    ) -> List[Document]:
        """多条件语义检索（生成384维查询向量）"""
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
        log.info(f"检索条件: {expr}")
        # 执行检索
        results = self.vector_db.similarity_search(
            query=text,
            k=k,
            param={  # 检索参数（影响精度/速度）
                "metric_type": "L2",  # 相似度计算方式
                "params": {
                    "ef": 64,  # 检索时的ef参数（越大精度越高，速度越慢）
                    "nprobe": 10  # IVF索引的检索参数
                }
            },
            expr=expr,  # 元数据过滤
        )

        log.info(f"检索到 {len(results)} 条匹配结果")
        return results

    def delete_by_filter(self, filter_expr: str) -> None:
        """按条件删除数据"""
        self.vector_db.delete(expr=filter_expr)
        print(f"✅ 已删除符合条件的数据（{filter_expr}）")

    def delete_all(self) -> None:
        """清空集合"""
        self.vector_db.delete(expr="status >= 0")
        print("✅ 已清空所有数据")

    # def close(self) -> None:
    #     """关闭连接"""
    #     print("🔌 连接已关闭")


# ------------------------------
# 使用示例
# ------------------------------
if __name__ == "__main__":
    pass

    # # 1. 初始化数据库
    # db = AgentVectorDB(
    #     host="localhost",
    #     port="19530",
    #     collection_name="agent_collection",
    #     model_name="all-MiniLM-L6-v2"
    # )
    #
    # # 2. 构建测试实体
    # test_entities = [
    #     MilvusInterviewEntity(
    #         text="Java中volatile关键字的作用及实现原理？",
    #         difficulty=2,
    #         tech_stack="Java",
    #         domain="并发编程",
    #         position="后端开发工程师"
    #     ),
    #     MilvusInterviewEntity(
    #         text="Python中的GIL锁对多线程的影响？如何解决？",
    #         difficulty=3,
    #         tech_stack="Python",
    #         domain="并发编程",
    #         position="Python开发工程师"
    #     )
    # ]
    #
    # # 3. 插入数据
    # db.add_entities(test_entities)
    #
    # # 4. 检索测试
    # results = db.query(
    #     text="volatiles是什么",
    #     k=1,
    #     difficulty=2,
    #     tech_stack="Java"
    # )
    #
    # # 5. 打印结果
    # for doc in results:
    #     print(f"\n📝 匹配文本：{doc.page_content}")
    #     print(f"📌 元数据：{doc.metadata}")

    # 6. 关闭连接
    # db.close()
