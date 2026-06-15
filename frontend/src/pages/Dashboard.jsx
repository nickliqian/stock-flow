import React, { useState, useEffect } from 'react'
import { Row, Col, Card, Typography, Empty, Spin, Tag } from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  BarChartOutlined,
  SearchOutlined,
  RocketOutlined,
  BulbOutlined,
  ExperimentOutlined,
  BookOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined,
} from '@ant-design/icons'
import { getMarketIndices, getSignalMatrix, apiCall } from '../services/api'

const { Title, Text, Link } = Typography

// 快捷导航分组配置
const NAV_GROUPS = [
  {
    title: '市场概览',
    icon: <BarChartOutlined />,
    color: '#1677ff',
    items: [
      { label: '大盘总览', path: '/overview' },
      { label: '板块资金', path: '/sector' },
      { label: '个股资金', path: '/stock' },
      { label: '市场宽度', path: '/breadth' },
    ],
  },
  {
    title: '选股工具',
    icon: <SearchOutlined />,
    color: '#52c41a',
    items: [
      { label: '多维选股', path: '/screener' },
      { label: '智能荐股', path: '/recommendation' },
      { label: '自选股', path: '/watchlist' },
    ],
  },
  {
    title: '策略中心',
    icon: <RocketOutlined />,
    color: '#722ed1',
    items: [
      { label: '策略总览', path: '/strategy' },
      { label: '策略进化', path: '/evolution' },
      { label: '自适应权重', path: '/adaptive' },
      { label: '因子轮动', path: '/factormodel' },
      { label: '信号有效性', path: '/effectiveness' },
      { label: '拥挤度', path: '/crowding' },
    ],
  },
  {
    title: '智能分析',
    icon: <BulbOutlined />,
    color: '#fa8c16',
    items: [
      { label: '智能分析', path: '/smart' },
      { label: '筹码分析', path: '/chip' },
      { label: '机构雷达', path: '/radar' },
      { label: '股东情报', path: '/shareholder' },
      { label: '内部人信号', path: '/insider' },
      { label: 'Alpha评分', path: '/alpha' },
    ],
  },
  {
    title: '高级工具',
    icon: <ExperimentOutlined />,
    color: '#13c2c2',
    items: [
      { label: '配对交易', path: '/pairtrading' },
      { label: '组合构建', path: '/portfolio' },
      { label: '多周期共振', path: '/multi-timeframe' },
      { label: '波动率分区', path: '/volatility' },
      { label: '信号告警', path: '/alerts' },
    ],
  },
  {
    title: '研究资料',
    icon: <BookOutlined />,
    color: '#eb2f96',
    items: [
      { label: '资料浏览', path: '/research' },
      { label: '事件日历', path: '/events' },
    ],
  },
]

// 大盘指数卡片
function IndexCard({ data }) {
  const pctChg = data?.pct_chg || 0
  const isUp = pctChg > 0
  const isDown = pctChg < 0
  const color = isUp ? '#cf1322' : isDown ? '#3f8600' : '#666'

  return (
    <Card
      hoverable
      size="small"
      style={{
        borderRadius: 8,
        borderLeft: `3px solid ${color}`,
      }}
      bodyStyle={{ padding: '12px 16px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>{data?.name || '--'}</Text>
          <div style={{ fontSize: 20, fontWeight: 600, color, marginTop: 4 }}>
            {data?.close ? data.close.toLocaleString() : '--'}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 14, fontWeight: 500, color }}>
            {pctChg > 0 ? '+' : ''}{pctChg.toFixed(2)}%
          </div>
          <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>
            {data?.change > 0 ? '+' : ''}{data?.change?.toFixed(2) || '0'}
          </div>
        </div>
      </div>
    </Card>
  )
}

// 快捷导航卡片
function NavCard({ group, navigate }) {
  return (
    <Card
      hoverable
      title={
        <span style={{ fontSize: 14, fontWeight: 600 }}>
          <span style={{ color: group.color, marginRight: 8 }}>{group.icon}</span>
          {group.title}
        </span>
      }
      headStyle={{ borderBottom: `2px solid ${group.color}20`, padding: '8px 16px' }}
      bodyStyle={{ padding: '8px 16px 16px' }}
      style={{ borderRadius: 8, height: '100%' }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {group.items.map((item) => (
          <Tag
            key={item.path}
            color="default"
            style={{
              cursor: 'pointer',
              padding: '4px 12px',
              margin: 0,
              borderRadius: 4,
              fontSize: 13,
            }}
            onClick={() => navigate(item.path)}
          >
            {item.label}
          </Tag>
        ))}
      </div>
    </Card>
  )
}

// 信号条目
function SignalItem({ item }) {
  const isBuy = item.direction === 'BUY' || item.direction === 'bullish'
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '8px 0',
        borderBottom: '1px solid #f0f0f0',
      }}
    >
      <div style={{ flex: 1 }}>
        <Text strong style={{ fontSize: 13 }}>{item.stock_name || item.ts_code}</Text>
        <div style={{ fontSize: 11, color: '#999' }}>{item.strategy_name || item.name}</div>
      </div>
      <Tag color={isBuy ? 'green' : 'red'} style={{ margin: 0 }}>
        {item.direction || '--'}
      </Tag>
      <Text style={{ marginLeft: 12, fontSize: 13, fontWeight: 500, minWidth: 40, textAlign: 'right' }}>
        {item.score != null ? item.score.toFixed(1) : '--'}
      </Text>
    </div>
  )
}

// 事件条目
function EventItem({ item }) {
  const pressure = item.pressure_score || 0
  const color = pressure >= 70 ? '#cf1322' : pressure >= 40 ? '#fa8c16' : '#3f8600'
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '8px 0',
        borderBottom: '1px solid #f0f0f0',
      }}
    >
      <div style={{ flex: 1 }}>
        <Text strong style={{ fontSize: 13 }}>{item.name || item.ts_code}</Text>
        <div style={{ fontSize: 11, color: '#999' }}>
          {item.unlock_date || item.float_date || '--'}
          {item.holder_name ? ` · ${item.holder_name}` : ''}
        </div>
      </div>
      <Tag color={color} style={{ margin: 0 }}>
        压力 {pressure}
      </Tag>
    </div>
  )
}

/**
 * Dashboard 首页组件
 * 包含大盘指数速览、快捷导航、最新预警、最近事件四个区域
 */
export default function Dashboard() {
  const navigate = useNavigate()

  // 大盘指数
  const [indices, setIndices] = useState(null)
  const [indicesLoading, setIndicesLoading] = useState(true)

  // 信号矩阵
  const [signals, setSignals] = useState([])
  const [signalsLoading, setSignalsLoading] = useState(true)

  // 解禁事件
  const [events, setEvents] = useState([])
  const [eventsLoading, setEventsLoading] = useState(true)

  // 获取大盘指数
  useEffect(() => {
    const controller = new AbortController()
    setIndicesLoading(true)
    getMarketIndices(null, { signal: controller.signal })
      .then((res) => {
        const data = res?.data || res
        setIndices(data?.indices || {})
      })
      .catch((err) => {
        if (err?.code !== 'ERR_CANCELED' && err?.name !== 'CanceledError') {
          console.error('Failed to load indices:', err)
        }
      })
      .finally(() => setIndicesLoading(false))
    return () => controller.abort()
  }, [])

  // 获取信号矩阵（最近5条）
  useEffect(() => {
    const controller = new AbortController()
    setSignalsLoading(true)
    getSignalMatrix(null, 1, null, { signal: controller.signal })
      .then((res) => {
        const data = res?.data || res
        const stocks = data?.stocks || []
        // 取前5个有信号的股票
        const top = stocks.slice(0, 5).map((s) => {
          const signalEntries = Object.entries(s.signals || {})
          const topSignal = signalEntries[0]
          return {
            ts_code: s.ts_code,
            stock_name: s.name,
            strategy_name: topSignal ? topSignal[0] : '--',
            direction: topSignal ? topSignal[1].score > 0 ? 'BUY' : 'SELL' : '--',
            score: s.total_score,
          }
        })
        setSignals(top)
      })
      .catch((err) => {
        if (err?.code !== 'ERR_CANCELED' && err?.name !== 'CanceledError') {
          console.error('Failed to load signals:', err)
        }
      })
      .finally(() => setSignalsLoading(false))
    return () => controller.abort()
  }, [])

  // 获取解禁事件
  useEffect(() => {
    const controller = new AbortController()
    setEventsLoading(true)
    apiCall('/events/unlock-calendar', { signal: controller.signal })
      .then((res) => {
        const data = res?.data || res
        const items = data?.data || []
        setEvents(items.slice(0, 5))
      })
      .catch((err) => {
        if (err?.code !== 'ERR_CANCELED' && err?.name !== 'CanceledError') {
          console.error('Failed to load events:', err)
        }
      })
      .finally(() => setEventsLoading(false))
    return () => controller.abort()
  }, [])

  // 指数代码映射（按显示顺序）
  const indexOrder = ['000001.SH', '399001.SZ', '399006.SZ', '000688.SH']
  const indexNames = {
    '000001.SH': '上证指数',
    '399001.SZ': '深证成指',
    '399006.SZ': '创业板指',
    '000688.SH': '科创50',
  }

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* 区域1：大盘指数速览 */}
      <div style={{ marginBottom: 16 }}>
        <Title level={5} style={{ marginBottom: 12, fontSize: 14, color: '#666' }}>
          📊 大盘指数速览
        </Title>
        <Spin spinning={indicesLoading}>
          <Row gutter={[12, 12]}>
            {indexOrder.map((code) => (
              <Col xs={12} sm={6} key={code}>
                <IndexCard
                  data={indices?.[code] || { name: indexNames[code], close: 0, change: 0, pct_chg: 0 }}
                />
              </Col>
            ))}
          </Row>
        </Spin>
      </div>

      {/* 区域2：快捷导航 */}
      <div style={{ marginBottom: 16 }}>
        <Title level={5} style={{ marginBottom: 12, fontSize: 14, color: '#666' }}>
          🚀 快捷导航
        </Title>
        <Row gutter={[12, 12]}>
          {NAV_GROUPS.map((group) => (
            <Col xs={24} sm={12} md={8} key={group.title}>
              <NavCard group={group} navigate={navigate} />
            </Col>
          ))}
        </Row>
      </div>

      {/* 区域3 & 4：预警和事件 */}
      <Row gutter={[12, 12]}>
        {/* 最新预警 */}
        <Col xs={24} md={12}>
          <Card
            title={<span style={{ fontSize: 14 }}>⚡ 最新预警</span>}
            headStyle={{ borderBottom: '2px solid #faad1420', padding: '8px 16px' }}
            bodyStyle={{ padding: '0 16px 16px' }}
            style={{ borderRadius: 8, height: '100%' }}
          >
            <Spin spinning={signalsLoading}>
              {signals.length > 0 ? (
                signals.map((item, idx) => (
                  <SignalItem key={idx} item={item} />
                ))
              ) : (
                <Empty description="暂无预警数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Spin>
          </Card>
        </Col>

        {/* 最近事件 */}
        <Col xs={24} md={12}>
          <Card
            title={<span style={{ fontSize: 14 }}>📅 最近事件</span>}
            headStyle={{ borderBottom: '2px solid #ff4d4f20', padding: '8px 16px' }}
            bodyStyle={{ padding: '0 16px 16px' }}
            style={{ borderRadius: 8, height: '100%' }}
          >
            <Spin spinning={eventsLoading}>
              {events.length > 0 ? (
                events.map((item, idx) => (
                  <EventItem key={idx} item={item} />
                ))
              ) : (
                <Empty description="暂无事件数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              )}
            </Spin>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
