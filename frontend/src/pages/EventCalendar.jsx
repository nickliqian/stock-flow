import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Tabs, Space, Slider, DatePicker,
  Spin, Empty, message, Badge, Typography, Tooltip, Button, Segmented,
} from 'antd'
import {
  ReloadOutlined, WarningOutlined, CheckCircleOutlined,
  CalendarOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { apiCall } from '../services/api'

const { Text, Title } = Typography
const { RangePicker } = DatePicker

const API_BASE = ''

const COLORS = {
  high: '#cf1322',
  medium: '#faad14',
  low: '#3f8600',
  primary: '#1677ff',
  muted: '#999999',
  bullish: '#3f8600',
  bearish: '#cf1322',
  neutral: '#d48806',
}

const cardStyle = { background: '#ffffff', border: '1px solid #e8e8e8' }

/**
 * 格式化金额为万元/亿元显示
 */
function formatAmount(value) {
  if (value == null || value === 0) return '0'
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)}亿`
  if (value >= 10000) return `${(value / 10000).toFixed(0)}万`
  return value.toLocaleString()
}

/**
 * 格式化股数
 */
function formatShares(value) {
  if (value == null || value === 0) return '0'
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)}亿`
  if (value >= 10000) return `${(value / 10000).toFixed(0)}万`
  return value.toLocaleString()
}

/**
 * 事件日历仪表板
 * 限售解禁日历 + 回购信号分析 + 事件热力图
 */
export default function EventCalendar() {
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('unlock')

  // Tab 1: Unlock Calendar
  const [unlockData, setUnlockData] = useState(null)
  const [unlockDateRange, setUnlockDateRange] = useState(null)
  const [minRatio, setMinRatio] = useState(1)

  // Tab 2: Buyback Signals
  const [buybackData, setBuybackData] = useState(null)
  const [buybackDateRange, setBuybackDateRange] = useState(null)
  const [minAmount, setMinAmount] = useState(0)

  // Tab 3: Heatmap
  const [heatmapData, setHeatmapData] = useState(null)

  // ============================================================
  // Data Fetching
  // ============================================================

  const fetchUnlockData = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (unlockDateRange && unlockDateRange[0]) {
        params.set('start_date', unlockDateRange[0].format('YYYYMMDD'))
      }
      if (unlockDateRange && unlockDateRange[1]) {
        params.set('end_date', unlockDateRange[1].format('YYYYMMDD'))
      }
      params.set('min_unlock_ratio', String(minRatio / 100))
      const res = await apiCall(`${API_BASE}/events/unlock-calendar?${params.toString()}`)
      const d = res?.data || res
      setUnlockData(d)
    } catch (err) {
      console.error('Failed to load unlock data:', err)
      message.error('解禁日历数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [unlockDateRange, minRatio])

  const fetchBuybackData = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (buybackDateRange && buybackDateRange[0]) {
        params.set('start_date', buybackDateRange[0].format('YYYYMMDD'))
      }
      if (buybackDateRange && buybackDateRange[1]) {
        params.set('end_date', buybackDateRange[1].format('YYYYMMDD'))
      }
      params.set('min_amount', String(minAmount * 10000))
      const res = await apiCall(`${API_BASE}/events/buyback-signals?${params.toString()}`)
      const d = res?.data || res
      setBuybackData(d)
    } catch (err) {
      console.error('Failed to load buyback data:', err)
      message.error('回购信号数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [buybackDateRange, minAmount])

  const fetchHeatmapData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiCall(`${API_BASE}/events/heatmap`)
      const d = res?.data || res
      setHeatmapData(d)
    } catch (err) {
      console.error('Failed to load heatmap data:', err)
      message.error('事件热力图数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  // Auto-fetch on tab change
  useEffect(() => {
    if (activeTab === 'unlock' && !unlockData) fetchUnlockData()
    if (activeTab === 'buyback' && !buybackData) fetchBuybackData()
    if (activeTab === 'heatmap' && !heatmapData) fetchHeatmapData()
  }, [activeTab]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = () => {
    if (activeTab === 'unlock') fetchUnlockData()
    if (activeTab === 'buyback') fetchBuybackData()
    if (activeTab === 'heatmap') fetchHeatmapData()
  }

  // ============================================================
  // Tab 1: 解禁日历 (Unlock Calendar)
  // ============================================================

  const unlockSummary = unlockData?.summary || {}
  const unlockEvents = unlockData?.data || []

  const unlockColumns = [
    {
      title: '解禁日期',
      dataIndex: 'float_date',
      key: 'float_date',
      width: 110,
      sorter: (a, b) => (a.float_date || '').localeCompare(b.float_date || ''),
    },
    {
      title: '股票代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '解禁股数',
      dataIndex: 'float_share',
      key: 'float_share',
      width: 130,
      sorter: (a, b) => (a.float_share || 0) - (b.float_share || 0),
      render: (v) => v != null ? formatShares(v) : '--',
    },
    {
      title: '解禁比例',
      dataIndex: 'float_ratio',
      key: 'float_ratio',
      width: 110,
      sorter: (a, b) => (a.float_ratio || 0) - (b.float_ratio || 0),
      render: (v) => {
        if (v == null) return '--'
        const pct = (v * 100).toFixed(2)
        const color = v >= 0.05 ? COLORS.high : v >= 0.02 ? COLORS.medium : COLORS.low
        return <span style={{ color, fontWeight: 600 }}>{pct}%</span>
      },
    },
    {
      title: '压力评分',
      dataIndex: 'pressure_score',
      key: 'pressure_score',
      width: 110,
      sorter: (a, b) => (a.pressure_score || 0) - (b.pressure_score || 0),
      defaultSortOrder: 'descend',
      render: (v) => {
        if (v == null) return '--'
        const color = v >= 50 ? COLORS.high : v >= 25 ? COLORS.medium : COLORS.low
        const label = v >= 50 ? '高' : v >= 25 ? '中' : '低'
        return (
          <Space size={4}>
            <span style={{ color, fontWeight: 700, fontSize: 14 }}>{Math.round(v)}</span>
            <Tag color={color} style={{ margin: 0 }}>{label}</Tag>
          </Space>
        )
      },
    },
    {
      title: '距今(天)',
      dataIndex: 'days_until',
      key: 'days_until',
      width: 90,
      render: (v) => {
        if (v == null) return '--'
        const color = v <= 0 ? COLORS.high : v <= 7 ? COLORS.medium : COLORS.low
        return <span style={{ color, fontWeight: 600 }}>{v}</span>
      },
    },
    {
      title: '持有人',
      dataIndex: 'holder_name',
      key: 'holder_name',
      ellipsis: true,
      render: (v) => v || '--',
    },
    {
      title: '解禁原因',
      dataIndex: 'float_reason',
      key: 'float_reason',
      ellipsis: true,
      width: 140,
      render: (v) => v || '--',
    },
  ]

  // ============================================================
  // Tab 2: 回购信号 (Buyback Signals)
  // ============================================================

  const buybackSummary = buybackData?.summary || {}
  const buybackSignals = buybackData?.data || []

  const buybackColumns = [
    {
      title: '公告日期',
      dataIndex: 'ann_date',
      key: 'ann_date',
      width: 110,
    },
    {
      title: '股票代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '回购金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 140,
      sorter: (a, b) => (a.amount || 0) - (b.amount || 0),
      defaultSortOrder: 'descend',
      render: (v) => {
        if (v == null || v === 0) return '--'
        return <span style={{ fontWeight: 600 }}>{formatAmount(v)}</span>
      },
    },
    {
      title: '回购数量(股)',
      dataIndex: 'vol',
      key: 'vol',
      width: 130,
      sorter: (a, b) => (a.vol || 0) - (b.vol || 0),
      render: (v) => v != null ? formatShares(v) : '--',
    },
    {
      title: '价格区间',
      key: 'price_range',
      width: 140,
      render: (_, record) => {
        const low = record.low_limit
        const high = record.high_limit
        if (!low && !high) return '--'
        return `${low || '--'} ~ ${high || '--'}`
      },
    },
    {
      title: '信心评分',
      dataIndex: 'confidence_score',
      key: 'confidence_score',
      width: 120,
      sorter: (a, b) => (a.confidence_score || 0) - (b.confidence_score || 0),
      render: (v) => {
        if (v == null) return '--'
        const score = Math.round(v)
        const color = score >= 80 ? COLORS.low : score >= 50 ? COLORS.medium : COLORS.high
        const label = score >= 80 ? '强' : score >= 50 ? '中' : '弱'
        return (
          <Space size={4}>
            <span style={{ color, fontWeight: 700, fontSize: 14 }}>{score}</span>
            <Tag color={color} style={{ margin: 0 }}>{label}</Tag>
          </Space>
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v) => (
        <Tag color={v ? COLORS.low : COLORS.muted}>
          {v ? '进行中' : '已到期'}
        </Tag>
      ),
    },
    {
      title: '距今(天)',
      dataIndex: 'days_since',
      key: 'days_since',
      width: 90,
      render: (v) => {
        if (v == null) return '--'
        const color = v <= 7 ? COLORS.low : v <= 30 ? COLORS.medium : COLORS.muted
        return <span style={{ color }}>{v}</span>
      },
    },
    {
      title: '回购原因',
      dataIndex: 'reason',
      key: 'reason',
      ellipsis: true,
      width: 160,
      render: (v) => v || '--',
    },
  ]

  // ============================================================
  // Tab 3: 事件热力图 (Event Heatmap)
  // ============================================================

  const heatmapSummary = heatmapData?.summary || {}
  const riskStocks = heatmapData?.risk_stocks || []
  const opportunityStocks = heatmapData?.opportunity_stocks || []

  const riskColumns = [
    {
      title: '股票代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '解禁压力',
      dataIndex: 'unlock_pressure',
      key: 'unlock_pressure',
      width: 120,
      sorter: (a, b) => (a.unlock_pressure || 0) - (b.unlock_pressure || 0),
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ color: COLORS.high, fontWeight: 700 }}>{v}</span>
      ),
    },
    {
      title: '解禁次数',
      dataIndex: 'unlock_count',
      key: 'unlock_count',
      width: 100,
    },
    {
      title: '回购信心',
      dataIndex: 'buyback_confidence',
      key: 'buyback_confidence',
      width: 110,
      render: (v) => (
        <span style={{ color: COLORS.muted }}>无回购</span>
      ),
    },
    {
      title: '风险等级',
      dataIndex: 'risk_level',
      key: 'risk_level',
      width: 100,
      render: (v) => (
        <Tag color={v === 'high' ? COLORS.high : COLORS.medium}>
          {v === 'high' ? '⚠️ 高风险' : '⚡ 中风险'}
        </Tag>
      ),
    },
  ]

  const opportunityColumns = [
    {
      title: '股票代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '回购信心',
      dataIndex: 'buyback_confidence',
      key: 'buyback_confidence',
      width: 120,
      sorter: (a, b) => (a.buyback_confidence || 0) - (b.buyback_confidence || 0),
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ color: COLORS.low, fontWeight: 700 }}>{v}</span>
      ),
    },
    {
      title: '回购次数',
      dataIndex: 'buyback_count',
      key: 'buyback_count',
      width: 100,
    },
    {
      title: '解禁压力',
      dataIndex: 'unlock_pressure',
      key: 'unlock_pressure',
      width: 110,
      render: (v) => (
        <span style={{ color: v > 0 ? COLORS.medium : COLORS.low }}>
          {v > 0 ? v : '无'}
        </span>
      ),
    },
    {
      title: '机会等级',
      dataIndex: 'opportunity_level',
      key: 'opportunity_level',
      width: 110,
      render: (v) => (
        <Tag color={v === 'high' ? COLORS.low : COLORS.primary}>
          {v === 'high' ? '✅ 高机会' : '📈 中机会'}
        </Tag>
      ),
    },
  ]

  // ============================================================
  // Tab Definitions
  // ============================================================

  const tabItems = [
    {
      key: 'unlock',
      label: '🔓 解禁日历',
      children: (
        <div>
          {/* 筛选器 */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }} align="middle">
            <Col>
              <Space>
                <Text>日期范围:</Text>
                <RangePicker
                  value={unlockDateRange}
                  onChange={setUnlockDateRange}
                  placeholder={['开始日期', '结束日期']}
                  size="small"
                />
              </Space>
            </Col>
            <Col>
              <Space>
                <Text>最小比例:</Text>
                <Slider
                  min={0}
                  max={10}
                  step={0.5}
                  value={minRatio}
                  onChange={setMinRatio}
                  style={{ width: 160 }}
                  tooltip={{ formatter: (v) => `${v}%` }}
                />
                <Text type="secondary">{minRatio}%</Text>
              </Space>
            </Col>
            <Col>
              <Button type="primary" icon={<ReloadOutlined />} onClick={fetchUnlockData} loading={loading}>
                查询
              </Button>
            </Col>
          </Row>

          {/* 统计卡片 */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={12} sm={6}>
              <Card size="small" style={cardStyle}>
                <Statistic
                  title="解禁事件总数"
                  value={unlockSummary.total_events || 0}
                  valueStyle={{ color: COLORS.primary }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small" style={cardStyle}>
                <Statistic
                  title="高压力事件"
                  value={unlockSummary.high_pressure_count || 0}
                  valueStyle={{ color: COLORS.high }}
                  prefix={<WarningOutlined />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small" style={cardStyle}>
                <Statistic
                  title="总解禁股数"
                  value={formatShares(unlockSummary.total_unlock_shares)}
                  valueStyle={{ color: COLORS.medium }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small" style={cardStyle}>
                <Statistic
                  title="平均压力评分"
                  value={unlockSummary.avg_pressure_score || 0}
                  valueStyle={{
                    color: (unlockSummary.avg_pressure_score || 0) >= 50 ? COLORS.high :
                           (unlockSummary.avg_pressure_score || 0) >= 25 ? COLORS.medium : COLORS.low,
                  }}
                />
              </Card>
            </Col>
          </Row>

          {/* 数据表格 */}
          <Table
            dataSource={unlockEvents}
            columns={unlockColumns}
            rowKey={(r, i) => `${r.ts_code}-${r.float_date}-${i}`}
            size="small"
            pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
            scroll={{ x: 1100 }}
          />
        </div>
      ),
    },
    {
      key: 'buyback',
      label: '💰 回购信号',
      children: (
        <div>
          {/* 筛选器 */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }} align="middle">
            <Col>
              <Space>
                <Text>日期范围:</Text>
                <RangePicker
                  value={buybackDateRange}
                  onChange={setBuybackDateRange}
                  placeholder={['开始日期', '结束日期']}
                  size="small"
                />
              </Space>
            </Col>
            <Col>
              <Space>
                <Text>最小金额:</Text>
                <Slider
                  min={0}
                  max={5000}
                  step={100}
                  value={minAmount}
                  onChange={setMinAmount}
                  style={{ width: 200 }}
                  tooltip={{ formatter: (v) => `${v}万` }}
                />
                <Text type="secondary">{minAmount}万</Text>
              </Space>
            </Col>
            <Col>
              <Button type="primary" icon={<ReloadOutlined />} onClick={fetchBuybackData} loading={loading}>
                查询
              </Button>
            </Col>
          </Row>

          {/* 统计卡片 */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={12} sm={6}>
              <Card size="small" style={cardStyle}>
                <Statistic
                  title="回购公告总数"
                  value={buybackSummary.total_announcements || 0}
                  valueStyle={{ color: COLORS.primary }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small" style={cardStyle}>
                <Statistic
                  title="总回购金额"
                  value={formatAmount(buybackSummary.total_buyback_amount)}
                  valueStyle={{ color: COLORS.low }}
                  prefix="💰"
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small" style={cardStyle}>
                <Statistic
                  title="平均信心评分"
                  value={buybackSummary.avg_confidence_score || 0}
                  valueStyle={{
                    color: (buybackSummary.avg_confidence_score || 0) >= 80 ? COLORS.low :
                           (buybackSummary.avg_confidence_score || 0) >= 50 ? COLORS.medium : COLORS.high,
                  }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small" style={cardStyle}>
                <Statistic
                  title="进行中回购"
                  value={buybackSummary.active_buyback_count || 0}
                  valueStyle={{ color: COLORS.low }}
                  prefix={<ThunderboltOutlined />}
                />
              </Card>
            </Col>
          </Row>

          {/* 数据表格 */}
          <Table
            dataSource={buybackSignals}
            columns={buybackColumns}
            rowKey={(r, i) => `${r.ts_code}-${r.ann_date}-${i}`}
            size="small"
            pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
            scroll={{ x: 1200 }}
          />
        </div>
      ),
    },
    {
      key: 'heatmap',
      label: '🗺️ 事件热力图',
      children: (
        <div>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col>
              <Button type="primary" icon={<ReloadOutlined />} onClick={fetchHeatmapData} loading={loading}>
                刷新数据
              </Button>
            </Col>
          </Row>

          {heatmapData ? (
            <>
              {/* 综合统计卡片 */}
              <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                <Col xs={12} sm={6}>
                  <Card size="small" style={cardStyle}>
                    <Statistic
                      title="风险股票数"
                      value={heatmapSummary.risk_stock_count || 0}
                      valueStyle={{ color: COLORS.high }}
                      prefix={<WarningOutlined />}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={6}>
                  <Card size="small" style={cardStyle}>
                    <Statistic
                      title="机会股票数"
                      value={heatmapSummary.opportunity_stock_count || 0}
                      valueStyle={{ color: COLORS.low }}
                      prefix={<CheckCircleOutlined />}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={6}>
                  <Card size="small" style={cardStyle}>
                    <Statistic
                      title="综合信号"
                      value={heatmapSummary.overall_label || '--'}
                      valueStyle={{
                        color: heatmapSummary.overall_signal === 'bullish' ? COLORS.bullish :
                               heatmapSummary.overall_signal === 'bearish' ? COLORS.bearish : COLORS.neutral,
                        fontSize: 16,
                      }}
                    />
                  </Card>
                </Col>
                <Col xs={12} sm={6}>
                  <Card size="small" style={cardStyle}>
                    <Statistic
                      title="事件活跃度"
                      value={heatmapSummary.activity_index || 0}
                      suffix="/ 100"
                      valueStyle={{ color: COLORS.primary }}
                    />
                  </Card>
                </Col>
              </Row>

              {/* 信号对比 */}
              <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                <Col xs={12}>
                  <Card size="small" title="解禁压力总分" style={cardStyle}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.high }}>
                        {heatmapSummary.total_unlock_pressure || 0}
                      </div>
                      <div style={{ color: '#999', fontSize: 12 }}>
                        即将解禁 {heatmapSummary.upcoming_unlock_count || 0} 笔
                      </div>
                    </div>
                  </Card>
                </Col>
                <Col xs={12}>
                  <Card size="small" title="回购信心总分" style={cardStyle}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 36, fontWeight: 700, color: COLORS.low }}>
                        {heatmapSummary.total_buyback_confidence || 0}
                      </div>
                      <div style={{ color: '#999', fontSize: 12 }}>
                        近期回购 {heatmapSummary.recent_buyback_count || 0} 笔
                      </div>
                    </div>
                  </Card>
                </Col>
              </Row>

              {/* 风险股票表 */}
              <Card
                size="small"
                title={
                  <Space>
                    <WarningOutlined style={{ color: COLORS.high }} />
                    <span>⚠️ 风险股票（高解禁压力 + 无回购）</span>
                    <Badge count={riskStocks.length} style={{ backgroundColor: COLORS.high }} />
                  </Space>
                }
                style={{ marginBottom: 16, ...cardStyle }}
              >
                {riskStocks.length > 0 ? (
                  <Table
                    dataSource={riskStocks}
                    columns={riskColumns}
                    rowKey="ts_code"
                    size="small"
                    pagination={{ pageSize: 10 }}
                  />
                ) : (
                  <Empty description="暂无高风险股票" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>

              {/* 机会股票表 */}
              <Card
                size="small"
                title={
                  <Space>
                    <CheckCircleOutlined style={{ color: COLORS.low }} />
                    <span>✅ 机会股票（有回购 + 低解禁压力）</span>
                    <Badge count={opportunityStocks.length} style={{ backgroundColor: COLORS.low }} />
                  </Space>
                }
                style={cardStyle}
              >
                {opportunityStocks.length > 0 ? (
                  <Table
                    dataSource={opportunityStocks}
                    columns={opportunityColumns}
                    rowKey="ts_code"
                    size="small"
                    pagination={{ pageSize: 10 }}
                  />
                ) : (
                  <Empty description="暂无机会股票" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </>
          ) : (
            <Empty description="点击刷新加载数据" />
          )}
        </div>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Card
        title='📅 事件日历 — 解禁 + 回购信号'
        extra={
          <Space>
            <Segmented
              options={[
                { label: '解禁日历', value: 'unlock' },
                { label: '回购信号', value: 'buyback' },
                { label: '事件热力图', value: 'heatmap' },
              ]}
              value={activeTab}
              onChange={setActiveTab}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={handleRefresh}
              loading={loading}
            >
              刷新
            </Button>
          </Space>
        }
        style={cardStyle}
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <Spin size='large' tip='加载中...' />
          </div>
        ) : (
          <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
        )}
      </Card>
    </div>
  )
}
