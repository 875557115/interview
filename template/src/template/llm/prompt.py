


class PromptTemplate:
    # 模板结构（可固化为类的常量，如你代码中的SYSTEM_TEMPLATE）
    SYSTEM_TEMPLATE = """
    # Role（角色）
    {role}

    # Task（核心任务）
    {task}

    # Rules（约束规则）
    {rules}

    # Knowledge Base（参考依据）
    {knowledge_base}

    # Example（参考示例，可选）
    {example}

    # Output Style（输出格式）
    {output_style}
    """

    # 填充模板示例
    template_data = {
        "role": "你是AI技术面试答题助手，擅长解答编程面试题",
        "task": "参考知识库，为用户的面试问题提供准确、结构化的回答",
        "rules": "1. 优先用知识库内容；2. 无相关内容标注「知识库未覆盖」；3. 不编造信息",
        "knowledge_base": "Python装饰器：修改函数行为的语法糖...",
        "example": "输入：解释装饰器 → 输出：1. 原理：xxx；2. 场景：xxx",
        "output_style": "分点说明，每个要点不超过2句话，语言简洁专业"
    }

    # 渲染模板（自动填充变量，避免手动拼接）
    rendered_prompt = SYSTEM_TEMPLATE.format(**template_data)


    pass
