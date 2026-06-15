import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 响应拦截器：统一错误处理（忽略取消请求的错误日志）
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError') {
      // AbortController 取消的请求，静默忽略
      return Promise.reject(error)
    }
    console.error('API Error:', error.message)
    return Promise.reject(error)
  }
)

/**
 * 过滤掉 null、undefined 和空字符串的参数
 * @param {Object} params - 原始参数
 * @returns {Object} 清理后的参数
 */
function cleanParams(params) {
  const result = {}
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') result[k] = v
  })
  return result
}

/**
 * 通用 API 调用函数 — 保留给尚未提取专用函数的路由使用
 * 注意：新代码应优先使用专用函数，避免依赖此通用函数
 *
 * @param {string} url - 完整的 API 路径（如 /api/strategies/institutional/flow）
 * @returns {Promise<any>} API 响应数据
 */
export async function apiCall(url) {
  return api.get(url)
}

/**
 * 获取大盘资金总览
 * @param {string} tradeDate - YYYYMMDD，默认今天
 */
export async function getMarketOverview(tradeDate, { signal } = {}) {
  const params = tradeDate ? { trade_date: tradeDate } : {}
  return api.get('/market/overview', { params, signal })
}

/**
 * 获取北向资金数据
 * @param {string} tradeDate - YYYYMMDD，默认今天
 */
export async function getNorthFund(tradeDate, { signal } = {}) {
  const params = tradeDate ? { trade_date: tradeDate } : {}
  return api.get('/market/north', { params, signal })
}

/**
 * 获取板块列表（分页）
 * @param {number} page - 页码，从1开始
 * @param {number} size - 每页条数，默认20
 * @param {string} tradeDate - YYYYMMDD，默认今天
 * @param {string} sortOrder - 排序方向: 'desc'（净流入TOP）/ 'asc'（净流出TOP）
 */
export async function getSectors(page = 1, size = 20, tradeDate, sortOrder = 'desc', sortBy = 'net_inflow', { signal } = {}) {
  const params = { page, size, sort_order: sortOrder, sort_by: sortBy }
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/sectors', { params, signal })
}

/**
 * 搜索板块
 * @param {string} query - 搜索关键词
 * @param {string} tradeDate - YYYYMMDD，默认今天
 */
export async function searchSectors(query, tradeDate, { signal } = {}) {
  const params = { q: query }
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/sectors/search', { params, signal })
}

/**
 * 搜索个股
 * @param {string} query - 搜索关键词（代码/名称）
 */
export async function searchStocks(query, { signal } = {}) {
  return api.get('/stocks/search', { params: { q: query }, signal })
}

/**
 * 获取个股资金流向详情
 * @param {string} tsCode - 股票代码，如 000001.SZ
 */
export async function getStockDetail(tsCode, { signal } = {}) {
  return api.get(`/stocks/${tsCode}`, { signal })
}

/**
 * 获取个股龙虎榜
 * @param {string} tsCode - 股票代码
 */
export async function getDragonTiger(tsCode, { signal } = {}) {
  return api.get(`/stocks/${tsCode}/dragon`, { signal })
}

/**
 * 获取资金趋势（近N日北向资金）
 * @param {number} days - 最近N个交易日，默认10
 */
export async function getFundTrend(days = 10, { signal } = {}) {
  return api.get('/market/trend', { params: { days }, signal })
}

/**
 * 获取资金流向趋势（近N日各类型资金净流入）
 * @param {number} days - 最近N个交易日，默认5
 */
export async function getFlowTrend(days = 5, { signal } = {}) {
  return api.get('/market/flow-trend', { params: { days }, signal })
}

/**
 * 获取全市场成交额趋势
 * @param {number} days - 最近N个交易日，默认30
 */
export async function getTurnoverTrend(days = 30, { signal } = {}) {
  return api.get('/market/turnover/trend', { params: { days }, signal })
}

/**
 * 获取个股日线行情数据（K线图）
 * @param {string} tsCode - 股票代码，如 000001.SZ
 * @param {number} days - 最近N个交易日，默认20
 */
export async function getStockDaily(tsCode, days = 20, { signal } = {}) {
  return api.get(`/stocks/${tsCode}/daily`, { params: { days }, signal })
}

/**
 * 获取个股资金流向趋势（近N日各类型资金净流入）
 * @param {string} tsCode - 股票代码，如 000001.SZ
 * @param {number} days - 最近N个交易日，默认10
 */
export async function getStockFlowTrend(tsCode, days = 10, { signal } = {}) {
  return api.get(`/stocks/${tsCode}/flow-trend`, { params: { days }, signal })
}

/**
 * 获取个股基本面指标（PE、PB、市值等）
 * @param {string} tsCode - 股票代码，如 000001.SZ
 */
export async function getStockBasic(tsCode, { signal } = {}) {
  return api.get(`/stocks/${tsCode}/basic`, { signal })
}

/**
 * 获取板块成分股列表
 * @param {string} sectorCode - 板块代码
 * @param {string} tradeDate - YYYYMMDD，默认今天
 */
export async function getSectorMembers(sectorCode, tradeDate, { signal } = {}) {
  const params = tradeDate ? { trade_date: tradeDate } : {}
  return api.get(`/sectors/${sectorCode}/members`, { params, signal })
}

/**
 * 获取板块资金流向趋势（近N日净流入数据）
 * @param {string} sectorCode - 板块代码
 * @param {number} days - 最近N个交易日，默认30
 */
export async function getSectorTrend(sectorCode, days = 30, { signal } = {}) {
  return api.get(`/sectors/${sectorCode}/trend`, { params: { days }, signal })
}

/**
 * 获取个股资金流向排行榜
 * @param {string} tradeDate - YYYYMMDD，默认今天
 * @param {string} type - net_inflow（净流入）或 net_outflow（净流出）
 * @param {number} limit - 返回数量，默认20
 */
export async function getStockRanking(tradeDate, type = 'net_inflow', limit = 20, { signal } = {}) {
  const params = { type, limit }
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/market/stock-ranking', { params, signal })
}

/**
 * 获取全市场涨跌分布
 * @param {string} tradeDate - YYYYMMDD，默认今天
 */
export async function getMarketBreadth(tradeDate, { signal } = {}) {
  const params = {}
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/market/breadth', { params, signal })
}

/**
 * 获取市场宽度指标快照（涨跌分布+涨跌停+均线突破+换手率+温度）
 * @param {string} tradeDate - YYYYMMDD，默认最新
 */
export async function getBreadthSnapshot(tradeDate, { signal } = {}) {
  const params = {}
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/market-breadth', { params, signal })
}

/**
 * 获取市场温度历史
 * @param {number} days - 最近N个交易日，默认30
 */
export async function getTemperatureHistory(days = 30, { signal } = {}) {
  return api.get('/market-breadth/temperature', { params: { days }, signal })
}

/**
 * 获取涨跌停统计数据
 * @param {string} tradeDate - YYYYMMDD，默认今天
 */
export async function getLimitStats(tradeDate, { signal } = {}) {
  const params = {}
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/market/limit-stats', { params, signal })
}

/**
 * 获取三大指数实时行情
 * @param {string} tradeDate - YYYYMMDD，默认今天
 */
export async function getMarketIndices(tradeDate, { signal } = {}) {
  const params = {}
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/market/indices', { params, signal })
}

/**
 * 多维度选股筛选器
 * @param {Object} params - 筛选参数
 * @param {string} params.trade_date - 交易日期 YYYYMMDD
 * @param {number} params.pe_min - PE(TTM) 最小值
 * @param {number} params.pe_max - PE(TTM) 最大值
 * @param {number} params.pb_min - PB 最小值
 * @param {number} params.pb_max - PB 最大值
 * @param {number} params.mv_min - 总市值最小值(亿元)
 * @param {number} params.mv_max - 总市值最大值(亿元)
 * @param {number} params.turnover_min - 换手率最小值(%)
 * @param {number} params.turnover_max - 换手率最大值(%)
 * @param {number} params.volume_ratio_min - 量比最小值
 * @param {number} params.volume_ratio_max - 量比最大值
 * @param {number} params.dv_min - 股息率最小值(%)
 * @param {number} params.dv_max - 股息率最大值(%)
 * @param {number} params.net_inflow_min - 净流入最小值(万元)
 * @param {string} params.name - 股票名称/代码模糊搜索
 * @param {string} params.industry - 行业筛选
 * @param {string} params.sort_by - 排序字段
 * @param {string} params.sort_order - 排序方向 asc/desc
 * @param {number} params.page - 页码
 * @param {number} params.page_size - 每页条数
 */
export async function screenStocks(params = {}, { signal } = {}) {
  return api.get('/screener/stocks', { params: cleanParams(params), signal })
}

/**
 * 技术指标选股
 * @param {Object} params - 筛选参数
 * @param {string} params.trade_date - 交易日期 YYYYMMDD
 * @param {boolean} params.macd_golden - MACD金叉
 * @param {boolean} params.macd_dead - MACD死叉
 * @param {boolean} params.kdj_golden - KDJ金叉
 * @param {boolean} params.kdj_overbought - KDJ超买
 * @param {boolean} params.kdj_oversold - KDJ超卖
 * @param {boolean} params.rsi_oversold - RSI超卖
 * @param {boolean} params.rsi_overbought - RSI超买
 * @param {boolean} params.boll_break_upper - 突破布林上轨
 * @param {boolean} params.boll_break_lower - 跌破布林下轨
 * @param {boolean} params.cci_oversold - CCI超卖
 * @param {boolean} params.cci_overbought - CCI超买
 * @param {boolean} params.ma5_above_ma20 - MA5在MA20上方
 * @param {number} params.page - 页码
 * @param {number} params.page_size - 每页条数
 */
export async function screenBySignals(params = {}, { signal } = {}) {
  return api.get('/technical/screen', { params: cleanParams(params), signal })
}

/**
 * 概念板块列表
 * @param {number} page - 页码
 * @param {number} page_size - 每页条数
 * @param {string} sort_by - 排序字段
 * @param {string} sort_order - 排序方向 asc/desc
 * @param {string} name - 概念名称模糊搜索
 */
export async function getConcepts(page = 1, page_size = 20, sort_by = 'pct_change', sort_order = 'desc', name = '', { signal } = {}) {
  const params = { page, page_size, sort_by, sort_order }
  if (name) params.name = name
  return api.get('/concepts', { params, signal })
}

/**
 * 概念板块详情
 * @param {string} tsCode - 概念代码
 */
export async function getConceptDetail(tsCode, { signal } = {}) {
  return api.get(`/concepts/${tsCode}`, { signal })
}

/**
 * 概念板块成分股
 * @param {string} tsCode - 概念代码
 */
export async function getConceptMembers(tsCode, { signal } = {}) {
  return api.get(`/concepts/${tsCode}/members`, { signal })
}

/**
 * 获取所有策略列表
 */
export async function getStrategies({ signal } = {}) {
  return api.get('/strategies/', { signal })
}

/**
 * 执行单个策略
 * @param {string} name - 策略名称
 * @param {Object} params - { trade_date, limit }
 */
export async function executeStrategy(name, params = {}, { signal } = {}) {
  return api.post(`/strategies/execute/${name}`, cleanParams(params), { signal })
}

/**
 * 一次性执行所有策略
 * @param {Object} params - { trade_date }
 */
export async function executeAllStrategies(params = {}, { signal } = {}) {
  return api.post('/strategies/execute-all', cleanParams(params), { signal })
}

/**
 * 策略共振扫描：找出被多个策略同时选中的股票
 * @param {Object} params - { trade_date, min_strategies }
 */
export async function getStrategyConfluence(params = {}, { signal } = {}) {
  return api.get('/strategies/confluence', { params: cleanParams(params), signal })
}

/**
 * 回测指定策略的历史表现
 * @param {string} name - 策略名称
 * @param {Object} params - { start_date, end_date, hold_days, limit }
 */
export async function backtestStrategy(name, params = {}, { signal } = {}) {
  return api.get(`/strategies/backtest/${name}`, { params: cleanParams(params), signal })
}

/**
 * 策略板块热力图
 * @param {Object} params - { trade_date }
 */
export async function getStrategySectorHeatmap(params = {}, { signal } = {}) {
  return api.get('/strategies/sector-heatmap', { params: cleanParams(params), signal })
}


// === 策略智能分析 API ===

/**
 * 获取所有策略健康度概览
 * @param {number} lookbackDays - 回看天数
 */
export async function getStrategyHealth(lookbackDays = 20, { signal } = {}) {
  return api.get('/strategies/intelligence/health', { params: { lookback_days: lookbackDays }, signal })
}

/**
 * 获取策略胜率趋势
 * @param {string} strategyName - 策略名称
 * @param {number} days - 趋势天数
 */
export async function getStrategyTrend(strategyName, days = 30, { signal } = {}) {
  return api.get(`/strategies/intelligence/trend/${strategyName}`, { params: { days }, signal })
}

/**
 * 对比多个策略的表现
 * @param {string[]} strategyNames - 策略名称列表
 * @param {number} days - 回看天数
 */
export async function compareStrategies(strategyNames, days = 20, { signal } = {}) {
  return api.get('/strategies/intelligence/compare', { params: { strategies: strategyNames.join(','), days }, signal })
}

/**
 * 获取策略推荐
 */
export async function getStrategyRecommendation({ signal } = {}) {
  return api.get('/strategies/intelligence/recommend', { signal })
}

// === 策略组合 API ===

/**
 * 组合多个策略
 * @param {string[]} strategyNames - 策略名称列表
 * @param {string} operator - 逻辑运算符: AND 或 OR
 * @param {string} tradeDate - 交易日期 YYYYMMDD
 */
export async function composeStrategies(strategyNames, operator = 'AND', tradeDate, { signal } = {}) {
  const params = { strategies: strategyNames.join(','), operator }
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/strategies/compose', { params: cleanParams(params), signal })
}

/**
 * 获取预置的策略组合
 */
export async function getComposePresets({ signal } = {}) {
  return api.get('/strategies/compose/presets', { signal })
}

// === 市场状态检测 API ===

/**
 * 获取当前市场状态分析
 */
export async function getMarketRegime({ signal } = {}) {
  return api.get('/strategies/regime', { signal })
}

/**
 * 获取市场状态历史
 * @param {number} limit - 返回天数
 */
export async function getRegimeHistory(limit = 20, { signal } = {}) {
  return api.get('/strategies/regime/history', { params: { limit }, signal })
}

/**
 * 获取当前市场状态下的策略推荐
 */
export async function getRegimeRecommendations({ signal } = {}) {
  return api.get('/strategies/regime/recommend', { signal })
}

// === 策略相关性分析 API ===

/**
 * 获取策略选股重叠度（Jaccard 相似系数）
 * @param {string} tradeDate - YYYYMMDD，默认最新交易日
 */
export async function getStrategyOverlap(tradeDate, { signal } = {}) {
  const params = tradeDate ? { trade_date: tradeDate } : {}
  return api.get('/strategies/correlation/overlap', { params, signal })
}

/**
 * 获取策略收益率相关性矩阵（Pearson 相关系数）
 * @param {number} days - 回看天数
 */
export async function getStrategyCorrelationMatrix(days = 20, { signal } = {}) {
  return api.get('/strategies/correlation/matrix', { params: { days }, signal })
}

/**
 * 获取策略配置优化（均值方差分析）
 * @param {number} days - 回看天数
 */
export async function getStrategyOptimize(days = 20, { signal } = {}) {
  return api.get('/strategies/correlation/optimize', { params: { days }, signal })
}

/**
 * 获取体制自适应策略配置
 */
export async function getRegimeAllocation({ signal } = {}) {
  return api.get('/strategies/correlation/regime', { signal })
}

/**
 * 获取策略配置综合分析
 * @param {string} tradeDate - YYYYMMDD
 */
export async function getPortfolioSummary(tradeDate, { signal } = {}) {
  const params = tradeDate ? { trade_date: tradeDate } : {}
  return api.get('/strategies/correlation/summary', { params, signal })
}

// === 策略信号矩阵 API ===

/**
 * 获取策略信号矩阵
 * @param {string} tradeDate - YYYYMMDD，默认最新交易日
 * @param {number} minStrategies - 最少触发策略数，默认1
 * @param {string} category - 策略分类过滤: value/momentum/flow/event/combo
 */
export async function getSignalMatrix(tradeDate, minStrategies = 1, category = null, { signal } = {}) {
  const params = {}
  if (tradeDate) params.trade_date = tradeDate
  if (minStrategies > 1) params.min_strategies = minStrategies
  if (category) params.category = category
  return api.get('/strategies/signals/matrix', { params: cleanParams(params), signal })
}

// === 自选股 API ===

/**
 * 获取自选股列表
 * @param {string} groupName - 分组名称筛选（可选）
 */
export async function getWatchlist(groupName, { signal } = {}) {
  const params = groupName ? { group_name: groupName } : {}
  return api.get('/watchlist', { params, signal })
}

/**
 * 添加自选股
 * @param {string} tsCode - 股票代码
 * @param {string} groupName - 分组名称
 * @param {string} notes - 备注
 */
export async function addToWatchlist(tsCode, groupName = 'default', notes = '', { signal } = {}) {
  return api.post('/watchlist', { ts_code: tsCode, group_name: groupName, notes }, { signal })
}

/**
 * 删除自选股
 * @param {string} tsCode - 股票代码
 */
export async function removeFromWatchlist(tsCode, { signal } = {}) {
  return api.delete(`/watchlist/${tsCode}`, { signal })
}

/**
 * 更新自选股
 * @param {string} tsCode - 股票代码
 * @param {Object} data - { group_name, notes }
 */
export async function updateWatchlist(tsCode, data, { signal } = {}) {
  return api.put(`/watchlist/${tsCode}`, data, { signal })
}

/**
 * 获取所有自选股的信号汇总
 */
export async function getWatchlistSignals({ signal } = {}) {
  return api.get('/watchlist/signals', { signal })
}

/**
 * 获取单只股票的信号详情
 * @param {string} tsCode - 股票代码
 */
export async function getStockSignals(tsCode, { signal } = {}) {
  return api.get(`/watchlist/${tsCode}/signals`, { signal })
}

/**
 * 获取自选股统计信息
 */
export async function getWatchlistStats({ signal } = {}) {
  return api.get('/watchlist/stats', { signal })
}

/** AI 工作日志 */
export async function getActivityLogs(params = {}, { signal } = {}) {
  return api.get('/activity-log', { params: cleanParams(params), signal })
}

export async function getActivityLog(id, { signal } = {}) {
  return api.get(`/activity-log/${id}`, { signal })
}

export async function createActivityLog(data, { signal } = {}) {
  return api.post('/activity-log', data, { signal })
}

// === 资金流向背离分析 API ===

/**
 * 资金流向背离扫描
 * @param {Object} params - { trade_date, lookback_days, signal_type, min_strength }
 */
export async function getDivergenceScan(params = {}, { signal } = {}) {
  return api.get('/strategies/flow-intelligence/divergence-scan', { params: cleanParams(params), signal })
}

/**
 * 深度分析单只股票的资金流向背离
 * @param {string} tsCode - 股票代码
 * @param {number} lookbackDays - 回看天数
 */
export async function analyzeStockFlow(tsCode, lookbackDays = 10, { signal } = {}) {
  return api.get(`/strategies/flow-intelligence/analyze/${tsCode}`, { params: { lookback_days: lookbackDays }, signal })
}

// === 筹码穿透率 & 股权质押风险 API ===

/**
 * 获取筹码穿透率 & 股权质押风险分析
 * @param {Object} params - { trade_date, pledge_ratio_min, pledge_ratio_max }
 */
export async function getChipAnalysis(params = {}, { signal } = {}) {
  return api.get('/strategies/chip-analysis', { params: cleanParams(params), signal })
}

// === 股票健康度评分 API ===

/**
 * 获取单只股票的综合健康度评分
 * @param {string} tsCode - 股票代码
 * @param {string} tradeDate - 交易日 YYYYMMDD
 */
export async function getStockHealth(tsCode, tradeDate, { signal } = {}) {
  const params = {}
  if (tradeDate) params.trade_date = tradeDate
  return api.get(`/strategies/health/${tsCode}`, { params, signal })
}

/**
 * 获取全市场 TOP 健康度股票排名
 * @param {Object} params - { trade_date, limit }
 */
export async function getMarketHealthTop(params = {}, { signal } = {}) {
  return api.get('/strategies/health/market/top', { params: cleanParams(params), signal })
}

/**
 * 创建一个带有 AbortController 的 Axios 请求包装器。
 * 用于在 useEffect cleanup 中取消过期请求，防止竞态条件。
 *
 * @param {Object} axiosConfig - Axios 请求配置（如 { url, method, params, data }）
 * @param {AbortSignal} signal - AbortController.signal
 * @returns {Promise} Axios 响应 promise
 */
export function cancellableRequest(axiosConfig, signal) {
  return api({ ...axiosConfig, signal })
}

/**
 * 创建一个 AbortController 并返回 signal 和 abort 函数。
 * 典型用法：
 *   useEffect(() => {
 *     const controller = new AbortController();
 *     fetchData(controller.signal);
 *     return () => controller.abort();
 *   }, [deps]);
 */

// === 量化因子模型 API ===

/**
 * 获取因子表现历史
 * @param {number} lookbackDays - 回看天数
 * @param {string} tradeDate - YYYYMMDD
 */
export async function getFactorPerformance(lookbackDays = 20, tradeDate, { signal } = {}) {
  const params = { lookback_days: lookbackDays }
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/strategies/factor-model/performance', { params: cleanParams(params), signal })
}

/**
 * 获取因子动量信号
 * @param {number} recentDays - 近期天数
 * @param {number} olderDays - 历史天数
 * @param {string} tradeDate - YYYYMMDD
 */
export async function getFactorMomentum(recentDays = 5, olderDays = 15, tradeDate, { signal } = {}) {
  const params = { recent_days: recentDays, older_days: olderDays }
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/strategies/factor-model/momentum', { params: cleanParams(params), signal })
}

/**
 * 获取当前因子轮动状态
 * @param {string} tradeDate - YYYYMMDD
 */
export async function getFactorRegime(tradeDate, { signal } = {}) {
  const params = tradeDate ? { trade_date: tradeDate } : {}
  return api.get('/strategies/factor-model/regime', { params, signal })
}

/**
 * 因子轮动选股
 * @param {number} topFactors - 取前N个因子
 * @param {number} limit - 选股数量
 * @param {string} tradeDate - YYYYMMDD
 */
export async function getFactorRotation(topFactors = 2, limit = 30, tradeDate, { signal } = {}) {
  const params = { top_factors: topFactors, limit }
  if (tradeDate) params.trade_date = tradeDate
  return api.get('/strategies/factor-model/rotation', { params: cleanParams(params), signal })
}

/**
 * 获取单股因子暴露度
 * @param {string} tsCode - 股票代码
 * @param {string} tradeDate - YYYYMMDD
 */
export async function getFactorExposure(tsCode, tradeDate, { signal } = {}) {
  const params = tradeDate ? { trade_date: tradeDate } : {}
  return api.get(`/strategies/factor-model/exposure/${tsCode}`, { params, signal })
}

// === 内部人与机构智能 API ===

/**
 * 获取全市场置信度扫描
 * @param {number} limit - 返回数量，默认50
 */
export async function getInsiderConviction(limit = 50, { signal } = {}) {
  return api.get('/insider/conviction', { params: { limit }, signal })
}

/**
 * 获取单只股票的详细置信度分析
 * @param {string} tsCode - 股票代码，如 000001.SZ
 */
export async function getInsiderConvictionDetail(tsCode, { signal } = {}) {
  return api.get(`/insider/conviction/${tsCode}`, { signal })
}

/**
 * 获取指定股票的内部人交易明细
 * @param {string} tsCode - 股票代码
 * @param {number} days - 回溯天数，默认30
 */
export async function getInsiderTrades(tsCode, days = 30, { signal } = {}) {
  return api.get(`/insider/trades/${tsCode}`, { params: { days }, signal })
}

/**
 * 获取股东人数变动趋势
 * @param {string} tsCode - 股票代码
 */
export async function getShareholderTrend(tsCode, { signal } = {}) {
  return api.get(`/insider/shareholder-trend/${tsCode}`, { signal })
}

// ==================== Portfolio Constructor ====================

/**
 * 获取组合构建候选股票池
 * @param {number} minStrategies - 最少策略匹配数
 */
export async function getPortfolioCandidates(minStrategies = 2, { signal } = {}) {
  return api.get('/portfolio/candidates', { params: { min_strategies: minStrategies }, signal })
}

/**
 * 优化组合配置
 * @param {string} method - 优化方法: mean_variance/risk_parity/equal_weight/max_sharpe
 * @param {number} maxStocks - 最大持仓数
 * @param {number} maxSectorPct - 单行业最大占比
 */
export async function optimizePortfolio(method = 'mean_variance', maxStocks = 15, maxSectorPct = 0.30, { signal } = {}) {
  return api.get('/portfolio/optimize', { params: { method, max_stocks: maxStocks, max_sector_pct: maxSectorPct }, signal })
}

/**
 * 对比多种优化方法
 */
export async function comparePortfolios({ signal } = {}) {
  return api.get('/portfolio/compare', { signal })
}

/**
 * 获取绩效归因
 * @param {string} method - 优化方法
 */
export async function getPortfolioAttribution(method = 'mean_variance', { signal } = {}) {
  return api.get('/portfolio/attribution', { params: { method }, signal })
}

export default api
