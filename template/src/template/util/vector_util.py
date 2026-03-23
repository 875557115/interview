# 1. 导出旧集合数据
from pymilvus import (
    FieldSchema, DataType, Collection, CollectionSchema,
    connections, exceptions, utility
)
import time

# ========== 核心修复：添加 Milvus 认证配置 ==========
# 根据你的 Milvus 认证方式选择（二选一）：
# 方式1：使用 Token 认证（Milvus 2.2+ 推荐）
MILVUS_TOKEN = "root:Milvus"  # 默认是 root:Milvus，若修改过请替换为实际值
# 方式2：使用用户名密码（旧版本兼容）
MILVUS_USER = "root"
MILVUS_PASSWORD = "Milvus"

# 连接Milvus（添加认证信息）
try:
    connections.connect(
        alias="default",
        host="localhost",
        port="19530",
        # 方式1：Token 认证（优先，Milvus 会优先识别 Token）
        token=MILVUS_TOKEN,
        # 方式2：用户名密码（备用，可保留但建议只选一种）
        user=MILVUS_USER,
        password=MILVUS_PASSWORD
    )
    print("✅ 成功连接 Milvus 服务器（已携带认证凭证）")
except exceptions.MilvusException as e:
    raise Exception(f"❌ Milvus 连接失败：{e}")

# ========== 核心修复1：前置校验集合是否存在 ==========
COLLECTION_NAME = "agent_collection"
data_old = []  # 初始化旧数据列表
if utility.has_collection(COLLECTION_NAME):
    # 关键修复：先处理旧集合的索引+加载
    collection_old = Collection(name=COLLECTION_NAME)

    # 步骤1：检查旧集合是否有索引，没有就临时创建（查询必须）
    try:
        # 尝试获取向量索引
        _ = collection_old.indexes
    except exceptions.MilvusException:
        # 旧集合无索引，临时创建
        collection_old.create_index(
            field_name="vector",
            index_params={"index_type": "HNSW", "metric_type": "L2", "params": {"M": 16, "efConstruction": 64}}
        )
        print("⚠️ 旧集合无索引，已临时创建")
        # 等待索引创建完成（关键：给Milvus 2秒时间生效）
        time.sleep(2)

    # 步骤2：加载旧集合到内存（查询必须）
    collection_old.load()
    print("✅ 旧集合已加载到内存")

    # 步骤3：查询数据
    data_old = collection_old.query(expr="pk >= 0", output_fields=["*"])
    print(f"导出旧数据 {len(data_old)} 条")

    # 2. 删除旧集合（先卸载再删除，避免资源占用）
    collection_old.release()  # 卸载内存中的集合
    collection_old.drop()
    # 等待集合删除生效（延长至2秒，确保元数据同步）
    time.sleep(2)
    print("✅ 已删除旧集合")
else:
    print(f"ℹ️ 未检测到旧集合 {COLLECTION_NAME}，跳过数据导出和删除步骤")

# 3. 新建集合（包含新字段）
from pymilvus import FieldSchema, DataType

# 面试题库向量数据库（Milvus）完整字段定义
from pymilvus import FieldSchema, DataType

# 保留原有字段 + 仅新增缺失的核心字段
from pymilvus import FieldSchema, DataType

fields = [
    # 基础标识字段（主键/时间/状态）
    FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True, description="面试题唯一自增主键ID"),
    FieldSchema(name="create_time", dtype=DataType.INT64, nullable=False, description="创建时间戳（毫秒级）"),
    FieldSchema(name="update_time", dtype=DataType.INT64, nullable=False, description="最后更新时间戳（毫秒级）"),
    FieldSchema(name="status", dtype=DataType.INT64, nullable=False, default=1, description="生效状态：1=草稿 2=上线 3=下线"),
    #
    # # 结构化业务字段（筛选/分类）
    FieldSchema(name="difficulty", dtype=DataType.INT64, nullable=True, description="难度：1=简单 2=中等 3=困难 4=专家"),
    FieldSchema(name="tech_stack", dtype=DataType.VARCHAR, max_length=128, nullable=True, description="适配技术栈（如Java/Python）"),
    FieldSchema(name="domain", dtype=DataType.VARCHAR, max_length=512, nullable=True, description="技术领域（多值逗号分隔）"),
    FieldSchema(name="position", dtype=DataType.VARCHAR, max_length=512, nullable=True, description="适配岗位（多值逗号分隔）"),
    FieldSchema(name="interview_stage", dtype=DataType.VARCHAR, max_length=256, nullable=True, description="面试阶段（多值逗号分隔）"),
    FieldSchema(name="tag", dtype=DataType.VARCHAR, max_length=512, nullable=True, description="自定义标签（多值逗号分隔）"),

    # 向量化字段（语义检索）
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=384, description="题干语义向量（384维）"),
    FieldSchema(name="embedding_model", dtype=DataType.VARCHAR, max_length=128, nullable=True, description="向量生成模型名称"),

    # 内容字段（文本内容）
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535, description="题干原文内容"),
    FieldSchema(name="reference", dtype=DataType.VARCHAR, max_length=256, nullable=True, description="参考资料链接/备注")
]
schema_new = CollectionSchema(fields, description="面试题")

# 双重保险：确保集合不存在后再创建
if utility.has_collection(COLLECTION_NAME):
    Collection(name=COLLECTION_NAME).drop()
    time.sleep(1)

collection_new = Collection(name=COLLECTION_NAME, schema=schema_new)
print("✅ 新建集合成功")

# 4. 导入旧数据 + 强制刷盘 + 创建索引 + 校验
if len(data_old) > 0:
    try:
        # 核心修复2：清洗旧数据字段（匹配新Schema）
        valid_fields = [f.name for f in fields]
        cleaned_data = []
        for item in data_old:
            # 只保留新集合中存在的字段
            cleaned_item = {k: v for k, v in item.items() if k in valid_fields}
            cleaned_data.append(cleaned_item)

        # 插入数据
        insert_res = collection_new.insert(cleaned_data)
        # 强制刷盘（关键：确保数据写入磁盘，否则索引创建可能失败）
        collection_new.flush()
        print(f"✅ 导入 {len(insert_res.primary_keys)} 条旧数据并刷盘")
    except exceptions.MilvusException as e:
        print(f"⚠️ 旧数据导入失败：{e}，将继续创建索引")

# ========== 核心修复：创建索引 + 校验 + 重试 ==========
index_created = False
retry_times = 3  # 最多重试3次
for i in range(retry_times):
    try:
        # 创建索引（明确索引名称，便于校验）
        collection_new.create_index(
            field_name="vector",
            index_params={"index_type": "HNSW", "metric_type": "L2", "params": {"M": 16, "efConstruction": 64}},
            index_name="vector_index"  # 给索引命名，方便校验
        )
        # 校验索引是否真的创建成功
        indexes = collection_new.indexes
        if indexes:
            index_created = True
            print(f"✅ 向量索引创建成功！索引信息：{indexes}")
            break
    except exceptions.MilvusException as e:
        print(f"⚠️ 第{i + 1}次创建索引失败：{e}，1秒后重试...")
        time.sleep(1)

if not index_created:
    raise Exception("❌ 索引创建失败，无法继续！")

# 加载集合（此时索引已确认存在，不会报700错误）
collection_new.load()
print("✅ 新集合加载成功，索引生效！")
print("重建集合+导入数据成功，新字段已添加！")

# 可选：关闭连接（优雅退出）
connections.disconnect("default")
