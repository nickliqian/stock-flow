# Stock Flow

> 🚀 A股资金流向分析系统 | Capital Flow Analytics for China A-Shares

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 项目简介

Stock Flow 是一个专业的 A 股量化分析平台，集成了 **23 个策略引擎**和 **9 大高级分析模块**，为投资者提供从资金流向追踪、多维选股到策略回测的全流程量化工具。

**核心特性：**
- 💰 实时资金流向监控（主力、北向、板块）
- 📊 23 个量化策略引擎（价值/动量/资金/事件/组合）
- 🧠 9 大高级分析引擎（信号矩阵、因子轮动、自进化等）
- 📈 多维选股器（技术面 + 基本面）
- 🔄 自动化数据更新（盘中每小时 + 收盘后）
- 🎯 策略回测与优化
- 📱 RESTful API（可对接任意前端）

---

## 🏗️ 功能模块

### 📊 数据层
| 模块 | 说明 |
|------|------|
| 市场概览 | 大盘资金流向、北向资金、涨跌统计 |
| 板块数据 | 行业板块资金流向、成分股、概念板块 |
| 个股数据 | K 线、财务指标、筹码分布、股东信息 |
| 事件日历 | 财报披露、限售解禁、股东增减持 |

### 🎯 策略引擎（23 个）

| # | 策略名称 | 分类 | 图标 | 说明 |
|---|---------|------|------|------|
| 1 | MACD 金叉 | 动量 | 📈 | DIF 上穿 DEA 且零轴上方 |
| 2 | 均线多头排列 | 动量 | 📊 | MA5 > MA10 > MA20 > MA60 |
| 3 | KDJ 超卖反弹 | 动量 | 🔄 | K/D < 20 金叉 |
| 4 | 趋势量价共振 | 动量 | 📈 | 价升量增趋势确认 |
| 5 | 放量突破 | 动量 | 🚀 | 成交量突破 20 日均量 |
| 6 | 连板追踪 | 动量 | 🔥 | 连续涨停板股票 |
| 7 | 涨停回封 | 事件 | 🎯 | 涨停后回调再封板 |
| 8 | 超跌反弹 | 动量 | 📉 | 连续下跌后的技术反弹 |
| 9 | 低估值金矿 | 价值 | 💎 | PE/PB 双低 |
| 10 | 高股息策略 | 价值 | 💰 | 股息率 > 3% |
| 11 | 主力资金流入 | 资金 | 💵 | 大单净流入 |
| 12 | 智能资金追踪 | 资金 | 🤖 | 聪明钱行为模式 |
| 13 | 融资余额增长 | 资金 | 📊 | 杠杆资金流入 |
| 14 | 融券资金收敛 | 资金 | 🔄 | 空头回补信号 |
| 15 | 断层金坑 | 事件 | 🕳️ | 跳空缺口后企稳 |
| 16 | 板块轮动 | 组合 | 🔄 | 行业轮动信号 |
| 17 | 量价异动 | 事件 | ⚡ | 异常成交量检测 |
| 18 | 趋势量价共振 | 动量 | 📈 | 量价配合确认趋势 |
| 19 | 多周期动量 | 动量 | 📊 | 日/周/月多周期共振 |
| 20 | 价值基金共振 | 价值 | 🏛️ | 机构重仓 + 低估值 |
| 21 | 大宗交易溢价 | 事件 | 💎 | 溢价大宗交易 |
| 22 | 内部人信心 | 事件 | 👔 | 高管增持信号 |
| 23 | 芯片质押策略 | 风险 | ⚠️ | 质押率风险监控 |

### 🧠 高级分析引擎

| 引擎 | 功能 | API 路径 |
|------|------|----------|
| Flow Intelligence | 资金流向背离分析 | `/api/strategies/flow-intelligence/*` |
| Signal Matrix | 策略信号矩阵 | `/api/strategies/signals/matrix` |
| Market Breadth | 市场宽度与温度 | `/api/market-breadth/*` |
| Volatility Clustering | 波动率聚类与风险分区 | `/api/volatility/*` |
| Strategy Evolution | 策略自进化引擎 | `/api/strategies/evolution/*` |
| Pair Trading | 协整配对交易 | `/api/pair-trading/*` |
| Factor Model | 因子轮动模型 | `/api/strategies/factor-model/*` |
| Institutional Radar | 机构动向雷达 | `/api/strategies/institutional/*` |
| Crowding Evolution | 策略拥挤度演进 | `/api/strategies/crowding-*` |

---

## 🛠️ 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (任意外部系统)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI REST API                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Market   │ │ Screener │ │ Strategy │ │ Technical│       │
│  │ Routes   │ │ Routes   │ │ Routes   │ │ Routes   │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Market   │ │ Stock    │ │ Screener │ │ Strategy │       │
│  │ Service  │ │ Service  │ │ Service  │ │ Service  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Engine Layer                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              23 Strategy Engines                     │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         9 Advanced Analysis Engines                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │ SQLite   │ │ TuShare  │ │ In-Memory│                    │
│  │ Cache    │ │ API      │ │ Cache    │                    │
│  └──────────┘ └──────────┘ └──────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

**技术栈：**
- **后端框架**: FastAPI + Uvicorn
- **数据源**: TuShare Pro API
- **数据库**: SQLite (缓存) + PostgreSQL (可选)
- **缓存**: 内存缓存 + SQLite 持久化
- **定时任务**: APScheduler
- **数据处理**: Pandas + NumPy

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.9+
- TuShare Pro Token（[注册获取](https://tushare.pro/register)）

### 2. 安装

```bash
# 克隆项目
git clone https://github.com/your-username/stock-flow.git
cd stock-flow

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# 安装依赖
pip install -r backend/requirements.txt
```

### 3. 配置

```bash
# 创建密钥目录
mkdir -p ~/.secrets
chmod 700 ~/.secrets

# 配置 TuShare Token
cat > ~/.secrets/tushare.env << 'EOF'
TUSHARE_TOKEN=your_token_here
EOF
chmod 600 ~/.secrets/tushare.env
```

### 4. 启动服务

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问 API 文档: http://localhost:8000/docs

---

## 📡 API 端点列表

### 市场数据
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/market/overview` | 市场概览 |
| GET | `/api/market/north-fund` | 北向资金 |
| GET | `/api/market/flow-trend` | 资金流向趋势 |
| GET | `/api/market/limit-stats` | 涨跌停统计 |
| GET | `/api/market/indices` | 大盘指数 |

### 选股筛选
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/screener/stocks` | 多维度选股 |
| GET | `/api/sector/overview` | 板块概览 |
| GET | `/api/sector/{code}/stocks` | 板块成分股 |

### 策略引擎
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/strategies/` | 策略列表 |
| POST | `/api/strategies/execute/{name}` | 执行单策略 |
| POST | `/api/strategies/execute-all` | 执行全部策略 |
| GET | `/api/strategies/confluence` | 策略共振扫描 |
| GET | `/api/strategies/sector-heatmap` | 策略板块热力图 |
| GET | `/api/strategies/backtest/{name}` | 策略回测 |

### 高级分析
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/strategies/signals/matrix` | 信号矩阵 |
| GET | `/api/strategies/regime` | 市场状态检测 |
| GET | `/api/strategies/flow-intelligence/*` | 资金背离分析 |
| GET | `/api/strategies/evolution/*` | 策略自进化 |
| GET | `/api/strategies/factor-model/*` | 因子轮动 |
| GET | `/api/strategies/crowding-*` | 拥挤度分析 |
| GET | `/api/pair-trading/*` | 配对交易 |
| GET | `/api/volatility/*` | 波动率分析 |
| GET | `/api/market-breadth/*` | 市场宽度 |

### 个股分析
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/stock/{code}` | 个股详情 |
| GET | `/api/stock/{code}/daily` | K 线数据 |
| GET | `/api/technical/{code}` | 技术指标 |
| GET | `/api/strategies/health/{code}` | 健康度评分 |

---

## ⏰ 定时任务

| 任务 | 时间 | 说明 |
|------|------|------|
| 盘中更新 | 每小时 9:00-15:00 | 更新资金流向、板块数据、涨跌停统计 |
| 收盘更新 | 15:05 | 收盘后全量更新 |
| 趋势预缓存 | 每小时 :30 | 预缓存 30/60/90 天趋势数据 |

---

## 📁 目录结构

```
stock-flow/
├── README.md                    # 项目说明
├── LICENSE                      # MIT License
├── docs/
│   └── STRATEGY-GUIDE.md       # 策略与算法文档
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── config.py           # 配置管理
│   │   ├── models.py           # 数据模型
│   │   ├── cache.py            # 缓存管理
│   │   ├── scheduler.py        # 定时任务
│   │   ├── utils.py            # 工具函数
│   │   ├── routes/             # API 路由
│   │   │   ├── market.py
│   │   │   ├── sector.py
│   │   │   ├── stock.py
│   │   │   ├── screener.py
│   │   │   ├── strategy.py
│   │   │   ├── technical.py
│   │   │   ├── portfolio.py
│   │   │   ├── pair_trading.py
│   │   │   ├── volatility.py
│   │   │   ├── market_breadth.py
│   │   │   └── ...
│   │   ├── services/           # 业务逻辑层
│   │   │   ├── market.py
│   │   │   ├── sector.py
│   │   │   ├── stock.py
│   │   │   ├── screener.py
│   │   │   └── strategy.py
│   │   └── engine/             # 策略引擎层
│   │       ├── base.py         # 策略基类
│   │       ├── registry.py     # 策略注册表
│   │       ├── strategies/     # 23 个策略实现
│   │       │   ├── macd_golden_cross.py
│   │       │   ├── ma_alignment.py
│   │       │   ├── kdj_oversold_rebound.py
│   │       │   └── ...
│   │       ├── flow_intelligence.py
│   │       ├── signal_matrix.py
│   │       ├── market_breadth.py
│   │       ├── volatility_clustering.py
│   │       ├── strategy_evolution.py
│   │       ├── pair_trading.py
│   │       ├── factor_model.py
│   │       ├── institutional_radar.py
│   │       ├── crowding_evolution.py
│   │       └── ...
│   ├── data/                   # SQLite 缓存
│   ├── tests/                  # 单元测试
│   └── requirements.txt        # Python 依赖
└── frontend/                   # 前端（可选）
```

---

## 📊 策略分类体系

```
                    ┌─────────────────────────────────────┐
                    │           Stock Flow                 │
                    └─────────────────────────────────────┘
                                    │
        ┌───────────────┬───────────┼───────────┬───────────────┐
        ▼               ▼           ▼           ▼               ▼
   ┌─────────┐    ┌─────────┐ ┌─────────┐ ┌─────────┐    ┌─────────┐
   │  价值   │    │  动量   │ │  资金   │ │  事件   │    │  组合   │
   │ Value   │    │Momentum │ │  Flow   │ │ Event   │    │ Combo   │
   └─────────┘    └─────────┘ └─────────┘ └─────────┘    └─────────┘
   · 低估值       · MACD金叉   · 主力流入   · 涨停回封    · 板块轮动
   · 高股息       · 均线多头   · 智能追踪   · 断层金坑    · 多策略
   · 基金共振     · KDJ超卖    · 融资增长   · 大宗交易    · 共振
                  · 量价突破   · 融券收敛   · 内部人信心
```

---

## 📸 界面预览

> 🖥️ **策略信号矩阵** — 一目了然查看所有策略的选股结果
>
> 📊 **资金流向仪表板** — 实时追踪主力资金、北向资金动向
>
> 📈 **策略回测报告** — 历史表现、胜率、夏普比率
>
> 🎯 **多维选股器** — PE/PB/市值/换手率/量比等多条件筛选

---

## 🤝 贡献

欢迎贡献代码、报告 Bug 或提出新功能建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 License

本项目采用 [MIT License](LICENSE) 开源协议。

---

## ⚠️ 免责声明

本系统仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。作者不对使用本系统产生的任何损失承担责任。

---

<p align="center">
  <sub>Built with ❤️ for A-Share Quantitative Analysis</sub>
</p>
