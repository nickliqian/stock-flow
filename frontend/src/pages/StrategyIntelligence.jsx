import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Row, Col, Statistic, Space, Spin, Empty, Select, Tag, Tooltip,
  Typography, Progress, Badge, Button, Radio, Table, Divider, Alert, message,
} from 'antd'
import {
  ThunderboltOutlined, TrophyOutlined, LineChartOutlined, SwapOutlined,
  AimOutlined, FireOutlined, ArrowUpOutlined, ArrowDownOutlined, MinusOutlined,
  BulbOutlined, StarOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { getStrategyHealth, getStrategyTrend, compareStrategies, getStrategyRecommendation } from '../services/api'

const { Text, Title } = Typography

const CATEGORY_MAP = {
  value: { label: '价值', color: '#1890ff' },
  momentum: { label: '动量', color: '#fa8c16' },
  flow: { label: '资金', color: '#52c41a' },
  event: { label: '事件', color: '#722ed1' },
  combo: { label: '组合', color: '#f5222d' },
}

function healthColor(score) {
  if (score >= 70) return '#52c41a'
  if (score >= 40) return '#faad14'
  return '#d9d9d9'
}

function retTag(val) {
  if (val == null) return <Tag>--</Tag>
  if (val > 0) return <Tag color="success"><ArrowUpOutlined /> {val}%</Tag>
  if (val < 0) return <Tag color="error"><ArrowDownOutlined /> {val}%</Tag>
  return <Tag color="default"><MinusOutlined /> 0%</Tag>
}

/** Strategy Health Card */
function HealthCard({ data, onClick }) {
  const cat = CATEGORY_MAP[data.category] || { label: data.category, color: '#999' }
  return (
    <Card
      hoverable
      style={{ height: '100%', borderLeft: `3px solid ${healthColor(data.health_score)}` }}
      onClick={() => onClick?.(data.name)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Space>
            <span style={{ fontSize: 24 }}>{data.icon}</span>
            <Text strong>{data.description}</Text>
          </Space>
          <div style={{ marginTop: 4 }}>
            <Tag color={cat.color}>{cat.label}</Tag>
            {!data.data_available && <Tag color="default">暂无数据</Tag>}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <Progress
            type="dashboard"
            percent={data.health_score}
            size={64}
            strokeColor={healthColor(data.health_score)}
            format={(pct) => <span style={{ fontSize: 12 }}>{pct}</span>}
          />
        </div>
      </div>
      {data.data_available && (
        <Row gutter={8} style={{ marginTop: 12 }}>
          <Col span={8}>
            <Statistic title="1日胜率" value={data.win_rate_1d} suffix="%" valueStyle={{ fontSize: 14, color: data.win_rate_1d > 50 ? '#52c41a' : '#f5222d' }} />
          </Col>
          <Col span={8}>
            <Statistic title="3日胜率" value={data.win_rate_3d} suffix="%" valueStyle={{ fontSize: 14 }} />
          </Col>
          <Col span={8}>
            <Statistic title="平均收益" value={data.avg_ret_1d} suffix="%" valueStyle={{ fontSize: 14, color: data.avg_ret_1d > 0 ? '#52c41a' : '#f5222d' }} />
          </Col>
        </Row>
      )}
      {data.data_available && (
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            近{data.snapshot_count}个交易日 · 日均{data.avg_picks_per_day}只 · 共跟踪{data.total_tracked}只
          </Text>
        </div>
      )}
    </Card>
  )
}

/** Strategy Trend Chart */
function TrendChart({ strategyName }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!strategyName) return
    const controller = new AbortController()
    setLoading(true)
    getStrategyTrend(strategyName, 30, { signal: controller.signal })
      .then((res) => { if (res?.success) setData(res.data) })
      .catch((err) => {
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        message.error('趋势数据加载失败')
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [strategyName])

  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  if (!data || !data.trend || data.trend.length === 0) {
    return <Empty description="暂无趋势数据" />
  }

  const dates = data.trend.map(t => t.trade_date)
  const winRates = data.trend.map(t => t.win_rate_1d)
  const avgReturns = data.trend.map(t => t.avg_return_1d)
  const pickCounts = data.trend.map(t => t.pick_count)

  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['1日胜率', '平均收益(%)', '选股数量'], top: 0 },
    grid: { top: 40, bottom: 30, left: 50, right: 50 },
    xAxis: { type: 'category', data: dates, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '胜率/收益(%)', position: 'left' },
      { type: 'value', name: '数量', position: 'right' },
    ],
    series: [
      { name: '1日胜率', type: 'line', data: winRates, smooth: true, itemStyle: { color: '#52c41a' } },
      { name: '平均收益(%)', type: 'line', data: avgReturns, smooth: true, itemStyle: { color: '#1890ff' } },
      { name: '选股数量', type: 'bar', yAxisIndex: 1, data: pickCounts, itemStyle: { color: '#d9d9d9' } },
    ],
  }

  return <ReactECharts option={option} style={{ height: 320 }} />
}

/** Strategy Comparison View */
function ComparisonView({ strategies }) {
  const [selected, setSelected] = useState([])
  const [compData, setCompData] = useState(null)
  const [loading, setLoading] = useState(false)

  const doCompare = useCallback(async () => {
    if (selected.length < 2) {
      message.warning('请至少选择2个策略')
      return
    }
    setLoading(true)
    try {
      const res = await compareStrategies(selected, 20)
      if (res?.success) setCompData(res.data)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      message.error('对比失败')
    } finally {
      setLoading(false)
    }
  }, [selected])

  const columns = [
    { title: '策略', dataIndex: 'icon', width: 50, render: (v) => <span style={{ fontSize: 20 }}>{v}</span> },
    { title: '名称', dataIndex: 'description', width: 140 },
    { title: '类别', dataIndex: 'category', width: 80, render: (v) => <Tag color={CATEGORY_MAP[v]?.color}>{CATEGORY_MAP[v]?.label || v}</Tag> },
    { title: '跟踪数', dataIndex: 'total_tracked', width: 80, sorter: (a, b) => a.total_tracked - b.total_tracked },
    { title: '1日胜率', dataIndex: 'win_rate_1d', width: 100, sorter: (a, b) => a.win_rate_1d - b.win_rate_1d,
      render: (v) => <span style={{ color: v > 50 ? '#52c41a' : v > 0 ? '#f5222d' : '#999' }}>{v}%</span> },
    { title: '3日胜率', dataIndex: 'win_rate_3d', width: 100, sorter: (a, b) => a.win_rate_3d - b.win_rate_3d,
      render: (v) => <span>{v}%</span> },
    { title: '5日胜率', dataIndex: 'win_rate_5d', width: 100, sorter: (a, b) => a.win_rate_5d - b.win_rate_5d,
      render: (v) => <span>{v}%</span> },
    { title: '1日平均收益', dataIndex: 'avg_ret_1d', width: 110, sorter: (a, b) => a.avg_ret_1d - b.avg_ret_1d,
      render: (v) => retTag(v) },
    { title: '日均选股', dataIndex: 'avg_picks_per_day', width: 90, render: (v) => <span>{v}只</span> },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Select
          mode="multiple"
          placeholder="选择要对比的策略（至少2个）"
          style={{ minWidth: 400 }}
          value={selected}
          onChange={setSelected}
          options={strategies.map(s => ({ label: `${s.icon} ${s.description}`, value: s.name }))}
        />
        <Button type="primary" icon={<SwapOutlined />} onClick={doCompare} loading={loading} disabled={selected.length < 2}>
          开始对比
        </Button>
      </Space>
      {compData && (
        <Table
          columns={columns}
          dataSource={compData.strategies?.map((s, i) => ({ ...s, key: s.name + i }))}
          pagination={false}
          size="small"
          scroll={{ x: 1000 }}
        />
      )}
    </div>
  )
}

/** Recommendation Banner */
function RecommendationBanner() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    getStrategyRecommendation({ signal: controller.signal })
      .then((res) => { if (res?.success) setData(res.data) })
      .catch(() => {})
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  if (loading) return <Spin />
  if (!data) return null

  const rec = data.recommendation
  if (!rec) {
    return (
      <Alert
        type="info"
        icon={<BulbOutlined />}
        message="策略推荐"
        description={data.message || '暂无足够数据'}
        style={{ marginBottom: 16 }}
      />
    )
  }

  return (
    <Alert
      type="success"
      icon={<TrophyOutlined />}
      message={
        <Space>
          <span>今日推荐策略：</span>
          <Tag color="gold" style={{ fontSize: 14 }}>
            {rec.icon} {rec.description}
          </Tag>
          <Text type="secondary">信任度 {rec.trust_score}分</Text>
        </Space>
      }
      description={rec.reason}
      style={{ marginBottom: 16 }}
      showIcon
    />
  )
}

/** Main Page */
export default function StrategyIntelligence() {
  const [healthData, setHealthData] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedStrategy, setSelectedStrategy] = useState(null)
  const [view, setView] = useState('health')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    getStrategyHealth(20, { signal: controller.signal })
      .then((res) => {
        if (res?.success && res.data) {
          setHealthData(res.data)
        }
      })
      .catch((err) => {
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        message.error('策略健康数据加载失败')
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  return (
    <div>
      <RecommendationBanner />

      <Space style={{ marginBottom: 16 }}>
        <Radio.Group value={view} onChange={(e) => setView(e.target.value)}>
          <Radio.Button value="health">🩺 策略健康度</Radio.Button>
          <Radio.Button value="trend">📈 胜率趋势</Radio.Button>
          <Radio.Button value="compare">🔄 策略对比</Radio.Button>
        </Radio.Group>
      </Space>

      {view === 'health' && (
        <Spin spinning={loading}>
          <Row gutter={[16, 16]}>
            {healthData.map((s) => (
              <Col xs={24} sm={12} md={8} lg={6} key={s.name}>
                <HealthCard data={s} onClick={(name) => { setSelectedStrategy(name); setView('trend') }} />
              </Col>
            ))}
          </Row>
          {healthData.length === 0 && !loading && <Empty description="暂无策略数据，请先执行策略积累表现数据" />}
        </Spin>
      )}

      {view === 'trend' && (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Text>选择策略：</Text>
            <Select
              style={{ width: 240 }}
              placeholder="选择策略查看趋势"
              value={selectedStrategy}
              onChange={setSelectedStrategy}
              options={healthData.map(s => ({ label: `${s.icon} ${s.description}`, value: s.name }))}
            />
          </Space>
          {selectedStrategy ? (
            <TrendChart strategyName={selectedStrategy} />
          ) : (
            <Empty description="请选择一个策略查看趋势" />
          )}
        </div>
      )}

      {view === 'compare' && (
        <ComparisonView strategies={healthData} />
      )}
    </div>
  )
}
