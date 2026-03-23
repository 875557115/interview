from template.util.logger import get_logger

from template.llm.model_factory import create_llm

logger = get_logger("llm_client")

# 全局唯一LLM实例，自动根据配置加载模型
llm = create_llm()
logger.info("LLM 初始化完成，业务层无需关心底层模型")
