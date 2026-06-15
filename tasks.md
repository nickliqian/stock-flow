# Stock Flow — 任务清单

## 阶段 1: 项目初始化
- [ ] 1.1 创建项目目录结构（backend/ frontend/）
- [ ] 1.2 安装 Python 依赖（FastAPI, SQLAlchemy, tushare, pandas, apscheduler）
- [ ] 1.3 安装前端依赖（React, Vite, ECharts, axios）
- [ ] 1.4 创建 TuShare 密钥配置

## 阶段 2: 后端核心
- [ ] 2.1 数据模型（models.py）— 6张表
- [ ] 2.2 TuShare 客户端（clients/tushare.py）
- [ ] 2.3 缓存服务（cache.py）
- [ ] 2.4 数据服务（services/market.py, sector.py, stock.py）
- [ ] 2.5 API 路由（routes/market.py, sector.py, stock.py）
- [ ] 2.6 FastAPI 主入口（main.py）
- [ ] 2.7 定时调度（scheduler.py）
- [ ] 2.8 种子数据（seed.py）

## 阶段 3: 前端
- [ ] 3.1 Vite + React 项目初始化
- [ ] 3.2 API 服务层（services/api.js）
- [ ] 3.3 工具函数（utils/format.js）
- [ ] 3.4 通用组件（FundCard, TrendChart, SectorTable, StockSearch, Pagination）
- [ ] 3.5 页面组件（MarketOverview, SectorFlow, StockFlow）
- [ ] 3.6 H5 响应式样式
- [ ] 3.7 前端构建

## 阶段 4: 集成 & 部署
- [ ] 4.1 数据库初始化脚本
- [ ] 4.2 后端启动 & API 验证
- [ ] 4.3 前端代理配置（Nginx / Vite proxy）
- [ ] 4.4 端到端测试
- [ ] 4.5 部署到 8080 端口

## 阶段 5: 测试
- [ ] 5.1 单元测试（核心业务逻辑）
- [ ] 5.2 集成测试（API 端点）
- [ ] 5.3 性能验证
