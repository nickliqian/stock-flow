# 股票资金流向分析 — 需求规格 (spec.md)

## 1. 背景
构建一个 H5 适配的 Web 应用，展示 A 股市场当日资金流向，帮助用户快速了解大盘、板块和个股的资金动向。

## 2. 核心功能

### 页面 1: 大盘资金总览
- **资金总览卡片**: 主力净流入（万元）、超大单净流入、大单净流入、中单净流入、小单净流入
- **北向资金卡片**: 沪股通净买入、深股通净买入、北向资金合计。需展示**历史对比**（与昨日对比、与近5日均值对比）
- **大盘资金趋势图**: 分钟级资金流向曲线（主力/超大/大/中/小单分层展示）

### 页面 2: 板块资金流向
- **板块列表**: Top 20 行业板块，展示主力净流入/流出排名
- **分页**: 支持翻页浏览全部板块（共约594个行业板块）
- **置顶功能**: 用户可置顶关注的板块
- **数据来源**: `ths_index`（板块列表）→ `ths_member`（成分股）→ `moneyflow_dc`（个股流向）→ 按板块聚合
- **字段**: 板块名称、板块代码、主力净流入、大单净流入、大单占比、领涨股、涨跌幅

### 页面 3: 个股资金流向
- **搜索**: 支持**股票代码**和**名称**模糊搜索
- **个股详情卡片**: 股票代码、名称、涨跌幅、换手率、成交额
- **资金流向明细**: 主力/超大/大/中/小单净流入，**大单净量**、**大单占比**
- **龙虎榜**: 股票名称、涨幅、换手率、成交额、净买入额、上榜原因、**大单净量**、**大单占比**

## 3. 数据更新策略
- 每小时自动更新一次（盘中 9:30-15:00 每整点更新）
- 收盘后增加一次最终更新
- 前端显示最后更新时间

## 4. 技术方案（确认）
- **前端**: React + H5 响应式 + ECharts 图表
- **后端**: FastAPI + TuShare API + SQLite 缓存
- **数据源**: TuShare（moneyflow, moneyflow_dc, moneyflow_hsgt, top_list, ths_index, ths_member）

## 5. 用户交互
- **板块置顶**: 点击星标置顶/取消，localStorage 持久化
- **分页**: 上一页/下一页，每页 20 条
- **搜索**: 实时搜索（debounce 300ms），代码/名称混合匹配
- **刷新**: 手动刷新按钮 + 自动定时刷新

## 6. 非功能需求
- H5 适配（移动端优先）
- 首屏加载 < 2s
- 数据缓存（SQLite），避免重复请求 TuShare

---

## 7. 系统设计

### 7.1 方案概览

**整体思路**：三层架构 — 前端（React）→ 后端 API（FastAPI）→ 数据层（TuShare + SQLite）

```
┌─────────────────────────────────────────┐
│              前端 React H5               │
│  大盘总览 │ 板块流向 │ 个股流向          │
└──────────────────┬──────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────┐
│            FastAPI 后端                  │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐  │
│  │ API路由  │ │ 定时任务 │ │ 缓存服务  │  │
│  │ routes  │ │ scheduler│ │  cache    │  │
│  └────┬────┘ └────┬────┘ └─────┬─────┘  │
│       │           │            │         │
│  ┌────▼───────────▼────────────▼─────┐   │
│  │         数据服务层 (service)       │   │
│  │  market │ sector │ stock │ north  │   │
│  └────────────────┬──────────────────┘   │
│                   │                      │
│  ┌────────────────▼──────────────────┐   │
│  │        TuShare 客户端             │   │
│  └────────────────┬──────────────────┘   │
│                   │                      │
│  ┌────────────────▼──────────────────┐   │
│  │     SQLite 缓存 (cache_db)        │   │
│  └───────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

#### 后端模块划分

| 模块 | 职责 | 文件 |
|------|------|------|
| **API 路由** | HTTP 接口，请求校验，响应格式化 | `app/routes/market.py`, `sector.py`, `stock.py` |
| **数据服务** | 业务逻辑：聚合板块数据、计算大单比例、对比北向历史 | `app/services/market.py`, `sector.py`, `stock.py` |
| **TuShare 客户端** | 封装 API 调用，异常处理，重试 | `app/clients/tushare_client.py` |
| **缓存层** | SQLite 读写，过期判断，批量更新 | `app/cache.py` |
| **定时调度** | 每小时触发数据更新，开盘/收盘特殊处理 | `app/scheduler.py` |
| **数据模型** | SQLAlchemy ORM 定义表结构 | `app/models.py` |

#### 前端模块划分

| 模块 | 职责 |
|------|------|
| **页面组件** | 3 个页面：MarketOverview, SectorFlow, StockFlow |
| **图表组件** | ECharts 封装：趋势图、柱状图、饼图 |
| **通用组件** | 搜索框、分页器、置顶按钮、加载状态 |
| **API 服务** | axios 封装，请求/响应拦截 |
| **工具函数** | 金额格式化、涨跌颜色、debounce |

#### 数据流

```
用户打开页面
  → 前端调用 /api/market/overview
    → FastAPI 检查 SQLite 缓存
      → 命中 → 直接返回
      → 未命中 → 调用 TuShare → 写入缓存 → 返回
  → 前端渲染 ECharts 图表
```

#### 关键 Trade-off

| 决策 | 选择 | 牺牲 |
|------|------|------|
| 缓存策略 | SQLite 文件缓存 | 并发写入性能（单用户可接受）|
| 数据更新 | 每小时全量拉取 | 非实时（用户要求如此）|
| 板块数据 | 聚合计算（ths_member → moneyflow_dc） | 首次加载慢（需拉取成分股）|
| 前端状态 | 简单 useState + localStorage | 未引入 Redux（复杂度低）|

### 7.2 组件设计

#### 项目结构

```
stock-flow/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置（TuShare token, DB path, 更新间隔）
│   │   ├── models.py            # SQLAlchemy ORM 模型
│   │   ├── cache.py             # 缓存服务（检查过期、批量写入）
│   │   ├── clients/
│   │   │   ├── __init__.py
│   │   │   └── tushare.py       # TuShare API 封装
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── market.py        # 大盘 + 北向资金逻辑
│   │   │   ├── sector.py        # 板块聚合计算
│   │   │   └── stock.py         # 个股 + 龙虎榜
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── market.py        # /api/market/*
│   │       ├── sector.py        # /api/sectors/*
│   │       └── stock.py         # /api/stocks/*
│   ├── scheduler.py             # 定时更新任务
│   ├── requirements.txt
│   └── seed.py                  # 初始化板块数据
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── MarketOverview.jsx
│   │   │   ├── SectorFlow.jsx
│   │   │   └── StockFlow.jsx
│   │   ├── components/
│   │   │   ├── FundCard.jsx      # 资金卡片
│   │   │   ├── TrendChart.jsx    # 趋势图
│   │   │   ├── SectorTable.jsx   # 板块表格（含分页、置顶）
│   │   │   ├── StockSearch.jsx   # 搜索框
│   │   │   └── Pagination.jsx
│   │   ├── services/api.js       # axios 封装
│   │   └── utils/format.js       # 金额格式化、颜色
│   ├── package.json
│   └── vite.config.js
└── docs/
    └── design-docs/stock-flow/capital-flow/spec.md
```

#### 核心类设计

**1. TuShare 客户端 — `clients/tushare.py`**

```python
class TuShareClient:
    """封装 TuShare API，统一异常处理和重试"""
    
    def __init__(self, token: str, api_url: str):
        self.pro = ts.pro_api(token)
    
    def get_moneyflow(self, ts_code=None, trade_date=None) -> pd.DataFrame:
    def get_moneyflow_hsgt(self, trade_date=None) -> pd.DataFrame:
    def get_top_list(self, trade_date=None) -> pd.DataFrame:
    def get_ths_index(self) -> pd.DataFrame:
    def get_ths_member(self, ts_code: str) -> pd.DataFrame:
    def get_moneyflow_dc(self, trade_date=None) -> pd.DataFrame:
```

**2. 缓存服务 — `cache.py`**

```python
class CacheService:
    """SQLite 缓存管理"""
    
    def __init__(self, db_path: str):
        self.engine = create_engine(f"sqlite:///{db_path}")
    
    def is_fresh(self, table, trade_date, max_age_minutes=60) -> bool:
    def upsert(self, table: str, data: pd.DataFrame):
    def get_market_overview(self, trade_date) -> dict:
    def get_sector_flows(self, trade_date, page, size) -> list:
```

**3. 数据服务 — `services/`**

```python
class MarketService:
    async def get_overview(self, trade_date=None) -> dict:
    async def get_north_fund(self, trade_date=None) -> dict:

class SectorService:
    async def get_sectors(self, page=1, size=20) -> dict:
    async def search_sectors(self, query: str) -> list:

class StockService:
    async def search_stocks(self, query: str) -> list:
    async def get_stock_flow(self, ts_code: str) -> dict:
    async def get_dragon_tiger(self, trade_date=None) -> list:
```

**4. API 路由**

| 端点 | 方法 | 说明 | 参数 |
|------|------|------|------|
| `/api/market/overview` | GET | 大盘资金总览 | `trade_date` (可选) |
| `/api/market/north` | GET | 北向资金 + 历史对比 | `trade_date` (可选) |
| `/api/sectors` | GET | 板块列表（分页） | `page`, `size` |
| `/api/sectors/search` | GET | 搜索板块 | `q` |
| `/api/stocks/search` | GET | 搜索个股 | `q` |
| `/api/stocks/{ts_code}` | GET | 个股资金流向 | - |
| `/api/stocks/{ts_code}/dragon` | GET | 龙虎榜 | - |

**5. 数据模型**

```python
# 大盘资金流向
class MarketFlow(Base):
    __tablename__ = "market_flow"
    id, trade_date, buy_sm_vol, sell_sm_vol, ..., net_mf_amount

# 北向资金
class NorthFundFlow(Base):
    __tablename__ = "north_fund_flow"
    id, trade_date, ggt_ss, ggt_sz, hgt, sgt, north_money

# 板块资金（聚合计算结果）
class SectorFlow(Base):
    __tablename__ = "sector_flow"
    id, trade_date, sector_code, sector_name, net_inflow, large_net, large_pct, lead_stock, lead_chg

# 个股资金流向
class StockFlow(Base):
    __tablename__ = "stock_flow"
    id, trade_date, ts_code, name, ..., buy_lg_vol, sell_lg_vol, net_lg_amount

# 龙虎榜
class DragonTiger(Base):
    __tablename__ = "dragon_tiger"
    id, trade_date, ts_code, name, pct_chg, turnover, amount, net_buy, reason, lg_net_vol, lg_pct

# 股票基础信息（搜索用）
class StockBasic(Base):
    __tablename__ = "stock_basic"
    id, ts_code, symbol, name, industry
```

**6. 定时调度**

```python
class DataScheduler:
    async def update_all(self):
        """每小时更新：检查交易时间 → 拉取数据 → 聚合板块 → 写入缓存"""
```

### 7.3 核心逻辑

#### 1. 板块聚合计算

```python
async def aggregate_sector_flows(trade_date: str):
    """板块资金流向聚合"""
    
    # 1. 成分股列表缓存（每天更新一次）
    sector_members = cache.get_or_fetch("sector_members", tushare.get_ths_all_members)
    
    # 2. 一次拉取全市场资金流向（单次 API 调用）
    all_flows = tushare.get_moneyflow_dc(trade_date=trade_date)
    
    # 3. 内存中聚合
    for sector_code, member_codes in sector_members.items():
        sector_flows = all_flows[all_flows.ts_code.isin(member_codes)]
        sector_net_inflow = sector_flows.net_mf_amount.sum()
        sector_large_net = (sector_flows.buy_lg_amount - sector_flows.sell_lg_amount).sum()
        sector_total = sector_flows.net_mf_amount.abs().sum()
        sector_large_pct = sector_large_net / sector_total * 100 if sector_total > 0 else 0
        lead_stock = sector_flows.loc[sector_flows.pct_chg.idxmax()] if not sector_flows.empty else None
```

**边界处理**：成分股为空 → 跳过；数据缺失 → 0 填充；除零 → 比例设 0

#### 2. 北向资金历史对比

```python
async def get_north_fund_with_comparison(trade_date: str):
    today = tushare.get_moneyflow_hsgt(trade_date=trade_date)
    yesterday = tushare.get_moneyflow_hsgt(trade_date=get_previous_trade_date(trade_date))
    last_5 = tushare.get_moneyflow_hsgt(trade_date=get_last_n_trade_dates(trade_date, 5))
    
    return {
        "today": today.north_money,
        "vs_yesterday": today.north_money - yesterday.north_money,
        "vs_yesterday_pct": (today.north_money - yesterday.north_money) / abs(yesterday.north_money) * 100,
        "avg_5day": last_5.north_money.mean(),
        "vs_5day_pct": (today.north_money - last_5.north_money.mean()) / abs(last_5.north_money.mean()) * 100,
    }
```

#### 3. 搜索实现

```python
async def search_stocks(query: str):
    sql = """
        SELECT ts_code, symbol, name, industry 
        FROM stock_basic 
        WHERE name LIKE :q1 OR ts_code LIKE :q2 OR symbol LIKE :q3
        LIMIT 20
    """
    return db.execute(sql, {"q1": f"%{query}%", "q2": f"%{query}%", "q3": f"%{query}%"})
```

前端 debounce 300ms，后端查 SQLite（stock_basic 已预加载全市场）

#### 4. 定时更新策略

```python
class DataScheduler:
    def start(self):
        # 每小时整点更新
        self.scheduler.add_job(self.update_all, CronTrigger(minute=0))
        # 收盘后额外更新（15:05）
        self.scheduler.add_job(self.update_all, CronTrigger(hour=15, minute=5))
    
    async def update_all(self, trade_date: str):
        if not is_trade_date():
            return
        
        # 并行拉取各数据源
        await asyncio.gather(
            self.update_market_flow(trade_date),
            self.update_north_fund(trade_date),
            self.update_stock_flows(trade_date),
            self.update_dragon_tiger(trade_date),
        )
        # 板块聚合依赖 stock_flows，需在之后执行
        await self.update_sector_flows(trade_date)
```

#### 性能优化

| 优化点 | 方案 | 效果 |
|--------|------|------|
| 板块聚合 | 一次拉取全市场流向，内存聚合 | API 调用从 594+ → 2 次 |
| 搜索 | stock_basic 表加索引 | 查询速度提升 |
| 缓存分层 | 成分股 24h、基础信息 7天、流向 1h | 减少无效请求 |
| 并行更新 | asyncio.gather 并行拉取 | 更新时间减半 |

### 7.4 方案优劣

（待讨论）

## 8. 备选方案

（待讨论）

## 9. 测试计划

（待讨论）

## 10. 可观测性 & 运维

（待讨论）
