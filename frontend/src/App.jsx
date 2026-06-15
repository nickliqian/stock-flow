import React, { useState, Component, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom'
import { ConfigProvider, Layout, Menu, Button, theme, Space, Typography, DatePicker, Spin } from 'antd'
import {
  ReloadOutlined,
  BarChartOutlined,
  StockOutlined,
  FundOutlined,
  CalendarOutlined,
  SearchOutlined,
  AppstoreOutlined,
  RocketOutlined,
  StarOutlined,
  RobotOutlined,
  BulbOutlined,
  CrownOutlined,
  ExperimentOutlined,
  BankOutlined,
  WarningOutlined,
  SwapOutlined,
  PieChartOutlined,
  RiseOutlined,
  BookOutlined,
  AlertOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import zhCN from 'antd/locale/zh_CN'

dayjs.locale('zh-cn')

// React.lazy 动态导入 — 代码分割，按需加载页面组件
const MarketOverview = React.lazy(() => import('./pages/MarketOverview'))
const SectorFlow = React.lazy(() => import('./pages/SectorFlow'))
const StockFlow = React.lazy(() => import('./pages/StockFlow'))
const StockScreener = React.lazy(() => import('./pages/StockScreener'))
const StrategyDashboard = React.lazy(() => import('./pages/StrategyDashboard'))
const FactorModel = React.lazy(() => import('./pages/FactorModel'))
const ActivityLog = React.lazy(() => import('./pages/ActivityLog'))
const Watchlist = React.lazy(() => import('./pages/Watchlist'))
const SmartAnalysis = React.lazy(() => import('./pages/SmartAnalysis'))
const ChipIntelligence = React.lazy(() => import('./pages/ChipIntelligence'))
const StrategyEvolution = React.lazy(() => import('./pages/StrategyEvolution'))
const InstitutionalRadar = React.lazy(() => import('./pages/InstitutionalRadar'))
const MarketBreadth = React.lazy(() => import('./pages/MarketBreadth'))
const AdaptiveWeight = React.lazy(() => import('./pages/AdaptiveWeight'))
const ShareholderIntelligence = React.lazy(() => import('./pages/ShareholderIntelligence'))
const CrowdingEvolution = React.lazy(() => import('./pages/CrowdingEvolution'))
const SignalEffectiveness = React.lazy(() => import('./pages/SignalEffectiveness'))
const EventCalendar = React.lazy(() => import('./pages/EventCalendar'))
const InsiderConviction = React.lazy(() => import('./pages/InsiderConviction'))
const AlphaScoring = React.lazy(() => import('./pages/AlphaScoring'))
const Recommendation = React.lazy(() => import('./pages/Recommendation'))
const PairTrading = React.lazy(() => import('./pages/PairTrading'))
const PortfolioBuilder = React.lazy(() => import('./pages/PortfolioBuilder'))
const MultiTimeframe = React.lazy(() => import('./pages/MultiTimeframe'))
const ResearchBrowser = React.lazy(() => import('./pages/ResearchBrowser'))
const VolatilityClustering = React.lazy(() => import('./pages/VolatilityClustering'))
const SignalAlerts = React.lazy(() => import('./pages/SignalAlerts'))
const Dashboard = React.lazy(() => import('./pages/Dashboard'))

const { Header, Sider, Content } = Layout

/**
 * Error Boundary 组件
 * 捕获子组件的渲染错误，防止整个应用白屏
 */
class ErrorBoundary extends Component {
  state = { hasError: false, error: null }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('Component error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, textAlign: 'center' }}>
          <Typography.Title level={4} type="danger">页面加载出错</Typography.Title>
          <Typography.Paragraph type="secondary">
            {this.state.error?.message || '未知错误'}
          </Typography.Paragraph>
          <Button type="primary" onClick={() => this.setState({ hasError: false, error: null })}>
            重试
          </Button>
        </div>
      )
    }
    return this.props.children
  }
}

// 路由 key → 菜单 key 映射
const ROUTE_MAP = {
  '/': 'dashboard',
  '/overview': 'overview',
  '/sector': 'sector',
  '/stock': 'stock',
  '/screener': 'screener',
  '/strategy': 'strategy',
  '/smart': 'smart',
  '/breadth': 'breadth',
  '/chip': 'chip',
  '/evolution': 'evolution',
  '/adaptive': 'adaptive',
  '/factormodel': 'factormodel',
  '/watchlist': 'watchlist',
  '/activity': 'activity',
  '/research': 'research',
  '/radar': 'radar',
  '/shareholder': 'shareholder',
  '/events': 'events',
  '/crowding': 'crowding',
  '/effectiveness': 'effectiveness',
  '/insider': 'insider',
  '/alpha': 'alpha',
  '/recommendation': 'recommendation',
  '/pairtrading': 'pairtrading',
  '/portfolio': 'portfolio',
  '/multi-timeframe': 'multi-timeframe',
  '/volatility': 'volatility',
  '/alerts': 'alerts',
}

const menuItems = [
  {
    key: 'market',
    icon: <BarChartOutlined />,
    label: '市场概览',
    children: [
      { key: 'overview', label: '大盘总览' },
      { key: 'sector', label: '板块资金' },
      { key: 'stock', label: '个股资金' },
      { key: 'breadth', label: '市场宽度' },
    ],
  },
  {
    key: 'pick',
    icon: <SearchOutlined />,
    label: '选股工具',
    children: [
      { key: 'screener', label: '多维选股' },
      { key: 'recommendation', label: '智能荐股' },
      { key: 'watchlist', label: '自选股' },
    ],
  },
  {
    key: 'strat',
    icon: <RocketOutlined />,
    label: '策略中心',
    children: [
      { key: 'strategy', label: '策略总览' },
      { key: 'evolution', label: '策略进化' },
      { key: 'adaptive', label: '自适应权重' },
      { key: 'factormodel', label: '因子轮动' },
      { key: 'effectiveness', label: '信号有效性' },
      { key: 'crowding', label: '拥挤度' },
    ],
  },
  {
    key: 'analysis',
    icon: <BulbOutlined />,
    label: '智能分析',
    children: [
      { key: 'smart', label: '智能分析' },
      { key: 'chip', label: '筹码分析' },
      { key: 'radar', label: '机构雷达' },
      { key: 'shareholder', label: '股东情报' },
      { key: 'insider', label: '内部人信号' },
      { key: 'alpha', label: 'Alpha评分' },
    ],
  },
  {
    key: 'tools',
    icon: <ExperimentOutlined />,
    label: '高级工具',
    children: [
      { key: 'pairtrading', label: '配对交易' },
      { key: 'portfolio', label: '组合构建' },
      { key: 'multi-timeframe', label: '多周期共振' },
      { key: 'volatility', label: '波动率分区' },
      { key: 'alerts', label: '信号告警' },
    ],
  },
  {
    key: 'research-group',
    icon: <BookOutlined />,
    label: '研究资料',
    children: [
      { key: 'research', label: '资料浏览' },
      { key: 'events', label: '事件日历' },
    ],
  },
  {
    key: 'system',
    icon: <RobotOutlined />,
    label: '系统',
    children: [
      { key: 'activity', label: 'AI日志' },
    ],
  },
]

// 页面信息映射 — 动态显示页面标题和描述
const PAGE_INFO = {
  dashboard: { title: '首页', desc: '市场概览与快捷导航' },
  overview: { title: '大盘总览', desc: '上证/深成/创业板资金流向与涨跌统计' },
  sector: { title: '板块资金', desc: '行业板块资金流向排行与成分股' },
  stock: { title: '个股资金', desc: '个股主力资金流向与趋势分析' },
  breadth: { title: '市场宽度', desc: '涨跌分布、市场温度与宽度趋势' },
  screener: { title: '多维选股', desc: '技术面+基本面多维度筛选' },
  recommendation: { title: '智能荐股', desc: '7维度综合评分BUY/HOLD/AVOID' },
  watchlist: { title: '自选股', desc: '关注股票的资金流向追踪' },
  strategy: { title: '策略总览', desc: '23个量化策略引擎信号矩阵' },
  evolution: { title: '策略进化', desc: '策略衰减检测与参数优化' },
  adaptive: { title: '自适应权重', desc: '动态策略权重计算' },
  factormodel: { title: '因子轮动', desc: '价值/动量/资金/事件因子追踪' },
  effectiveness: { title: '信号有效性', desc: '策略信号质量与信任度评估' },
  crowding: { title: '拥挤度', desc: '策略拥挤度演进与风险预警' },
  smart: { title: '智能分析', desc: 'AI驱动的综合市场分析' },
  chip: { title: '筹码分析', desc: '筹码分布与成本分析' },
  radar: { title: '机构雷达', desc: '龙虎榜机构席位动向' },
  shareholder: { title: '股东情报', desc: '股东人数变动与持仓分析' },
  insider: { title: '内部人信号', desc: '高管增持/减持与置信度评分' },
  alpha: { title: 'Alpha评分', desc: '行业相对Alpha评分与热力图' },
  pairtrading: { title: '配对交易', desc: '协整配对发现与价差信号' },
  portfolio: { title: '组合构建', desc: '等权/风险平价/因子加权组合' },
  'multi-timeframe': { title: '多周期共振', desc: '日/周/月多周期动量共振' },
  volatility: { title: '波动率分区', desc: '全市场波动率聚类与风险分区' },
  alerts: { title: '信号告警', desc: '实时策略信号与异常检测' },
  research: { title: '研究资料', desc: '搜集资料浏览与手动录入' },
  events: { title: '事件日历', desc: '财报披露/限售解禁/回购信号' },
  activity: { title: 'AI日志', desc: '系统执行记录与状态监控' },
}

/**
 * 应用主组件
 * 使用 React Router + Ant Design Layout 构建专业金融终端界面
 */
function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)
  const [selectedStock, setSelectedStock] = useState(null)
  const [tradeDate, setTradeDate] = useState(null)

  // 从 URL 获取当前 tab
  const activeTab = ROUTE_MAP[location.pathname] || 'dashboard'

  // 菜单点击 → 导航到对应 URL
  const handleMenuClick = ({ key }) => {
    navigate(`/${key}`)
  }

  // 从子组件跳转
  const handleSelectStockFromSector = (stock) => {
    setSelectedStock(stock)
    navigate('/stock')
  }

  const handleSelectSectorFromOverview = () => {
    navigate('/sector')
  }

  const stockProps = activeTab === 'stock' && selectedStock
    ? { initialStock: selectedStock }
    : {}

  // 根据路由渲染对应页面
  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard key={`dashboard-${refreshKey}`} />
      case 'overview':
        return (
          <MarketOverview
            key={`overview-${refreshKey}`}
            tradeDate={tradeDate}
            onTradeDateChange={setTradeDate}
            onSelectStock={handleSelectStockFromSector}
            onSelectSector={handleSelectSectorFromOverview}
          />
        )
      case 'sector':
        return (
          <SectorFlow
            key={`sector-${refreshKey}`}
            tradeDate={tradeDate}
            onSelectStock={handleSelectStockFromSector}
          />
        )
      case 'stock':
        return (
          <StockFlow
            key={`stock-${refreshKey}`}
            tradeDate={tradeDate}
            {...stockProps}
          />
        )
      case 'screener':
        return (
          <StockScreener
            key={`screener-${refreshKey}`}
            tradeDate={tradeDate}
            onSelectStock={handleSelectStockFromSector}
          />
        )
      case 'strategy':
        return (
          <StrategyDashboard
            key={`strategy-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      case 'smart':
        return (
          <SmartAnalysis
            key={`smart-${refreshKey}`}
            tradeDate={tradeDate}
            onSelectStock={handleSelectStockFromSector}
          />
        )
      case 'breadth':
        return (
          <MarketBreadth
            key={`breadth-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      case 'chip':
        return (
          <ChipIntelligence
            key={`chip-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      case 'evolution':
        return (
          <StrategyEvolution
            key={`evolution-${refreshKey}`}
          />
        )
      case 'adaptive':
        return (
          <AdaptiveWeight
            key={`adaptive-${refreshKey}`}
          />
        )
      case 'factormodel':
        return (
          <FactorModel
            key={`factormodel-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      case 'watchlist':
        return (
          <Watchlist
            key={`watchlist-${refreshKey}`}
            tradeDate={tradeDate}
            onSelectStock={handleSelectStockFromSector}
          />
        )
      case 'activity':
        return (
          <ActivityLog
            key={`activity-${refreshKey}`}
          />
        )
      case 'research':
        return (
          <ResearchBrowser
            key={`research-${refreshKey}`}
          />
        )
      case 'radar':
        return (
          <InstitutionalRadar
            key={`radar-${refreshKey}`}
          />
        )
      case 'shareholder':
        return (
          <ShareholderIntelligence
            key={`shareholder-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      case 'events':
        return (
          <EventCalendar
            key={`events-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      case 'crowding':
        return (
          <CrowdingEvolution
            key={`crowding-${refreshKey}`}
          />
        )
      case 'effectiveness':
        return (
          <SignalEffectiveness
            key={`effectiveness-${refreshKey}`}
          />
        )
      case 'insider':
        return (
          <InsiderConviction
            key={`insider-${refreshKey}`}
          />
        )
      case 'alpha':
        return (
          <AlphaScoring
            key={`alpha-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      case 'recommendation':
        return (
          <Recommendation
            key={`recommendation-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      case 'pairtrading':
        return (
          <PairTrading
            key={`pairtrading-${refreshKey}`}
          />
        )
      case 'portfolio':
        return (
          <PortfolioBuilder
            key={`portfolio-${refreshKey}`}
          />
        )
      case 'multi-timeframe':
        return (
          <MultiTimeframe
            key={`multi-timeframe-${refreshKey}`}
          />
        )
      case 'volatility':
        return (
          <VolatilityClustering
            key={`volatility-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      case 'alerts':
        return (
          <SignalAlerts
            key={`alerts-${refreshKey}`}
            tradeDate={tradeDate}
          />
        )
      default:
        return <Navigate to="/" replace />
    }
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1677ff',
          colorSuccess: '#3f8600',
          colorError: '#cf1322',
          colorWarning: '#d48806',
          borderRadius: 6,
          fontFamily: "-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif",
        },
      }}
    >
      <Layout style={{ minHeight: '100vh' }}>
        {/* 左侧导航栏 */}
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          width={200}
          collapsedWidth={60}
          theme="light"
          style={{
            overflow: 'auto',
            height: '100vh',
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
            zIndex: 100,
          }}
        >
          {/* Logo 区域 */}
          <div
            style={{
              height: 56,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'linear-gradient(135deg, #001529 0%, #1a1a2e 100%)',
              overflow: 'hidden',
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              borderBottom: '1px solid rgba(255,255,255,0.1)',
            }}
            onClick={() => navigate('/')}
          >
            {collapsed ? (
              <span style={{ fontSize: 24, filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))' }}>💹</span>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 26, filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))' }}>💹</span>
                <span style={{
                  color: '#fff',
                  fontSize: 15,
                  fontWeight: 600,
                  letterSpacing: 1,
                  textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                }}>
                  资金流向系统
                </span>
              </div>
            )}
          </div>
          <Menu
            theme="light"
            mode="inline"
            selectedKeys={[activeTab]}
            defaultOpenKeys={['market', 'pick', 'strat', 'analysis', 'tools', 'research-group', 'system']}
            items={menuItems}
            onClick={handleMenuClick}
            style={{ borderRight: 0, maxHeight: 'calc(100vh - 48px)', overflowY: 'auto' }}
          />
        </Sider>

        {/* 右侧内容区 */}
        <Layout style={{ marginLeft: collapsed ? 60 : 200, transition: 'margin-left 0.2s' }}>
          {/* 顶部标题栏 */}
          <Header
            style={{
              background: '#001529',
              padding: '0 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid rgba(255,255,255,0.1)',
              height: 56,
              lineHeight: '56px',
            }}
          >
            {(() => {
              const pageInfo = PAGE_INFO[activeTab] || PAGE_INFO.overview
              return (
                <div>
                  <div style={{ color: '#fff', fontSize: 16, fontWeight: 600, letterSpacing: 0.5 }}>
                    {pageInfo.title}
                  </div>
                  <div style={{ color: 'rgba(255,255,255,0.65)', fontSize: 12, marginTop: -4 }}>
                    {pageInfo.desc}
                  </div>
                </div>
              )
            })()}
            <Space size={8}>
              <DatePicker
                locale={zhCN}
                value={tradeDate ? dayjs(tradeDate, 'YYYYMMDD') : null}
                onChange={(date) => {
                  setTradeDate(date ? date.format('YYYYMMDD') : null)
                  setRefreshKey((k) => k + 1)
                }}
                disabledDate={(current) => {
                  if (!current) return false
                  const dow = current.day()
                  return dow === 0 || dow === 6
                }}
                placeholder="最新交易日"
                allowClear
                size="small"
                style={{ width: 140 }}
                suffixIcon={<CalendarOutlined style={{ color: 'rgba(255,255,255,0.65)' }} />}
              />
              <Button
                type="text"
                icon={<ReloadOutlined />}
                onClick={() => setRefreshKey((k) => k + 1)}
                style={{ color: 'rgba(255,255,255,0.65)' }}
                title="刷新数据"
              />
            </Space>
          </Header>

          {/* 主内容区 */}
          <Content
            style={{
              padding: 16,
              overflow: 'auto',
            }}
          >
            <ErrorBoundary key={activeTab}>
              <Suspense fallback={<div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300 }}><Spin size="large" tip="加载中..." /></div>}>
                {renderContent()}
              </Suspense>
            </ErrorBoundary>
          </Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  )
}

/**
 * 根组件 — 包裹 BrowserRouter
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/*" element={<AppLayout />} />
      </Routes>
    </BrowserRouter>
  )
}
