"""
统一日志模块 - 控制台彩色日志 + 文件日志
"""

import os
import logging
import colorlog
from datetime import datetime
from logging.handlers import RotatingFileHandler

from .config import settings, ensure_dirs

_LOGGER_INITIALIZED = False


def get_logger(name: str = "app") -> logging.Logger:
    """获取指定名称的日志对象"""
    global _LOGGER_INITIALIZED
    if not _LOGGER_INITIALIZED:
        ensure_dirs()
        _LOGGER_INITIALIZED = True

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    if settings.DEBUG:
        logger.setLevel(logging.DEBUG)

    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s | %(levelname)-7s | %(name)-18s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件 Handler
    log_file = os.path.join(settings.LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)-18s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger


def log_op(logger, action: str, status: str = "INFO", detail: str = ""):
    """统一的操作日志记录辅助"""
    msg = f"[{action}] {status}"
    if detail:
        msg += f" - {detail}"
    logger.info(msg)
