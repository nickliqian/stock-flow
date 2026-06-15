import React, { useState, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Space,
  Spin, Empty, DatePicker, Select, InputNumber, Typography, message, Tooltip,
} from 'antd'
import {
  LineChartOutlined, TrophyOutlined, WarningOutlined,
  ArrowUpOutlined, ArrowDownOutlined, BarChartOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { backtestStrategy } from '../services/api'

const { Text, Title } = Typography
const { RangePicker } = DatePicker

/** 统计卡片 */
function StatCards({ stats }) {
  if (!stats) return null
  const winRateColor = stats.win_rate >= 60 ? '#52c41a' : stats.win_rate >= 45 ? '#faad14' : '#ff4d4f'
  const sharpeColor = stats.sharpe_ratio >= 1 ? '#52c41a' : stats.sharpe_ratio >= 0 ? '#faad14' : '#ff4d4f'

  return (
    <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
      <Col xs={12} sm={6}>
        <Card size="small">
          <Statistic
            title="胜率"
            value={stats.win_rate}
            suffix="%"
            valueStyle={{ color: winRateColor, fontSize: 20 }}
            prefix={<TrophyOutlined />}
          />
        </Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card size="small">
          <Statistic
            title="累计收益"
            value={stats.total_return}
            suffix="%"
            valueStyle={{ color: stats.total_return >= 0 ? '#52c41a' : '#ff4d4f', fontSize: 20 }}
            prefix={stats.total_return >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
          />
        </Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card size="small">
          <Statistic
            title="最大回撤"
            value={stats.max_drawdown}
            suffix="%"
            valueStyle={{ color: '#ff4d4f', fontSize: 20 }}
            prefix={<WarningOutlined />}
          />
        </Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card size="small">
          <Statistic
            title="夏普比率"
            value={stats.sharpe_ratio}
            valueStyle={{ color: sharpeColor, fontSize: 20 }}
            prefix={<BarChartOutlined />}
          />
        </Card>
      </Col>
    </Row>
  )
}

/** 简易收益曲线（CSS bar chart） */
function EquityCurve({ data }) {
  if (!data || data.length === 0) return null

  const values = data.map(d => d.value)
  const minVal = Math.min(...values) * 0.98
  const maxVal = Math.max(...values) * 1.02
  const range = maxVal - minVal || 1

  return (
    <Card size="small" title="📈 净值曲线" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', height: 120, gap: 1, padding: '0 4px' }}>
        {data.map((d, i) => {
          const height = ((d.value - minVal) / range) * 100
          const color = d.value >= 100 ? '#52c41a' : '#ff4d4f'
          return (
            <Tooltip key={i} title={`${d.date}: ${d.value}`}>
              <div style={{
                flex: 1,
                height: `${Math.max(height, 2)}%`,
                backgroundColor: color,
                borderRadius: '2px 2px 0 0',
                opacity: 0.8,
                minWidth: 2,
                cursor: 'pointer',
              }} />
            </Tooltip>
          )
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
        <Text type="secondary" style={{ fontSize: 11 }}>{data[0]?.date}</Text>
        <Text type="secondary" style={{ fontSize: 11 }}>初始: 100</Text>
        <Text type="secondary" style={{ fontSize: 11 }}>{data[data.length - 1]?.date}</Text>
      </div>
    </Card>
  )
}

/** 每日结果表格 */
function DailyTable({ data }) {
  if (!data || data.length === 0) return null

  const columns = [
    { title: '日期', dataIndex: 'date', width: 100, render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text> },
    { title: '选股数', dataIndex: 'picks_count', width: 80, align: 'center' },
    {
      title: '平均收益',
      dataIndex: 'avg_return',
      width: 100,
      align: 'center',
      sorter: (a, b) => (a.avg_return || 0) - (b.avg_return || 0),
      render: (v) => v != null ? (
        <Text style={{ color: v >= 0 ? '#52c41a' : '#ff4d4f', fontWeight: 600 }}>
          {v >= 0 ? '+' : ''}{v.toFixed(2)}%
        </Text>
      ) : '--',
    },
    {
      title: '最佳',
      dataIndex: 'best_return',
      width: 90,
      align: 'center',
      render: (v) => v != null ? <Text style={{ color: '#52c41a' }}>+{v.toFixed(2)}%</Text> : '--',
    },
    {
      title: '最差',
      dataIndex: 'worst_return',
      width: 90,
      align: 'center',
      render: (v) => v != null ? <Text style={{ color: '#ff4d4f' }}>{v.toFixed(2)}%</Text> : '--',
    },
    {
      title: 'TOP选股',
      key: 'top_picks',
      render: (_, record) => {
        if (!record.picks || record.picks.length === 0) return '--'
        return (
          <Space size={4} wrap>
            {record.picks.slice(0, 3).map((p, i) => (
              <Tooltip key={i} title={`${p.name} ${p.return_pct >= 0 ? '+' : ''}${p.return_pct}%`}>
                <Tag style={{ fontSize: 11 }}>
                  {p.name} <Text style={{ color: p.return_pct >= 0 ? '#52c41a' : '#ff4d4f', fontSize: 11 }}>
                    {p.return_pct >= 0 ? '+' : ''}{p.return_pct}%
                  </Text>
                </Tag>
              </Tooltip>
            ))}
          </Space>
        )
      },
    },
  ]

  return (
    <Table
      columns={columns}
      dataSource={data.map((d, i) => ({ ...d, key: d.date + i }))}
      pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 个交易日` }}
      size="small"
      scroll={{ x: 700 }}
    />
  )
}

/** 回测主组件 */
export default function StrategyBacktest({ strategies }) {
  const [selectedStrategy, setSelectedStrategy] = useState(null)
  const [dateRange, setDateRange] = useState(null)
  const [holdDays, setHoldDays] = useState(5)
  const [topN, setTopN] = useState(30)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleBacktest = useCallback(async () => {
    if (!selectedStrategy) {
      message.warning('请选择策略')
      return
    }
    if (!dateRange || dateRange.length !== 2) {
      message.warning('请选择回测日期范围')
      return
    }

    setLoading(true)
    setResult(null)
    try {
      const res = await backtestStrategy(selectedStrategy, {
        start_date: dateRange[0].format('YYYYMMDD'),
        end_date: dateRange[1].format('YYYYMMDD'),
        hold_days: holdDays,
        limit: topN,
      })
      if (res?.success) {
        setResult(res.data)
      } else {
        message.error(res?.error || '回测失败')
      }
    } catch (err) {
      console.error('Backtest failed:', err)
      message.error('回测请求失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [selectedStrategy, dateRange, holdDays, topN])

  const strategyOptions = (strategies || []).map(s => ({
    value: s.name,
    label: `${s.icon} ${s.description}`,
  }))

  return (
    <div>
      {/* 回测参数面板 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap size="middle" style={{ width: '100%' }}>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>策略</Text>
            <Select
              style={{ width: 280 }}
              placeholder="选择回测策略"
              options={strategyOptions}
              value={selectedStrategy}
              onChange={setSelectedStrategy}
            />
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>日期范围</Text>
            <RangePicker
              value={dateRange}
              onChange={setDateRange}
              disabledDate={(current) => current && current.isAfter(dayjs())}
              placeholder={['开始日期', '结束日期']}
            />
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>持有天数</Text>
            <InputNumber min={1} max={20} value={holdDays} onChange={setHoldDays} style={{ width: 70 }} />
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>每日选股</Text>
            <InputNumber min={5} max={50} value={topN} onChange={setTopN} style={{ width: 70 }} />
          </div>
          <Button type="primary" icon={<LineChartOutlined />} onClick={handleBacktest} loading={loading}>
            开始回测
          </Button>
        </Space>
      </Card>

      {/* 回测结果 */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" tip="回测计算中，涉及大量历史数据，请耐心等待..." />
        </div>
      )}

      {!loading && result && (
        <>
          {/* 策略信息 */}
          <div style={{ marginBottom: 12 }}>
            <Space>
              <Tag color="blue" style={{ fontSize: 14 }}>{result.strategy?.icon}</Tag>
              <Text strong style={{ fontSize: 14 }}>{result.strategy?.description}</Text>
              <Tag>{result.params?.start_date} ~ {result.params?.end_date}</Tag>
              <Tag>持有{result.params?.hold_days}天</Tag>
              <Tag>每日选{result.params?.top_n}只</Tag>
            </Space>
          </div>

          {/* 统计卡片 */}
          <StatCards stats={result.stats} />

          {/* 额外统计 */}
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            <Col xs={12} sm={6}>
              <Card size="small">
                <Statistic title="日均收益" value={result.stats?.avg_return} suffix="%/日" valueStyle={{ fontSize: 16 }} />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small">
                <Statistic title="盈亏比" value={result.stats?.profit_loss_ratio} valueStyle={{ fontSize: 16 }} />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small">
                <Statistic title="最佳单日" value={result.stats?.best_day} suffix="%/日" valueStyle={{ color: '#52c41a', fontSize: 16 }} />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small">
                <Statistic title="最差单日" value={result.stats?.worst_day} suffix="%/日" valueStyle={{ color: '#ff4d4f', fontSize: 16 }} />
              </Card>
            </Col>
          </Row>

          {/* 净值曲线 */}
          <EquityCurve data={result.equity_curve} />

          {/* 每日详情 */}
          <Card size="small" title="📊 每日回测明细">
            <DailyTable data={result.daily_results} />
          </Card>
        </>
      )}

      {!loading && !result && (
        <Empty description="选择策略和日期范围，点击「开始回测」" />
      )}
    </div>
  )
}
