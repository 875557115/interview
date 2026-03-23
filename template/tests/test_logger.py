import os
from aiagent.template.src.template.util.logger import get_logger  # 导入你的logger


def test_get_logger():
    """
    测试logger创建：
    1. 能正常创建logger
    2. logger名称正确
    3. 日志级别是INFO
    """
    logger = get_logger("test_logger")

    # 断言1：logger不为空
    assert logger is not None
    # 断言2：logger名称正确
    assert logger.name == "test_logger"
    # 断言3：日志级别是INFO
    assert logger.level == 20  # logging.INFO = 20
    # 断言4：有至少一个handler（控制台/文件）
    assert len(logger.handlers) > 0


def test_logger_output():
    """
    测试日志输出：
    1. 能输出INFO级别日志
    2. 日志文件能正常创建
    """
    logger = get_logger("test_output")
    log_msg = "这是一条测试日志"
    logger.info(log_msg)

    # 断言：日志目录存在
    log_dir = "logs"
    assert os.path.exists(log_dir)
    # 断言：日志文件存在
    log_files = os.listdir(log_dir)
    assert len(log_files) > 0
