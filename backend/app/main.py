import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from .models import init_db
from .services.base import get_global_cache
from .routes.market import router as market_router
from .routes.sector import router as sector_router
from .routes.stock import router as stock_router
from .routes.screener import router as screener_router
from .routes.technical import router as technical_router
from .routes.concept import router as concept_router
from .routes.strategy import router as strategy_router
from .routes.watchlist import router as watchlist_router
from .routes.activity_log import router as activity_log_router
from .routes.market_breadth import router as market_breadth_router
from .routes.shareholder import router as shareholder_router
from .routes.event_calendar import router as event_calendar_router
from .routes.insider import router as insider_router
from .routes.alpha import router as alpha_router
from .routes.recommendation import router as recommendation_router
from .routes.pair_trading import router as pair_trading_router
from .routes.portfolio import router as portfolio_router
from .routes.multi_timeframe import router as multi_timeframe_router
from .routes.research_browser import router as research_browser_router
from .routes.volatility import router as volatility_router
from .routes.signal_alert import router as signal_alert_router
from .scheduler import DataScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Scheduler instance
scheduler = DataScheduler()

# Reusable cache instance (singleton shared with all Services)
cache = get_global_cache()


@asynccontextmanager
async def lifespan(app):
    """Manage startup and shutdown events."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Starting scheduler...")
    scheduler.start()
    logger.info("Stock Flow API started.")
    yield
    logger.info("Stopping scheduler...")
    scheduler.stop()


app = FastAPI(
    title="Stock Flow API",
    description="A股资金流向分析系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
cors_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:80,http://localhost:3000,http://localhost:3001"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """记录每个请求的方法、路径、耗时、状态码。排除健康检查端点避免日志洪泛。"""
    if request.url.path == "/api/health":
        return await call_next(request)
    start_time = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response

# Include routers
app.include_router(market_router)
app.include_router(sector_router)
app.include_router(stock_router)
app.include_router(screener_router)
app.include_router(technical_router)
app.include_router(concept_router)
app.include_router(strategy_router)
app.include_router(watchlist_router)
app.include_router(activity_log_router)
app.include_router(market_breadth_router)
app.include_router(shareholder_router)
app.include_router(event_calendar_router)
app.include_router(insider_router)
app.include_router(alpha_router)
app.include_router(recommendation_router)
app.include_router(pair_trading_router)
app.include_router(portfolio_router)
app.include_router(multi_timeframe_router)
app.include_router(research_browser_router)
app.include_router(volatility_router)
app.include_router(signal_alert_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器，防止栈追踪泄露到客户端。"""
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/api/health")
def health_check():
    """健康检查，包含数据库连接状态。"""
    from sqlalchemy import text
    from .models import SessionLocal
    db_status = "disconnected"
    try:
        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))
            db_status = "connected"
        finally:
            session.close()
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status, "version": "1.0.0"}
