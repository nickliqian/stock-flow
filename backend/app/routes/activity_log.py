"""AI 工作日志 API routes."""

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import json

from ..models import ActivityLog
from ..services.base import get_global_cache
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/activity-log", tags=["activity-log"])


def _safe_json_list(raw: str) -> list:
    """Safely parse a JSON string into a list, returning [] on failure."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


class CreateLogRequest(BaseModel):
    task_type: str = Field(default="manual", max_length=20)
    task_name: str = Field(default="", max_length=100)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    status: str = Field(default="success", max_length=20)
    summary: str = Field(default="", max_length=500)
    files_changed: Optional[List[str]] = None
    details: str = Field(default="", max_length=10000)


class UpdateLogRequest(BaseModel):
    details: Optional[str] = Field(default=None, max_length=10000)
    summary: Optional[str] = Field(default=None, max_length=500)
    files_changed: Optional[List[str]] = None


@router.post("")
def create_log(data: CreateLogRequest):
    """写入工作日志（供 cron 任务调用）."""
    cache = get_global_cache()
    with cache._session() as session:
        try:
            now = datetime.now().isoformat(timespec="seconds")
            log = ActivityLog(
                task_type=data.task_type,
                task_name=data.task_name,
                started_at=data.started_at or now,
                finished_at=data.finished_at or now,
                duration_seconds=data.duration_seconds or 0,
                status=data.status,
                summary=data.summary,
                files_changed=json.dumps(data.files_changed or [], ensure_ascii=False),
                details=data.details,
            )
            session.add(log)
            session.commit()
            return {"success": True, "id": log.id}
        except Exception as e:
            session.rollback()
            logger.error("创建日志失败: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="创建日志失败，请稍后重试")


@router.get("")
def list_logs(
    task_type: Optional[str] = Query(None, description="筛选任务类型"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """日志列表（支持分页、按类型筛选）."""
    cache = get_global_cache()
    with cache._session() as session:
        where = "WHERE 1=1"
        params = {}
        if task_type:
            where += " AND task_type = :task_type"
            params["task_type"] = task_type

        total = session.execute(
            text(f"SELECT COUNT(*) FROM activity_log {where}"), params
        ).scalar()

        offset = (page - 1) * page_size
        rows = session.execute(
            text(f"SELECT * FROM activity_log {where} ORDER BY started_at DESC LIMIT :limit OFFSET :offset"),
            {**params, "limit": page_size, "offset": offset},
        ).fetchall()

        items = []
        for r in rows:
            items.append({
                "id": r.id,
                "task_type": r.task_type,
                "task_name": r.task_name,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "duration_seconds": r.duration_seconds,
                "status": r.status,
                "summary": r.summary,
                "files_changed": _safe_json_list(r.files_changed),
                "details": r.details,
                "created_at": r.created_at,
            })

        return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/stats/summary")
def get_stats():
    """统计摘要."""
    cache = get_global_cache()
    with cache._session() as session:
        total = session.execute(text("SELECT COUNT(*) FROM activity_log")).scalar()
        by_type = session.execute(
            text("SELECT task_type, COUNT(*) as cnt FROM activity_log GROUP BY task_type")
        ).fetchall()
        recent = session.execute(
            text("SELECT COUNT(*) FROM activity_log WHERE started_at >= date('now', '-7 days')")
        ).scalar()
        return {
            "total": total,
            "recent_7days": recent,
            "by_type": {r.task_type: r.cnt for r in by_type},
        }


@router.put("/{log_id}")
def update_log(log_id: int, data: UpdateLogRequest):
    """更新日志详情."""
    cache = get_global_cache()
    with cache._session() as session:
        try:
            log = session.get(ActivityLog, log_id)
            if not log:
                raise HTTPException(status_code=404, detail="Not found")
            if data.details is not None:
                log.details = data.details
            if data.summary is not None:
                log.summary = data.summary
            if data.files_changed is not None:
                log.files_changed = json.dumps(data.files_changed, ensure_ascii=False)
            session.commit()
            return {"success": True}
        except HTTPException:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            logger.error("更新日志失败: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail="更新日志失败，请稍后重试")


@router.get("/{log_id}")
def get_log(log_id: int):
    """日志详情."""
    cache = get_global_cache()
    with cache._session() as session:
        r = session.execute(
            text("SELECT * FROM activity_log WHERE id = :id"), {"id": log_id}
        ).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Not found")
        return {
            "id": r.id,
            "task_type": r.task_type,
            "task_name": r.task_name,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "duration_seconds": r.duration_seconds,
            "status": r.status,
            "summary": r.summary,
            "files_changed": _safe_json_list(r.files_changed),
            "details": r.details,
            "created_at": r.created_at,
        }
