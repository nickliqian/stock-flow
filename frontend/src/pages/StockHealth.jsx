import React, { useState, useCallback } from 'react'
import {
  Card, Input, Row, Col, Statistic, Table, Tag, Progress, Space,
  Typography, Button, Spin, Empty, Tooltip, Divider, Badge,
} from 'antd'
import {
  HeartOutlined, TrophyOutlined, SearchOutlined,
  ArrowUpOutlined, ArrowDownOutlined, MinusOutlined,
  ThunderboltOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { getStockHealth, getMarketHealthTop } from '../services/api'

const { Title, Text, Paragraph } = Typography

// 等级颜色映射
const GRADE_CONFIG = {
  'A+': { color: '#52c41a', bg: '#f6ffed', border: '#b7eb8f', label: '极优' },
  'A':  { color: '#52c41a', bg: '#f6ffed', border: '#b7eb8f', label: '优秀' },
  'B+': { color: '#1677ff', bg: '#e6f4ff', border: '#91caff', label: '良好' },
  'B':  { color: '#1677ff', bg: '#e6f4ff', border: '#91caff', label: '中等' },
  'C+': { color: '#faad14', bg: '#fffbe6', border: '#ffe58f', label: '偏弱' },
  'C':  { color: '#faad14', bg: '#fffbe6', border: '#ffe58f', label: '较弱' },
  'D':  { color: '#ff4d4f', bg: '#fff2f0', border: '#ffccc7', label: '风险' },
}

function getGrade(score) {
  if (score >= 90) return 'A+'
  if (score >= 80) return 'A'
  if (score >= 70) return 'B+'
  if (score >= 60) return 'B'
  if (score >= 50) return 'C+'
  if (score >= 40) return 'C'
  return 'D'
}

function getScoreColor(score) {
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#1677ff'
  if (score >= 40) return '#faad14'
  return '#ff4d4f'
}

// 维度中文名映射
const DIM_NAMES = {
  strategy: '策略信号',
  technical: '技术指标',
  money_flow: '资金流向',
  fundamental: '基本面',
  chip_risk: '筹码风险',
}

const DIM_ICONS = {
  strategy: '🎯',
  technical: '📈',
  money_flow: '💰',
  fundamental: '📊',
  chip_risk: '🎲',
}

/** 健康度圆环 */
function HealthRing({ score, size = 120 }) {
  const grade = getGrade(score)
  const config = GRADE_CONFIG[grade]
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      border: `4px solid ${config.color}`,
      background: config.bg,
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      boxShadow: `0 0 20px ${config.color}33`,
    }}>
      <div style={{ fontSize: size * 0.35, fontWeight: 700, color: config.color, lineHeight: 1 }}>
        {Math.round(score)}
      </div>
      <div style={{ fontSize: size * 0.15, color: config.color, marginTop: 2 }}>
        {grade} · {config.label}
      </div>
    </div>
  )
}

/** 维度评分条 */
function DimensionBar({ name, icon, score, max, details }) {
  const pct = max > 0 ? (score / max) * 100 : 0
  const color = pct >= 70 ? '#52c41a' : pct >= 40 ? '#1677ff' : '#ff4d4f'
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <Text strong>{icon} {name}</Text>
        <Text type="secondary">{score.toFixed(1)} / {max}</Text>
      </div>
      <Progress
        percent={pct}
        strokeColor={color}
        showInfo={false}
        size="small"
      />
    </div>
  )
}

/** 信号标签 */
function SignalTag({ type, text }) {
  const config = {
    bullish: { color: 'red', icon: <ArrowUpOutlined />, label: '看多' },
    bearish: { color: 'green', icon: <ArrowDownOutlined />, label: '看空' },
    neutral: { color: 'blue', icon: <MinusOutlined />, label: '中性' },
  }
  const c = config[type] || config.neutral
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <Tag color={c.color} icon={c.icon}>{c.label}</Tag>
      <Text>{text}</Text>
    </div>
  )
}

/**
 * 股票健康度评分仪表板
 * - 单股查询：输入股票代码，展示5维度健康度评分 + 信号列表
 * - 市场排名：TOP N 健康度股票
 */
export default function StockHealth({ tradeDate, onSelectStock }) {
  const [stockCode, setStockCode] = useState('')
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(false)
  const [topStocks, setTopStocks] = useState(null)
  const [loadingTop, setLoadingTop] = useState(false)
  const [error, setError] = useState(null)

  const handleSearch = useCallback(async () => {
    if (!stockCode.trim()) return
    setLoading(true)
    setError(null)
    setHealth(null)
    try {
      const res = await getStockHealth(stockCode.trim(), tradeDate)
      if (res?.success) {
        setHealth(res.data)
      } else {
        setError(res?.error || '查询失败')
      }
    } catch (err) {
      setError(err?.message || '查询失败，请检查股票代码')
    } finally {
      setLoading(false)
    }
  }, [stockCode, tradeDate])

  const handleLoadTop = useCallback(async () => {
    setLoadingTop(true)
    try {
      const res = await getMarketHealthTop({ trade_date: tradeDate, limit: 30 })
      if (res?.success) {
        setTopStocks(res.data)
      }
    } catch (err) {
      console.error('Load top health failed:', err)
    } finally {
      setLoadingTop(false)
    }
  }, [tradeDate])

  // TOP 股票表格列
  const topColumns = [
    {
      title: '排名',
      width: 60,
      render: (_, __, i) => <Badge count={i + 1} style={{ backgroundColor: i < 3 ? '#faad14' : '#d9d9d9' }} />,
    },
    {
      title: '代码',
      dataIndex: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '名称',
      dataIndex: 'stock_name',
      width: 100,
    },
    {
      title: '健康度',
      dataIndex: 'health_score',
      width: 120,
      sorter: (a, b) => a.health_score - b.health_score,
      defaultSortOrder: 'descend',
      render: (v) => {
        const grade = getGrade(v)
        const config = GRADE_CONFIG[grade]
        return (
          <Space>
            <Progress
              percent={v}
              size="small"
              strokeColor={config.color}
              format={() => `${v.toFixed(0)}分`}
              style={{ width: 80 }}
            />
            <Tag color={config.color}>{grade}</Tag>
          </Space>
        )
      },
    },
    {
      title: '策略',
      key: 'strategy',
      width: 80,
      render: (_, r) => {
        const s = r.dimensions?.strategy
        return s ? <Text type="secondary">{s.score.toFixed(0)}/{s.max}</Text> : '-'
      },
    },
    {
      title: '技术',
      key: 'technical',
      width: 80,
      render: (_, r) => {
        const s = r.dimensions?.technical
        return s ? <Text type="secondary">{s.score.toFixed(0)}/{s.max}</Text> : '-'
      },
    },
    {
      title: '资金',
      key: 'money_flow',
      width: 80,
      render: (_, r) => {
        const s = r.dimensions?.money_flow
        return s ? <Text type="secondary">{s.score.toFixed(0)}/{s.max}</Text> : '-'
      },
    },
    {
      title: '基本面',
      key: 'fundamental',
      width: 80,
      render: (_, r) => {
        const s = r.dimensions?.fundamental
        return s ? <Text type="secondary">{s.score.toFixed(0)}/{s.max}</Text> : '-'
      },
    },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      {/* 顶部查询区 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Space>
              <HeartOutlined style={{ fontSize: 20, color: '#ff4d4f' }} />
              <Title level={4} style={{ margin: 0 }}>🩺 股票健康度评分</Title>
              {tradeDate && <Tag>{tradeDate}</Tag>}
            </Space>
            <Paragraph type="secondary" style={{ margin: '4px 0 0', fontSize: 12 }}>
              聚合 5 个维度（策略信号 + 技术指标 + 资金流向 + 基本面 + 筹码风险）生成 0-100 综合健康度评分
            </Paragraph>
          </Col>
          <Col>
            <Space>
              <Input
                placeholder="输入股票代码，如 000001.SZ"
                value={stockCode}
                onChange={(e) => setStockCode(e.target.value)}
                onPressEnter={handleSearch}
                style={{ width: 260 }}
                prefix={<SearchOutlined />}
              />
              <Button type="primary" onClick={handleSearch} loading={loading}>
                查询
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        {/* 左侧：单股健康度详情 */}
        <Col xs={24} lg={14}>
          {loading && (
            <Card><div style={{ textAlign: 'center', padding: 60 }}><Spin tip="计算健康度中..." /></div></Card>
          )}
          {error && (
            <Card><Empty description={error} /></Card>
          )}
          {!loading && !error && !health && (
            <Card>
              <Empty
                image={<HeartOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
                description="输入股票代码查询健康度评分"
              />
            </Card>
          )}
          {health && (
            <>
              {/* 总分 + 等级 */}
              <Card style={{ marginBottom: 16 }}>
                <Row gutter={24} align="middle">
                  <Col>
                    <HealthRing score={health.health_score} size={130} />
                  </Col>
                  <Col flex="auto">
                    <Space direction="vertical" size={4}>
                      <Title level={3} style={{ margin: 0 }}>
                        {health.stock_name || health.ts_code}
                      </Title>
                      <Text type="secondary">{health.ts_code}</Text>
                      <Text type="secondary">交易日: {health.trade_date}</Text>
                    </Space>
                  </Col>
                </Row>
              </Card>

              {/* 5 维度评分 */}
              <Card title="📊 五维度评分" style={{ marginBottom: 16 }}>
                {Object.entries(health.dimensions || {}).map(([key, dim]) => (
                  <DimensionBar
                    key={key}
                    name={DIM_NAMES[key] || key}
                    icon={DIM_ICONS[key] || '📋'}
                    score={dim.score}
                    max={dim.max}
                    details={dim.details}
                  />
                ))}
              </Card>

              {/* 策略命中详情 */}
              {health.dimensions?.strategy?.details?.matched_strategies?.length > 0 && (
                <Card title="🎯 策略命中" style={{ marginBottom: 16 }}>
                  <Space wrap>
                    {health.dimensions.strategy.details.matched_strategies.map((s, i) => (
                      <Tag key={i} color={
                        s.category === 'value' ? 'blue' :
                        s.category === 'momentum' ? 'orange' :
                        s.category === 'flow' ? 'green' :
                        s.category === 'event' ? 'purple' : 'red'
                      }>
                        {s.strategy} (+{s.points})
                      </Tag>
                    ))}
                  </Space>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">
                      共命中 {health.dimensions.strategy.details.matched_count} 个策略，
                      得分 {health.dimensions.strategy.score}/{health.dimensions.strategy.max}
                    </Text>
                  </div>
                </Card>
              )}
            </>
          )}
        </Col>

        {/* 右侧：市场 TOP 排名 */}
        <Col xs={24} lg={10}>
          <Card
            title={<span><TrophyOutlined /> 市场健康度 TOP</span>}
            extra={
              <Button
                icon={<ReloadOutlined />}
                onClick={handleLoadTop}
                loading={loadingTop}
                size="small"
              >
                加载
              </Button>
            }
          >
            {loadingTop && (
              <div style={{ textAlign: 'center', padding: 40 }}><Spin tip="加载中..." /></div>
            )}
            {!loadingTop && !topStocks && (
              <Empty description="点击「加载」查看市场 TOP 健康度股票" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
            {topStocks && (
              <>
                <Row gutter={16} style={{ marginBottom: 16 }}>
                  <Col span={8}>
                    <Statistic title="分析股票" value={topStocks.total} suffix="只" />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="TOP 均分"
                      value={
                        topStocks.results?.length
                          ? (topStocks.results.reduce((s, r) => s + r.health_score, 0) / topStocks.results.length).toFixed(1)
                          : 0
                      }
                    />
                  </Col>
                  <Col span={8}>
                    <Statistic
                      title="最高分"
                      value={topStocks.results?.[0]?.health_score?.toFixed(1) || 0}
                      valueStyle={{ color: '#52c41a' }}
                    />
                  </Col>
                </Row>
                <Table
                  dataSource={topStocks.results || []}
                  columns={topColumns}
                  rowKey="ts_code"
                  size="small"
                  pagination={false}
                  scroll={{ y: 400 }}
                  onRow={(record) => ({
                    onClick: () => onSelectStock?.({ ts_code: record.ts_code, name: record.stock_name }),
                    style: { cursor: 'pointer' },
                  })}
                />
              </>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
