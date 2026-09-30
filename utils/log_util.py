import logging
from datetime import datetime
from pathlib import Path
# 第三步封装日志

# 项目根目录。
# __file__ 表示当前文件路径：utils/log_util.py
# parent 是 utils 目录，parent.parent 就是项目根目录。
# 这样写的好处是：无论从哪里运行脚本，日志都会固定写到项目的 logs 目录。
BASE_DIR = Path(__file__).resolve().parent.parent

# 日志目录：项目根目录/logs
LOG_DIR = BASE_DIR / "logs"


def get_logger():
    """
    获取项目统一使用的 logger 对象。

    logging.getLogger(name) 有缓存机制：
    同一个 name 多次获取到的是同一个 logger 对象。
    所以整个项目都用同一个 name，就可以做到统一日志入口。
    """
    logger = logging.getLogger("pytest")

    # 设置日志级别。
    # INFO 表示会记录 info、warning、error、critical 级别的日志。
    # debug 级别不会记录。
    logger.setLevel(logging.INFO)

    # 是否把日志继续传递给 root logger。
    # True 表示：除了写入我们自己的文件日志，也把日志交给 pytest 捕获。
    # pytest.ini 中的 log_cli 决定是否同时在终端实时显示这些日志。
    logger.propagate = True

    # 防止重复添加 handler。
    # 因为 get_logger() 可能会被多个模块多次调用，
    # 如果不判断，FileHandler 会被反复添加，最终一条日志写多遍。
    if logger.handlers:
        return logger

    # 自动创建 logs 目录。
    # exist_ok=True 表示目录已存在时不报错。
    LOG_DIR.mkdir(exist_ok=True)

    # 按日期生成日志文件名。
    # 例如：logs/log_2026-05-23.log
    # 每天一个日志文件，方便按日期排查问题。
    log_path = LOG_DIR / f"log_{datetime.now().strftime('%Y-%m-%d')}.log"

    # 文件日志处理器。
    # 负责把日志内容写入 log_path 指定的文件。
    # encoding="utf-8" 用来避免中文日志乱码。
    file_handler = logging.FileHandler(log_path, encoding="utf-8")

    # 日志格式。
    # asctime：日志时间
    # levelname：日志级别，比如 INFO、ERROR
    # filename：输出日志的 Python 文件名
    # message：实际日志内容
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(filename)s - %(message)s"
    )

    # 给文件处理器绑定日志格式。
    file_handler.setFormatter(formatter)

    # 把文件处理器添加到 logger。
    # 添加后，logger.info()/logger.error() 才会真正写入文件。
    logger.addHandler(file_handler)

    return logger


# 项目公共 logger。
# 其他文件可以直接导入使用：
# from utils.log_util import logger
# logger.info("请求成功")
logger = get_logger()
