import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Space,
  Spin, Empty, Tooltip, Badge, Typography, Slider, DatePicker,
  Segmented, Tabs, Progress, Divider, message,
} from 'antd'
import {
  ReloadOutlined, AlertOutlined, ThunderboltOutlined,
  FireOutlined, SafetyCertificateOutlined, HistoryOutlined,
  BarChartOutlined, EyeOutlined,
} from '@ant-design/icons'
import axios from 'axios'
import dayjs from 'dayjs'

const { Text, Title } = Typography

// 策略信号强度颜色
const STRENGTH_COLORS = {
  2: { color: '#8c8c8c', bg: '#2a2a2a', label: '一般' },
  3: { color: '#1677ff', bg: '#0a1628', label: '中等' },
  4: { color: '#fa8c16', bg: '#2a1a08', label: '强' },
  5: { color: '#f5222d', bg: '#2a0808', label: '极强' },
  6: { color: '#722ed1', bg: '#1a0828', label: '超强' },
}

function getStrengthColor(count) {
  if (count >= 6) return STRENGTH_COLORS[6]
  if (count >= 5) return STRENGTH_COLORS[5]
  if (count >= 4) return STRENGTH_COLORS[4]
  if (count >= 3) return STRENGTH_COLORS[3]
  return STRENGTH_COLORS[2]
}

// ------------------------------------------------------------------
// Tab 1: 实时告警
// ------------------------------------------------------------------
function AlertsTab({ tradeDate, loading }) {
  const [alerts, setAlerts] = useState([])
  const [total, setTotal] = useState(0)
  const [minStrategies, setMinStrategies] = useState(3)
  const [fetching, setFetching] = useState(false)
  const [summary, setSummary] = useState(null)

  const fetchAlerts = useCallback(async () => {
    if (!tradeDate) return
    setFetching(true)
    try {
      const [alertsRes, summaryRes] = await Promise.all([
        axios.get('/api/alerts/', { params: { trade_date: tradeDate, min_strategies: minStrategies } }),
        axios.get('/api/alerts/summary', { params: { trade_date: tradeDate } }),
      ])
      setAlerts(alertsRes.data?.data?.alerts || [])
      setTotal(alertsRes.data?.data?.total || 0)
      setSummary(summaryRes.data?.data || null)
    } catch (e) {
      console.error('Failed to load alerts:', e)
      message.error('加载告警数据失败')
    } finally {
      setFetching(false)
    }
  }, [tradeDate, minStrategies])

  useEffect(() => { fetchAlerts() }, [fetchAlerts])

  const columns = [
    {
      title: '强度',
      dataIndex: 'strategy_count',
      key: 'strategy_count',
      width: 70,
      sorter: (a, b) => a.strategy_count - b.strategy_count,
      defaultSortOrder: 'descend',
      render: (count) => {
        const s = getStrengthColor(count)
        return <Badge count={count} style={{ backgroundColor: s.color }} overflowCount={99} />
      },
    },
    {
      title: '代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
      render: (code) => <Text code style={{ color: '#e0e0e0' }}>{code}</Text>,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 100,
      render: (name) => <span style={{ color: '#e0e0e0' }}>{name}</span>,
    },
    {
      title: '策略数',
      dataIndex: 'strategy_count',
      key: 'strategy_count_num',
      width: 80,
      render: (count) => {
        const s = getStrengthColor(count)
        return <Tag color={s.color}>{count}个策略</Tag>
      },
    },
    {
      title: '总分',
      dataIndex: 'total_score',
      key: 'total_score',
      width: 90,
      sorter: (a, b) => a.total_score - b.total_score,
      render: (score) => (
        <span style={{ color: score >= 200 ? '#f5222d' : score >= 150 ? '#fa8c16' : '#e0e0e0', fontWeight: 600 }}>
          {score?.toFixed(1)}
        </span>
      ),
    },
    {
      title: '最高分',
      dataIndex: 'max_score',
      key: 'max_score',
      width: 80,
      render: (score) => <span style={{ color: '#52c41a' }}>{score?.toFixed(1)}</span>,
    },
  ]

  const expandedRowRender = (record) => {
    if (!record.strategies?.length) return null
    return (
      <div style={{ padding: '8px 0' }}>
        <Row gutter={[8, 8]}>
          {record.strategies.map((s, i) => (
            <Col key={i} xs={24} sm={12} md={8} lg={6}>
              <Card
                size="small"
                style={{
                  backgroundColor: s.signal_type === 'bullish' ? '#0a1628' : s.signal_type === 'bearish' ? '#1a0808' : '#1a1a1a',
                  border: `1px solid ${s.signal_type === 'bullish' ? '#1677ff33' : s.signal_type === 'bearish' ? '#f5222d33' : '#333'}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text style={{ color: '#e0e0e0', fontSize: 12 }}>{s.strategy_name}</Text>
                  <Tag color={s.score >= 60 ? '#52c41a' : s.score < 30 ? '#f5222d' : '#faad14'} style={{ margin: 0 }}>
                    {s.score?.toFixed(1)}
                  </Tag>
                </div>
                {s.details && (
                  <div style={{ marginTop: 4 }}>
                    <Text style={{ color: '#888', fontSize: 11 }} ellipsis>
                      {(() => { try { return JSON.parse(s.details)?.reason || '' } catch { return s.details.slice(0, 50) } })()}
                    </Text>
                  </div>
                )}
              </Card>
            </Col>
          ))}
        </Row>
      </div>
    )
  }

  return (
    <div>
      {/* Controls */}
      <Card size="small" style={{ marginBottom: 12, backgroundColor: '#1a1a1a', border: '1px solid #333' }}>
        <Space size="large" wrap>
          <span style={{ color: '#e0e0e0' }}>最小策略数:</span>
          <Slider
            min={2}
            max={6}
            value={minStrategies}
            onChange={setMinStrategies}
            style={{ width: 200 }}
            marks={{ 2: '2', 3: '3', 4: '4', 5: '5', 6: '6' }}
          />
          <Tag color="blue">≥ {minStrategies} 个策略</Tag>
        </Space>
      </Card>

      {/* Stats Cards */}
      {summary && (
        <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ backgroundColor: '#1a1a1a', border: '1px solid #333', textAlign: 'center' }}>
              <Statistic title={<span style={{ color: '#888' }}>总信号</span>} value={summary.total_signals} valueStyle={{ color: '#e0e0e0' }} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ backgroundColor: '#1a1a1a', border: '1px solid #333', textAlign: 'center' }}>
              <Statistic
                title={<span style={{ color: '#888' }}>涉及股票</span>}
                value={summary.total_stocks}
                valueStyle={{ color: '#1677ff' }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ backgroundColor: '#1a1a1a', border: '1px solid #333', textAlign: 'center' }}>
              <Statistic
                title={<span style={{ color: '#888' }}>强信号 (4+)</span>}
                value={summary.strong_alerts}
                valueStyle={{ color: '#fa8c16' }}
                suffix={<FireOutlined />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" style={{ backgroundColor: '#1a1a1a', border: '1px solid #333', textAlign: 'center' }}>
              <Statistic
                title={<span style={{ color: '#888' }}>极强 (5+)</span>}
                value={summary.very_strong_alerts}
                valueStyle={{ color: '#f5222d' }}
                suffix={<ThunderboltOutlined />}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* Alerts Table */}
      <Card
        size="small"
        title={<span style={{ color: '#e0e0e0' }}>🚨 告警列表 <Text type="secondary">({total} 只股票)</Text></span>}
        extra={<Button icon={<ReloadOutlined />} onClick={fetchAlerts} loading={fetching} size="small">刷新</Button>}
        style={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
      >
        <Table
          dataSource={alerts}
          columns={columns}
          rowKey="ts_code"
          size="small"
          loading={fetching}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
          expandable={{ expandedRowRender, expandRowByClick: true }}
          locale={{ emptyText: <Empty description="暂无告警数据" /> }}
        />
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------
// Tab 2: 信号统计
// ------------------------------------------------------------------
function StatsTab({ tradeDate }) {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!tradeDate) return
    setLoading(true)
    axios.get('/api/alerts/summary', { params: { trade_date: tradeDate } })
      .then(res => setSummary(res.data?.data || null))
      .catch(() => message.error('加载统计数据失败'))
      .finally(() => setLoading(false))
  }, [tradeDate])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />
  if (!summary) return <Empty description="暂无数据" />

  // 策略贡献表
  const stratColumns = [
    { title: '策略', dataIndex: 'strategy_name', key: 'name', render: (t) => <Text style={{ color: '#e0e0e0' }}>{t}</Text> },
    { title: '信号数', dataIndex: 'count', key: 'count', sorter: (a, b) => a.count - b.count, defaultSortOrder: 'descend' },
    { title: '均分', dataIndex: 'avg_score', key: 'avg', render: (v) => v?.toFixed(1) },
    {
      title: '占比',
      key: 'pct',
      render: (_, r) => {
        const pct = summary.total_signals > 0 ? (r.count / summary.total_signals * 100) : 0
        return <Progress percent={pct} size="small" strokeColor="#1677ff" format={(p) => `${p.toFixed(1)}%`} />
      },
    },
  ]

  // 分布表
  const distColumns = [
    {
      title: '策略数',
      dataIndex: 'strategy_count',
      key: 'sc',
      render: (v) => {
        const s = getStrengthColor(v)
        return <Badge count={v} style={{ backgroundColor: s.color }} />
      },
    },
    { title: '股票数', dataIndex: 'stock_count', key: 'sc2' },
    {
      title: '占比',
      key: 'pct',
      render: (_, r) => {
        const total = summary.distribution?.reduce((s, d) => s + d.stock_count, 0) || 1
        const pct = r.stock_count / total * 100
        return <Progress percent={pct} size="small" strokeColor="#52c41a" format={(p) => `${p.toFixed(1)}%`} />
      },
    },
  ]

  return (
    <div>
      <Row gutter={[12, 12]}>
        {/* 信号类型分布 */}
        <Col xs={24} md={8}>
          <Card size="small" title={<span style={{ color: '#e0e0e0' }}>📊 信号类型分布</span>} style={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}>
            {Object.entries(summary.signal_type_dist || {}).map(([type, count]) => (
              <div key={type} style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                <Tag color={type === 'bullish' ? '#52c41a' : type === 'bearish' ? '#f5222d' : '#faad14'} style={{ width: 60, textAlign: 'center' }}>
                  {type === 'bullish' ? '看多' : type === 'bearish' ? '看空' : '中性'}
                </Tag>
                <Progress
                  percent={summary.total_signals > 0 ? (count / summary.total_signals * 100) : 0}
                  size="small"
                  strokeColor={type === 'bullish' ? '#52c41a' : type === 'bearish' ? '#f5222d' : '#faad14'}
                  format={() => count}
                  style={{ flex: 1 }}
                />
              </div>
            ))}
          </Card>
        </Col>

        {/* 策略数分布 */}
        <Col xs={24} md={8}>
          <Card size="small" title={<span style={{ color: '#e0e0e0' }}>📈 策略数分布</span>} style={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}>
            <Table
              dataSource={summary.distribution || []}
              columns={distColumns}
              rowKey="strategy_count"
              size="small"
              pagination={false}
            />
          </Card>
        </Col>

        {/* TOP 股票 */}
        <Col xs={24} md={8}>
          <Card size="small" title={<span style={{ color: '#e0e0e0' }}>🏆 TOP 信号强度</span>} style={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}>
            {summary.top_stocks?.map((s, i) => (
              <div key={s.ts_code} style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
                <span style={{
                  color: i < 3 ? '#faad14' : '#888',
                  fontWeight: i < 3 ? 700 : 400,
                  width: 20,
                  textAlign: 'center',
                  fontSize: 13,
                }}>
                  {i + 1}
                </span>
                <Text style={{ color: '#e0e0e0', fontSize: 13, flex: 1, marginLeft: 4 }}>
                  {s.name} <Text type="secondary" style={{ fontSize: 11 }}>({s.ts_code})</Text>
                </Text>
                <Badge count={s.strategy_count} style={{ backgroundColor: getStrengthColor(s.strategy_count).color }} />
              </div>
            ))}
          </Card>
        </Col>
      </Row>

      {/* 策略贡献表 */}
      <Card size="small" title={<span style={{ color: '#e0e0e0' }}>📋 策略贡献排行</span>} style={{ backgroundColor: '#1a1a1a', border: '1px solid #333', marginTop: 12 }}>
        <Table
          dataSource={summary.strategy_contribution || []}
          columns={stratColumns}
          rowKey="strategy_name"
          size="small"
          pagination={false}
        />
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------
// Tab 3: 信号历史
// ------------------------------------------------------------------
function HistoryTab({ tradeDate }) {
  const [tsCode, setTsCode] = useState('')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  const fetchHistory = useCallback(async () => {
    if (!tsCode.trim()) {
      message.warning('请输入股票代码')
      return
    }
    setLoading(true)
    setSearched(true)
    try {
      const res = await axios.get(`/api/alerts/history/${tsCode.trim()}`, { params: { days: 20 } })
      setHistory(res.data?.data?.history || [])
    } catch (e) {
      console.error('Failed to load history:', e)
      message.error('加载信号历史失败')
    } finally {
      setLoading(false)
    }
  }, [tsCode])

  const columns = [
    {
      title: '日期',
      dataIndex: 'trade_date',
      key: 'date',
      width: 110,
      render: (d) => <Text style={{ color: '#e0e0e0' }}>{d?.slice(0, 4)}-{d?.slice(4, 6)}-{d?.slice(6, 8)}</Text>,
    },
    {
      title: '策略数',
      dataIndex: 'strategy_count',
      key: 'sc',
      width: 70,
      render: (count) => {
        const s = getStrengthColor(count)
        return <Badge count={count} style={{ backgroundColor: s.color }} />
      },
    },
    {
      title: '总分',
      dataIndex: 'total_score',
      key: 'ts',
      width: 80,
      render: (score) => <span style={{ color: '#faad14', fontWeight: 600 }}>{score?.toFixed(1)}</span>,
    },
    {
      title: '触发策略',
      key: 'strategies',
      render: (_, record) => (
        <Space size={[4, 4]} wrap>
          {record.strategies?.map((s, i) => (
            <Tooltip key={i} title={`${s.strategy_name}: ${s.score?.toFixed(1)} (${s.signal_type})`}>
              <Tag
                color={s.score >= 60 ? '#52c41a' : s.score < 30 ? '#f5222d' : '#faad14'}
                style={{ margin: 0, fontSize: 11, cursor: 'pointer' }}
              >
                {s.strategy_name} ({s.score?.toFixed(0)})
              </Tag>
            </Tooltip>
          ))}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Card size="small" style={{ marginBottom: 12, backgroundColor: '#1a1a1a', border: '1px solid #333' }}>
        <Space size="middle">
          <span style={{ color: '#e0e0e0' }}>股票代码:</span>
          <input
            value={tsCode}
            onChange={(e) => setTsCode(e.target.value)}
            placeholder="如 000001.SZ"
            onKeyDown={(e) => e.key === 'Enter' && fetchHistory()}
            style={{
              width: 160, padding: '4px 8px', borderRadius: 4,
              border: '1px solid #333', backgroundColor: '#2a2a2a', color: '#e0e0e0',
              fontSize: 13, outline: 'none',
            }}
          />
          <Button type="primary" icon={<HistoryOutlined />} onClick={fetchHistory} loading={loading} size="small">
            查询
          </Button>
        </Space>
      </Card>

      <Card
        size="small"
        title={<span style={{ color: '#e0e0e0' }}>📈 信号历史 {tsCode && <Text type="secondary">({tsCode})</Text>}</span>}
        style={{ backgroundColor: '#1a1a1a', border: '1px solid #333' }}
      >
        {!searched ? (
          <Empty description="输入股票代码查询信号历史" />
        ) : (
          <Table
            dataSource={history}
            columns={columns}
            rowKey="trade_date"
            size="small"
            loading={loading}
            pagination={false}
            expandable={{
              expandedRowRender: (record) => (
                <div style={{ padding: '4px 0' }}>
                  <Row gutter={[8, 8]}>
                    {record.strategies?.map((s, i) => (
                      <Col key={i} xs={24} sm={12} md={8} lg={6}>
                        <Card
                          size="small"
                          style={{
                            backgroundColor: s.signal_type === 'bullish' ? '#0a1628' : s.signal_type === 'bearish' ? '#1a0808' : '#1a1a1a',
                            border: `1px solid ${s.signal_type === 'bullish' ? '#1677ff33' : s.signal_type === 'bearish' ? '#f5222d33' : '#333'}`,
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Text style={{ color: '#e0e0e0', fontSize: 11 }}>{s.strategy_name}</Text>
                            <Tag color={s.score >= 60 ? '#52c41a' : s.score < 30 ? '#f5222d' : '#faad14'} style={{ margin: 0, fontSize: 10 }}>
                              {s.score?.toFixed(1)}
                            </Tag>
                          </div>
                        </Card>
                      </Col>
                    ))}
                  </Row>
                </div>
              ),
              expandRowByClick: true,
            }}
            locale={{ emptyText: <Empty description="该股票暂无信号历史" /> }}
          />
        )}
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------
// Main Page
// ------------------------------------------------------------------
export default function SignalAlerts({ tradeDate: propDate }) {
  const [tradeDate, setTradeDate] = useState(propDate || dayjs().format('YYYYMMDD'))
  const [activeTab, setActiveTab] = useState('alerts')
  const [generating, setGenerating] = useState(false)
  const [lastGenerate, setLastGenerate] = useState(null)

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const res = await axios.get('/api/alerts/signals', { params: { trade_date: tradeDate } })
      if (res.data?.success) {
        message.success(`生成 ${res.data.data.total_signals} 条信号，涉及 ${res.data.data.strategies} 个策略`)
        setLastGenerate(new Date())
      } else {
        message.error(res.data?.error || '生成信号失败')
      }
    } catch (e) {
      message.error('生成信号失败: ' + (e.message || '未知错误'))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div>
      {/* Header */}
      <Card
        size="small"
        style={{ marginBottom: 12, backgroundColor: '#1a1a1a', border: '1px solid #333' }}
      >
        <Row justify="space-between" align="middle">
          <Col>
            <Space size="middle">
              <Title level={4} style={{ color: '#e0e0e0', margin: 0 }}>🚨 策略信号告警系统</Title>
              {lastGenerate && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  上次生成: {dayjs(lastGenerate).format('HH:mm:ss')}
                </Text>
              )}
            </Space>
          </Col>
          <Col>
            <Space size="middle">
              <DatePicker
                value={tradeDate ? dayjs(tradeDate, 'YYYYMMDD') : null}
                onChange={(date) => setTradeDate(date ? date.format('YYYYMMDD') : null)}
                disabledDate={(current) => {
                  if (!current) return false
                  const dow = current.day()
                  return dow === 0 || dow === 6
                }}
                placeholder="选择日期"
                allowClear={false}
                size="small"
                style={{ width: 140 }}
              />
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={handleGenerate}
                loading={generating}
                size="small"
              >
                生成信号
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'alerts',
            label: '🚨 实时告警',
            children: <AlertsTab tradeDate={tradeDate} />,
          },
          {
            key: 'stats',
            label: '📊 信号统计',
            children: <StatsTab tradeDate={tradeDate} />,
          },
          {
            key: 'history',
            label: '📈 信号历史',
            children: <HistoryTab tradeDate={tradeDate} />,
          },
        ]}
      />
    </div>
  )
}
