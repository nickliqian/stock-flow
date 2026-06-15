"""研究资料浏览器 API routes — 只读浏览 ~/projects/stock-research/ 目录."""

import os
import stat
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

logger = __import__("logging").getLogger(__name__)

router = APIRouter(prefix="/api/research-browser", tags=["research-browser"])

# ---------- 常量 ----------

# 研究资料根目录（展开 ~）
RESEARCH_ROOT = Path(os.path.expanduser("~/projects/stock-research")).resolve()

# 只允许浏览这些子目录
ALLOWED_SUBDIRS = {"raw", "insights", "library", "archive", "logs"}

# 目录树最大递归深度
MAX_DEPTH = 3


# ---------- 安全工具 ----------


def _safe_path(relative: str) -> Path:
    """将相对路径解析为绝对路径，校验不逃逸出 RESEARCH_ROOT.

    Returns:
        解析后的绝对路径

    Raises:
        HTTPException 403 — 路径穿越或越界
        HTTPException 404 — 文件/目录不存在
    """
    # 拼接后 realpath 会解析符号链接和 .. 等
    target = (RESEARCH_ROOT / relative).resolve()

    # 校验路径是否在根目录内
    if not str(target).startswith(str(RESEARCH_ROOT)):
        raise HTTPException(status_code=403, detail="路径越界，禁止访问")

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"路径不存在: {relative}")

    return target


def _node_info(path: Path, base: Path) -> dict:
    """构造单个文件/目录节点的字典."""
    rel = path.relative_to(base)
    st = path.stat()
    info = {
        "name": path.name,
        "path": str(rel),
        "type": "dir" if path.is_dir() else "file",
        "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }
    if path.is_file():
        info["size"] = st.st_size
    return info


def _build_tree(path: Path, base: Path, depth: int) -> dict | None:
    """递归构建目录树，最大深度 MAX_DEPTH.

    - 仅返回 ALLOWED_SUBDIRS 中的顶层子目录
    - 目录节点包含 children 列表
    - 文件节点不包含 children
    """
    if depth > MAX_DEPTH:
        return None

    node = _node_info(path, base)

    if path.is_dir():
        children = []
        try:
            for entry in sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                # 第一层只保留白名单目录
                if depth == 0 and entry.name not in ALLOWED_SUBDIRS:
                    continue
                child = _build_tree(entry, base, depth + 1)
                if child:
                    children.append(child)
        except PermissionError:
            pass  # 无权限的目录静默跳过
        node["children"] = children

    return node


# ---------- API 端点 ----------


@router.get("/tree")
def get_tree():
    """返回 ~/projects/stock-research/ 的目录树结构.

    只返回 raw/、insights/、logs/ 三个子目录，最大递归深度 3 层。
    """
    if not RESEARCH_ROOT.exists():
        raise HTTPException(status_code=404, detail="研究资料目录不存在")

    tree = _build_tree(RESEARCH_ROOT, RESEARCH_ROOT, depth=0)
    return tree or {"name": RESEARCH_ROOT.name, "path": "", "type": "dir", "children": []}


@router.get("/file")
def get_file(path: str = Query(..., description="相对于 stock-research 根目录的文件路径")):
    """返回指定文件的原始文本内容（只读）.

    安全校验：path 必须在 ~/projects/stock-research/ 内。
    """
    target = _safe_path(path)

    if not target.is_file():
        raise HTTPException(status_code=400, detail="路径不是文件")

    # 读取文件内容
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件不是 UTF-8 文本文件")

    st = target.stat()
    return {
        "content": content,
        "filename": target.name,
        "size": st.st_size,
        "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }
