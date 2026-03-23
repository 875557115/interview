# 业务层 ，将问题转成向量，检索向量数据库，调用大模型，返回结果
import asyncio
import traceback

from langchain_community.embeddings import HuggingFaceEmbeddings
from template.llm.client import llm
from template.rag.milvus_practice import AgentVectorDB, MilvusInterviewEntity
from template.util.logger import get_logger
from template.rag.history import process_question_lightweight
from langchain_text_splitters import RecursiveCharacterTextSplitter
from template.util.theard_pool import ProductionThreadPool

logger = get_logger("qa_service")

# 初始化Embedding模型
embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",  # 轻量级模型，适配中文/英文
    encode_kwargs={"normalize_embeddings": True}  # 可选：归一化提升检索效果
)

vector_db_instance = AgentVectorDB(
    host="localhost",
    port="19530",
    collection_name="agent_collection"
)

from langchain_core.prompts import ChatPromptTemplate


# 统筹上下文，识别用户意图的prompt


# 问题检索
async def search_by_vector(query):
    try:

        # 识别用户意图，简练用户问题
        intention = process_question_lightweight("user_001", "session_001", query, "")

        # 检索
        result = await asyncio.to_thread(vector_db_instance.query, query, 5, )
        logger.info(f"检索结果：{result}")

        # prompt整理
        message = prompt_template.format_messages(
            question=intention,
            knowledge_base=result
        )

        # 调用ollama模型
        check = llm.astream(message)
        logger.info("开始接收模型流式输出...")
        full_response = ""
        # 必须用 async for 遍历异步迭代器，才能拿到每一段输出
        async for chunk in check:
            chunk_content = chunk.content.strip() if hasattr(chunk, "content") else str(chunk)
            if chunk_content:
                full_response += chunk_content
                yield chunk_content
        logger.info(f"模型完整响应：{full_response}")
    except Exception as e:
        logger.error("向量化失败: {}", e)


# 文本向量化
async def text_vector_fun(text_wash: str):
    try:

        # 构建prompt模板
        message = text_wash_prompt_template.format_messages(
            data=text_wash
        )
        # 大模型预处理
        result_content = ""
        async for chunk in llm.astream(message):
            chunk_content = chunk.content.strip() if hasattr(chunk, "content") else str(chunk)
            if chunk_content:
                result_content += chunk_content
        logger.info(f"大模型处理结果：{result_content}")

        # 解析JSON结果
        import json
        result_data = json.loads(result_content)
        entities_data = result_data.get("entities", [])

        # 转换为MilvusInterviewEntity对象列表
        entities = []
        for entity_data in entities_data:
            entity = MilvusInterviewEntity(
                text=entity_data.get("text", "").strip(),
                difficulty=entity_data.get("difficulty", 2),
                tech_stack=entity_data.get("tech_stack", ""),
                domain=entity_data.get("domain", ""),
                position=entity_data.get("position", "")
            )
            entities.append(entity)
            logger.info(
                f"提取信息：tech_stack={entity.tech_stack}, domain={entity.domain}, difficulty={entity.difficulty}, position={entity.position} \n")

        # 插入向量库
        vector_db_instance.add_texts(entities)
        logger.info(f"成功插入 {len(entities)} 条数据到向量库")
        return f"成功向量化 {len(entities)} 条文本"
    except Exception as e:
        logger.error(f"向量化失败：{str(e)},{traceback.format_exc()}")
        return f"向量化失败：{str(e)}"


# 按标题拆分的文本向量化
async def text_with_title_vector_fun(text_wash: str):
    """
    按照标题+内容拆分文本，并入库向量库
    格式要求：每个知识点以数字编号开头，如 "1. 标题内容"
    """
    try:
        import re
        import json

        # 1. 使用正则表达式按数字编号拆分标题和内容
        if not text_wash:
            logger.warning("输入文本为空")
            return "输入文本为空"

        # 匹配 "数字. 内容" 的格式
        pattern = r'(\d+)\.\s*([^\n]+(?:\n(?!\d+\.\s)[^\n]*)*)'
        matches = re.findall(pattern, text_wash)

        if not matches:
            logger.warning("未找到标题格式匹配项")
            return "未找到标题格式匹配项"

        logger.info(f"成功解析出 {len(matches)} 个知识点")

        # 2. 为每个标题构建prompt，调用大模型进行分析
        entities = []
        for idx, (num, content) in enumerate(matches, 1):
            try:
                # 3. 构建prompt模板，分析单个知识点
                message = title_analysis_prompt_template.format_messages(
                    title_num=num,
                    content=content.strip()
                )

                # 4. 大模型分析结果
                result_content = ""
                async for chunk in llm.astream(message):
                    chunk_content = chunk.content.strip() if hasattr(chunk, "content") else str(chunk)
                    if chunk_content:
                        result_content += chunk_content

                logger.info(f"【{num}】大模型分析结果：{result_content}")

                # 5. 解析JSON结果
                result_data = json.loads(result_content)

                # 6. 创建MilvusInterviewEntity对象
                entity = MilvusInterviewEntity(
                    text=f"【{num}】{content.strip()}",  # 保留标题编号
                    difficulty=result_data.get("difficulty", 2),
                    tech_stack=result_data.get("tech_stack", ""),
                    domain=result_data.get("domain", ""),
                    position=result_data.get("position", "")
                )
                entities.append(entity)
                logger.info(
                    f"✓ 【{num}】提取信息：tech_stack={entity.tech_stack}, domain={entity.domain}, "
                    f"difficulty={entity.difficulty}, position={entity.position}")

            except json.JSONDecodeError as e:
                logger.error(f"【{num}】JSON解析失败：{str(e)}，跳过此项")
                continue
            except Exception as e:
                logger.error(f"【{num}】处理失败：{str(e)}，跳过此项")
                continue

        # 7. 批量插入向量库
        if entities:
            vector_db_instance.add_texts(entities)
            logger.info(f"✅ 成功插入 {len(entities)} 条数据到向量库")
            return f"按标题拆分：成功向量化 {len(entities)} 条文本"
        else:
            logger.warning("没有成功转换的实体")
            return "没有成功转换的实体"

    except Exception as e:
        logger.error(f"按标题拆分向量化失败：{str(e)},{traceback.format_exc()}")
        return f"按标题拆分向量化失败：{str(e)}"


# 数据切割
async def text_segment_fun(text_wash: str):
    text_segment_list = []
    try:
        # 1. 检查输入文本
        if not text_wash:
            return text_segment_list

        # 2. 使用正则表达式按数字编号分割
        import re
        # 匹配数字编号格式，如 "1. "
        segments = re.split(r'(\d+\.\s+)', text_wash)

        # 3. 重组分割结果，保留数字编号
        result = []
        for i in range(1, len(segments), 2):
            if i + 1 < len(segments):
                # 组合数字编号和内容
                combined = segments[i] + segments[i + 1]
                result.append(combined)

        # 4. 对每个分割后的片段进行二次切割（如果需要）
        for segment in result:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_overlap=20,
                separators=["\n", "。", "；", "、"],
                keep_separator=True
            )
            sub_segments = text_splitter.split_text(segment)
            text_segment_list.extend(sub_segments)

        # 5. 查看结果
        for i, split in enumerate(result):
            print(f"片段{i + 1}-----------------------：\n{split}")
        return text_segment_list
    except Exception as e:
        logger.error(f"文本切割失败: {e}")
        return []  # 异常时返回空列表，避免后续处理出错


# 用户向大模型提问的prompt
prompt_template = ChatPromptTemplate.from_messages([
    (
        "system",
        """
        # Role
        你是一名专业的 AI 技术面试答题助手，擅长基于给定知识库解答编程、系统设计类面试问题。

        # Task
        严格参考提供的知识库内容，结合你的专业知识，为用户的面试问题提供清晰、准确、结构化的回答。

        # Rules
        1. 优先使用知识库中的内容回答问题，知识库内容优先于你的默认知识；
        2. 回答必须逻辑清晰，尽量使用分点说明，每个要点不超过2句话；
        3. 涉及技术概念时，先引用知识库中的定义，再补充简单解释；
        4. 如果知识库中无相关内容，需明确说明「知识库未覆盖该知识点」，再基于自身知识回答；
        5. 绝对不要编造不存在的信息，不确定的内容需标注「可能原因/多种情况」；
        6. 仅回答和面试题相关的内容，不扩展无关技术点。

        # Knowledge Base（核心参考依据）
        {knowledge_base}

        # Output Style
        简洁、专业、结构化，符合技术面试答题规范。
        """
    ),
    (
        "human",
        """
        面试问题：
        {question}
        """
    )
])

# 数据切割，存入数据
text_wash_prompt_template = ChatPromptTemplate.from_messages([
    (
        "system",  # 明确角色为system，提升指令优先级
        """
        ### 文本清洗与分割指令
        请严格按照以下规则对目标文本进行处理，核心要求：优化格式以同时适配「文本向量化」和「精准文本切割」，并按照MilvusInterviewEntity结构进行分割。

        #### 一、基础格式清理规则（必须执行）
        1. 空格处理：移除行首/行尾空白字符，段落内连续空格合并为1个，保留词汇间必要单个空格；
        2. 标点标准化：统一转为中文标点，移除无意义冗余标点，保留核心标点语义完整性；
        3. 特殊格式剥离：移除所有文本标记、装饰性符号、非打印字符，统一编码为UTF-8。

        #### 二、核心分割规则（必须执行）
        1. 语义单元化：将文本分割为独立的语义单元，每个单元应该是一个完整的技术问题或知识点；
        2. 完整性保证：确保每个分割后的单元语义完整，不拆分专有名词/技术术语，如果信息缺失，补全技术知识；

        #### 三、内容分析规则（必须执行）
        1. 技术栈分析：识别每个语义单元中涉及的主要编程语言或技术框架；
        2. 技术领域分析：识别每个语义单元所属的技术领域，如并发编程、数据库、网络等；
        3. 难度分析：评估每个语义单元内容的难度等级，1=简单，2=中等，3=困难，4=专家；
        4. 岗位分析：识别每个语义单元内容适合的岗位，如后端开发工程师、前端开发工程师等。

        #### 四、输出强制要求（必须严格遵守）
        1. 仅输出纯JSON格式文本，无任何前置/后置文字（包括但不限于```json、代码块标记、说明文字、示例）；
        2. JSON结构包含以下字段：
           - "entities"：数组，每个元素对应一个语义单元，包含text（原文）、tech_stack（技术栈，归类技术属于哪个技术栈，例如spring属于java，只能属于一个语言）、domain（技术领域）、difficulty（1-4）、position（适合岗位）；
        3. 确保JSON格式合法可解析，无语法错误。
        """
    ),
    ("user", "清洗内容：{data}")  # 用户输入部分，{data}为待清洗文本占位符
])

# 标题内容分析prompt模板
title_analysis_prompt_template = ChatPromptTemplate.from_messages([
    (
        "system",
        """
        ### 标题内容分析指令
        你是一名技术面试内容分析专家，需要对给定的标题和内容进行深度分析。

        #### 分析要求
        1. 技术栈识别：识别主要编程语言或技术框架，格式：技术名称（如Java、Python、Spring、React等）
        2. 技术领域：分析所属领域（如并发编程、数据库、网络、算法、系统设计等）
        3. 难度评估：评估难度等级，1=简单，2=中等，3=困难，4=专家级
        4. 岗位定位：识别适合的岗位类型（如后端开发、前端开发、全栈开发、数据库工程师等）

        #### 输出要求
        1. 仅输出合法的JSON格式，无任何前置/后置文字
        2. JSON格式：
           {
             "difficulty": 2,
             "tech_stack": "Java",
             "domain": "并发编程",
             "position": "后端开发工程师"
           }
        3. 字段说明：
           - difficulty: 数字 1-4
           - tech_stack: 单一技术栈名称（只能选一个）
           - domain: 技术领域
           - position: 适合岗位
        """
    ),
    (
        "human",
        """
        【{title_num}】
        {content}

        请分析上述内容并返回JSON格式的分析结果。
        """
    )
])

if __name__ == '__main__':

    # async def main():  # 定义异步主函数
    #     try:
    #         result = await search_by_vector("Python深拷贝和浅拷贝的区别？")  # await触发执行
    #         logger.info(f"最终结果：{result}")
    #     except Exception as e:
    #         logger.error(f"测试执行失败：{e}")
    #
    # # 步骤2：运行异步主函数
    # asyncio.run(main())

    # async def main():  # 定义异步主函数
    #     res: str = ""
    #     try:
    #         result = await text_vector(
    #             """
    #         1，springboot的start  （时间轮）
    #         14，spring创建bean的参数
    #             singleton	​单例​（默认作用域）：容器中只有一个实例，所有请求共享同一个 Bean。	@Scope("singleton") 或 XML 中 <bean scope="singleton"/>
    #             prototype	​多例​：每次请求（如 getBean() 或依赖注入）都会创建一个新的实例。	@Scope("prototype") 或 XML 中 <bean scope="prototype"/>
    #             request	每个 HTTP 请求创建一个新实例（仅 Web 应用有效）。	@Scope("request") 或 XML 中 <bean scope="request"/>
    #             session	每个 HTTP Session 创建一个新实例（仅 Web 应用有效）。	@Scope("session") 或 XML 中 <bean scope="session"/>
    #             application	每个 ServletContext 生命周期内一个实例（仅 Web 应用有效）。	@Scope("application") 或 XML 中 <bean scope="application"/>
    #             websocket	每个 WebSocket 会话一个实例（仅 Web 应用有效）。	@Scope("websocket") 或 XML 中 <bean scope="websocket"/>
    #         2，spring的扩展点
    #             在 Bean 初始化前后插入逻辑	BeanPostProcessor、@PostConstruct
    #             动态修改 Bean 定义	BeanFactoryPostProcessor
    #             监听容器事件	ApplicationListener
    #             AOP 增强	@Aspect、Pointcut、Advisor
    #             Web 请求拦截	HandlerInterceptor
    #             自定义事务管理	PlatformTransactionManager
    #             Starter 自动化配置	AutoConfigurationImportSelector、BeanFactoryPostProcessor
    #         15，bean的注入方式
    #         10,beanfactory和factorybean的区别
    #             BeanFactory	Spring 容器的顶层接口，定义如何获取和管理 Bean​（核心容器功能）。	​容器本身​（Bean 的工厂）
    #             FactoryBean	提供一种灵活创建复杂 Bean 的方式，封装 Bean 的实例化过程（解决特殊 Bean 的创建问题）。	​Bean 的工厂​（生产 Bean 的工具）
    #         3，kafka的数据丢失保证
    #         4，cas的优略势
    #             优势:
    #                 避免了传统锁（如 synchronized 或 ReentrantLock）的开销（如线程阻塞、上下文切换），在高并发场景下性能更高。
    #                 适合实现乐观锁​（假设冲突少，通过重试解决冲突）
    #                 避免死锁
    #             劣势
    #                 ABA问题
    #                 自旋消耗cpu资源
    #         5，aqs的机制
    #         6，like会不会导致索引失效
    #             %前置会导致索引失效
    #         7，nacos，springcloud的原理
    #         8，mybatis的原理
    #         9，线程池的运行原理
    #         11，epoll的实现机制
    #         12，jvm的运行流程
    #         13，秒杀场景
    #             高并发请求	前端削峰（按钮防点击）、接入层限流、服务异步化、缓存库存
    #             库存超卖	Redis 原子操作扣减 + Lua 脚本保证一致性
    #             系统崩溃	分层削峰、消息队列缓冲、数据库分库分表
    #             恶意请求	IP 限流、用户鉴权、验证码
    #
    #             CDN（静态页面） → Nginx（限流） → Spring Boot（缓存扣减库存） → Kafka（异步下单） → MySQL（最终一致性）
    #         16，jvm常用参数
    #
    #
    #         17，内存泄露，内存溢出
    #             内存溢出-oom
    #             内存泄露-threadlolcatime，或者是长期无法清理的对象
    #         18，saas的理解
    #             可在云端部署，减少私有化部分，方便监控，私有化部署。
    #         19，线程的运行状态
    #             新建，可运行，阻塞，等待，定时等待，销毁
    #         20，动态代理的实现
    #             通过反射，将内容加载到内存中，通过反射，获取对象信息，再通过拦截器的实现代理
    #         21，使用核心线程数后，线程执行完任务后，核心线程会不会被释放，怎么实现的
    #             核心线程数可以释放，也可以不释放，默认是不释放，等任务执行完成后，会阻塞，等待新的任务
    #         22，jdk的异常
    #             Error​	OutOfMemoryError、StackOverflowError 等	严重系统级错误，程序通常无法恢复，应避免捕获（如内存耗尽、JVM 崩溃）。
    #             ​Exception​	​受检异常（Checked Exception）​​
    #             ​运行时异常（Unchecked Exception）​​	需要程序显式处理的异常（受检异常）或可选择性处理的异常（运行时异常）。
    #             ​​(1) 受检异常（Checked Exception）​​
    #             ​特点​：继承自 Exception，​编译器强制要求处理​（try-catch 或 throws 声明）。
    #             ​典型例子​：
    #             IOException（文件/网络操作失败）
    #             SQLException（数据库访问错误）
    #             ClassNotFoundException（类加载失败）
    #             FileNotFoundException（文件不存在）
    #             ​​(2) 运行时异常（Unchecked Exception）​​
    #             ​特点​：继承自 RuntimeException，​编译器不强制处理，通常由编程错误引起。
    #             ​典型例子​：
    #             NullPointerException（空指针访问）
    #             ArrayIndexOutOfBoundsException（数组越界）
    #             IllegalArgumentException（非法参数）
    #             ArithmeticException（算术错误，如除零）
    #             ClassCastException（类型转换失败）
    #         23，在springboot实例化之前进行一些操作
    #             可以通过继承SpringApplicationRunListener来实现一些扩展功能
    #         24，redis的具体hash内的某个key能不能设置ttl
    #             不能
    #         25，索引失效
    #             违反最左前缀原则	联合索引必须从最左列开始匹配	确保查询条件按索引顺序书写
    #             索引列上使用函数或运算	MySQL 无法对计算后的列使用索引	避免在索引列上使用函数或运算
    #             != 或 <> 操作符	可能导致全表扫描	尽量改用 = 或范围查询
    #             NOT IN 或 NOT EXISTS	子查询结果集大时优化器可能放弃索引	改用 JOIN 或 EXISTS
    #             LIKE 以 % 开头	无法利用索引的有序性	改用前缀匹配（如 'A%'）
    #             索引列参与计算或类型转换	MySQL 无法对计算后的列使用索引	避免在索引列上计算或转换
    #             数据分布不均匀	优化器认为全表扫描更快	优化数据分布或强制使用索引（FORCE INDEX）
    #             OR 条件部分列无索引	导致全表扫描	确保 OR 的所有列都有索引
    #             IS NULL 或 IS NOT NULL	NULL 值占比高时优化器可能放弃索引	尽量避免 NULL 或使用默认值替代
    #             ORDER BY 或 GROUP BY 乱序	索引顺序与排序顺序不一致	调整查询顺序或创建复合索引
    #         26，数据库cpu 100%排查
    #             ​进程级排查​	top、htop、pidstat	数据库进程 CPU 过高
    #             ​SQL 级排查​	SHOW PROCESSLIST、EXPLAIN、慢查询日志	未优化的 SQL、全表扫描、索引失效
    #             ​锁竞争排查​	SHOW ENGINE INNODB STATUS、pg_locks	锁等待、死锁
    #             ​配置排查​	SHOW VARIABLES、pg_settings	缓冲池太小、排序缓冲区不足
    #             ​系统级排查​	vmstat、iostat、netstat	CPU 负载高、内存不足、磁盘 I/O 瓶颈""")  # await触发执行
    #         async for chunk in result:
    #             res+=chunk  # 收集每个 yield 出来的 chunk
    #         final_result = "".join(res)  # 拼接最终结果
    #         logger.info(f"最终结果：{final_result}")
    #     except Exception as e:
    #         logger.error(f"测试执行失败：{e}")

    # 步骤2：运行异步主函数
    # asyncio.run(main())

    async def main():
        try:
            result = await  text_segment_fun("""
# 后端高频面试知识点（紧凑版）
1. SpringBoot Starter：Starter是场景化依赖包，通过AutoConfiguration自动装配；时间轮是高效定时任务结构，环形数组+指针，10W+任务场景复杂度O(1)
2. Spring扩展点：BeanPostProcessor/@PostConstruct(Bean初始化)、BeanFactoryPostProcessor(修改Bean定义)、ApplicationListener(监听容器事件)、@Aspect/Pointcut( AOP)、HandlerInterceptor(Web拦截)、PlatformTransactionManager(事务)、AutoConfigurationImportSelector(Starter)、ApplicationContextInitializer(容器初始化)
3. Kafka数据丢失保证：生产者(acks=all+重试+手动确认)、Broker(副本≥2+unclean.leader.election=false)、消费者(手动提交offset+幂等性)
4. CAS优劣：优势(无锁/高并发/防死锁)、劣势(ABA问题/自旋耗CPU/仅单变量)，解决：版本号/自旋次数限制
5. AQS机制：基于CLH队列+volatile state，核心组件(同步状态/等待队列/条件队列)，应用：ReentrantLock/CountDownLatch
6. LIKE索引：%前缀失效、前缀匹配(A%)有效、%A%全表扫描
7. Nacos&SpringCloud：Nacos(服务注册-心跳/配置中心-热更新)；SpringCloud核心：注册中心+配置中心+负载均衡+熔断+网关
8. MyBatis原理：加载配置→SqlSessionFactory→SqlSession→Mapper代理→Executor执行SQL→结果映射，核心组件：SqlSession/Executor/TypeHandler
9. 线程池运行：核心线程(默认不回收，allowCoreThreadTimeOut=true可回收)→队列→非核心线程→拒绝策略，参数：corePoolSize/maximumPoolSize/keepAliveTime/workQueue/handler
10. BeanFactory&FactoryBean：BeanFactory(容器顶层接口，管理Bean)、FactoryBean(创建复杂Bean，重写getObject)
11. Epoll：Linux I/O多路复用，红黑树+就绪链表，LT/ET触发，无FD限制，高并发优于select/poll
12. JVM运行流程：类加载(加载-验证-准备-解析-初始化)→运行时数据区(方法区/堆/虚拟机栈/本地方法栈/程序计数器)→执行引擎(解释/JIT)+GC
13. 秒杀场景：前端削峰+Nginx限流+Redis原子扣库存+Kafka异步+MySQL最终一致；防超卖(Lua脚本/行锁)；防恶意请求(IP限流/验证码)
14. Spring Bean作用域：singleton(单例/默认)、prototype(多例)、request(请求)、session(会话)、application(应用)、websocket(WebSocket会话)
15. Bean注入方式：构造器注入(推荐)、Setter注入、字段注入(@Autowired)、静态工厂注入、实例工厂注入
16. JVM常用参数：-Xms(初始堆)、-Xmx(最大堆)、-Xmn(新生代)、-XX:SurvivorRatio(幸存区比例)、-XX:MetaspaceSize(元空间)、-XX:+PrintGCDetails(打印GC)
17. 内存泄露vs溢出：泄露(对象长期无法回收，如ThreadLocal未清理/静态集合引用)、溢出(OOM，内存不足，如堆/栈/元空间满)
18. SaaS理解：云端部署，多租户共享，按需付费，低运维成本；支持私有化部署，易监控，减少私有化开发量
19. 线程运行状态：新建(NEW)、可运行(RUNNABLE)、阻塞(BLOCKED)、等待(WAITING)、定时等待(TIMED_WAITING)、销毁(TERMINATED)
20. 动态代理实现：JDK动态代理(基于接口+反射，Proxy+InvocationHandler)、CGLIB(基于继承+ASM，MethodInterceptor)，核心：反射加载类+拦截器增强
21. 核心线程释放：默认不释放(阻塞等新任务)，设置allowCoreThreadTimeOut(true)则空闲超时(keepAliveTime)后释放
22. JDK异常：Error(严重，OOM/StackOverflow，不捕获)、Exception(受检：IOException/SQLException，编译器强制处理；运行时：NPE/数组越界，编程错误)
23. SpringBoot实例化前操作：继承SpringApplicationRunListener，重写starting()等方法；或ApplicationContextInitializer
24. Redis Hash的Key设置TTL：不能，仅Hash整体可设TTL，解决：拆分Hash/单独存储Key+TTL
25. 索引失效场景：最左前缀违反、索引列函数/运算、!=/<>=、NOT IN/NOT EXISTS、%前缀LIKE、类型转换、数据分布不均、OR部分无索引、IS NULL占比高、排序乱序
26. 数据库CPU 100%排查：进程级(top/htop)、SQL级(SHOW PROCESSLIST/EXPLAIN/慢日志)、锁竞争(SHOW ENGINE INNODB STATUS)、配置(SHOW VARIABLES)、系统级(vmstat/iostat)""")
        except Exception as e:
            logger.error(f"切割失败：{str(e)}")


    asyncio.run(main())
