import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Segmented, Space,
  Spin, Input, Empty, message, Progress, Typography, Divider,
} from 'antd'
import {
  ReloadOutlined, SearchOutlined, ArrowUpOutlined, ArrowDownOutlined,
  RiseOutlined, FallOutlined, BankOutlined, UserOutlined,
} from '@ant-design/icons'
import { apiCall } from '../services/api'

const { Text, Title } = Typography

const API_BASE = ''

const COLORS = {
  increase: '#cf1322',
  decrease: '#3f8600',
  primary: '#1677ff',
  warning: '#faad14',
  muted: '#999999',
  strongBuy: '#cf1322',
  buy: '#d48806',
  hold: '#1677ff',
  sell: '#999999',
}

const cardStyle = { background: '#ffffff', border: '1px solid #e8e8e8' }

/**
 * 内部人与机构智能仪表板
 * 整合4个数据源生成置信度信号
 */
export default function InsiderConviction() {
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('conviction')

  // Tab 1: Conviction Scan
  const [convictionData, setConvictionData] = useState(null)
  const [convictionFilter, setConvictionFilter] = useState('all')

  // Tab 2: Insider Trades
  const [tradesData, setTradesData] = useState(null)
  const [tradesCode, setTradesCode] = useState('')
  const [tradesDays, setTradesDays] = useState(30)

  // Tab 3: Shareholder Trend
  const [trendData, setTrendData] = useState(null)
  const [trendCode, setTrendCode] = useState('')

  // ============================================================
  // Data Fetching
  // ============================================================

  const fetchConvictionData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiCall(`${API_BASE}/insider/conviction?limit=100`)
      const d = res?.data || res
      setConvictionData(d)
    } catch (err) {
      console.error('Failed to load conviction data:', err)
      message.error('置信度数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchTradesData = useCallback(async (tsCode) => {
    if (!tsCode) {
      message.warning('请输入股票代码')
      return
    }
    setLoading(true)
    try {
      const res = await apiCall(`${API_BASE}/insider/trades/${tsCode}?days=${tradesDays}`)
      const d = res?.data || res
      setTradesData(d)
    } catch (err) {
      console.error('Failed to load trades data:', err)
      message.error('内部人交易数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [tradesDays])

  const fetchTrendData = useCallback(async (tsCode) => {
    if (!tsCode) {
      message.warning('请输入股票代码')
      return
    }
    setLoading(true)
    try {
      const res = await apiCall(`${API_BASE}/insider/shareholder-trend/${tsCode}`)
      const d = res?.data || res
      setTrendData(d)
    } catch (err) {
      console.error('Failed to load trend data:', err)
      message.error('股东趋势数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  // Auto-fetch on tab change
  useEffect(() => {
    if (activeTab === 'conviction' && !convictionData) fetchConvictionData()
  }, [activeTab, convictionData, fetchConvictionData])

  const handleRefresh = () => {
    if (activeTab === 'conviction') fetchConvictionData()
    if (activeTab === 'trades' && tradesCode) fetchTradesData(tradesCode)
    if (activeTab === 'trend' && trendCode) fetchTrendData(trendCode)
  }

  // ============================================================
  // Tab 1: Conviction Scan
  // ============================================================

  const filteredStocks = (() => {
    if (!convictionData?.stocks) return []
    let list = convictionData.stocks
    if (convictionFilter === 'strong_buy') list = list.filter(s => s.conviction_level === 'Strong Buy')
    if (convictionFilter === 'buy') list = list.filter(s => s.conviction_level === 'Buy')
    if (convictionFilter === 'hold') list = list.filter(s => s.conviction_level === 'Hold')
    if (convictionFilter === 'sell') list = list.filter(s => s.conviction_level === 'Sell')
    return list
  })()

  const summary = convictionData?.summary || {}

  const levelColor = (level) => {
    switch (level) {
      case 'Strong Buy': return COLORS.strongBuy
      case 'Buy': return COLORS.buy
      case 'Hold': return COLORS.hold
      case 'Sell': return COLORS.sell
      default: return COLORS.muted
    }
  }

  const levelLabel = (level) => {
    switch (level) {
      case 'Strong Buy': return '强烈看多'
      case 'Buy': return '看多'
      case 'Hold': return '持有'
      case 'Sell': return '看空'
      default: return '--'
    }
  }

  const convictionColumns = [
    {
      title: '排名',
      key: 'rank',
      width: 60,
      render: (_, __, index) => <Text style={{ color: '#999' }}>{index + 1}</Text>,
    },
    {
      title: '股票代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '置信度',
      dataIndex: 'conviction_score',
      key: 'conviction_score',
      width: 100,
      sorter: (a, b) => a.conviction_score - b.conviction_score,
      defaultSortOrder: 'descend',
      render: (v) => (
        <Progress
          percent={v}
          size="small"
          strokeColor={v >= 80 ? COLORS.strongBuy : v >= 60 ? COLORS.buy : v >= 40 ? COLORS.hold : COLORS.sell}
          format={(p) => <span style={{ fontWeight: 700 }}>{p}</span>}
        />
      ),
    },
    {
      title: '信号等级',
      dataIndex: 'conviction_level',
      key: 'conviction_level',
      width: 100,
      render: (v) => (
        <Tag color={levelColor(v)} style={{ fontWeight: 600 }}>
          {levelLabel(v)}
        </Tag>
      ),
    },
    {
      title: '内部人买入',
      dataIndex: 'insider_buying_count',
      key: 'insider_buying_count',
      width: 100,
      render: (v, record) => (
        <Space size={4}>
          {v > 0 && <Tag color="red">买入{v}次</Tag>}
          {record.insider_buying_count === 0 && <Text type="secondary">--</Text>}
        </Space>
      ),
    },
    {
      title: '股东趋势',
      key: 'shareholder_trend',
      width: 100,
      render: (_, record) => {
        const sig = record.signals?.shareholder_concentration || {}
        const pct = sig.holder_count_change_pct || 0
        if (pct < -10) return <Tag color="blue">筹码集中</Tag>
        if (pct > 10) return <Tag color="orange">筹码分散</Tag>
        return <Tag color="default">稳定</Tag>
      },
    },
    {
      title: '机构占比',
      key: 'institutional_ratio',
      width: 100,
      render: (_, record) => {
        const sig = record.signals?.shareholder_concentration || {}
        const ratio = sig.top10_institutional_ratio || 0
        return <span>{ratio > 0 ? `${ratio.toFixed(1)}%` : '--'}</span>
      },
    },
    {
      title: '质押比例',
      key: 'pledge_ratio',
      width: 100,
      render: (_, record) => {
        const sig = record.signals?.pledge_relief || {}
        const ratio = sig.pledge_ratio
        if (ratio == null) return <Text type="secondary">无质押</Text>
        const color = ratio < 10 ? 'green' : ratio < 30 ? 'orange' : 'red'
        return <span style={{ color }}>{ratio.toFixed(1)}%</span>
      },
    },
  ]

  const expandedRowRender = (record) => {
    const sig = record.signals || {}
    const items = [
      { label: '内部人买入信号', data: sig.insider_buying, weight: '30%' },
      { label: '股东集中度信号', data: sig.shareholder_concentration, weight: '30%' },
      { label: '业绩预告信号', data: sig.forecast_surprise, weight: '20%' },
      { label: '质押风险信号', data: sig.pledge_relief, weight: '20%' },
    ]
    return (
      <Row gutter={[16, 8]}>
        {items.map((item, i) => (
          <Col xs={24} sm={12} key={i}>
            <Card size="small" style={{ background: '#fafafa' }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Text strong>{item.label} <Text type="secondary" style={{ fontSize: 12 }}>权重{item.weight}</Text></Text>
                {item.data ? (
                  <Row gutter={[8, 4]}>
                    <Col span={8}>
                      <Statistic
                        title="得分"
                        value={item.data.score ?? '--'}
                        valueStyle={{ fontSize: 16 }}
                      />
                    </Col>
                    {Object.entries(item.data).filter(([k]) => k !== 'score').map(([k, v]) => (
                      <Col span={8} key={k}>
                        <Text type="secondary" style={{ fontSize: 11 }}>{k}</Text>
                        <br />
                        <Text style={{ fontSize: 13 }}>{v != null ? (typeof v === 'number' ? v.toFixed(2) : v) : '--'}</Text>
                      </Col>
                    ))}
                  </Row>
                ) : (
                  <Text type="secondary">暂无数据</Text>
                )}
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    )
  }

  // ============================================================
  // Tab 2: Insider Trades
  // ============================================================

  const trades = tradesData?.trades || []
  const tradesSummary = tradesData?.summary || {}

  const tradesColumns = [
    {
      title: '公告日期',
      dataIndex: 'ann_date',
      key: 'ann_date',
      width: 110,
      sorter: (a, b) => (a.ann_date || '').localeCompare(b.ann_date || ''),
      defaultSortOrder: 'descend',
    },
    {
      title: '股东名称',
      dataIndex: 'holder_name',
      key: 'holder_name',
      ellipsis: true,
    },
    {
      title: '操作',
      dataIndex: 'change_type',
      key: 'change_type',
      width: 80,
      render: (v) => (
        <Tag color={v === '买入' ? COLORS.decrease : COLORS.increase}>
          {v}
        </Tag>
      ),
    },
    {
      title: '变动股数',
      dataIndex: 'change_shares',
      key: 'change_shares',
      width: 140,
      render: (v, record) => {
        const isBuy = record.change_type === '买入'
        return (
          <span style={{ color: isBuy ? COLORS.decrease : COLORS.increase, fontWeight: 600 }}>
            {isBuy ? '+' : '-'}{v?.toLocaleString() || '--'}
          </span>
        )
      },
    },
    {
      title: '均价',
      dataIndex: 'avg_price',
      key: 'avg_price',
      width: 90,
      render: (v) => v ? `¥${v.toFixed(2)}` : '--',
    },
    {
      title: '金额(万)',
      dataIndex: 'amount_wan',
      key: 'amount_wan',
      width: 110,
      render: (v, record) => {
        const isBuy = record.change_type === '买入'
        return (
          <span style={{ color: isBuy ? COLORS.decrease : COLORS.increase, fontWeight: 600 }}>
            {v?.toLocaleString(undefined, { maximumFractionDigits: 1 }) || '--'}
          </span>
        )
      },
    },
    {
      title: '持股比例%',
      dataIndex: 'after_ratio',
      key: 'after_ratio',
      width: 100,
      render: (v) => v != null ? `${v.toFixed(2)}%` : '--',
    },
  ]

  // ============================================================
  // Tab 3: Shareholder Trend
  // ============================================================

  const trendHistory = trendData?.history || []
  const topHolders = trendData?.top10_holders || []

  // Simple CSS line chart
  const renderLineChart = () => {
    if (trendHistory.length < 2) {
      return <Empty description="数据不足，无法绘图" image={Empty.PRESENTED_IMAGE_SIMPLE} />
    }

    const values = trendHistory.map(h => h.holder_num)
    const maxVal = Math.max(...values)
    const minVal = Math.min(...values)
    const range = maxVal - minVal || 1
    const width = 600
    const height = 200
    const padding = 40
    const chartW = width - padding * 2
    const chartH = height - padding * 2

    const points = values.map((v, i) => ({
      x: padding + (i / (values.length - 1)) * chartW,
      y: padding + chartH - ((v - minVal) / range) * chartH,
      value: v,
      date: trendHistory[i]?.end_date,
    }))

    const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')

    return (
      <div style={{ overflow: 'auto' }}>
        <svg width={width} height={height} style={{ background: '#fafafa', borderRadius: 6 }}>
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => (
            <line
              key={i}
              x1={padding}
              y1={padding + chartH * (1 - pct)}
              x2={padding + chartW}
              y2={padding + chartH * (1 - pct)}
              stroke="#e8e8e8"
              strokeDasharray="4"
            />
          ))}
          {/* Y axis labels */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => (
            <text
              key={i}
              x={padding - 5}
              y={padding + chartH * (1 - pct) + 4}
              textAnchor="end"
              fontSize={10}
              fill="#999"
            >
              {Math.round(minVal + range * pct).toLocaleString()}
            </text>
          ))}
          {/* X axis labels */}
          {points.filter((_, i) => i % Math.max(1, Math.floor(points.length / 6)) === 0).map((p, i) => (
            <text
              key={i}
              x={p.x}
              y={height - 5}
              textAnchor="middle"
              fontSize={9}
              fill="#999"
            >
              {p.date?.slice(4, 6)}/{p.date?.slice(6, 8)}
            </text>
          ))}
          {/* Line */}
          <path d={pathD} fill="none" stroke={COLORS.primary} strokeWidth={2} />
          {/* Dots */}
          {points.map((p, i) => (
            <circle key={i} cx={p.x} cy={p.y} r={3} fill={COLORS.primary} />
          ))}
        </svg>
      </div>
    )
  }

  const topHoldersColumns = [
    {
      title: '股东名称',
      dataIndex: 'holder_name',
      key: 'holder_name',
      ellipsis: true,
    },
    {
      title: '持股比例%',
      dataIndex: 'hold_ratio',
      key: 'hold_ratio',
      width: 110,
      render: (v) => v ? `${(v * 100).toFixed(2)}%` : '--',
    },
    {
      title: '持股数量',
      dataIndex: 'hold_amount',
      key: 'hold_amount',
      width: 120,
      render: (v) => v ? v.toLocaleString() : '--',
    },
    {
      title: '类型',
      dataIndex: 'holder_type',
      key: 'holder_type',
      width: 80,
    },
    {
      title: '机构',
      dataIndex: 'is_institutional',
      key: 'is_institutional',
      width: 70,
      render: (v) => v ? <Tag color={COLORS.primary}>机构</Tag> : <Tag>非机构</Tag>,
    },
  ]

  // ============================================================
  // Render
  // ============================================================

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>🏛️ 内部人与机构智能</Title>
        <Space>
          <ReloadOutlined
            style={{ fontSize: 16, cursor: 'pointer', color: '#666' }}
            onClick={handleRefresh}
          />
        </Space>
      </div>

      {/* Tab Selector */}
      <Segmented
        value={activeTab}
        onChange={setActiveTab}
        options={[
          { label: '🏛️ 置信度扫描', value: 'conviction' },
          { label: '👔 内部人交易', value: 'trades' },
          { label: '📊 股东趋势', value: 'trend' },
        ]}
        style={{ marginBottom: 16 }}
      />

      <Spin spinning={loading}>
        {/* Tab 1: Conviction Scan */}
        {activeTab === 'conviction' && (
          <div>
            {/* Summary Cards */}
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
              <Col xs={12} sm={6}>
                <Card size="small" style={cardStyle}>
                  <Statistic
                    title="扫描总数"
                    value={summary.total_scanned || 0}
                    valueStyle={{ fontSize: 24, color: COLORS.primary }}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small" style={cardStyle}>
                  <Statistic
                    title="强烈看多"
                    value={summary.strong_buy || 0}
                    valueStyle={{ fontSize: 24, color: COLORS.strongBuy }}
                    prefix={<RiseOutlined />}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small" style={cardStyle}>
                  <Statistic
                    title="看多"
                    value={summary.buy || 0}
                    valueStyle={{ fontSize: 24, color: COLORS.buy }}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={6}>
                <Card size="small" style={cardStyle}>
                  <Statistic
                    title="看空"
                    value={summary.sell || 0}
                    valueStyle={{ fontSize: 24, color: COLORS.sell }}
                    prefix={<FallOutlined />}
                  />
                </Card>
              </Col>
            </Row>

            {/* Filter */}
            <Space style={{ marginBottom: 16 }}>
              <Text type="secondary">筛选等级:</Text>
              <Segmented
                value={convictionFilter}
                onChange={setConvictionFilter}
                options={[
                  { label: '全部', value: 'all' },
                  { label: '强烈看多', value: 'strong_buy' },
                  { label: '看多', value: 'buy' },
                  { label: '持有', value: 'hold' },
                  { label: '看空', value: 'sell' },
                ]}
                size="small"
              />
            </Space>

            <Table
              dataSource={filteredStocks}
              columns={convictionColumns}
              rowKey="ts_code"
              size="small"
              pagination={{ pageSize: 20, showSizeChanger: false }}
              expandable={{
                expandedRowRender,
                rowExpandable: (record) => !!record.signals,
              }}
              scroll={{ x: 900 }}
            />
          </div>
        )}

        {/* Tab 2: Insider Trades */}
        {activeTab === 'trades' && (
          <div>
            <Card style={{ ...cardStyle, marginBottom: 16 }}>
              <Space>
                <Input
                  placeholder="输入股票代码，如 000001.SZ"
                  value={tradesCode}
                  onChange={(e) => setTradesCode(e.target.value)}
                  onPressEnter={() => fetchTradesData(tradesCode)}
                  prefix={<SearchOutlined />}
                  style={{ width: 260 }}
                />
                <Segmented
                  value={tradesDays}
                  onChange={(v) => setTradesDays(v)}
                  options={[
                    { label: '7天', value: 7 },
                    { label: '30天', value: 30 },
                    { label: '90天', value: 90 },
                  ]}
                  size="small"
                />
                <Segmented
                  value="search"
                  onChange={() => fetchTradesData(tradesCode)}
                  options={[{ label: '查询', value: 'search' }]}
                  size="small"
                />
              </Space>
            </Card>

            {tradesData && (
              <>
                <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                  <Col span={8}>
                    <Card size="small" style={cardStyle}>
                      <Statistic title="交易总数" value={tradesSummary.total || 0} />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small" style={cardStyle}>
                      <Statistic
                        title="买入次数"
                        value={tradesSummary.buy_count || 0}
                        valueStyle={{ color: COLORS.decrease }}
                      />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small" style={cardStyle}>
                      <Statistic
                        title="卖出次数"
                        value={tradesSummary.sell_count || 0}
                        valueStyle={{ color: COLORS.increase }}
                      />
                    </Card>
                  </Col>
                </Row>

                <Table
                  dataSource={trades}
                  columns={tradesColumns}
                  rowKey={(r, i) => `${r.ann_date}-${i}`}
                  size="small"
                  pagination={{ pageSize: 20 }}
                  scroll={{ x: 800 }}
                />
              </>
            )}
          </div>
        )}

        {/* Tab 3: Shareholder Trend */}
        {activeTab === 'trend' && (
          <div>
            <Card style={{ ...cardStyle, marginBottom: 16 }}>
              <Space>
                <Input
                  placeholder="输入股票代码，如 000001.SZ"
                  value={trendCode}
                  onChange={(e) => setTrendCode(e.target.value)}
                  onPressEnter={() => fetchTrendData(trendCode)}
                  prefix={<SearchOutlined />}
                  style={{ width: 260 }}
                />
                <Segmented
                  value="search"
                  onChange={() => fetchTrendData(trendCode)}
                  options={[{ label: '查询', value: 'search' }]}
                  size="small"
                />
              </Space>
            </Card>

            {trendData && (
              <>
                {/* Trend Info */}
                <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                  <Col span={8}>
                    <Card size="small" style={cardStyle}>
                      <Statistic title="当前趋势" value={trendData.trend_label || '--'} />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small" style={cardStyle}>
                      <Statistic
                        title="变化幅度"
                        value={trendData.change_pct || 0}
                        precision={2}
                        suffix="%"
                        valueStyle={{
                          color: (trendData.change_pct || 0) < 0 ? COLORS.decrease
                            : (trendData.change_pct || 0) > 0 ? COLORS.increase : COLORS.muted
                        }}
                      />
                    </Card>
                  </Col>
                  <Col span={8}>
                    <Card size="small" style={cardStyle}>
                      <Statistic
                        title="前十大股东数"
                        value={topHolders.length}
                      />
                    </Card>
                  </Col>
                </Row>

                {/* Line Chart */}
                <Card title="股东人数趋势" size="small" style={{ ...cardStyle, marginBottom: 16 }}>
                  {renderLineChart()}
                </Card>

                {/* Top 10 Holders */}
                <Card title="前十大股东" size="small" style={cardStyle}>
                  <Table
                    dataSource={topHolders}
                    columns={topHoldersColumns}
                    rowKey={(r, i) => `${r.holder_name}-${i}`}
                    size="small"
                    pagination={false}
                  />
                </Card>
              </>
            )}
          </div>
        )}
      </Spin>
    </div>
  )
}
