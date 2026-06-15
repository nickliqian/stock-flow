import React, { useState, useEffect, useCallback } from 'react'
import { Card, Row, Col, Statistic, Spin, Segmented, Typography, Tag, Space, Empty, Alert, Tabs, Badge } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined, ClockCircleOutlined } from '@ant-design/icons'
import FundCard from '../components/FundCard'
import NorthFundCard from '../components/NorthFundCard'
import TrendChart from '../components/TrendChart'
import FlowTrendChart from '../components/FlowTrendChart'
import TurnoverChart from '../components/TurnoverChart'
import BreadthChart from '../components/BreadthChart'
import StockRanking from '../components/StockRanking'
import SectorRanking from '../components/SectorRanking'
import LimitStats from '../components/LimitStats'
import MarketIndex from '../components/MarketIndex'
import { getMarketOverview, getNorthFund, getFundTrend, getFlowTrend, getTurnoverTrend, getMarketBreadth, getMarketIndices } from '../services/api'
import { formatAmount, getColor } from '../utils/format'

const { Text } = Typography

/**
 * 大盘总览页面
 * 使用 Ant Design 构建专业金融终端界面
 */
export default function MarketOverview({ tradeDate, onTradeDateChange, onSelectStock, onSelectSector }) {
  const [overview, setOverview] = useState(null)
  const [north, setNorth] = useState(null)
  const [indices, setIndices] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)

  // Trend days state for each chart
  const [flowDays, setFlowDays] = useState(7)
  const [northDays, setNorthDays] = useState(7)
  const [turnoverDays, setTurnoverDays] = useState(7)

  // Trend data
  const [flowTrend, setFlowTrend] = useState(null)
  const [northTrend, setNorthTrend] = useState(null)
  const [turnoverTrend, setTurnoverTrend] = useState(null)
  const [trendLoading, setTrendLoading] = useState(false)

  // Breadth data
  const [breadth, setBreadth] = useState(null)

  // Tab state
  const [activeTab, setActiveTab] = useState('overview')

  const fetchData = useCallback(async (signal) => {
    setLoading(true)
    setError(null)
    try {
      const [overviewData, northData, breadthData, indicesData] = await Promise.all([
        getMarketOverview(tradeDate, { signal }),
        getNorthFund(tradeDate, { signal }),
        getMarketBreadth(tradeDate, { signal }).catch(() => null),
        getMarketIndices(tradeDate, { signal }).catch(() => null),
      ])
      setOverview(overviewData?.data || overviewData)
      setNorth(northData?.data || northData)
      setBreadth(breadthData?.data || breadthData)
      setIndices(indicesData?.data || indicesData)
      setLastUpdate(new Date().toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('加载大盘数据失败:', err)
      setError('数据加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [tradeDate])

  const fetchTrends = useCallback(async (flowD, northD, turnoverD, signal) => {
    setTrendLoading(true)
    try {
      const [flowData, northData, turnoverData] = await Promise.all([
        getFlowTrend(flowD, { signal }).catch(() => ({ labels: [], series: {} })),
        getFundTrend(northD, { signal }).catch(() => ({ labels: [], series: {} })),
        getTurnoverTrend(turnoverD, { signal }).catch(() => ({ labels: [], values: [] })),
      ])
      setFlowTrend(flowData?.data || flowData)
      setNorthTrend(northData?.data || northData)
      setTurnoverTrend(turnoverData?.data || turnoverData)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('加载趋势数据失败:', err)
    } finally {
      setTrendLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(controller.signal)
    return () => controller.abort()
  }, [fetchData])

  // Load trends when days change
  useEffect(() => {
    const controller = new AbortController()
    fetchTrends(flowDays, northDays, turnoverDays, controller.signal)
    return () => controller.abort()
  }, [flowDays, northDays, turnoverDays, fetchTrends])

  if (loading && !overview) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (error) {
    return (
      <Alert
        type="error"
        message={error}
        showIcon
        action={
          <button
            onClick={fetchData}
            style={{
              border: '1px solid #cf1322',
              borderRadius: 6,
              background: '#fff',
              color: '#cf1322',
              padding: '4px 16px',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            重新加载
          </button>
        }
      />
    )
  }

  const mainInflow = overview?.main_net_inflow || 0
  const totalTurnover = overview?.total_turnover || 0

  // Tab badge counts
  const northMoney = north?.north_money || 0
  const limitUpCount = breadth?.limit_up || 0

  // 大盘概览 Tab 内容
  const overviewTab = (
    <div>
      {/* 大盘指数卡片 */}
      <MarketIndex data={indices} loading={loading} />

      {/* 顶部统计卡片 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={8}>
          <Card className="stat-card" size="small">
            <Statistic
              title="主力净流入"
              value={mainInflow}
              precision={2}
              formatter={(val) => formatAmount(val)}
              valueStyle={{ color: getColor(mainInflow) }}
              prefix={mainInflow > 0 ? <ArrowUpOutlined /> : mainInflow < 0 ? <ArrowDownOutlined /> : <MinusOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card className="stat-card" size="small">
            <Statistic
              title="今日成交额"
              value={totalTurnover}
              precision={2}
              formatter={(val) => formatAmount(val)}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card className="stat-card" size="small">
            <Statistic
              title="北向资金净买入"
              value={northMoney}
              precision={2}
              formatter={(val) => formatAmount(val)}
              valueStyle={{ color: getColor(northMoney) }}
              prefix={northMoney > 0 ? <ArrowUpOutlined /> : northMoney < 0 ? <ArrowDownOutlined /> : <MinusOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 资金流向明细 */}
      <FundCard data={overview} />

      {/* 大盘资金趋势图 */}
      <Card
        className="chart-card"
        title="📈 大盘资金趋势"
        size="small"
        extra={
          <Segmented
            className="day-segmented"
            size="small"
            value={flowDays}
            onChange={setFlowDays}
            options={[
              { label: '7天', value: 7 },
              { label: '15天', value: 15 },
              { label: '30天', value: 30 },
              { label: '60天', value: 60 },
              { label: '90天', value: 90 },
            ]}
          />
        }
      >
        <Spin spinning={trendLoading} size="small">
          <FlowTrendChart data={flowTrend} compact />
        </Spin>
      </Card>

      {/* 成交额趋势图 */}
      <Card
        className="chart-card"
        title="📊 成交额趋势"
        size="small"
        extra={
          <Segmented
            className="day-segmented"
            size="small"
            value={turnoverDays}
            onChange={setTurnoverDays}
            options={[
              { label: '7天', value: 7 },
              { label: '15天', value: 15 },
              { label: '30天', value: 30 },
              { label: '60天', value: 60 },
              { label: '90天', value: 90 },
            ]}
          />
        }
      >
        <Spin spinning={trendLoading} size="small">
          <TurnoverChart data={turnoverTrend} compact />
        </Spin>
      </Card>

      {/* 板块资金流向排行 */}
      <SectorRanking tradeDate={tradeDate} onSelectSector={onSelectSector} />
    </div>
  )

  // 北向资金 Tab 内容
  const northTab = (
    <div>
      {/* 北向资金卡片 */}
      <NorthFundCard data={north} />

      {/* 北向资金趋势图 */}
      <Card
        className="chart-card"
        title="📈 北向资金趋势"
        size="small"
        extra={
          <Segmented
            className="day-segmented"
            size="small"
            value={northDays}
            onChange={setNorthDays}
            options={[
              { label: '7天', value: 7 },
              { label: '15天', value: 15 },
              { label: '30天', value: 30 },
              { label: '60天', value: 60 },
              { label: '90天', value: 90 },
            ]}
          />
        }
      >
        <Spin spinning={trendLoading} size="small">
          <TrendChart data={northTrend} compact />
        </Spin>
      </Card>

      {/* 个股资金排行 */}
      <StockRanking tradeDate={tradeDate} onSelectStock={onSelectStock} />
    </div>
  )

  // 涨跌停 Tab 内容
  const limitTab = (
    <div>
      {/* 涨跌分布图 */}
      <Card className="chart-card" title="📊 涨跌分布（Market Breadth）" size="small">
        <BreadthChart data={breadth} tradeDate={tradeDate} />
      </Card>

      {/* 涨跌停监控（含按行业/连板/分页） */}
      <LimitStats tradeDate={tradeDate} />
    </div>
  )

  // Tab items with Badge
  const tabItems = [
    {
      key: 'overview',
      label: <span>大盘概览</span>,
      children: overviewTab,
    },
    {
      key: 'north',
      label: (
        <span>
          北向资金
          {northMoney !== 0 && (
            <Badge
              count={formatAmount(northMoney)}
              style={{
                marginLeft: 8,
                backgroundColor: northMoney > 0 ? '#cf1322' : '#3f8600',
                fontWeight: 600,
                fontSize: 11,
              }}
            />
          )}
        </span>
      ),
      children: northTab,
    },
    {
      key: 'limit',
      label: (
        <span>
          涨跌停
          {limitUpCount > 0 && (
            <Badge
              count={limitUpCount}
              style={{
                marginLeft: 8,
                backgroundColor: '#cf1322',
                fontWeight: 600,
                fontSize: 11,
              }}
            />
          )}
        </span>
      ),
      children: limitTab,
    },
  ]

  return (
    <div>
      {/* 更新时间 */}
      <div style={{ textAlign: 'right', marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          数据日期: {(() => {
            const s = String(tradeDate || '').replace(/-/g, '')
            const today = new Date()
            const todayStr = `${today.getFullYear()}${String(today.getMonth()+1).padStart(2,'0')}${String(today.getDate()).padStart(2,'0')}`
            return s === todayStr ? '今日' : `${s.slice(4,6)}-${s.slice(6,8)}`
          })()}
          {lastUpdate && ` | 更新: ${lastUpdate}`}
        </Text>
      </div>

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        type="card"
        items={tabItems}
        style={{ marginBottom: 0 }}
      />

      {/* 数据说明 */}
      <Card size="small" style={{ marginTop: 16 }}>
        <Space direction="vertical" size={2}>
          <Text type="secondary" style={{ fontSize: 12 }}>📌 数据来源：东方财富资金流向数据</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>📌 交易时段自动刷新</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>📌 金额单位：万元（自动换算万/亿）</Text>
        </Space>
      </Card>
    </div>
  )
}
