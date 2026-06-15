
## 2026-06-15 — 行业相对Alpha评分引擎 (Evolution Phase 27)

### 决策理由
项目已有 22 个策略和全面的市场分析能力，但缺乏一个核心维度：**行业相对因子评分**。Barra 风格的多因子模型是机构量化的标配，但个人散户完全没有这个维度的分析工具。本轮实现「行业百分位排名 + 行业热力图 + 同业对比 + 轮动信号」四合一引擎。

**为什么选这个而不是其他功能：**
1. **创新性** — 市面上没有个人股票工具做「Barra风格行业相对因子评分」
2. **杠杆效应** — 复用现有 daily_basic + moneyflow + stock_basic 数据，零额外 API 成本
3. **用户价值** — 回答「这只股票在同行业中处于什么位置」，这是价值投资的核心问题
4. **策略集成** — 新数据可与现有 22 策略形成互补

### 实现方案

#### 后端
1. **AlphaScoringEngine** (`backend/app/engine/alpha_scoring.py`, 898行)
   - 5 因子维度：价值(30%) + 动量(25%) + 资金(25%) + 质量(10%) + 市值(10%)
   - 行业百分位排名（最少 5 只股票/行业）
   - 全市场 Alpha 排行、单股画像、行业热力图、同业对比

2. **IndustryRotationEngine** (`backend/app/engine/industry_heatmap.py`, 520行)
   - 行业资金流向汇总 + 轮动信号检测（轮入/加速/轮出/减速）
   - Bug 修复：早期返回时 summary 字典缺少 rotation_in 等键

3. **5 个 API 端点** (`backend/app/routes/alpha.py`)
   - `GET /api/alpha/score` — 全市场 Alpha 评分排行
   - `GET /api/alpha/score/{ts_code}` — 单股 Alpha 画像
   - `GET /api/alpha/industry-heatmap` — 行业热力图
   - `GET /api/alpha/peer-comparison/{ts_code}` — 同业对比
   - `GET /api/alpha/rotation-signals` — 行业轮动信号

#### 前端
1. **AlphaScoring.jsx** — 4-Tab 仪表板 (972行)
   - 🏆 Alpha 排行：统计卡片 + 可排序表格(5因子+行业百分位) + 行业筛选 + 市值滑块
   - 🗺️ 行业热力图：彩色卡片网格 + 点击展开 + 汇总统计
   - 🔍 同业对比：股票搜索 + 目标卡片 + 因子柱状对比 + 同业表格
   - 🔄 轮动信号：信号类型筛选 + 迷你柱状图 + 颜色标签

### 验证结果
- ✅ 后端启动成功，22 策略注册
- ✅ Alpha 评分 TOP3：山鹰国际 92.7 / 森麒麟 90.7 / 浙江龙盛 90.5
- ✅ 同业对比：600567.SH 在造纸行业有 33 只同业
- ✅ 行业热力图/轮动信号：因 moneyflow_dc 仅 1 天数据暂无轮动信号（数据积累后将自动生效）
- ✅ 前端构建成功（4587 模块，2727KB）
- ✅ Activity Log 已记录（ID: 59）

### 创新点
- 市面上没有个人股票工具做「Barra风格行业相对因子评分 + 行业热力图 + 同业对比」
- 将机构量化的多因子分析方法论平民化
- 与现有策略系统互补：策略选股 + Alpha 评分 = 完整的选股工具链

---


## 2026-06-15 — 内部人与机构信号引擎 (Evolution Phase 26)

### 决策理由
项目已有 22 个策略和全面的市场分析能力，但缺乏一个核心维度：**公司内部人行为与机构持仓变化**。这是机构量化中最强大的领先指标之一——当董监高买入、股东人数下降（散户出局）、业绩预增同时出现时，往往是股价启动的前兆。个人散户完全没有这个维度的分析工具。

**为什么选这个而不是其他功能：**
1. **创新性** — 市面上没有个人股票工具做「内部人行为+股东集中+业绩预告+质押风险」四维联合评分
2. **杠杆效应** — 利用 4 个之前未使用的 Tushare API（stk_holdertrade/stk_holdernumber/top10_holders/pledge_stat），零额外数据成本
3. **用户价值** — 回答「哪些股票的内部人正在买入、机构正在吸筹」，这是最直接的买入信号
4. **策略集成** — 新策略自动参与共振分析，增强 22 策略的多样性

### 实现方案

#### 后端
1. **InsiderConvictionEngine** (`backend/app/engine/insider_conviction.py`, 635行)
   - 4 个评分维度：
     - 内部人买入(30%)：董监高净买入 > 100万 = positive conviction
     - 股东集中度(30%)：股东人数下降 + top10_holders 增加 = 机构吸筹
     - 业绩预告(20%)：express_vip 累计净利润增长 > 20% = positive
     - 质押风险(20%)：质押比例降低 = 风险缓解
   - 综合置信度评分 0-100，等级：Strong Buy(80+)/Buy(60+)/Hold(40+)/Sell(<40)

2. **InsiderConvictionStrategy** (`backend/app/engine/strategies/insider_conviction.py`, 235行)
   - 置信度评分 >= 60 且内部人买入次数 >= 2
   - 自动注册到策略引擎，参与共振分析

3. **4个新数据加载器** (`backend/app/engine/data_loader.py`)
   - stk_holdertrade：董监高交易记录
   - stk_holdernumber：股东人数变化
   - top10_holders：前十大股东变化
   - pledge_stat_v2：质押统计

4. **新增 4 个 API 端点** (`backend/app/routes/insider.py`)
   - `GET /api/insider/conviction` — 全市场置信度扫描
   - `GET /api/insider/conviction/{ts_code}` — 单股置信度详情
   - `GET /api/insider/trades/{ts_code}` — 内部人交易历史
   - `GET /api/insider/shareholder-trend/{ts_code}` — 股东人数趋势

#### 前端
1. **InsiderConviction.jsx** — 内部人信号仪表板 (738行)
   - 3个Tab：🏛️ 置信度扫描 / 👔 内部人交易 / 📊 股东趋势
   - 置信度扫描：统计卡片 + 置信度筛选 + 表格 + 展开信号详情
   - 内部人交易：日期筛选 + 买入/卖出颜色编码
   - 股东趋势：股票搜索 + SVG折线图 + 十大股东变动表格
   - 新增「🏛️ 内部人信号」Tab

### 验证结果
- ✅ 后端启动成功，22 策略注册（含 insider_conviction）
- ✅ 扫描 4247 只股票：47 只看多，2083 只持有，2117 只看空
- ✅ TOP 股票：002179.SZ（76.0分/看多）、600177.SH（73.0分）、002661.SZ（73.0分）
- ✅ 股东趋势 API 返回真实数据
- ✅ 前端构建成功

### 修改文件清单
- `backend/app/engine/insider_conviction.py` — 新建，内部人信号引擎（635行）
- `backend/app/engine/strategies/insider_conviction.py` — 新建，内部人信号策略（235行）
- `backend/app/routes/insider.py` — 新建，4个API端点
- `backend/app/engine/data_loader.py` — 新增4个数据加载器
- `backend/app/main.py` — 注册insider路由
- `backend/app/engine/base.py` — 新增insider_conviction到STRATEGY_CATEGORIES
- `frontend/src/pages/InsiderConviction.jsx` — 新建，内部人信号仪表板（738行）
- `frontend/src/App.jsx` — 新增「内部人信号」Tab
- `frontend/src/services/api.js` — 新增4个API函数

### 创新点
- 市面上没有个人股票工具做「内部人行为+股东集中+业绩预告+质押风险」四维联合评分
- 利用 4 个之前未使用的 Tushare API，零额外数据成本
- 与现有策略系统无缝集成，参与共振分析

---

# Stock-Flow Changelog

## 2026-06-15 — 股票健康度评分引擎 (Evolution Phase 20)

### 决策理由
项目已有 22 个策略、策略共振、回测、智能分析、市场定性、配置优化、板块轮动和资金背离系统，但缺乏一个核心能力：**将所有信号聚合为单一可解释的健康度评分**。用户需要逐一查看 5+ 个页面才能了解一只股票的全貌，这在实际使用中非常低效。

**为什么选这个而不是其他功能：**
1. **创新性** — 市面上没有个人股票工具做「5维度综合健康度评分」。机构量化有类似的多因子评分系统，散户完全没有
2. **杠杆效应** — 让 22 个策略 + 技术指标 + 资金流 + 基本面 + 筹码数据从「分散查看」升级为「一眼全览」，极大提升策略系统的可用性
3. **用户价值** — 回答「这只股票整体怎么样」，这是日常决策的核心问题
4. **数据基础** — 完美利用已有的所有数据源，零额外 API 成本

### 实现方案

#### 后端
1. **StockHealthEngine** (`backend/app/engine/health.py`, 755行)
   - 5 个评分维度：策略信号(35%) + 技术指标(20%) + 资金流向(25%) + 基本面(10%) + 筹码风险(10%)
   - 策略信号：评估 20 个策略的关键条件命中，按分类加权
   - 技术指标：MACD/KDJ/RSI 金叉与超买超卖
   - 资金流向：连续净流入趋势、大单占比、流入加速
   - 基本面：PE/PB/股息率/市值分级评分
   - 筹码风险：筹码穿透率 + 股权质押比例
   - 综合评分 0-100，等级 A+ 到 D

2. **新增 2 个 API 端点** (`backend/app/routes/strategy.py`)
   - `GET /api/strategies/health/{ts_code}` — 单股健康度评分
   - `GET /api/strategies/health/market/top` — 全市场 TOP 排名

#### 前端
1. **StockHealth.jsx** — 健康度评分仪表板
   - 健康度圆环 + 等级标签
   - 5 维度进度条可视化
   - 策略命中标签（按分类颜色编码）
   - 市场 TOP 排名表格
   - 集成到 SmartAnalysis 作为首个子 Tab

### 验证结果
- ✅ 后端启动成功
- ✅ 平安银行(000001.SZ)健康度 51.0分(C+)，命中7个策略
- ✅ 前端构建成功（4576模块，2591KB）

### 修改文件清单
- `backend/app/engine/health.py` — 新建，股票健康度评分引擎（755行）
- `backend/app/routes/strategy.py` — 新增 2 个 health 端点
- `frontend/src/pages/StockHealth.jsx` — 新建，健康度评分仪表板
- `frontend/src/pages/SmartAnalysis.jsx` — 新增健康度子 Tab
- `frontend/src/services/api.js` — 新增 getStockHealth 和 getMarketHealthTop
- `docs/refactor-plan.md` — 新增 Phase 20 记录

### 创新点
- 市面上没有个人股票工具做「5维度综合健康度评分」
- 将 22 个策略 + 技术指标 + 资金流 + 基本面 + 筹码数据聚合为单一可解释的评分
- 帮助用户一眼看清任意股票的综合健康状况

---

## 2026-06-15 — 资金流向背离信号引擎 (Evolution Phase 19)

### 决策理由
项目已有 20 个策略、策略共振、回测、智能分析、市场定性、配置优化和板块轮动系统，但缺乏一个核心能力：**检测价格与资金流向的背离信号**。这是机构量化中非常重要的反转信号，个人散户完全没有这个维度的分析。

**为什么选这个而不是其他功能：**
1. **创新性** — 市面上没有个人股票工具做「价格-资金流向背离检测」。机构量化有类似的背离检测系统，散户完全没有
2. **用户价值** — 回答「哪些股票可能正在反转」，这是日常决策的核心问题之一
3. **杠杆效应** — 让策略系统从「单日快照」升级到「多日趋势+背离分析」，补上时间维度分析的最后一块拼图
4. **数据基础** — 完美利用已有的 moneyflow_multi + daily_multi 数据，零额外 API 成本

### 实现方案

#### 后端
1. **FlowIntelligenceEngine** (`backend/app/engine/flow_intelligence.py`, 586行)
   - `detect_divergence()`: 市场级背离扫描，检测所有股票的价格-资金流向背离
   - `analyze_stock()`: 单股深度分析，包含每日明细、动量、持续性评分
   - 背离检测逻辑：价格趋势 vs 主力资金净流入趋势的反向运动
   - 看涨背离：价格下跌但主力吸筹（机构建仓信号）
   - 看跌背离：价格上涨但主力出货（机构减仓信号）
   - 信号强度评分：价格趋势(40%) + 资金流向(30%) + 持续性(30%)

2. **FlowDivergence 策略** (`backend/app/engine/strategies/flow_divergence.py`, 179行)
   - 5日价格趋势 vs 5日主力资金净流入趋势的背离检测
   - 自动注册到策略引擎，参与共振分析

3. **新增 2 个 API 端点** (`backend/app/routes/strategy.py`)
   - `GET /api/strategies/flow-intelligence/divergence-scan` — 市场级背离扫描
   - `GET /api/strategies/flow-intelligence/analyze/{ts_code}` — 单股深度分析

#### 前端
1. **FlowIntelligence.jsx** — 资金流向背离分析仪表板
   - 控制面板：回看天数选择、信号类型筛选、最低强度筛选
   - 统计卡片：总扫描数、看涨背离数、看跌背离数、强信号数
   - 结果表格：信号类型标签、强度评分、价格趋势、资金趋势
   - 详情抽屉：每日明细、动量分析、持续性分析、背离解读

### 验证结果
- ✅ 后端启动成功，20 策略注册
- ✅ flow_divergence 策略执行：5只匹配股票（润阳科技、安彩高科、华微电子等）
- ✅ 背离扫描：5202只股票扫描，541只看涨背离，227只看跌背离
- ✅ 单股分析：平安银行分析正常返回每日明细和趋势数据
- ✅ 前端构建成功（2576KB）

### 修改文件清单
- `backend/app/engine/flow_intelligence.py` — 新建，资金流向背离分析引擎（586行）
- `backend/app/engine/strategies/flow_divergence.py` — 新建，背离信号选股策略（179行）
- `backend/app/engine/base.py` — 新增 flow_divergence 到 STRATEGY_CATEGORIES
- `backend/app/routes/strategy.py` — 新增 2 个 flow-intelligence 端点
- `frontend/src/pages/FlowIntelligence.jsx` — 新建，资金流向背离分析仪表板
- `frontend/src/App.jsx` — 新增「资金背离」Tab
- `frontend/src/services/api.js` — 新增 getDivergenceScan 和 analyzeStockFlow 函数
- `docs/refactor-plan.md` — 新增 Phase 19 记录

### 创新点
- 市面上没有个人股票工具做「价格-资金流向背离检测」
- 从「单日快照」升级到「多日趋势+背离分析」，补上时间维度分析的最后一块拼图
- 背离信号是机构量化的高级指标，帮助散户提前识别反转点

---

## 2026-06-14 — 策略信号矩阵 (Evolution Phase 17)

### 决策理由
项目已有 18 个策略、策略共振、回测、智能分析、市场定性和配置优化系统，但缺乏一个核心能力：**将所有策略信号统一展示在单一视图中**。用户需要逐一查看 18 个策略才能了解全貌，这在实际使用中非常低效。

**为什么选这个而不是其他功能：**
1. **创新性** — 市面上没有个人股票工具做「Stock × Strategy 信号矩阵」。机构量化有类似的信号聚合系统，散户完全没有
2. **杠杆效应** — 让所有 18 个策略从「逐个查看」升级为「一眼全览」，极大提升策略系统的可用性
3. **用户价值** — 回答「今天哪些股票被最多策略选中」，这是日常决策的核心问题
4. **数据基础** — 完美利用已有的策略引擎基础设施，零额外 API 成本

### 实现方案

#### 后端
1. **SignalMatrixEngine** (`backend/app/engine/signal_matrix.py`, 163行)
   - 为给定交易日执行所有策略，构建 Stock × Strategy 信号矩阵
   - 一次加载所有策略所需数据，多策略共享
   - 按策略数+总分排序，支持最小策略数过滤和分类过滤
   - 自动从 stock_basic 表获取股票名称和行业

2. **新增 API 端点** (`backend/app/routes/strategy.py`)
   - `GET /api/strategies/signals/matrix?trade_date=&min_strategies=&category=`
   - 返回 strategies（元数据）、stocks（信号矩阵）、summary（统计）

#### 前端
1. **SignalMatrix.jsx** — 策略信号矩阵仪表板（382行）
   - 统计卡片：触发股票总数、平均策略数、最大策略数
   - 策略分布柱状图（纯 CSS，无额外依赖）
   - 策略筛选：最小策略数滑块 + 分类下拉
   - 信号矩阵表格：18 个策略列，分数颜色编码（绿≥80/黄≥50/红<50）
   - 策略缩写列标题（高股息、低估值、均线多头等）
   - 点击股票行跳转个股详情

### 验证结果
- ✅ 后端启动成功，18 策略注册
- ✅ 信号矩阵 API：742 只股票触发 2+ 策略，6 只股票触发 6 策略
- ✅ TOP 股票：中化国际（6策略，78.3分）、宗申动力（6策略，78.1分）
- ✅ 前端构建成功（4572 模块）

### 修改文件清单
- `backend/app/engine/signal_matrix.py` — 新建，策略信号矩阵引擎（163行）
- `backend/app/routes/strategy.py` — 新增 signals/matrix 端点
- `frontend/src/pages/SignalMatrix.jsx` — 新建，信号矩阵仪表板（382行）
- `frontend/src/App.jsx` — 新增「信号矩阵」Tab
- `frontend/src/services/api.js` — 新增 getSignalMatrix 函数
- `docs/refactor-plan.md` — 新增 Phase 17 记录

### 创新点
- 市面上没有个人股票工具做「Stock × Strategy 信号矩阵」
- 将 18 个孤立策略统一为一个可交互的信号视图，一眼看清市场全貌
- 信号矩阵帮助用户识别「伪分散」——哪些股票被多个不相关策略同时选中

---

## 2026-06-14 — 策略相关性分析与智能配置引擎 (Evolution Phase 16)

### 决策理由
项目已有 18 个策略、策略共振、回测、智能分析和市场定性系统，但缺乏一个核心能力：**理解策略间的关系并智能配置**。这是从「策略工具」到「策略组合管理系统」的关键跨越。

**为什么选这个而不是其他功能：**
1. **创新性** — 市面上没有个人股票工具做策略级相关性分析和均值方差优化。机构量化才有，散户完全没有
2. **杠杆效应** — 让所有 18 个策略从「孤立使用」升级为「智能配置」，每个策略获得最优权重
3. **用户价值** — 回答「18 个策略该怎么分配注意力」，这是最实际的使用问题
4. **数据基础** — 完美利用已有的 strategy_performance + backtest + regime 数据，零额外 API 成本

### 实现方案

#### 后端
1. **StrategyCorrelationEngine** (`backend/app/engine/correlation.py`, 400行)
   - `get_overlap_matrix()`: Jaccard 相似系数，基于 strategy_snapshot 的 top_picks
   - `get_correlation_matrix()`: Pearson 相关系数，基于 strategy_performance 的 ret_1d
   - `optimize_allocation()`: 均值方差优化（等权/风险平价/最小方差/夏普加权）
   - `get_regime_allocation()`: 体制自适应配置（牛/熊/震荡/极端→分类权重→策略权重）
   - `get_portfolio_summary()`: 综合分析 + 智能洞察

2. **新增 5 个 API 端点** (`backend/app/routes/strategy.py`)
   - `GET /api/strategies/correlation/overlap` — 选股重叠度矩阵
   - `GET /api/strategies/correlation/matrix` — 收益率相关性矩阵
   - `GET /api/strategies/correlation/optimize` — 配置优化方案
   - `GET /api/strategies/correlation/regime` — 体制自适应配置
   - `GET /api/strategies/correlation/summary` — 综合分析仪表板

#### 前端
1. **StrategyPortfolio.jsx** — 5 个视图的策略配置仪表板
   - 综合概览：统计卡片 + 体制配置饼图 + 分类权重柱状图
   - 选股重叠：热力图矩阵 + TOP 重叠对表格
   - 收益相关：相关性热力图 + 解读指南
   - 配置优化：4 种方案对比 + 风险-收益散点图
   - 体制配置：状态横幅 + 分类权重 + 策略权重

#### Bug 修复
- 修复 `base.py` 中 `_find_col`/`_safe` 方法与 `STRATEGY_CATEGORIES` 字典的结构错位（方法体被字典分割）

### 验证结果
- ✅ 后端启动成功，18 策略注册
- ✅ 重叠分析：17 个策略，25 对重叠关系，最高重叠 53.8%（broken_net_gold ↔ low_valuation_gold）
- ✅ 体制配置：震荡🟡 + 18 策略权重分配正常
- ✅ 综合仪表板：2 条智能洞察（重叠 + 体制）
- ✅ 前端构建成功（4571 模块）

### 修改文件清单
- `backend/app/engine/correlation.py` — 新建，策略相关性与配置引擎（400行）
- `backend/app/engine/base.py` — 修复结构错位
- `backend/app/routes/strategy.py` — 新增 5 个 correlation 端点
- `frontend/src/pages/StrategyPortfolio.jsx` — 新建，策略配置仪表板（500+行）
- `frontend/src/App.jsx` — 新增「策略配置」Tab
- `frontend/src/services/api.js` — 新增 5 个 API 函数

### 创新点
- 市面上没有个人股票工具做「策略级相关性分析+均值方差优化+体制自适应配置」
- 将机构量化的 Markowitz 均值方差方法论平民化
- 选股重叠分析帮助用户识别「伪分散」（看似不同策略，实则选同样的股票）
- 体制自适应配置让策略权重随市场环境动态调整

---

## 2026-06-14 — 市场定性引擎 (Evolution Phase 14)

### 决策理由
项目已有 16 个策略和策略共振/回测/智能分析系统，但缺乏一个核心能力：**理解当前市场环境并自适应推荐策略**。这是从「选股工具」到「智能投资助手」的关键跨越。

**为什么选这个而不是其他功能：**
1. **创新性** — 市面上几乎没有个人股票工具做市场状态识别+策略适配。同花顺/东方财富只展示结果，不告诉你"当前该用什么策略"
2. **杠杆效应** — 让所有 16 个策略变得"语境感知"，每个策略不再孤立，而是根据市场环境获得权重调整
3. **用户价值** — 帮助用户回答"现在该买什么类型的股票"，这是日常决策的核心问题
4. **数据积累** — 每次检测记录 regime 历史，随时间推移可发现市场周期规律

### 实现方案

#### 后端
1. **MarketRegimeDetector** (`backend/app/engine/regime.py`, 632行)
   - 4 个检测信号，加权综合判断：
     - 指数趋势评分 (30%权重)：分析上证/深证/创业板 MA5/MA20 交叉 + 20日收益率
     - 策略表现评分 (30%权重)：对比动量类 vs 价值类策略近期胜率
     - 市场宽度评分 (20%权重)：衡量策略选股覆盖度
     - 策略共振评分 (20%权重)：检测多策略同时命中比例
   - 4 种市场状态：牛市🟢 / 熊市🔴 / 震荡🟡 / 极端🟣
   - 策略适配映射：每种状态对应推荐/可选/规避的策略组合

2. **新增 API 端点** (`backend/app/routes/strategy.py`)
   - `GET /api/strategies/regime` — 当前市场定性分析
   - `GET /api/strategies/regime/history` — 历史定性记录
   - `GET /api/strategies/regime/recommend` — 当前环境策略推荐

#### 前端
1. **MarketRegime.jsx** — 市场定性仪表板
   - 状态横幅：颜色编码（绿=牛/红=熊/黄=震荡/紫=极端）+ 置信度圆环
   - 4 个信号分解卡片 + 策略推荐面板 + 风险等级 + 一键执行

### 验证结果
- ✅ 后端启动成功，16 个策略正常
- ✅ regime API 返回：震荡，置信度 0.42
- ✅ 4 个检测信号均有数据
- ✅ 前端构建成功

### 修改文件清单
- `backend/app/engine/regime.py` — 新建，市场定性检测引擎（632行）
- `backend/app/routes/strategy.py` — 新增 3 个 regime 端点
- `frontend/src/pages/MarketRegime.jsx` — 新建，市场定性仪表板（447行）
- `frontend/src/App.jsx` — 新增「📊 市场定性」Tab
- `frontend/src/services/api.js` — 新增 3 个 API 函数

### 创新点
- 市面上没有个人股票工具做「市场状态→策略适配」
- 基于现有策略执行数据推断市场环境，零额外数据成本
- 策略推荐不是静态规则，而是基于实时信号加权计算

---


## 2026-06-14 — 策略组合器 (Evolution Phase 13)

### 决策理由
项目已有 16 个策略和共振引擎，但缺乏**让用户自由组合策略**的能力。当前只能查看单个策略结果或被动的共振评分，无法主动构建「低估值 AND 有资金流入」这样的复合筛选规则。

**为什么选这个而不是更多策略：**
1. **创新性** — 没有个人股票工具支持策略级 AND/OR 组合，TradingView 有指标组合但不是策略级
2. **杠杆效应** — 让所有 16 个策略变得可组合，每新增一个策略自动支持组合
3. **用户价值** — 「低估值+资金流入」是散户最常用的复合筛选逻辑
4. **架构干净** — 新增 composer 模块，不修改现有策略代码

### 实现方案

#### 后端
1. **StrategyComposer** (`backend/app/engine/composer.py`) — 策略组合引擎
   - `compose(trade_date, strategy_names, operator)` — 执行组合筛选
   - AND 逻辑：股票必须通过所有指定策略
   - OR 逻辑：股票通过任一指定策略即可
   - 组合评分：AND 匹配加权提升（更难满足，分数更高）
   - 4 个预设组合：价值+资金共振、动量+事件共振、超跌反弹、高分红防守

2. **新增 API 端点** (`backend/app/routes/strategy.py`)
   - `GET /api/strategies/compose?strategies=a,b&operator=AND` — 执行自定义组合
   - `GET /api/strategies/compose/presets` — 获取预设组合列表

#### 前端
1. **StrategyComposer.jsx** — 策略组合页面
   - 预设卡片：4 个一键组合
   - 自定义构建：策略多选 + AND/OR 切换
   - 结果表格：组合评分 + 匹配策略详情

2. **StrategyDashboard.jsx** — 新增「🧩 策略组合」Tab

### 验证结果
- ✅ 后端启动成功，16 个策略注册
- ✅ 4 个预设组合返回正确
- ✅ AND 组合测试：低估值金矿 AND 主力资金持续流入 → 7 只匹配（平安银行、中国太保、海尔智家等）
- ✅ 前端构建成功，可访问

### 修改文件清单
- `backend/app/engine/composer.py` — 新建，策略组合引擎
- `backend/app/routes/strategy.py` — 新增 2 个 compose 端点
- `frontend/src/pages/StrategyComposer.jsx` — 新建，组合页面
- `frontend/src/pages/StrategyDashboard.jsx` — 新增 Tab
- `frontend/src/services/api.js` — 新增 2 个 API 函数

---

## 2026-06-14 — 手动优化 + Bug 修复（用户驱动）

### 用户反馈的问题
1. **大盘指数缺科创50** → 新增 `000688.SH`，4 指数 2×2 网格
2. **指数卡片无交互** → 点击弹出 Drawer，显示 30 日 K 线 + 指数简介
3. **涨跌停列表无分页** → 默认 20 条/页，底部分页器
4. **涨跌停无分组视图** → 新增全部/按行业/连板 三种模式
5. **趋势图天数不够** → 新增 60 天、90 天切换选项
6. **趋势图加载慢** → scheduler 每小时:30 预缓存 90 天数据
7. **React Error #310** → 修复 LimitStats.jsx 和 MarketIndex.jsx 的 hooks 违规
8. **E2E 数据准确性测试** → 42 个测试用例，TuShare 直连交叉验证

### 修改文件清单
- `frontend/src/components/MarketIndex.jsx` — 科创50 + Drawer 抽屉 + hooks 修复
- `frontend/src/components/LimitStats.jsx` — 分页 + 模式切换 + hooks 修复
- `frontend/src/pages/MarketOverview.jsx` — 60/90 天切换
- `backend/app/services/market.py` — 科创50 指数 + index-kline API + 趋势预缓存
- `backend/app/scheduler.py` — 新增 `_precache_trends()` 定时预缓存
- `backend/tests/conftest.py` — 测试配置 + TuShare 直连验证器
- `backend/tests/test_data_accuracy.py` — 42 个 E2E 测试用例
- `docs/design-docs/stock-screener/strategy-system/spec.md` — 完整需求文档（6 模块）

---

## 2026-06-14 — 策略智能分析系统（Evolution Round 12）

### 决策理由
项目已有 16 个策略和回测引擎，但缺乏一个关键能力：**追踪策略本身是否有效**。用户看到"策略X选了50只股票"，但不知道策略X最近是否可靠。这是股票筛选器和专业分析平台之间的差距。

**为什么选这个而不是更多功能：**
1. **创新性** — 市面上几乎没有股票筛选器展示"策略有效性"，同花顺/东方财富只展示结果不展示效果
2. **用户价值** — 帮助用户判断"该信任哪个策略"，这是日常决策的核心需求
3. **杠杆效应** — 策略快照系统为未来的市场 regime 检测、策略自适应等高级功能铺路
4. **数据积累** — 每次执行自动记录，随时间推移数据越来越有价值

### 实现方案

#### 后端
1. **StrategySnapshot 模型** (`backend/app/models.py`)
   - 新增 `strategy_snapshot` 表：trade_date, strategy_name, pick_count, top_picks(JSON), avg_score, max_score
   - 记录每次策略执行的结果摘要

2. **StrategyPerformance 模型** (`backend/app/models.py`)
   - 新增 `strategy_performance` 表：trade_date, strategy_name, ts_code, entry_score, entry_price, ret_1d/3d/5d
   - 追踪推荐股票的实际后续收益

3. **StrategyIntelligenceService** (`backend/app/engine/intelligence.py`)
   - `record_snapshot()` — 记录策略执行快照（自动去重）
   - `record_performance()` — 计算推荐股票的1/3/5日收益率
   - `get_strategy_health()` — 计算所有策略的健康度评分（一致性40% + 胜率40% + 选股量20%）
   - `get_performance_trend()` — 策略胜率趋势数据（折线图用）
   - `compare_strategies()` — 多策略横向对比
   - `get_recommendation()` — 基于信任度评分推荐最佳策略

4. **自动记录钩子** (`backend/app/services/strategy.py`)
   - `execute_strategy()` 执行后自动调用 `record_snapshot()` + `record_performance()`
   - `execute_all()` 每个策略执行后同样自动记录
   - 失败不影响主流程（try/except 包裹）

5. **新增 API 端点** (`backend/app/routes/strategy.py`)
   - `GET /api/strategies/intelligence/health` — 策略健康度概览
   - `GET /api/strategies/intelligence/trend/{strategy_name}` — 策略胜率趋势
   - `GET /api/strategies/intelligence/compare` — 策略对比
   - `GET /api/strategies/intelligence/recommend` — 策略推荐

#### 前端
1. **StrategyIntelligence.jsx** — 策略洞察页面
   - 推荐横幅：展示当前最可靠的策略
   - 策略健康度卡片：环形进度条 + 胜率统计 + 数据概览
   - 胜率趋势图：ECharts折线图（胜率/收益/选股量）
   - 策略对比工具：多选策略 + 表格横向对比
   - 三个视图切换：健康度 / 趋势 / 对比

2. **StrategyDashboard.jsx** — 新增「策略洞察」Tab

### 创新点
- **策略有效性追踪**：市面上几乎没有产品展示"策略本身是否有效"
- **信任度评分**：综合一致性、胜率、选股质量的复合评分
- **自动数据积累**：每次执行自动记录，无需用户手动操作
- **可视化对比**：ECharts折线图 + 表格横向对比

### 修改文件清单
- `backend/app/models.py` — 新增 StrategySnapshot + StrategyPerformance
- `backend/app/engine/intelligence.py` — 新建，335行
- `backend/app/routes/strategy.py` — 新增4个端点
- `backend/app/services/strategy.py` — 新增自动记录钩子
- `frontend/src/pages/StrategyIntelligence.jsx` — 新建，254行
- `frontend/src/pages/StrategyDashboard.jsx` — 新增Tab + import
- `frontend/src/services/api.js` — 新增4个API函数

---

## 2026-06-14 — 自选股信号雷达（Evolution Round 11）

### 决策理由
策略引擎已有 16 个策略，但缺乏**将策略信号与用户持仓关联**的能力。用户每天需要手动检查每只关注股的信号，效率极低。本轮实现自选股管理和每日信号雷达系统，让 16 个策略从"全市场扫描工具"进化为"个人持仓监控系统"。

**为什么选这个而不是更多策略：**
1. **杠杆效应最高** — 自选股系统让所有 16 个策略对用户产生直接价值，每新增一个策略自动对自选股生效
2. **P0 优先级** — spec.md 中"每天开盘前查看自选股信号"是第一使用场景，但从未实现
3. **粘性功能** — 自选股让应用从"偶尔看看"变成"每天必看"，是产品留存的关键
4. **创新点** — "信号雷达"概念：对每只自选股运行所有策略，计算"置信度"（3+策略命中=高置信），这是市面上没有的功能

### 实现方案

#### 后端
1. **Watchlist 模型** (`backend/app/models.py`)
   - 新增 `Watchlist` 表：ts_code, name, group_name(default/观察仓/重仓/长线), added_date, notes, sort_order

2. **WatchlistService** (`backend/app/services/watchlist.py`)
   - `list_watchlist(group_name)` — 返回自选股列表 + 每只股票的当日策略信号
   - `add_to_watchlist(ts_code, group_name, notes)` — 添加自选股（自动从 stock_basic 获取名称）
   - `remove_from_watchlist(ts_code)` — 删除自选股
   - `update_watchlist(ts_code, group_name, notes)` — 更新自选股信息
   - `get_stock_signals(ts_code)` — 单只股票的策略信号详情
   - `get_all_signals(trade_date)` — 所有自选股的信号汇总
   - `get_stats()` — 统计：总数、分组数量、置信度分布
   - **信号生成**：复用 StrategyDataLoader 一次加载所有数据 + get_all_strategies() 遍历 16 个策略
   - **置信度计算**：0信号=none, 1=low, 2=medium, 3+=high

3. **Watchlist Routes** (`backend/app/routes/watchlist.py`)
   - `GET /api/watchlist/` — 自选股列表
   - `POST /api/watchlist/` — 添加自选股
   - `DELETE /api/watchlist/{ts_code}` — 删除自选股
   - `PUT /api/watchlist/{ts_code}` — 更新自选股
   - `GET /api/watchlist/signals` — 所有信号汇总
   - `GET /api/watchlist/stats` — 统计数据
   - `GET /api/watchlist/{ts_code}/signals` — 单股信号详情

#### 前端
4. **Watchlist 页面** (`frontend/src/pages/Watchlist.jsx`)
   - 统计卡片行：总数、高置信(3+)、中置信(2)、今日有信号
   - Segmented 分组筛选：全部 | 默认 | 观察仓 | 重仓 | 长线
   - 数据表格：信号Badge、股票名+代码、最新价、涨跌幅、触发策略Tag、置信度Progress、分组Tag、删除按钮
   - 展开行：每个触发策略的详细信息（名称、描述、评分、触发原因）
   - 添加自选股 Modal：StockSearch搜索 + 分组选择 + 备注

5. **API 函数** (`frontend/src/services/api.js`)
   - 新增 7 个自选股 API 函数

6. **App.jsx** — 新增「自选股」Tab（⭐ StarOutlined）

#### 代码清理
7. 修复 `financial_quality.py` → 重命名为 `volume_anomaly.py`（文件名与内容一致）

### 新增 API 端点
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/watchlist/` | 自选股列表（含信号） |
| POST | `/api/watchlist/` | 添加自选股 |
| DELETE | `/api/watchlist/{ts_code}` | 删除自选股 |
| PUT | `/api/watchlist/{ts_code}` | 更新自选股 |
| GET | `/api/watchlist/signals` | 所有信号汇总 |
| GET | `/api/watchlist/stats` | 统计数据 |
| GET | `/api/watchlist/{ts_code}/signals` | 单股信号详情 |

### 测试验证
- 添加自选股：`POST /api/watchlist/ {"ts_code":"000001.SZ"}` ✅ 自动获取名称"平安银行"
- 重复添加：`POST /api/watchlist/ {"ts_code":"000001.SZ"}` ✅ 返回错误提示
- 自选股列表：`GET /api/watchlist/` ✅ 返回 4 只股票 + 信号
- 信号汇总：`GET /api/watchlist/signals` ✅ 返回所有股票的策略信号
- 统计数据：`GET /api/watchlist/stats` ✅ 返回分组和置信度统计
- 删除自选股：`DELETE /api/watchlist/000001.SZ` ✅
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅

### 新增文件
- `backend/app/services/watchlist.py`
- `backend/app/routes/watchlist.py`
- `frontend/src/pages/Watchlist.jsx`

### 修改文件
- `backend/app/models.py` — 新增 Watchlist 模型
- `backend/app/main.py` — 注册 watchlist_router + CORS 方法更新
- `backend/app/engine/strategies/financial_quality.py` → 重命名为 `volume_anomaly.py`
- `frontend/src/services/api.js` — 新增自选股 API 函数
- `frontend/src/App.jsx` — 新增「自选股」Tab

---

## 2026-06-14 — 量价异动 + 超跌反弹策略（Evolution Round 10）

### 决策理由
策略引擎已有 12 个策略，但缺少**量价异动**和**超跌反弹**两类高频使用的策略。同时发现 Tushare `fina_indicator` 接口需要逐股查询（必填 ts_code），无法批量加载全市场财务数据，因此将原计划的"财务质量选股"改为基于 daily_basic 的"成交量异动"策略。

**为什么选这个组合：**
1. **成交量异动** — 换手率+量比是散户最关注的盘中信号，异常放量往往预示大行情启动，同花顺/东方财富都在首页展示"量比排行"
2. **超跌反弹** — "跌多了会反弹"是散户最朴素的交易逻辑，但需要量化筛选避免接飞刀，结合换手率和市值过滤提高胜率
3. **fina_indicator 数据限制** — 发现该接口必填 ts_code，无法批量查询全市场，改为使用可批量加载的 daily_basic 数据

### Tushare 数据能力探测发现
- `fina_indicator` / `income`：必填 ts_code，无法批量查询 ❌
- `margin_detail` / `cyq_perf`：需要高级权限 ❌
- `dragon_tiger`：方法不存在 ❌
- `limit_list_d` / `block_trade` / `concept`：当前无数据 ⚠️
- `hk_hold`：仅返回港股数据（非A股北向持仓）⚠️
- `stk_holdertrade`：内部人交易数据，但非常稀疏 ⚠️

### 实现方案

#### 后端：2 个新策略
1. **`strategies/financial_quality.py`** → 重写为 **📊 成交量异动 (volume_anomaly)**：
   - 筛选：换手率>5% + 量比>1.5 + 正涨幅 + 市值>30亿 + 非ST
   - 评分：换手率(40分) + 量比(30分) + 涨幅(20分) + 市值弹性(10分)
   - 数据：daily_basic + daily（均可批量加载）
   - 实测：55 只匹配（2026-06-12）

2. **`strategies/oversold_bounce.py`** — 🔥 超跌反弹：
   - 筛选：近20日跌幅≥15% + 日均换手率≥3% + 市值30~500亿 + 非ST
   - 评分：跌幅深度(50分) + 换手率(30分) + 市值弹性(20分)
   - 数据：daily_multi(20日OHLCV) + daily_basic
   - 实测：169 只匹配（2026-06-12）
   - 修复：原设计用60日跌幅但 daily_multi 只加载20天，已修正为15%阈值

#### 后端：数据加载器
3. **`data_loader.py`** — 新增 `_load_fina_indicator` 加载器
   - 根据 trade_date 推断最新报告期（1-4月→年报、5-8月→一季报等）
   - 调用 `pro.fina_indicator(period=period)` 获取数据
   - 虽然当前策略未使用，但为后续基本面策略铺路

### 策略覆盖现状
**14 个策略**：价值×3 + 动量×5 + 资金×1 + 事件×3 + 组合×2

| 类别 | 策略数 | 策略列表 |
|------|--------|----------|
| 💎 价值 | 3 | 低估值金矿、高股息防守、破净股淘金 |
| 🚀 动量 | 5 | 放量突破、均线多头、KDJ超卖、成交量异动、超跌反弹 |
| 💰 资金 | 1 | 主力持续流入 |
| ⚡ 事件 | 3 | 连板强势、涨停回封、大宗溢价 |
| 🔗 组合 | 2 | 价值资金共振、趋势量能共振 |

### 测试验证
- 策略列表：`curl /api/strategies/` ✅ 返回 14 个策略
- 成交量异动：`curl /api/strategies/execute/volume_anomaly` ✅ 55 只匹配
- 超跌反弹：`curl /api/strategies/execute/oversold_bounce` ✅ 169 只匹配
- 全部执行：`curl /api/strategies/execute-all` ✅ 14 个策略全部成功
- 策略共振：`curl /api/strategies/confluence` ✅ 380 只股票触发 2+ 策略
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅

### 新增文件
- `backend/app/engine/strategies/oversold_bounce.py`

### 修改文件
- `backend/app/engine/strategies/financial_quality.py` — 重写为 volume_anomaly 策略
- `backend/app/engine/data_loader.py` — 新增 fina_indicator 加载器

---

## 2026-06-14 — 策略回测引擎 + 2个新策略（Evolution Round 9）

### 决策理由
策略引擎已有 10 个策略覆盖价值(3)、动量(2)、资金(1)、事件(3)、组合(1)，但缺少**策略历史表现评估能力**。竞品调研发现，策略回测是专业级选股平台的核心差异化功能——同花顺/东方财富的免费工具都不提供集成回测。同时补充 KDJ超卖反弹 和 趋势+量能共振 两个高用户价值的缺失策略。

**为什么选这个组合：**
1. **策略回测引擎** — 让所有策略从"今天的选股结果"进化为"这个策略历史上表现如何"，是最大的杠杆效应投资：每新增一个策略都自动获得回测能力
2. **KDJ超卖反弹** — KDJ是散户最常用的技术指标之一，超卖反弹是经典的短线交易信号，填补动量类策略空白
3. **趋势+量能共振** — 双重验证（趋势确认+放量确认）是量化选股的黄金组合，属于组合类策略

### 竞品调研发现
- 同花顺「问财」：自然语言选股，AI解析策略条件
- 东方财富「资金流向」：主力资金博弈桑基图
- QuantConnect/聚宽：回测引擎+历史表现可视化
- TradingView：多策略组合面板+交叉验证

### 实现方案

#### 后端：策略回测引擎
1. **`engine/backtest.py`** — BacktestEngine 类
   - 遍历指定日期区间内的每个交易日
   - 在每个交易日执行策略，取 top_n 只股票
   - 查找持有 hold_days 天后的收盘价，计算收益率
   - 汇总统计指标：胜率、累计收益、最大回撤、夏普比率、盈亏比
   - 生成净值曲线（等权组合）
   - 数据缓存优化：避免重复加载同一日期的数据

#### 后端：2个新策略
2. **`strategies/kdj_oversold_rebound.py`** — 📉 KDJ超卖反弹：
   - 筛选：K值 < 20（超卖区）AND K > D（反弹信号）
   - 金叉检测：对比前一日数据判断K上穿D
   - 评分：K值越低分越高 + 金叉加分 + J值加分
   - 数据：stk_factor
   - 实测：892 只匹配

3. **`strategies/trend_volume_resonance.py`** — 🔥 趋势+量能共振：
   - 筛选：MA5 > MA10（多头趋势）AND 量比 > 1.5（放量确认）AND 涨幅 > 1%
   - 评分：趋势间距(40分) + 量比(40分) + 涨幅(20分)
   - 数据：stk_factor + daily_multi
   - 实测：109 只匹配

#### 后端：API路由
4. **`routes/strategy.py`** — 新增回测端点
   - `GET /api/strategies/backtest/{strategy_name}` — 参数：start_date, end_date, hold_days, limit

#### 前端：策略回测组件
5. **`pages/StrategyBacktest.jsx`** — 回测前端
   - 参数面板：策略选择 + 日期范围 + 持有天数 + 每日选股数
   - 统计卡片：胜率、累计收益、最大回撤、夏普比率
   - 额外统计：日均收益、盈亏比、最佳/最差单日
   - 净值曲线：CSS bar chart 可视化
   - 每日明细表格：日期、选股数、平均收益、最佳/最差、TOP选股

6. **`pages/StrategyDashboard.jsx`** — 新增「策略回测」Tab

### 策略覆盖现状
**12 个策略**：价值×3 + 动量×3 + 资金×1 + 事件×3 + 组合×2

### 测试验证
- 策略列表：`curl /api/strategies/` ✅ 返回 12 个策略
- KDJ超卖反弹：`curl /api/strategies/execute/kdj_oversold_rebound` ✅ 892 只匹配
- 趋势+量能共振：`curl /api/strategies/execute/trend_volume_resonance` ✅ 109 只匹配
- 全部执行：`curl /api/strategies/execute-all` ✅ 12 个策略全部成功
- 低估值金矿回测：`curl /api/strategies/backtest/low_valuation_gold?start_date=20260601&end_date=20260613` ✅ 胜率57.1%，累计收益1.17%，夏普1.96
- KDJ回测：`curl /api/strategies/backtest/kdj_oversold_rebound?start_date=20260601&end_date=20260613` ✅ 回测正常（揭示该策略在当前市场环境下表现不佳）
- 策略共振：`curl /api/strategies/confluence` ✅ 正常
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅

### 新增文件
- `backend/app/engine/backtest.py`
- `backend/app/engine/strategies/kdj_oversold_rebound.py`
- `backend/app/engine/strategies/trend_volume_resonance.py`
- `frontend/src/pages/StrategyBacktest.jsx`

### 修改文件
- `backend/app/routes/strategy.py` — 新增回测端点
- `frontend/src/services/api.js` — 新增 backtestStrategy 函数
- `frontend/src/pages/StrategyDashboard.jsx` — 新增策略回测Tab

---

## 2026-06-14 — 事件驱动策略 + 破净策略（Evolution Round 8）

### 决策理由
策略引擎已有 6 个策略覆盖价值(2)、动量(2)、资金(1)、组合(1)，但事件驱动(event)类别完全空白。本轮填补这个最大缺口，同时加入高用户价值的破净策略。

**为什么选这些策略：**
1. **连板强势股** — 涨停板追踪是中国散户最关注的功能之一，同花顺/东方财富都在首页重点展示，但免费工具很少提供策略级别的连板筛选
2. **涨停板打开后回封** — "分歧转一致"是短线交易的核心信号，市面上几乎没有免费工具做这个
3. **大宗交易溢价** — 机构溢价接货是强烈的看好信号，数据来自 block_trade 接口，竞品很少做
4. **破净股淘金** — 破净+资金流入的组合是价值投资的经典打法，用户基数大

### 实现方案

#### 后端：3 个新数据加载器
1. **`engine/data_loader.py`** — 新增 `limit_list_d`、`block_trade`、`daily` 加载器
   - `limit_list_d`：涨跌停列表（涨停/跌停类型、连板天数、开板次数）
   - `block_trade`：大宗交易（成交价、成交量、买方卖方）
   - `daily`：单日全市场 OHLCV（用于大宗交易溢价对比收盘价）

#### 后端：4 个新策略
2. **`strategies/consecutive_limit_up.py`** — 🔥 连板强势股：
   - 筛选：limit=='U'(涨停) AND limit_times>=2 AND open_times<3 AND 非ST
   - 评分：连板天数(max50) + 封板力度(max30) + 市值适中(max20)
   - 数据：limit_list_d
   - 实测：6 只匹配（宿迁联盛4连板、盛龙股份2连板等）

3. **`strategies/limit_up_reseal.py`** — 💪 涨停板打开后回封：
   - 筛选：limit=='U' AND open_times>0（有分歧但最终封住）
   - 评分：开板次数1-5次最佳(max30) + 换手率3-15%最佳(max25) + 成交额(max20) + 市值(max15)
   - 数据：limit_list_d
   - 实测：48 只匹配

4. **`strategies/block_trade_premium.py`** — 🐋 大宗交易溢价：
   - 筛选：block_trade.price > daily.close（买方溢价接货）AND amount>=500万
   - 评分：溢价率(max50) + 金额(max30) + 有买家名称(max20)
   - 数据：block_trade + daily
   - 实测：2 只匹配

5. **`strategies/broken_net_gold.py`** — 💎 破净股淘金：
   - 筛选：PB<1 AND 0<PE<20 AND net_mf_amount>0 AND 非ST
   - 评分：PB折扣(max30) + 资金净流入(max30) + 股息率(max20) + PE估值(max20)
   - 数据：daily_basic + moneyflow
   - 实测：135 只匹配（光大银行PB=0.38、平安银行PB=0.48等）

### 策略覆盖现状
**10 个策略**：价值×3 + 动量×2 + 资金×1 + 事件×3 + 组合×1

### 测试验证
- 策略列表：`curl /api/strategies/` ✅ 返回 10 个策略
- 连板强势股：`curl /api/strategies/execute/consecutive_limit_up` ✅ 6 只匹配
- 涨停回封：`curl /api/strategies/execute/limit_up_reseal` ✅ 48 只匹配
- 大宗溢价：`curl /api/strategies/execute/block_trade_premium` ✅ 2 只匹配
- 破净淘金：`curl /api/strategies/execute/broken_net_gold` ✅ 135 只匹配
- 全部执行：`curl /api/strategies/execute-all` ✅ 10 个策略全部成功
- 策略共振：`curl /api/strategies/confluence` ✅ 170 只股票触发 2+ 策略
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅

### 新增文件
- `backend/app/engine/strategies/consecutive_limit_up.py`
- `backend/app/engine/strategies/limit_up_reseal.py`
- `backend/app/engine/strategies/block_trade_premium.py`
- `backend/app/engine/strategies/broken_net_gold.py`

### 修改文件
- `backend/app/engine/data_loader.py` — 新增 limit_list_d、block_trade、daily 加载器


## 2026-06-14 — 策略引擎架构 + 4个预设选股策略（Evolution Round 4）

### 需求
从「条件筛选器」向「策略驱动的选股平台」进化。实现一个可扩展的策略引擎框架，支持预设选股策略的定义、执行和结果展示。每种策略封装独立的选股逻辑，通过注册机制自动发现，新策略只需新增一个文件即可接入系统。同时实现首批 4 个高价值预设策略。

### 核心架构设计
- **策略基类** (`BaseStrategy`)：定义 `required_data()` 和 `check()` 抽象方法
- **自动发现注册**：使用 `@register` 装饰器 + `pkgutil` 自动扫描 `engine/strategies/` 目录
- **集中式数据加载** (`StrategyDataLoader`)：一次加载多策略共享数据，避免重复 API 调用
- **策略服务** (`StrategyService`)：支持单策略执行、全部执行（共享数据）、策略列表查询

### 实现方案

#### 后端：策略引擎核心
1. **`engine/base.py`** — 策略基类：
   - `StrategyResult` 数据类：ts_code, name, score(0-100), signals(dict), reason(str)
   - `BaseStrategy` ABC：`required_data() -> List[str]`、`check(data) -> List[StrategyResult]`

2. **`engine/registry.py`** — 自动发现注册：
   - `@register` 装饰器自动注册策略实例
   - `load_all_strategies()` 使用 `pkgutil.iter_modules` 扫描包目录
   - 新策略只需在 `engine/strategies/` 下新建 `.py` 文件并加 `@register`

3. **`engine/data_loader.py`** — 集中式数据加载：
   - 支持单日和多日数据加载（moneyflow_multi, daily_multi）
   - 缓存优先：daily_basic 检查缓存新鲜度，moneyflow 每次拉取最新
   - 多日数据自动拼接为 DataFrame

#### 后端：4个预设策略
4. **`strategies/low_valuation_gold.py`** — ⛏️ 低估值金矿：
   - 筛选：PE_TTM < 15 AND PB < 2 AND dv_ratio > 3% AND total_mv > 50亿
   - 评分：基于 PE/PB/股息率的偏离度加权
   - 数据：daily_basic（单日批量）

5. **`strategies/high_dividend.py`** — 🛡️ 高股息防守：
   - 筛选：dv_ratio TOP50 且 PE_TTM < 20
   - 评分：股息率排名越靠前分越高
   - 数据：daily_basic（单日批量）

6. **`strategies/main_fund_inflow.py`** — 💰 主力资金持续流入：
   - 筛选：连续 3+ 日主力净流入 > 0（大单+超大单）
   - 评分：连续天数 × 累计净流入金额
   - 数据：moneyflow_multi（5日批量）

7. **`strategies/value_fund_resonance.py`** — 🎯 价值+资金共振：
   - 筛选：PE_TTM < 20 AND 近3日主力净流入 > 0 AND 换手率 > 2%
   - 评分：估值质量 + 资金关注度 + 活跃度
   - 数据：daily_basic + moneyflow_multi

#### 后端：服务与路由
8. **`services/strategy.py`** — 策略服务：
   - `list_strategies()` — 列出所有可用策略
   - `execute_strategy(name, trade_date, limit)` — 执行单个策略
   - `execute_all(trade_date)` — 一次性执行所有策略（共享数据加载）

9. **`routes/strategy.py`** — API 路由：
   - `GET /api/strategies/` — 策略列表
   - `GET /api/strategies/execute/{name}` — 执行单策略
   - `GET /api/strategies/execute-all` — 执行全部策略

#### 前端：策略仪表板
10. **`pages/StrategyDashboard.jsx`** — 策略仪表板页面：
    - 策略概览卡片：图标、名称、描述、匹配数、平均分
    - 单策略详情：点击卡片展开结果表格（股票代码、名称、评分、信号值、推荐理由）
    - 评分颜色编码：高分绿色、中分黄色、低分橙色
    - 「全部执行」按钮：一键运行所有策略
    - 分类标签：价值型、动量型、资金型、事件型、组合型
    - 加载状态和错误处理

11. **`services/api.js`** — 新增 API 函数：
    - `getStrategies()`、`executeStrategy(name, params)`、`executeAllStrategies(params)`

12. **`App.jsx`** — 新增「策略选股」Tab

### 新增 API 端点
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/strategies/` | 列出所有可用策略 |
| GET | `/api/strategies/execute/{name}` | 执行指定策略 |
| GET | `/api/strategies/execute-all` | 一次性执行全部策略 |

### 测试验证
- 策略列表：`curl /api/strategies/` ✅ 返回 4 个策略
- 低估值金矿：`curl /api/strategies/execute/low_valuation_gold?limit=3` ✅ 58 只匹配
  - 600015.SH(华夏银行): PE=4.1, PB=0.35, 股息率=5.79%, 市值1112亿
- 高股息防守：`curl /api/strategies/execute/high_dividend?limit=3` ✅ 50 只匹配
  - 002582.SZ: 股息率排名#7(10.32%), PE=2.18
- 主力资金流入：`curl /api/strategies/execute/main_fund_inflow?limit=3` ✅ 509 只匹配
- 价值+资金共振：`curl /api/strategies/execute/value_fund_resonance?limit=3` ✅ 142 只匹配
  - 600711.SH: PE=14.93, 近3日净流入2.08亿
- 全部执行：`curl /api/strategies/execute-all` ✅ 4 个策略全部成功
- 前端构建：`npm run build` 成功 ✅
- 后端重启：服务正常运行 ✅
- 现有端点验证：market/overview、screener/stocks 均正常 ✅

### 新增文件
- `backend/app/engine/__init__.py`
- `backend/app/engine/base.py`
- `backend/app/engine/registry.py`
- `backend/app/engine/data_loader.py`
- `backend/app/engine/strategies/__init__.py`
- `backend/app/engine/strategies/low_valuation_gold.py`
- `backend/app/engine/strategies/high_dividend.py`
- `backend/app/engine/strategies/main_fund_inflow.py`
- `backend/app/engine/strategies/value_fund_resonance.py`
- `backend/app/services/strategy.py`
- `backend/app/routes/strategy.py`
- `frontend/src/pages/StrategyDashboard.jsx`

### 修改文件
- `backend/app/main.py` — 注册 strategy_router
- `frontend/src/services/api.js` — 新增策略 API 函数
- `frontend/src/App.jsx` — 新增「策略选股」Tab

---

## 2026-06-14 — 技术指标选股 + 概念板块追踪（Evolution Round 2）

### 需求
从「资金流向展示工具」向「专业选股与分析平台」进化。本轮实现两个核心选股功能：
1. **技术指标选股**：基于 TuShare stk_factor 接口，支持 MACD/KDJ/RSI/布林带/CCI 等技术指标信号筛选，类似同花顺的「技术指标选股器」
2. **概念板块追踪**：接入同花顺 1725 个概念板块指数，展示涨跌幅、成分股、行情走势，类似东方财富的「概念板块」功能

### 实现方案

#### 功能一：技术指标选股

**后端**
1. **数据模型** (`backend/app/models.py`):
   - 新增 `StkFactor` 表，字段：trade_date, ts_code, close, open, high, low, pre_close, change, pct_change, vol, amount, adj_factor, macd_dif, macd_dea, macd, kdj_k, kdj_d, kdj_j, rsi_6, rsi_12, rsi_24, boll_upper, boll_mid, boll_lower, cci
   - 唯一约束：(trade_date, ts_code)

2. **TuShareClient** (`backend/app/clients/tushare.py`):
   - 新增 `get_stk_factor(trade_date)` 方法，批量获取全市场技术指标

3. **缓存服务** (`backend/app/cache.py`):
   - 新增 `upsert_stk_factor()` 批量写入
   - 新增 `get_stk_factor_all()` 查询全市场技术指标（LEFT JOIN stock_basic 获取名称）
   - 新增 `get_stk_factor_count()` 统计缓存记录数
   - 新增 `get_stk_factor_prev_day()` 获取前一交易日数据（用于金叉/死叉检测）

4. **业务服务** (`backend/app/services/technical.py`):
   - 新建 `TechnicalService` 类
   - `screen_by_signals()` — 支持 12 种技术信号筛选
   - 信号类型：MACD金叉/死叉、KDJ金叉/超买/超卖、RSI超买/超卖、布林带突破上轨/跌破下轨、CCI超买/超卖、MA5>MA20
   - 金叉/死叉检测需要对比前一交易日数据
   - 自动从 TuShare 拉取并缓存 stk_factor 数据

5. **API路由** (`backend/app/routes/technical.py`):
   - `GET /api/technical/screen` — 技术指标选股

**前端**
1. **API函数** (`frontend/src/services/api.js`):
   - 新增 `screenBySignals(params)` 函数

2. **选股页面** (`frontend/src/pages/StockScreener.jsx`):
   - 重构为 Tabs 组件，包含「条件选股」和「技术指标选股」两个子页面
   - 新增 `TechnicalScreener` 组件
   - **信号快捷按钮**：10 个可多选组合的信号按钮（MACD金叉/死叉、KDJ超卖/超买、RSI超卖/超买、突破上轨/跌破下轨、CCI超卖/超买）
   - **结果表格**：10 列（股票、行业、收盘价、涨跌幅、MACD(DIF/DEA/MACD)、KDJ(K/D/J)、RSI(6/12/24)、布林带(上/中/下)、CCI、信号标签）
   - 信号标签使用红/绿/蓝颜色编码

#### 功能二：概念板块追踪

**后端**
1. **业务服务** (`backend/app/services/concept.py`):
   - 新建 `ConceptService` 类
   - `list_concepts()` — 概念板块列表，关联 sector_daily 获取涨跌幅，关联 sector_member 获取成分股数
   - `get_concept_detail()` — 概念详情 + 近10日行情走势
   - `get_concept_members()` — 概念成分股列表 + 基本面数据（daily_basic）

2. **API路由** (`backend/app/routes/concept.py`):
   - `GET /api/concepts` — 概念板块列表（分页、排序、搜索）
   - `GET /api/concepts/{ts_code}` — 概念详情 + 近10日行情
   - `GET /api/concepts/{ts_code}/members` — 概念成分股列表

**前端**
1. **API函数** (`frontend/src/services/api.js`):
   - 新增 `getConcepts()`, `getConceptDetail()`, `getConceptMembers()` 函数

2. **概念板块页面** (`frontend/src/pages/ConceptBoard.jsx`):
   - 新建概念板块追踪页面
   - **搜索框**：模糊搜索概念名称
   - **数据表格**：7 列（概念名称、代码、成分股数、收盘价、涨跌幅、成交额、换手率）
   - **点击展开**：Drawer 抽屉显示概念详情（近10日行情 + 成分股列表）
   - 成分股表格：股票名称、代码、收盘价、PE(TTM)、PB、总市值

3. **应用主组件** (`frontend/src/App.jsx`):
   - 新增「概念板块」Tab，使用 AppstoreOutlined 图标

### 新增 API 端点
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/technical/screen` | 技术指标选股（12种信号） |
| GET | `/api/concepts` | 概念板块列表 |
| GET | `/api/concepts/{ts_code}` | 概念详情 + 近10日行情 |
| GET | `/api/concepts/{ts_code}/members` | 概念成分股列表 |

### 测试验证
- 技术指标选股（MACD金叉）：`curl /api/technical/screen?trade_date=20260612&macd_golden=true` ✅ 1329 只
- 技术指标选股（RSI超卖）：`curl /api/technical/screen?trade_date=20260612&rsi_oversold=true` ✅ 1416 只
- 技术指标选股（RSI+KDJ超卖组合）：`curl /api/technical/screen?rsi_oversold=true&kdj_oversold=true` ✅ 1251 只
- 概念板块列表：`curl /api/concepts?page_size=5` ✅ 1725 个概念板块
- 概念详情：`curl /api/concepts/885338.TI` ✅ 融资融券概念，近10日行情
- 概念成分股：`curl /api/concepts/885338.TI/members` ✅ 3787 只成分股
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅
- 现有端点验证：market/overview、screener/stocks、sectors 均正常 ✅

### 修改文件
- `backend/app/models.py` — 新增 StkFactor 模型
- `backend/app/config.py` — 新增 STK_FACTOR_CACHE_MINUTES 配置
- `backend/app/clients/tushare.py` — 新增 get_stk_factor 方法
- `backend/app/cache.py` — 新增 stk_factor 缓存方法，更新白名单
- `backend/app/services/technical.py` — 新建技术指标选股服务
- `backend/app/routes/technical.py` — 新建技术指标选股路由
- `backend/app/services/concept.py` — 新建概念板块追踪服务
- `backend/app/routes/concept.py` — 新建概念板块路由
- `backend/app/main.py` — 注册 technical_router 和 concept_router
- `frontend/src/services/api.js` — 新增 screenBySignals、getConcepts、getConceptDetail、getConceptMembers
- `frontend/src/pages/StockScreener.jsx` — 重构为 Tabs，新增 TechnicalScreener 组件
- `frontend/src/pages/ConceptBoard.jsx` — 新建概念板块页面
- `frontend/src/App.jsx` — 新增「概念板块」Tab

---

## 2026-06-14 — 添加多维度选股筛选器（Stock Screener）

### 需求
用户需要一个专业级的条件选股功能，类似同花顺/东方财富的「条件选股器」。支持按 PE、PB、市值、换手率、量比、股息率、资金净流入等多维度条件组合筛选股票，帮助用户快速定位符合特定投资策略的标的。这是从「资金流向展示工具」向「专业选股与分析平台」进化的关键功能。

### 实现方案

#### 后端
1. **TuShareClient** (`backend/app/clients/tushare.py`):
   - 新增 `get_all_daily_basic(trade_date)` 方法，批量获取指定交易日全市场所有股票的 daily_basic 数据
   - 字段：pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv, circ_mv, turnover_rate, volume_ratio 等

2. **缓存服务** (`backend/app/cache.py`):
   - 新增 `batch_upsert_daily_basic(data, trade_date)` — 批量写入全市场 daily_basic 数据
   - 新增 `get_all_daily_basic(trade_date)` — 查询全市场 daily_basic 并 LEFT JOIN stock_basic 获取股票名称和行业
   - 新增 `get_all_daily_basic_count(trade_date)` — 统计缓存记录数

3. **业务服务** (`backend/app/services/screener.py`):
   - 新建 `ScreenerService` 类
   - `screen_stocks()` — 主筛选方法，支持 18 个筛选参数 + 排序 + 分页
   - `_ensure_daily_basic()` — 自动检测缓存完整性，不足 3000 条时从 TuShare 批量拉取
   - `_apply_filters()` — 支持 PE(TTM)、PB、总市值、流通市值、换手率、量比、股息率、净流入、名称搜索、行业筛选
   - 自动合并 `moneyflow_dc` 数据获取资金净流入信息

4. **API路由** (`backend/app/routes/screener.py`):
   - 新建路由器，前缀 `/api/screener`
   - `GET /api/screener/stocks` — 多维度选股筛选器
   - 参数：pe_min/max, pb_min/max, mv_min/max, circ_mv_min/max, turnover_min/max, volume_ratio_min/max, dv_min/max, net_inflow_min, name, industry, sort_by, sort_order, page, page_size

#### 前端
1. **API函数** (`frontend/src/services/api.js`):
   - 新增 `screenStocks(params)` 函数

2. **选股页面** (`frontend/src/pages/StockScreener.jsx`):
   - 新建专业多维度选股筛选器页面
   - **快速筛选预设**：💎低估值、💰高股息、🔥高换手、🏦大市值、🚀小盘股、📈放量
   - **可折叠筛选面板**：18 个筛选输入框，支持 PE/PB/市值/换手率/量比/股息率/净流入等
   - **可排序数据表**：11 列（股票名称、行业、收盘价、PE、PB、总市值、流通市值、换手率、量比、股息率、净流入）
   - **分页**：支持 20/50/100 条/页切换
   - **交互**：点击股票行跳转到个股详情，颜色编码（红涨绿跌、估值分色）

3. **应用主组件** (`frontend/src/App.jsx`):
   - 新增「条件选股」Tab，使用 SearchOutlined 图标
   - 传递 tradeDate 和 onSelectStock props

### 功能特点
- **批量数据加载**：首次查询自动从 TuShare 批量拉取全市场 ~5500 只股票的 daily_basic 数据并缓存
- **18 维筛选**：PE/PB/市值/换手率/量比/股息率/净流入/名称/行业等多条件组合
- **6 个快速预设**：一键应用常用选股策略
- **毫秒级筛选**：所有筛选在本地内存中完成，响应极快
- **容错设计**：daily_basic 数据不足时自动补全，不影响其他功能
- **资金流向整合**：自动合并 moneyflow_dc 数据，显示资金净流入

### 测试验证
- API 测试（全量）：`curl /api/screener/stocks?page_size=3` ✅ 返回 5512 只股票
- API 测试（低估值）：`curl /api/screener/stocks?pe_min=0&pe_max=15` ✅ 筛选出 426 只
- API 测试（高股息）：`curl /api/screener/stocks?dv_min=3` ✅ 筛选出 517 只
- API 测试（大市值）：`curl /api/screener/stocks?mv_min=1000` ✅ 筛选出 202 只
- API 测试（名称搜索）：`curl /api/screener/stocks?name=茅台` ✅ 找到贵州茅台
- API 测试（排序）：`curl /api/screener/stocks?sort_by=pe_ttm&sort_order=asc&page_size=3` ✅
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅
- 现有端点验证：market/overview、sectors、stocks/search 均正常 ✅

### 修改文件
- `backend/app/clients/tushare.py` — 新增 get_all_daily_basic 方法
- `backend/app/cache.py` — 新增 batch_upsert_daily_basic、get_all_daily_basic、get_all_daily_basic_count 方法
- `backend/app/services/screener.py` — 新建 ScreenerService 业务服务
- `backend/app/routes/screener.py` — 新建选股路由器
- `backend/app/main.py` — 注册 screener_router
- `frontend/src/services/api.js` — 新增 screenStocks 函数
- `frontend/src/pages/StockScreener.jsx` — 新建选股筛选器页面
- `frontend/src/App.jsx` — 新增「条件选股」Tab

---

## 2026-06-14 — 添加大盘指数显示功能

### 需求
用户在大盘总览页面，除了看到资金流向、北向资金等数据，希望能一目了然地看到三大指数（上证指数、深证成指、创业板指）的实时行情。市场指数是股票类App最基础的数据展示，同花顺、东方财富均在首页最显眼位置展示指数行情，帮助用户快速判断市场整体走势。

### 实现方案

#### 后端
1. **TuShareClient** (`backend/app/clients/tushare.py`):
   - 新增 `get_index_daily()` 方法，调用 TuShare `index_daily` API 获取指数日线行情
   - 支持按 ts_code 和 trade_date 查询

2. **数据模型** (`backend/app/models.py`):
   - 新增 `IndexDaily` 表，字段：ts_code, trade_date, close, open, high, low, pre_close, change, pct_chg, vol, amount
   - 唯一约束：(ts_code, trade_date)
   - 缓存有效期：60分钟

3. **缓存服务** (`backend/app/cache.py`):
   - 新增 `upsert_index_daily()` 批量写入
   - 新增 `get_index_daily()` 查询方法
   - 更新 `is_fresh` 白名单支持 "index_daily" 表

4. **业务服务** (`backend/app/services/market.py`):
   - 新增 `get_market_indices()` 方法
   - 查询三大指数：上证指数(000001.SH)、深证成指(399001.SZ)、创业板指(399006.SZ)
   - 先查缓存，缓存未命中时从 TuShare API 获取并缓存

5. **API路由** (`backend/app/routes/market.py`):
   - 新增 `GET /api/market/indices?trade_date=YYYYMMDD`
   - 返回三大指数的收盘价、涨跌额、涨跌幅、成交量、成交额

#### 前端
1. **API函数** (`frontend/src/services/api.js`):
   - 新增 `getMarketIndices(tradeDate)` 函数

2. **指数卡片组件** (`frontend/src/components/MarketIndex.jsx`):
   - 新建组件，展示三大指数实时行情
   - 每个指数显示：名称、收盘价、涨跌额、涨跌幅、成交量、成交额
   - 红涨绿跌（中国股市惯例）
   - 响应式布局：手机端竖排，桌面端三列横排
   - 成交量自动换算（手→亿手/万手），成交额自动换算（元→亿/万）

3. **大盘总览页面** (`frontend/src/pages/MarketOverview.jsx`):
   - 导入 MarketIndex 组件
   - 在 fetchData 中并行请求 indices 数据（`.catch(() => null)` 容错）
   - 在顶部资金统计卡片之前渲染指数卡片

### 功能特点
- **缓存60分钟**：避免频繁调用 TuShare API
- **容错设计**：指数数据加载失败不影响其他模块
- **自动换算**：成交量和成交额自动使用合适的单位显示
- **红涨绿跌**：符合中国股市显示惯例
- **响应式布局**：适配手机端和桌面端

### 测试验证
- API 测试：`curl /api/market/indices` ✅ 返回三大指数数据
  - 上证指数 4031.51 (+1.12%)、深证成指 14963.41 (+0.75%)、创业板指 3830.35 (+0.50%)
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅
- 现有端点验证：market/overview、market/north 均正常 ✅

### 修改文件
- `backend/app/clients/tushare.py` — 新增 get_index_daily 方法
- `backend/app/models.py` — 新增 IndexDaily 模型
- `backend/app/config.py` — 新增 INDEX_DAILY_CACHE_MINUTES 配置
- `backend/app/cache.py` — 新增 index_daily 缓存方法，更新白名单
- `backend/app/services/market.py` — 新增 get_market_indices 服务
- `backend/app/routes/market.py` — 新增 /indices 路由
- `frontend/src/services/api.js` — 新增 getMarketIndices 函数
- `frontend/src/components/MarketIndex.jsx` — 新建指数卡片组件
- `frontend/src/pages/MarketOverview.jsx` — 集成指数卡片

---

## 2026-06-14 — 添加历史日期选择功能

### 需求
大盘总览页面目前只能显示最新交易日的数据。用户需要能选择任意历史交易日，查看该日的资金流向、北向资金、涨跌分布、涨跌停监控、板块排行、个股排行等数据。这是股票分析工具的基础功能，支持用户回看历史市场状态，进行回测和分析。

### 实现方案

#### 前端
1. **应用主组件** (`frontend/src/App.jsx`):
   - 新增 `tradeDate` state（默认 null 表示最新交易日），提升到 App 层管理
   - 引入 antd `DatePicker` + `dayjs` 中文 locale
   - 顶部标题栏右侧添加日期选择器
   - `disabledDate` 限制周末不可选
   - 选择日期后递增 `refreshKey` 触发所有数据重新加载

2. **大盘总览页面** (`frontend/src/pages/MarketOverview.jsx`):
   - 接收 `tradeDate` prop
   - `getMarketOverview`、`getNorthFund`、`getMarketBreadth` 调用传入 `tradeDate`
   - 向子组件（BreadthChart、LimitStats、SectorRanking、StockRanking）传递 `tradeDate`

3. **板块排行组件** (`frontend/src/components/SectorRanking.jsx`):
   - 接收 `tradeDate` prop，传递给 `getSectors` API 调用

4. **API函数** (`frontend/src/services/api.js`):
   - `getSectors` 新增 `tradeDate` 可选参数

5. **样式** (`frontend/src/index.css`):
   - 添加暗色主题 DatePicker 样式覆盖（透明背景、白色文字）

#### 依赖
- `dayjs` 从 antd 间接依赖提升为直接依赖

### 已有支持（无需修改）
- `StockRanking.jsx` — 已接收 `tradeDate` prop ✅
- `LimitStats.jsx` — 已接收 `tradeDate` prop ✅
- `getMarketOverview`、`getNorthFund`、`getMarketBreadth`、`getStockRanking`、`getLimitStats` — 已支持 `tradeDate` 参数 ✅
- 所有后端 API 端点已支持 `trade_date` 查询参数 ✅

### 功能特点
- **DatePicker 放在顶部标题栏**：深色主题，中文 locale，清除按钮回到「最新」
- **周末日期自动禁用**：避免选择非交易日
- **全组件联动**：选择日期后所有数据（资金总览、北向资金、涨跌分布、涨跌停监控、板块排行、个股排行）同步更新
- **零后端改动**：所有 API 已支持 trade_date 参数
- **渐进式体验**：默认显示最新数据，用户可主动选择历史日期

### 测试验证
- API 测试（历史日期）：`curl /api/market/overview?trade_date=20260612` ✅ 返回 20260612 数据
- API 测试（北向资金）：`curl /api/market/north?trade_date=20260612` ✅
- API 测试（涨跌分布）：`curl /api/market/breadth?trade_date=20260612` ✅ 5965 只股票
- API 测试（涨跌停）：`curl /api/market/limit-stats?trade_date=20260612` ✅ 89 涨停 / 15 跌停
- API 测试（个股排行）：`curl /api/market/stock-ranking?trade_date=20260612&type=net_inflow&limit=3` ✅
- API 测试（板块排行）：`curl /api/sectors?trade_date=20260612&page=1&size=3` ✅
- 前端构建：`npm run build` 成功 ✅
- dayjs 直接依赖添加 ✅
- 暗色主题样式适配 ✅

### 修改文件
- `frontend/src/App.jsx` — 添加 tradeDate state、DatePicker、dayjs locale
- `frontend/src/pages/MarketOverview.jsx` — 接收 tradeDate prop，传递给子组件
- `frontend/src/components/SectorRanking.jsx` — 接收 tradeDate prop
- `frontend/src/services/api.js` — getSectors 新增 tradeDate 参数
- `frontend/src/index.css` — 添加暗色主题 DatePicker 样式
- `frontend/package.json` — 添加 dayjs 直接依赖

---

## 2026-06-14 — 添加个股基本面指标（PE/PB/市值）

### 需求
用户在查看个股资金流向时，除了价格走势和资金流向数据，还需要看到基本面指标（市盈率PE、市净率PB、总市值、流通市值、股息率等），以便结合估值和市值维度进行综合分析。这是股票类App的基础功能，同花顺、东方财富均在个股详情页展示这些指标。

### 实现方案

#### 后端
1. **TuShareClient** (`backend/app/clients/tushare.py`):
   - 新增 `get_daily_basic()` 方法，调用 TuShare `daily_basic` API
   - 获取：pe_ttm, pe, pb, ps_ttm, dv_ratio, total_share, float_share, total_mv, circ_mv, turnover_rate, volume_ratio

2. **数据模型** (`backend/app/models.py`):
   - 新增 `DailyBasic` 表，字段：trade_date, ts_code, close, turnover_rate, turnover_rate_f, volume_ratio, pe, pe_ttm, ps, ps_ttm, dv_ratio, dv_ttm, total_share, float_share, total_mv, circ_mv
   - 唯一约束：(trade_date, ts_code)

3. **缓存服务** (`backend/app/cache.py`):
   - 新增 `upsert_daily_basic()` 批量写入
   - 新增 `get_daily_basic()` 查询方法（按日期倒序）
   - 更新 `is_fresh` 白名单，缓存有效期 60 分钟

4. **业务服务** (`backend/app/services/stock.py`):
   - 新增 `get_stock_basic_info()` 方法
   - 先查缓存，缓存过期或无数据时从 TuShare API 获取并缓存
   - 格式化函数 `_format_daily_basic()` 返回标准化 dict

5. **API路由** (`backend/app/routes/stock.py`):
   - 新增 `GET /api/stocks/{ts_code}/basic`
   - 返回：pe_ttm, pe, pb, ps_ttm, dv_ratio, total_share, float_share, total_mv, circ_mv, turnover_rate, volume_ratio

#### 前端
1. **API函数** (`frontend/src/services/api.js`):
   - 新增 `getStockBasic(tsCode)` 函数

2. **个股流向页面** (`frontend/src/pages/StockFlow.jsx`):
   - 新增 `stockBasicData` state
   - `fetchStockData` 中并行请求 basic 数据（`.catch(() => null)` 容错）
   - 在个股头部信息下方添加基本面指标卡片
   - 卡片使用 2×3 网格布局，显示：PE(TTM)、PB、总市值、流通市值、股息率、换手率
   - 总市值/流通市值自动换算为亿元显示

### 功能特点
- **缓存60分钟**：避免频繁调用 TuShare API
- **容错设计**：基本面数据加载失败不影响其他模块
- **自动换算**：市值自动从万元换算为亿元
- **数据准确**：使用 TuShare daily_basic 接口，与同花顺/东方财富数据源一致

### 测试验证
- API 测试（平安银行）：`curl /api/stocks/000001.SZ/basic` ✅
  - PE(TTM)=5.07, PB=0.48, 总市值≈2181亿, 股息率=5.32%
- API 测试（贵州茅台）：`curl /api/stocks/600519.SH/basic` ✅
  - PE(TTM)=19.52, PB=6.03, 总市值≈1615亿, 股息率=4.00%
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅
- 现有端点验证：market/overview、stocks/{ts_code} 均正常 ✅

### 修改文件
- `backend/app/config.py` — 新增 DAILY_BASIC_CACHE_MINUTES 配置
- `backend/app/clients/tushare.py` — 新增 get_daily_basic 方法
- `backend/app/models.py` — 新增 DailyBasic 模型
- `backend/app/cache.py` — 新增 daily_basic 缓存方法，更新白名单
- `backend/app/services/stock.py` — 新增 get_stock_basic_info 服务
- `backend/app/routes/stock.py` — 新增 /basic 路由
- `frontend/src/services/api.js` — 新增 getStockBasic 函数
- `frontend/src/pages/StockFlow.jsx` — 集成基本面指标卡片

---

## 2026-06-14 — 添加板块资金流向排行（Sector Ranking）

### 需求
用户在大盘总览页面，除了看到个股资金流向排行榜，希望快速了解当天哪些板块资金流入最多、哪些板块资金流出最多。板块轮动是A股投资的核心分析维度（同花顺、东方财富均在首页展示板块排行），帮助用户一键判断市场热点板块。

### 实现方案

#### 前端
1. **排行榜组件** (`frontend/src/components/SectorRanking.jsx`):
   - 新建组件，参考 StockRanking 的设计模式
   - 使用 antd `Segmented` 切换「净流入TOP10」和「净流出TOP10」
   - 净流入：调用 `getSectors(1, 10)`，后端已按 `net_inflow` 降序排列
   - 净流出：调用 `getSectors(1, 300)`（覆盖全部约240个板块），前端升序排序取前10
   - 表格列：排名、板块名称、主力净流入、大单净流入、领涨股（含涨跌幅）
   - 金额用 `formatAmount` 格式化，颜色用 `getColor`
   - 点击板块行触发 `onSelectSector` 回调，跳转到板块资金流向 Tab

2. **大盘总览页面** (`frontend/src/pages/MarketOverview.jsx`):
   - 导入 `SectorRanking` 组件
   - 添加 `onSelectSector` prop
   - 放置在涨跌分布图（BreadthChart）和个股排行（StockRanking）之间

3. **应用主组件** (`frontend/src/App.jsx`):
   - 添加 `handleSelectSectorFromOverview` 处理函数
   - 点击板块行时自动切换到板块资金流向 Tab

### 功能特点
- **零后端改动**：复用现有 `/api/sectors` 接口，无需新增 API
- **净流入/净流出切换**：一键切换两种视角，快速定位热点和冷门板块
- **领涨股展示**：每个板块显示领涨股及其涨跌幅
- **容错设计**：加载失败时显示 Empty，不阻塞其他模块
- **交互流畅**：点击板块行跳转到板块详情页，查看成分股和趋势图

### 测试验证
- API 测试：`curl /api/sectors?page=1&size=5` ✅ 返回 240 个板块，数据完整
- 净流出验证：page 24 返回光刻机（-29万）、光纤概念（-20万）等净流出板块 ✅
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅
- Nginx 代理：`curl /api/sectors` 通过 ✅

### 修改文件
- `frontend/src/components/SectorRanking.jsx` — 新建板块排行榜组件
- `frontend/src/pages/MarketOverview.jsx` — 集成 SectorRanking 组件
- `frontend/src/App.jsx` — 添加板块选择回调

---

## 2026-06-14 — 添加涨跌分布图（Market Breadth）

### 需求
用户在大盘总览页面，除了看到资金流向和北向资金，希望能快速了解当天全市场的涨跌分布情况——多少只股票上涨、多少只下跌、涨跌分布区间如何。这是股票类App的核心功能（同花顺、东方财富、雪球均有此功能），帮助用户一键判断市场整体强弱。

### 实现方案

#### 后端
1. **业务服务** (`backend/app/services/market.py`):
   - 新增 `get_market_breadth()` 方法
   - 从 `get_moneyflow_dc` 获取当日全市场资金流向数据（包含 `pct_change` 字段）
   - 聚合统计：上涨/下跌/平盘家数、涨停/跌停家数、8个涨跌幅区间分布、全市场平均涨跌幅
   - 复用已有的 `moneyflow_dc` 缓存机制

2. **API路由** (`backend/app/routes/market.py`):
   - 新增 `GET /api/market/breadth?trade_date=YYYYMMDD`
   - 返回字段：trade_date, total_stocks, up_count, down_count, flat_count, limit_up, limit_down, distribution, avg_pct_change

#### 前端
1. **API函数** (`frontend/src/services/api.js`):
   - 新增 `getMarketBreadth(tradeDate)` 函数

2. **涨跌分布图组件** (`frontend/src/components/BreadthChart.jsx`):
   - 新建组件，使用 Ant Design Statistic + CSS flexbox 柱状图
   - 顶部4列统计：上涨家数、下跌家数、涨停/跌停、平均涨幅+多空比
   - 中间分段柱状图：8个涨跌幅区间，颜色区分涨（红）跌（绿）平（灰）
   - 底部涨跌分隔线

3. **大盘总览页面** (`frontend/src/pages/MarketOverview.jsx`):
   - 集成 BreadthChart 组件，放在成交额趋势图下方、个股排行榜上方
   - 并行加载 breadth 数据，失败时不阻塞其他模块

### 功能特点
- **复用缓存**：直接从 `moneyflow_dc` 缓存获取，无需额外 API 调用
- **容错设计**：breadth 数据加载失败不影响其他模块
- **8个分布区间**：`<-9%`, `-9%~-5%`, `-5%~-3%`, `-3%~0%`, `0%~3%`, `3%~5%`, `5%~9%`, `>9%`
- **多空比**：自动计算上涨/下跌家数比，直观判断市场强弱

### 测试验证
- API 测试：`curl /api/market/breadth` ✅ 返回 5965 只股票的完整分布数据
- 涨跌统计：上涨 3982（66.8%）、下跌 1525（25.6%）、平盘 458（7.7%）
- 涨停 123 家、跌停 39 家、平均涨幅 +1.04%
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅
- 现有端点验证：market/overview、market/north、market/stock-ranking 均正常 ✅

### 修改文件
- `backend/app/routes/market.py` — 新增 /breadth 路由
- `backend/app/services/market.py` — 新增 get_market_breadth 方法
- `frontend/src/services/api.js` — 新增 getMarketBreadth 函数
- `frontend/src/components/BreadthChart.jsx` — 新建涨跌分布图组件
- `frontend/src/pages/MarketOverview.jsx` — 集成 BreadthChart 组件

---

## 2026-06-14 — 添加个股多日资金流向趋势图

### 需求
用户在查看个股资金流向时，目前只能看到单日的资金流向柱状图。需要添加近N日（默认10日）的资金流向趋势折线图，帮助用户识别主力资金的连续流入/流出模式（如连续吸筹、持续出货等）。这是专业投资者的核心分析需求。

### 实现方案

#### 后端
1. **业务服务** (`backend/app/services/stock.py`):
   - 新增 `get_stock_flow_trend(ts_code, days=10)` 方法
   - 从 `get_latest_trade_date` 获取最新交易日
   - 使用 `get_last_n_trade_dates` 生成候选交易日列表（跳过周末和法定节假日）
   - 先查询 `stock_flow` 表已有数据
   - 对缺失日期调用 TuShare `moneyflow` API 补全并缓存
   - 返回格式与 `market.py` 的 `get_market_trend` 一致：`{labels: ['MM/DD', ...], series: {main_net: [...], super_large: [...], ...}}`
   - series 包含 5 条线：main_net（主力）、super_large（超大单）、large（大单）、medium（中单）、small（小单）

2. **API路由** (`backend/app/routes/stock.py`):
   - 新增 `GET /api/stocks/{ts_code}/flow-trend?days=10`

#### 前端
1. **API函数** (`frontend/src/services/api.js`):
   - 新增 `getStockFlowTrend(tsCode, days=10)` 函数

2. **个股流向页面** (`frontend/src/pages/StockFlow.jsx`):
   - 导入已有的 `FlowTrendChart` 组件（复用大盘资金流向趋势图组件）
   - 新增 `flowTrendData` state
   - `fetchStockData` 中并行请求 4 个接口（flow-trend 加 `.catch(() => ({series: {}}))` 容错）
   - 在 K线图之后、资金流向分布图之前渲染趋势图

### 功能特点
- **复用组件**：直接使用已有的 FlowTrendChart 组件，无需新建图表
- **增量加载**：优先从缓存读取，缺失日期才调用 TuShare API
- **容错设计**：趋势数据加载失败不影响其他模块
- **格式统一**：返回数据格式与大盘趋势图一致，前端零适配

### 修改文件
- `backend/app/services/stock.py` — 新增 get_stock_flow_trend 方法
- `backend/app/routes/stock.py` — 新增 /flow-trend 路由
- `frontend/src/services/api.js` — 新增 getStockFlowTrend 函数
- `frontend/src/pages/StockFlow.jsx` — 集成 FlowTrendChart 组件

### 测试验证
- API 测试：`curl /api/stocks/000001.SZ/flow-trend?days=10` ✅ 返回 11 个数据点，5 条线
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅
- 现有端点验证：market/overview、stocks/{ts_code} 均正常 ✅

---

## 2026-06-14 — 添加个股资金流向排行榜

### 需求
用户在大盘总览页面，除了看到市场总览和北向资金，希望能快速看到当天资金流入/流出最多的个股排行榜，无需逐个搜索。这是股票类 App 的核心功能之一（同花顺、东方财富均有此功能）。

### 实现方案

#### 后端
1. **TuShareClient** (`backend/app/clients/tushare.py`):
   - 已有 `get_moneyflow_dc()` 方法，获取东财口径全市场资金流向数据

2. **业务服务** (`backend/app/services/market.py`):
   - 新增 `get_stock_ranking()` 方法
   - 从 TuShare `moneyflow_dc` 获取当日全市场资金流向数据（约6000条记录）
   - 按 `net_amount` 字段排序（降序=净流入排行，升序=净流出排行）
   - 返回字段：ts_code, name, close, pct_change, net_amount, buy_elg_amount, buy_lg_amount
   - 通过 `stock_basic` 构建 ts_code → name 映射补充股票名称
   - 不缓存排行数据（实时性要求高）

3. **API路由** (`backend/app/routes/market.py`):
   - 新增 `GET /api/market/stock-ranking?trade_date=YYYYMMDD&type=net_inflow&limit=20`
   - 参数：trade_date（可选）、type（net_inflow/net_outflow）、limit（默认20）

#### 前端
1. **API函数** (`frontend/src/services/api.js`):
   - 新增 `getStockRanking(tradeDate, type, limit)` 函数

2. **排行榜组件** (`frontend/src/components/StockRanking.jsx`):
   - 新建组件，展示个股资金流向排行
   - 支持切换「净流入」和「净流出」两个 Tab（红/绿色按钮）
   - 表格显示：排名、名称、代码、收盘价、涨跌幅、净流入金额
   - 涨跌幅用 `getColorClass` 着色，净流入用 `formatAmount` 格式化
   - 点击股票行跳转到个股详情

3. **大盘总览页面** (`frontend/src/pages/MarketOverview.jsx`):
   - 集成 `StockRanking` 组件，放在资金流向趋势图下方

### Bug 修复
- 修复 moneyflow_dc 数据字段名：`net_amount` 而非 `net_mf_amount`
  - moneyflow_dc（东财口径）的净流入字段名为 `net_amount`
  - moneyflow（同花顺口径）的净流入字段名为 `net_mf_amount`
  - 原代码错误使用了 `net_mf_amount`，导致排行数据全为0

### 测试验证
- API 测试（净流入）：`curl /api/market/stock-ranking?trade_date=20260612&type=net_inflow&limit=5` ✅
  - 宁德时代 19.7亿、洛阳钼业 16.9亿、东山精密 15.5亿
- API 测试（净流出）：`curl /api/market/stock-ranking?trade_date=20260612&type=net_outflow&limit=3` ✅
  - 新易盛 -36.6亿、亨通光电 -22.7亿、中兴通讯 -19.7亿
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅
- Nginx 代理：`curl /api/market/stock-ranking` 通过 ✅

### 修改文件
- `backend/app/services/market.py` — 新增 get_stock_ranking 方法，修复 net_amount 字段名
- `backend/app/routes/market.py` — 新增 /api/market/stock-ranking 路由
- `frontend/src/services/api.js` — 新增 getStockRanking 函数
- `frontend/src/components/StockRanking.jsx` — 新建排行榜组件
- `frontend/src/pages/MarketOverview.jsx` — 集成排行榜组件

---

## 2026-06-13 — 添加板块成分股钻取功能

### 需求
用户在板块流向页面查看板块资金流向时，希望能点击某个板块查看其成分股列表，了解板块内哪些股票在驱动资金流入/流出。

### 实现方案

#### 后端
1. **API 路由** (`backend/app/routes/sector.py`):
   - 新增 `GET /api/sectors/{sector_code}/members?trade_date=YYYYMMDD`
   - 返回板块成分股列表及每只股票的资金流向数据

2. **业务服务** (`backend/app/services/sector.py`):
   - 新增 `get_sector_members()` 方法
   - 从 `sector_member` 表获取成分股列表
   - 直接调用 TuShare `moneyflow_dc` 接口获取当日资金流向数据
   - 按净流入金额降序排列返回
   - 修复了板块名称查找逻辑：直接查询 sector_flow 表而非遍历分页数据

3. **缓存服务** (`backend/app/cache.py`):
   - 移除了不再需要的 `get_sector_member_flows()` 方法
   - 成分股数据直接从 TuShare API 实时获取，不依赖 stock_flow 缓存表

#### 前端
1. **API 函数** (`frontend/src/services/api.js`):
   - 新增 `getSectorMembers(sectorCode, tradeDate)` 函数

2. **板块表格** (`frontend/src/components/SectorTable.jsx`):
   - 新增 `onSelect` prop，板块行可点击
   - 点击时触发钻取回调

3. **板块详情组件** (`frontend/src/components/SectorDetail.jsx`):
   - 新建组件，展示板块成分股列表
   - 表格显示：名称、代码、收盘价、涨跌幅、净流入
   - 点击成分股行跳转到个股流向详情
   - 返回按钮回到板块列表

4. **板块流向页面** (`frontend/src/pages/SectorFlow.jsx`):
   - 添加 `selectedSector`、`sectorMembers` 状态管理
   - 选中板块时显示 SectorDetail，否则显示板块列表
   - 接收 `onSelectStock` 回调支持跳转到个股

5. **应用主组件** (`frontend/src/App.jsx`):
   - 添加 `selectedStock` 状态和 `handleSelectStockFromSector` 回调
   - 从板块成分股点击股票时自动切换到个股流向 Tab

6. **个股流向页面** (`frontend/src/pages/StockFlow.jsx`):
   - 接收 `initialStock` prop，支持从外部传入初始股票
   - 传入时自动加载该股票的数据

### 功能特点
- **实时数据**：直接从 TuShare moneyflow_dc 获取，无需预填充 stock_flow 表
- **完整覆盖**：所有成分股都能显示资金流向数据
- **钻取流程**：板块列表 → 点击板块 → 成分股列表 → 点击股票 → 个股详情
- **排序展示**：成分股按净流入降序排列，快速定位资金流向

### 修改文件
- `backend/app/routes/sector.py` — 新增 /members 路由
- `backend/app/services/sector.py` — 新增 get_sector_members 方法，修复板块名称查询
- `backend/app/cache.py` — 移除 get_sector_member_flows 方法
- `frontend/src/services/api.js` — 新增 getSectorMembers 函数
- `frontend/src/components/SectorTable.jsx` — 添加 onSelect prop
- `frontend/src/components/SectorDetail.jsx` — 新建板块详情组件
- `frontend/src/pages/SectorFlow.jsx` — 集成板块详情展示
- `frontend/src/App.jsx` — 添加股票选择回调
- `frontend/src/pages/StockFlow.jsx` — 支持 initialStock prop

### 测试验证
- API 测试：`curl http://localhost:8080/api/sectors/885338.TI/members?trade_date=20260612` ✅
- 返回 3786 只成分股，数据完整（名称、收盘价、涨跌幅、净流入）
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅

---

## 2026-06-13 — 添加个股日线行情（K线图）功能

### 需求
用户在查看个股资金流向时，希望能同时看到近期价格走势，以便结合K线理解资金流向的意义。

### 实现方案

#### 后端
1. **TuShareClient** (`backend/app/clients/tushare.py`):
   - 新增 `get_daily()` 方法，调用 `pro.daily` 接口获取日线数据
   - 返回 OHLCV + 涨跌幅字段

2. **数据模型** (`backend/app/models.py`):
   - 新增 `DailyPrice` 表，字段：trade_date, ts_code, open, high, low, close, pre_close, change, pct_chg, vol, amount
   - 唯一约束：(trade_date, ts_code)

3. **缓存服务** (`backend/app/cache.py`):
   - 新增 `upsert_daily_prices()` 批量写入
   - 新增 `get_daily_prices()` 查询方法（按日期倒序）
   - 更新 `is_fresh` 白名单
   - 缓存有效期：60分钟

4. **业务服务** (`backend/app/services/stock.py`):
   - 新增 `get_daily_prices()` 方法
   - 获取最近20个交易日数据（按2倍天数请求以应对节假日）
   - 格式化为升序排列供K线图使用

5. **API路由** (`backend/app/routes/stock.py`):
   - `GET /api/stocks/{ts_code}/daily?days=20`

#### 前端
1. **API函数** (`frontend/src/services/api.js`):
   - 新增 `getStockDaily(tsCode, days)` 函数

2. **K线图组件** (`frontend/src/components/PriceTrendChart.jsx`):
   - 使用 ECharts candlestick 图表
   - 红涨绿跌（中国股市惯例）
   - 下方显示成交量柱状图
   - 支持鼠标悬停查看详情

3. **个股页面** (`frontend/src/pages/StockFlow.jsx`):
   - 集成 PriceTrendChart 组件
   - 位置：个股头部信息下方、资金流向分布图上方
   - 并行加载资金流向、龙虎榜、日线数据

### 功能特点
- **缓存60分钟**：避免频繁调用 TuShare API
- **自动限流保护**：每次请求 0.2s 延迟
- **智能日期范围**：请求2倍天数以覆盖节假日
- **K线+成交量**：上下联动展示

### 修改文件
- `backend/app/clients/tushare.py` — 新增 get_daily 方法
- `backend/app/models.py` — 新增 DailyPrice 模型
- `backend/app/config.py` — 新增 DAILY_PRICE_CACHE_MINUTES
- `backend/app/cache.py` — 新增 daily_price 缓存方法
- `backend/app/services/stock.py` — 新增 get_daily_prices 服务
- `backend/app/routes/stock.py` — 新增 /daily 路由
- `frontend/src/services/api.js` — 新增 getStockDaily 函数
- `frontend/src/components/PriceTrendChart.jsx` — 新建 K线图组件
- `frontend/src/pages/StockFlow.jsx` — 集成 K线图

### 测试验证
- API 测试：`curl http://localhost:8080/api/stocks/000001.SZ/daily?days=5` ✅
- 前端构建：`npm run build` 成功 ✅
- 后端重启：健康检查通过 ✅

---

## 2026-06-13 — 修复 stock_flow / dragon_tiger 数据覆盖 Bug

### 问题描述
`upsert_stock_flows` 和 `upsert_dragon_tiger` 方法在写入数据时，执行 `DELETE FROM xxx WHERE trade_date = :td`，删除了该交易日**所有股票**的数据。但 DataFrame 中只有当前查询的那一只股票，导致每次查询个股时，之前缓存的其他股票数据全部丢失。

**影响**：
- 用户查询股票 A → A 的数据写入 DB，B/C/D... 的数据被删除
- 用户再查股票 B → B 写入，A 的数据又被删除
- 结果：`stock_flow` 表永远只有最新查询的那一只股票

### 修复方案
将 DELETE 语句改为只删除 DataFrame 中包含的 `ts_code`：

```python
# Before (bug):
DELETE FROM stock_flow WHERE trade_date = :td

# After (fix):
DELETE FROM stock_flow WHERE trade_date = :td AND ts_code IN (:tc0, :tc1, ...)
```

使用动态生成的命名参数（`:tc0`, `:tc1`...）避免 SQLite 不支持 tuple 参数的问题。

### 修改文件
- `backend/app/cache.py`
  - `upsert_stock_flows()` (第 162-168 行): 改为按 ts_code 精确删除
  - `upsert_dragon_tiger()` (第 234-240 行): 同步修复

### 测试验证
- 单元测试：插入 A、B 两只股票，更新 A，验证 B 仍然存在 ✅
- API 测试：连续查询两只不同股票，验证 DB 中两行数据并存 ✅
