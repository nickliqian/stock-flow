"""研究资料浏览器 API routes — 浏览 ~/projects/stock-research/ 目录，支持手动录入."""

import os
import re
import stat
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

logger = __import__("logging").getLogger(__name__)

router = APIRouter(prefix="/api/research-browser", tags=["research-browser"])

# ---------- 常量 ----------

# 研究资料根目录（展开 ~）
RESEARCH_ROOT = Path(os.path.expanduser("~/projects/stock-research")).resolve()

# 只允许浏览这些子目录
ALLOWED_SUBDIRS = {"raw", "insights", "library", "archive", "output", "logs"}

# 目录树最大递归深度
MAX_DEPTH = 3

# 分类关键词映射（AI根据内容判断）
CATEGORY_KEYWORDS = {
    "market-strategy": ["选股", "策略", "选股策略"],
    "quantitative": ["量化", "量化炒股", "因子", "回测"],
    "analysis": ["分析", "股票分析", "基本面", "技术面"],
    "macro-micro": ["宏观", "微观", "经济", "GDP", "CPI", "PMI"],
    "institutional": ["主力", "机构", "资金", "北向", "龙虎榜"],
    "ai-sector": ["AI", "人工智能", "大模型", "ChatGPT", "算力"],
    "new-energy": ["新能源", "光伏", "风电", "储能", "锂电"],
    "pcb": ["PCB", "印制电路板", "覆铜板"],
    "semiconductor": ["半导体", "芯片", "集成电路", "晶圆"],
    "etf-index": ["ETF", "指数基金", "指数"],
    "convertible-bond": ["可转债", "转债"],
    "hk-us-stock": ["港股", "美股", "纳斯达克", "标普"],
    "futures-options": ["期货", "期权", "衍生品"],
    "fixed-income": ["债券", "固收", "利率", "国债"],
}

# 分类目录名称映射
CATEGORY_DIRS = {
    "market-strategy": "market-strategy",
    "quantitative": "quantitative",
    "analysis": "analysis",
    "macro-micro": "macro-micro",
    "institutional": "institutional",
    "ai-sector": "ai-sector",
    "new-energy": "new-energy",
    "pcb": "pcb",
    "semiconductor": "semiconductor",
    "etf-index": "etf-index",
    "convertible-bond": "convertible-bond",
    "hk-us-stock": "hk-us-stock",
    "futures-options": "futures-options",
    "fixed-income": "fixed-income",
}


# ---------- 请求模型 ----------


class CreateResearchRequest(BaseModel):
    """创建研究资料请求体."""

    title: str = Field(default="", description="标题，不填则AI自动生成")
    content: str = Field(..., min_length=1, description="资料内容（必填）")
    category: str = Field(default="auto", description="分类目录，auto则AI自动识别")


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
    if not target.is_relative_to(RESEARCH_ROOT):
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


def _classify_content(content: str, title: str = "") -> str:
    """根据内容和标题关键词自动分类，返回分类目录名."""
    text = f"{title} {content}".lower()
    scores: dict[str, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)
    return "analysis"  # 默认分类


def _generate_title(content: str, max_len: int = 20) -> str:
    """从内容中提取关键词生成标题（简易实现）."""
    # 去除 markdown 标记，取第一行有意义的文本
    lines = content.strip().splitlines()
    for line in lines:
        clean = re.sub(r"[#*>\-\[\]()]", "", line).strip()
        if len(clean) > 4:
            return clean[:max_len]
    # fallback: 取前 max_len 字符
    return content.strip()[:max_len] or "未命名资料"


def _make_filename(title: str) -> str:
    """生成文件名：YYYY-MM-DD_<标题关键词>_手动录入.md."""
    today = datetime.now().strftime("%Y-%m-%d")
    # 提取标题中的中文/英文关键词
    keywords = re.findall(r"[一-龥a-zA-Z]+", title)
    key_part = "_".join(keywords[:3]) if keywords else "资料"
    return f"{today}_{key_part}_手动录入.md"


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


@router.post("/create")
def create_research(req: CreateResearchRequest):
    """手动录入研究资料，创建 markdown 文件到 raw/<分类>/ 目录.

    分类规则：
    - category 为 'auto' 时，根据内容关键词自动分类
    - category 为具体分类名时，直接使用该分类
    """
    # 确定分类
    if req.category == "auto" or req.category not in CATEGORY_DIRS:
        category = _classify_content(req.content, req.title)
    else:
        category = req.category

    # 确定标题
    title = req.title.strip() if req.title.strip() else _generate_title(req.content)

    # 生成文件名
    filename = _make_filename(title)

    # 构建目标目录路径
    raw_dir = RESEARCH_ROOT / "raw"
    target_dir = raw_dir / category

    # 目录不存在则创建
    target_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件内容
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    file_content = f"""# {title}
> 来源：手动录入
> 录入时间：{now}
> 主题分类：{category}

## 核心内容
{req.content}

## 关键要点
- （请补充关键要点）
"""

    # 写入文件
    file_path = target_dir / filename
    file_path.write_text(file_content, encoding="utf-8")

    # 返回相对路径
    rel_path = f"raw/{category}/{filename}"
    logger.info("研究资料已创建: %s", rel_path)

    return {
        "success": True,
        "file_path": rel_path,
        "category": category,
        "title": title,
    }
