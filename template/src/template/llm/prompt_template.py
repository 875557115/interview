from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class PromptTemplate:

    role: str
    task: str
    context: str
    rules: List[str]
    tools: List[str]
    examples: List[Dict[str, str]]
    output_format: Dict[str, Any]
    sections: Optional[Dict[str, str]] = None

    # ======================
    # 各模块 Prompt
    # ======================

    def system_prompt(self) -> str:
        return f"""
# 角色
{self.role}

# 任务
{self.task}

# 背景
{self.context}
"""

    def rules_prompt(self) -> str:
        if not self.rules:
            return ""

        rules_text = "\n".join(
            [f"{i+1}. {rule}" for i, rule in enumerate(self.rules)]
        )

        return f"""
# 规则
{rules_text}
"""

    def tools_prompt(self) -> str:
        if not self.tools:
            return ""

        tools_text = "\n".join([f"- {tool}" for tool in self.tools])

        return f"""
# 可用工具
{tools_text}
"""

    def examples_prompt(self) -> str:
        if not self.examples:
            return ""

        example_text = ""
        for ex in self.examples:
            example_text += f"""
示例
用户: {ex['input']}
助手: {ex['output']}
"""

        return f"""
# 示例
{example_text}
"""

    def user_prompt(self, user_input: str) -> str:
        return f"""
# 用户问题
{user_input}
"""

    def output_prompt(self) -> str:
        return f"""
# 输出格式
请返回 JSON：

{self.output_format}

请在回答前进行逐步思考。
"""

    def custom_sections(self) -> str:
        """生成自定义部分"""
        if not self.sections:
            return ""

        custom_text = ""
        for section_name, section_content in self.sections.items():
            custom_text += f"""
{section_name}
{section_content}
"""
        return custom_text

    # ======================
    # 构建最终 Prompt
    # ======================

    def build(self, user_input: str) -> str:

        sections = [
            self.system_prompt(),
            self.rules_prompt(),
            self.tools_prompt(),
            self.examples_prompt(),
            self.custom_sections(),
            self.user_prompt(user_input),
            self.output_prompt()
        ]

        # 自动过滤空模块
        return "\n".join(filter(None, sections))


def create_text_wash_prompt() -> PromptTemplate:
    """创建文本清洗与分割的提示模板"""
    return PromptTemplate(
        role="你是一名专业的文本处理助手，擅长文本清洗、分割和分析。",
        task="对目标文本进行清洗、分割和分析，确保文本适合向量化和存储。",
        context="系统需要将长文本分割为适合Milvus向量数据库存储的短文本片段，每个片段长度不超过128个字符。",
        rules=[
            "不修改文本语义，可以优化表述方式。",
            "不拆分专有名词/技术术语。",
            "不添加不存在的信息。"
        ],
        tools=[],
        examples=[
            {
                "input": "Java中volatile关键字的作用及实现原理？Python中的GIL锁对多线程的影响？",
                "output": """{
  "entities": [
    {
      "text": "Java中volatile关键字的作用及实现原理。",
      "tech_stack": "Java",
      "domain": "并发编程",
      "difficulty": 3,
      "position": "后端开发工程师"
    },
    {
      "text": "Python中的GIL锁对多线程的影响。",
      "tech_stack": "Python",
      "domain": "并发编程",
      "difficulty": 3,
      "position": "Python开发工程师"
    }
  ]
}"""
            }
        ],
        output_format={
            "entities": [
                {
                    "text": "分割后的语义单元文本，长度不超过128个字符",
                    "tech_stack": "技术栈",
                    "domain": "技术领域",
                    "difficulty": "难度等级（1-4）",
                    "position": "适合岗位"
                }
            ]
        },
        sections={
            "### 基础格式清理规则（必须执行）": """
1. 空格处理：移除行首/行尾空白字符，段落内连续空格合并为1个，保留词汇间必要单个空格；
2. 标点标准化：统一转为中文标点，移除无意义冗余标点，保留核心标点语义完整性；
3. 特殊格式剥离：移除所有富文本标记、装饰性符号、非打印字符，统一编码为UTF-8。""",
            "### 核心分割规则（必须执行）": """
1. 语义单元化：将文本分割为独立的语义单元，每个单元应该是一个完整的技术问题或知识点；
2. 长度控制：每个语义单元长度不超过128个字符，超长单元按自然语义停顿点拆分；
3. 完整性保证：确保每个分割后的单元语义完整，不拆分专有名词/技术术语；
4. 去重处理：删除完全重复的语义单元。""",
            "### 内容分析规则（必须执行）": """
1. 技术栈分析：识别每个语义单元中涉及的主要编程语言或技术框架；
2. 技术领域分析：识别每个语义单元所属的技术领域，如并发编程、数据库、网络等；
3. 难度分析：评估每个语义单元内容的难度等级，1=简单，2=中等，3=困难，4=专家；
4. 岗位分析：识别每个语义单元内容适合的岗位，如后端开发工程师、前端开发工程师等。"""
        }
    )



'''示例
prompt = PromptTemplate(

    role="你是一名资深 AI 工程师",

    task="帮助用户解决技术问题",

    context="系统运行在 AI Agent 环境中，可以调用工具",

    rules=[
        "回答必须准确",
        "如果不知道请说不知道",
        "优先使用知识库"
    ],

    tools=[
        "search_tool: 搜索互联网",
        "weather_tool: 查询天气"
    ],

    examples=[
        {
            "input": "上海天气",
            "output": """
{
 "思考": "需要查询天气",
 "动作": "weather_tool",
 "动作输入": "上海",
 "答案": "上海今天22℃"
}
"""
        }
    ],

    output_format={
        "思考": "推理过程",
        "动作": "工具名称或none",
        "动作输入": "输入",
        "答案": "最终回答"
    }

)

prompt_text = prompt.build("Redis 是什么？")

print(prompt_text)

'''
