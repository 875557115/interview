import os
from langchain_community.vectorstores import Milvus
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from template.rag.loader import load_and_split_documents
from template.llm.client import llm
from template.llm.prompt_template import question_prompt
from template.util.logger import get_logger

logger = get_logger("vector_retriever")

# 初始化嵌入模型（本地开源模型，无需API密钥）
embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")


class InterviewQuestionRetriever:
    def __init__(
        self,
        question_dir: str = "./interview_questions",
        milvus_host: str = "localhost",  # Milvus 主机地址
        milvus_port: str = "19530",  # Milvus 端口
        collection_name: str = "interview_questions"  # Milvus 集合名
    ):
        """
        初始化面试题检索器（基于Milvus向量库）
        :param question_dir: 题库目录
        :param milvus_host: Milvus 服务地址
        :param milvus_port: Milvus 服务端口
        :param collection_name: Milvus 集合名称
        """
        self.question_dir = question_dir
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.collection_name = collection_name
        self.vector_db = self._init_vector_db()
        # 构建LangChain LCEL链式调用：检索→Prompt→LLM
        self.rag_chain = self._build_rag_chain()

    def _init_vector_db(self) -> Milvus:
        """初始化Milvus向量数据库"""
        # 加载并分块文档
        documents = load_and_split_documents(self.question_dir)

        # Milvus 连接配置
        connection_args = {
            "host": self.milvus_host,
            "port": self.milvus_port
        }

        try:
            # 初始化Milvus向量库
            # 如果集合已存在，直接连接；不存在则创建并插入文档
            vector_db = Milvus(
                embedding_function=embeddings,
                connection_args=connection_args,
                collection_name=self.collection_name
            )

            # 如果有新文档，添加到Milvus
            if documents:
                # 插入文档（自动向量化）
                vector_db.add_documents(documents)
                logger.info(f"成功向Milvus集合[{self.collection_name}]插入{len(documents)}条文档")
            else:
                logger.warning("题库目录暂无文档，请先添加面试题")

            logger.info(f"Milvus向量库初始化完成，连接地址：{self.milvus_host}:{self.milvus_port}")
            return vector_db
        except Exception as e:
            logger.error(f"Milvus连接/初始化失败：{str(e)}")
            raise e

    def _build_rag_chain(self):
        """
        构建RAG链式调用（LangChain LCEL核心）
        流程：检索相似题目 → 生成定制化题目
        """
        # 检索器（取Top3相似文档）
        retriever = self.vector_db.as_retriever(k=3)

        # LCEL链式调用：
        # 1. 并行执行：检索相似题目 + 传递参数
        # 2. 拼接Prompt
        # 3. 调用LLM
        # 4. 提取文本输出
        rag_chain = (
            RunnableParallel({
                "context": retriever,  # 从Milvus检索相似题目
                "tech_stack": RunnablePassthrough(),  # 技术栈参数
                "position": RunnablePassthrough(),  # 岗位参数
                "difficulty": RunnablePassthrough(),  # 难度参数
                "question_type": RunnablePassthrough()  # 题目类型参数
            })
            | question_prompt  # 拼接Prompt
            | llm  # 调用LLM
            | (lambda x: x.content)  # 提取回答文本
        )

        logger.info("基于Milvus的RAG链式调用初始化完成")
        return rag_chain

    async def generate_question(self, **kwargs) -> str:
        """
        生成定制化面试题（异步调用）
        :param kwargs: tech_stack, position, difficulty, question_type
        :return: 生成的面试题
        """
        try:
            # 检查Milvus集合是否为空（通过检索结果判断）
            test_retriever = self.vector_db.as_retriever(k=1)
            test_context = await test_retriever.ainvoke(kwargs.get("tech_stack", ""))
            if not test_context:
                logger.warning("Milvus向量库为空，直接生成题目（无检索）")
                prompt = question_prompt.format_messages(
                    tech_stack=kwargs.get("tech_stack"),
                    position=kwargs.get("position"),
                    difficulty=kwargs.get("difficulty"),
                    question_type=kwargs.get("question_type")
                )
                response = await llm.ainvoke(prompt)
                return response.content

            # 调用RAG链生成题目（基于Milvus检索）
            question = await self.rag_chain.ainvoke(kwargs)
            logger.info(f"生成面试题成功：{question[:50]}...")
            return question
        except Exception as e:
            logger.error(f"生成面试题失败：{str(e)}")
            raise e


# 全局检索器实例（适配你的Milvus环境）
question_retriever = InterviewQuestionRetriever(
    milvus_host="localhost",  # 替换为你的Milvus地址（如部署在其他机器需改IP）
    milvus_port="19530",  # 你的Milvus端口（默认19530）
    collection_name="interview_questions"
)

if __name__ == "__main__":
    print(question_retriever)

