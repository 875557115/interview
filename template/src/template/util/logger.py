from pathlib import Path
from loguru import logger
import sys
import logging

_LOGGER_CONFIGURED = False


class LoguruLoggingHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 关键：这里绝对不碰 extra，彻底避免 KeyError
        logger.opt(
            depth=4,
            exception=record.exc_info,
            ansi=True
        ).log(level, record.getMessage())


def _takeover_standard_logging():
    # 直接关掉 torch 这种第三方库的噪音，从根源解决
    logging.getLogger("torch").setLevel(logging.ERROR)
    logging.getLogger("torch._dynamo").setLevel(logging.ERROR)
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

    logging.root.handlers.clear()
    handler = LoguruLoggingHandler()
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)


def get_logger(name: str):
    global _LOGGER_CONFIGURED

    if not _LOGGER_CONFIGURED:
        logger.remove()

        # ===================== 核心修复 =====================
        # 彻底不用 {extra[name]}，这就是你一直报错的根源！
        # ====================================================
        LOG_FORMAT = (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{file.name}:{line} | "
            "{message} | "
            "{exception}"
        )

        # 控制台
        logger.add(
            sys.stdout,
            format=LOG_FORMAT,
            level="DEBUG",
            enqueue=True,
            colorize=True,
            backtrace=True,
            diagnose=True
        )

        # 文件
        current_file = Path(__file__).resolve()
        project_dir = current_file.parent.parent.parent.parent
        log_dir = project_dir / "logs"
        log_dir.mkdir(exist_ok=True)

        logger.add(
            log_dir / "interview_agent_{time:YYYYMMDD}.log",
            format=LOG_FORMAT,
            level="INFO",
            encoding="utf-8",
            rotation="00:00",
            retention="7 days",
            compression="zip",
            enqueue=True
        )

        _takeover_standard_logging()
        _LOGGER_CONFIGURED = True

    # 这里我们不用 bind(name=xxx) 了，避免触发 extra 机制
    return logger

# 全局异常处理
def custom_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    log = get_logger("global_exception")
    log.error("未捕获的全局异常", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = custom_exception_handler

# 测试用例
if __name__ == "__main__":
    # 测试1：Loguru日志
    log = get_logger("qa_service")
    log.info("===== Loguru日志测试开始 =====")

    # 测试2：标准logging日志（验证是否被接管）
    std_logger = logging.getLogger("test_standard_logging")
    std_logger.debug("这是logging的DEBUG日志（应被Loguru接管）")
    std_logger.info("这是logging的INFO日志（应被Loguru接管）")
    std_logger.error("这是logging的ERROR日志（应被Loguru接管）")

    # 测试3：异常日志
    try:
        1 / 0
    except Exception as e:
        log.exception("除法运算出错（带栈堆）")
        std_logger.exception("logging的异常日志（应被Loguru接管）")

    # 测试4：验证第三方库日志不报错（模拟PyTorch日志）
    torch_logger = logging.getLogger("torch._dynamo")
    torch_logger.info("模拟TorchDynamo日志（应被过滤，不报错）")

    log.info("===== Loguru日志测试结束 =====")
