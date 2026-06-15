"""
通用工具函数：文件处理、ID生成、文本清理
"""

import re
import os
import json
import hashlib
import uuid
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any, List, Dict


def gen_id(prefix: str = "id") -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def safe_filename(filename: str) -> str:
    filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
    return filename


def human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    for unit in ["KB", "MB", "GB"]:
        size /= 1024
        if size < 1024:
            return f"{size:.2f} {unit}"
    return f"{size:.2f} TB"


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def md5_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def clean_text(text: str) -> str:
    """通用文本清洗：去除多余空白、控制字符"""
    if not text:
        return ""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    return text.strip()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def list_files_by_ext(directory: str, exts: List[str]) -> List[Dict]:
    files = []
    for root, _, filenames in os.walk(directory):
        for fn in filenames:
            if fn.lower().endswith(tuple(exts)):
                p = os.path.join(root, fn)
                st = os.stat(p)
                files.append({
                    "name": fn,
                    "path": p,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                })
    return files


def move_file(src: str, dst: str) -> str:
    ensure_dir(os.path.dirname(dst))
    shutil.move(src, dst)
    return dst


def copy_file(src: str, dst: str) -> str:
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)
    return dst


def count_tokens_rough(text: str) -> int:
    """粗略Token估算：中文字符≈1.8token/字，英文≈4chars/token"""
    if not text:
        return 0
    cn = len(re.findall(r"[\u4e00-\u9fa5]", text))
    other = len(text) - cn
    return int(cn * 1.8 + other / 4)
