import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Space,
  Spin, Empty, Tooltip, Badge, Typography, Slider, message,
  Progress, Divider,
} from 'antd'
import {
  ReloadOutlined, ThunderboltOutlined, EyeOutlined,
  StarFilled, FireOutlined, RiseOutlined,
} from '@ant-design/icons'
import { getStrategyConfluence } from '../services/api'

const { Text, Title, Paragraph } = Typography

// 策略类别颜色
const CATEGORY_COLORS = {
  value: '#1677ff',
  momentum: '#fa8c16',
  flow: '#52c41a',
  event: '#722ed1',
  combo: '#f5222d',
}

// 策略类别中文名
const CATEGORY_NAMES = {
  value: '价值',
  momentum: '动量',
  flow: '资金',
  event: '事件',
  combo: '组合',
}

// 共振等级颜色
function confluenceLevel(score, numStrategies) {
  if (numStrategies >= 4) return { color: '#f5222d', label: '极强', bg: '#fff1f0' }
  if (numStrategies >= 3) return { color: '#fa8c16', label: '强', bg: '#fff7e6' }
  if (score >= 70) return { color: '#52c41a', label: '较强', bg: '#f6ffed' }
  if (score >= 50) return { color: '#1677ff', label: '中等', bg: '#e6f4ff' }
  return { color: '#999', label: '一般', bg: '#f5f5f5' }
}

/** 策略共振统计卡片 */
function ConfluenceStats({ data }) {
  if (!data) return null
  const results = data.results || []
  const total = results.length
  const strong = results.filter(r => r.num_strategies >= 3).length
  const veryStrong = results.filter(r => r.num_strategies >= 4).length
  const avgScore = total > 0 ? (results.reduce((s, r) => s + r.confluence_score, 0) / total).toFixed(1) : 0

  // 统计各策略被触发次数
  const strategyHits = {}
  results.forEach(r => {
    (r.strategies || []).forEach(s => {
      strategyHits[s.name] = (strategyHits[s.name] || 0) + 1
    })
  })

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={12} sm={6}>
        <Card size="small" style={{ textAlign: 'center' }}>
          <Statistic title="共振股票数" value={total} suffix="只" valueStyle={{ color: '#1677ff' }} />
        </Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card size="small" style={{ textAlign: 'center' }}>
          <Statistic title="强共振 (≥3策略)" value={strong} suffix="只" valueStyle={{ color: '#fa8c16' }} />
        </Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card size="small" style={{ textAlign: 'center' }}>
          <Statistic title="极强共振 (≥4策略)" value={veryStrong} suffix="只" valueStyle={{ color: '#f5222d' }} />
        </Card>
      </Col>
      <Col xs={12} sm={6}>
        <Card size="small" style={{ textAlign: 'center' }}>
          <Statistic title="平均共振分" value={avgScore} valueStyle={{ color: '#52c41a' }} />
        </Card>
      </Col>
    </Row>
  )
}

/** 策略命中热力图 */
function StrategyHeatmap({ results }) {
  if (!results || results.length === 0) return null

  // 收集所有策略
  const allStrategies = new Map()
  results.forEach(r => {
    (r.strategies || []).forEach(s => {
      if (!allStrategies.has(s.name)) {
        allStrategies.set(s.name, { icon: s.icon, category: s.category, name: s.name })
      }
    })
  })
  const stratList = Array.from(allStrategies.values())

  // 只展示前20只股票
  const topStocks = results.slice(0, 20)

  return (
    <Card size="small" title="🔥 策略命中热力图（TOP20）" style={{ marginBottom: 16 }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              <th style={{ padding: '6px 8px', textAlign: 'left', borderBottom: '1px solid #f0f0f0', minWidth: 120 }}>股票</th>
              {stratList.map(s => (
                <th key={s.name} style={{ padding: '6px 4px', textAlign: 'center', borderBottom: '1px solid #f0f0f0', minWidth: 40 }}>
                  <Tooltip title={s.name}>
                    <span>{s.icon}</span>
                  </Tooltip>
                </th>
              ))}
              <th style={{ padding: '6px 8px', textAlign: 'center', borderBottom: '1px solid #f0f0f0' }}>共振分</th>
            </tr>
          </thead>
          <tbody>
            {topStocks.map((stock, idx) => {
              const triggeredSet = new Set((stock.strategies || []).map(s => s.name))
              const level = confluenceLevel(stock.confluence_score, stock.num_strategies)
              return (
                <tr key={stock.ts_code} style={{ background: idx % 2 === 0 ? '#fafafa' : '#fff' }}>
                  <td style={{ padding: '6px 8px', borderBottom: '1px solid #f0f0f0' }}>
                    <Text strong style={{ fontSize: 12 }}>{stock.name}</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 10 }}>{stock.ts_code}</Text>
                  </td>
                  {stratList.map(s => (
                    <td key={s.name} style={{ padding: '6px 4px', textAlign: 'center', borderBottom: '1px solid #f0f0f0' }}>
                      {triggeredSet.has(s.name) ? (
                        <span style={{ color: CATEGORY_COLORS[s.category] || '#1677ff', fontSize: 16 }}>●</span>
                      ) : (
                        <span style={{ color: '#f0f0f0', fontSize: 16 }}>●</span>
                      )}
                    </td>
                  ))}
                  <td style={{ padding: '6px 8px', textAlign: 'center', borderBottom: '1px solid #f0f0f0' }}>
                    <Tag color={level.color} style={{ margin: 0 }}>
                      {stock.confluence_score.toFixed(0)}
                    </Tag>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

/** 单只股票的共振详情展开行 */
function ConfluenceDetail({ record }) {
  if (!record.strategies || record.strategies.length === 0) return null

  return (
    <div style={{ padding: '12px 16px', background: '#fafafa' }}>
      <Row gutter={[16, 12]}>
        {record.strategies.map((s, idx) => (
          <Col xs={24} sm={12} md={8} key={idx}>
            <Card
              size="small"
              style={{ borderLeft: `3px solid ${CATEGORY_COLORS[s.category] || '#1677ff'}` }}
            >
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space>
                  <span style={{ fontSize: 16 }}>{s.icon}</span>
                  <Tag color={CATEGORY_COLORS[s.category]} style={{ margin: 0 }}>
                    {CATEGORY_NAMES[s.category] || s.category}
                  </Tag>
                  <Text strong style={{ fontSize: 12 }}>{s.name}</Text>
                </Space>
                <Text type="secondary" style={{ fontSize: 11 }}>{s.reason}</Text>
                <Space size={4} wrap>
                  {Object.entries(s.signals || {}).filter(([k]) => !k.startsWith('_')).slice(0, 4).map(([k, v]) => (
                    <Tag key={k} style={{ fontSize: 10, margin: 0 }}>{k}: {typeof v === 'number' ? v.toFixed(2) : v}</Tag>
                  ))}
                </Space>
                <Text type="secondary" style={{ fontSize: 11 }}>策略得分: {s.score.toFixed(1)}</Text>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}

/** 主页面 */
export default function StrategyConfluence({ tradeDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [minStrategies, setMinStrategies] = useState(2)

  const fetchData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const params = { min_strategies: minStrategies }
      if (tradeDate) params.trade_date = tradeDate
      const res = await getStrategyConfluence(params, { signal })
      if (res?.success) {
        setData(res.data)
      } else {
        message.error('策略共振扫描失败')
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Confluence scan failed:', err)
      message.error('策略共振扫描失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [tradeDate, minStrategies])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(controller.signal)
    return () => controller.abort()
  }, [fetchData])

  const results = data?.results || []

  const columns = [
    {
      title: '排名',
      width: 50,
      render: (_, __, i) => i + 1,
    },
    {
      title: '股票',
      key: 'stock',
      width: 150,
      render: (_, record) => (
        <div>
          <Text strong>{record.name}</Text>
          <br />
          <Text type="secondary" style={{ fontSize: 11 }}>{record.ts_code}</Text>
        </div>
      ),
    },
    {
      title: '共振得分',
      dataIndex: 'confluence_score',
      width: 100,
      sorter: (a, b) => a.confluence_score - b.confluence_score,
      defaultSortOrder: 'descend',
      render: (score, record) => {
        const level = confluenceLevel(score, record.num_strategies)
        return (
          <Tooltip title={`共振等级：${level.label}`}>
            <Tag color={level.color} style={{ margin: 0, fontSize: 13, padding: '2px 8px' }}>
              {score.toFixed(1)}
            </Tag>
          </Tooltip>
        )
      },
    },
    {
      title: '命中策略',
      dataIndex: 'num_strategies',
      width: 100,
      sorter: (a, b) => a.num_strategies - b.num_strategies,
      defaultSortOrder: 'descend',
      render: (num, record) => {
        const level = confluenceLevel(record.confluence_score, num)
        return (
          <Space size={2}>
            <Badge
              count={num}
              showZero
              style={{
                backgroundColor: level.color,
                fontSize: 11,
              }}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>{level.label}</Text>
          </Space>
        )
      },
    },
    {
      title: '触发策略',
      key: 'strategies',
      render: (_, record) => (
        <Space size={4} wrap>
          {(record.strategies || []).map((s, i) => (
            <Tooltip key={i} title={`${s.name}（得分: ${s.score.toFixed(1)}）`}>
              <Tag
                color={CATEGORY_COLORS[s.category]}
                style={{ margin: 0, cursor: 'default' }}
              >
                {s.icon} {s.score.toFixed(0)}
              </Tag>
            </Tooltip>
          ))}
        </Space>
      ),
    },
    {
      title: '关键信号',
      key: 'signals',
      render: (_, record) => {
        const signals = record.best_signals || {}
        const items = []
        if (signals.pe_ttm != null) items.push(`PE ${signals.pe_ttm}`)
        if (signals.pb != null) items.push(`PB ${signals.pb}`)
        if (signals.dv_ratio != null) items.push(`股息 ${signals.dv_ratio}%`)
        if (signals.volume_ratio != null) items.push(`量比 ${signals.volume_ratio}x`)
        if (signals.pct_change != null) items.push(`涨幅 ${signals.pct_change}%`)
        if (signals.consecutive_days != null) items.push(`连续${signals.consecutive_days}日`)
        if (signals.ma5 != null) items.push(`MA5 ${signals.ma5}`)
        if (signals.alignment_gap_pct != null) items.push(`间距 ${signals.alignment_gap_pct}%`)
        if (items.length === 0) return '--'
        return (
          <Space size={2} wrap>
            {items.slice(0, 3).map((t, i) => (
              <Tag key={i} style={{ fontSize: 10, margin: 0 }}>{t}</Tag>
            ))}
          </Space>
        )
      },
    },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      {/* 顶部操作栏 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}>🎯 策略共振雷达</Title>
          {tradeDate && <Tag>{tradeDate}</Tag>}
        </Space>
        <Space>
          <Space size={8}>
            <Text type="secondary" style={{ fontSize: 12 }}>最少匹配策略:</Text>
            <Slider
              min={2}
              max={6}
              value={minStrategies}
              onChange={setMinStrategies}
              marks={{ 2: '2', 3: '3', 4: '4' }}
              style={{ width: 120 }}
            />
          </Space>
          <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      {/* 说明 */}
      <Card size="small" style={{ marginBottom: 16, background: '#f6ffed', border: '1px solid #b7eb8f' }}>
        <Space direction="vertical" size={2}>
          <Text strong style={{ fontSize: 13 }}>
            <FireOutlined style={{ color: '#f5222d' }} /> 什么是策略共振？
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            当多维度策略（价值、动量、资金等）同时选中同一只股票时，说明该股票在多个角度都具有投资价值。
            命中策略越多，信号越可靠。共振评分 = 各策略分数 × 策略数量加权系数。
          </Text>
        </Space>
      </Card>

      {/* 统计卡片 */}
      <ConfluenceStats data={data} />

      {/* 热力图 */}
      <StrategyHeatmap results={results} />

      {/* 结果表格 */}
      <Card size="small" title={`📊 共振股票列表（${results.length} 只）`}>
        <Spin spinning={loading}>
          {results.length === 0 && !loading ? (
            <Empty description="暂无共振结果，请尝试降低最少匹配策略数" />
          ) : (
            <Table
              columns={columns}
              dataSource={results.map((r, i) => ({ ...r, key: r.ts_code + i }))}
              pagination={{ pageSize: 20, showSizeChanger: false, showTotal: (t) => `共 ${t} 只` }}
              size="small"
              scroll={{ x: 900 }}
              expandable={{
                expandedRowRender: (record) => <ConfluenceDetail record={record} />,
                rowExpandable: (record) => record.strategies && record.strategies.length > 0,
              }}
            />
          )}
        </Spin>
      </Card>
    </div>
  )
}
