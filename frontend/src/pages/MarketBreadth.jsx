import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Row, Col, Statistic, Spin, Typography, Tag, Progress, Space, Tooltip,
} from 'antd'
import {
  ReloadOutlined, FireOutlined, RiseOutlined, FallOutlined,
  SwapOutlined, BarChartOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { getBreadthSnapshot, getTemperatureHistory } from '../services/api'

const { Text, Title } = Typography

const CARD_STYLE = { background: '#1f1f1f', border: '1px solid #303030', borderRadius: 8 }
const TEXT_DIM = { color: 'rgba(255,255,255,0.45)' }
const TEXT_NORMAL = { color: 'rgba(255,255,255,0.85)' }
const TEXT_SECONDARY = { color: 'rgba(255,255,255,0.65)' }

/**
 * 温度标签颜色映射
 */
function getTempColor(temp) {
  if (temp <= 20) return '#177ddc' // 极度恐惧 - 蓝
  if (temp <= 40) return '#13c2c2' // 恐惧 - 青
  if (temp <= 60) return '#d8bd14' // 中性 - 黄
  if (temp <= 80) return '#d48806' // 贪婪 - 橙
  return '#f5222d' // 极度贪婪 - 红
}

/**
 * 温度计仪表盘 — CSS 半圆弧实现
 */
function TemperatureGauge({ temperature, label }) {
  const color = getTempColor(temperature)
  // 半圆弧：用 conic-gradient 模拟
  const rotation = (temperature / 100) * 180 - 90 // -90 ~ 90

  return (
    <div style={{ textAlign: 'center', padding: '24px 0 8px' }}>
      <div style={{
        position: 'relative',
        width: 220,
        height: 120,
        margin: '0 auto',
        overflow: 'hidden',
      }}>
        {/* 背景弧 */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 200,
          height: 100,
          borderRadius: '100px 100px 0 0',
          background: 'conic-gradient(from 0.75turn, #177ddc, #13c2c2, #d8bd14, #d48806, #f5222d)',
          opacity: 0.3,
        }} />
        {/* 指针 */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: '50%',
          width: 3,
          height: 85,
          background: color,
          transformOrigin: 'bottom center',
          transform: `translateX(-50%) rotate(${rotation}deg)`,
          borderRadius: 2,
          transition: 'transform 0.8s ease-out',
          boxShadow: `0 0 8px ${color}80`,
        }} />
        {/* 中心圆点 */}
        <div style={{
          position: 'absolute',
          bottom: -6,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 12,
          height: 12,
          borderRadius: '50%',
          background: color,
          boxShadow: `0 0 10px ${color}80`,
        }} />
        {/* 刻度标签 */}
        <div style={{ position: 'absolute', bottom: 4, left: 8, ...TEXT_DIM, fontSize: 10 }}>0</div>
        <div style={{ position: 'absolute', bottom: 4, right: 8, ...TEXT_DIM, fontSize: 10 }}>100</div>
      </div>
      {/* 温度值 */}
      <div style={{ marginTop: 8 }}>
        <span style={{ fontSize: 42, fontWeight: 700, color, lineHeight: 1 }}>{temperature}</span>
      </div>
      <Tag color={color} style={{ marginTop: 4, fontSize: 14, padding: '2px 12px' }}>
        {label}
      </Tag>
    </div>
  )
}

/**
 * 分项评分小卡片
 */
function SubScoreCard({ icon, title, value, suffix, color }) {
  return (
    <Card size="small" style={{ ...CARD_STYLE, textAlign: 'center' }} bodyStyle={{ padding: '12px 8px' }}>
      <div style={{ fontSize: 20, marginBottom: 4, color: color || 'rgba(255,255,255,0.65)' }}>
        {icon}
      </div>
      <div style={{ ...TEXT_DIM, fontSize: 12, marginBottom: 4 }}>{title}</div>
      <div style={{ ...TEXT_NORMAL, fontSize: 20, fontWeight: 600 }}>
        {value}<span style={{ ...TEXT_DIM, fontSize: 12 }}>{suffix || ''}</span>
      </div>
    </Card>
  )
}

/**
 * 涨跌分布水平条形图
 */
function BreadthDistribution({ distribution }) {
  if (!distribution) return null
  const d = distribution.distribution || {}
  const total = distribution.total || 1

  const buckets = [
    { key: 'limit_up', label: '涨停', color: '#f5222d' },
    { key: 'up_5_9', label: '5~9%', color: '#ff4d4f' },
    { key: 'up_3_5', label: '3~5%', color: '#ff7a45' },
    { key: 'up_1_3', label: '1~3%', color: '#ffa940' },
    { key: 'up_0_1', label: '0~1%', color: '#ffc53d' },
    { key: 'flat', label: '平盘', color: '#8c8c8c' },
    { key: 'down_0_1', label: '0~1%', color: '#a0d911' },
    { key: 'down_1_3', label: '1~3%', color: '#52c41a' },
    { key: 'down_3_5', label: '3~5%', color: '#389e0d' },
    { key: 'down_5_9', label: '5~9%', color: '#237804' },
    { key: 'limit_down', label: '跌停', color: '#135200' },
  ]

  const maxVal = Math.max(...buckets.map(b => d[b.key] || 0), 1)
  const advance = distribution.advance || 0
  const decline = distribution.decline || 0
  const ratio = decline > 0 ? (advance / decline).toFixed(2) : '∞'

  return (
    <Card title="涨跌分布" size="small" style={CARD_STYLE}
      extra={<Tag color={advance > decline ? 'green' : advance < decline ? 'red' : 'default'}>
        A/D {ratio}
      </Tag>}
    >
      <Row gutter={[8, 6]}>
        {buckets.map(b => {
          const val = d[b.key] || 0
          const pct = (val / total * 100).toFixed(1)
          const barWidth = (val / maxVal * 100)
          return (
            <React.Fragment key={b.key}>
              <Col span={5} style={{ textAlign: 'right', ...TEXT_DIM, fontSize: 12, lineHeight: '22px' }}>
                {b.label}
              </Col>
              <Col span={17}>
                <div style={{
                  height: 18,
                  background: '#262626',
                  borderRadius: 3,
                  overflow: 'hidden',
                  position: 'relative',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${barWidth}%`,
                    background: b.color,
                    borderRadius: 3,
                    transition: 'width 0.6s ease-out',
                    minWidth: val > 0 ? 2 : 0,
                  }} />
                </div>
              </Col>
              <Col span={2} style={{ ...TEXT_SECONDARY, fontSize: 12, lineHeight: '22px' }}>
                {val}
              </Col>
            </React.Fragment>
          )
        })}
      </Row>
      {/* 涨跌汇总条 */}
      <div style={{ marginTop: 12, display: 'flex', height: 24, borderRadius: 4, overflow: 'hidden' }}>
        <div style={{
          width: `${advance / total * 100}%`,
          background: '#f5222d',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          ...TEXT_DIM, fontSize: 11,
        }}>
          上涨 {advance}
        </div>
        <div style={{
          width: `${(distribution.unchanged || 0) / total * 100}%`,
          background: '#434343',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          ...TEXT_DIM, fontSize: 11,
        }}>
          {(distribution.unchanged || 0) > 0 ? distribution.unchanged : ''}
        </div>
        <div style={{
          width: `${decline / total * 100}%`,
          background: '#135200',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          ...TEXT_DIM, fontSize: 11,
        }}>
          下跌 {decline}
        </div>
      </div>
    </Card>
  )
}

/**
 * 涨跌停统计卡片
 */
function LimitStatsCard({ limitStats }) {
  if (!limitStats) return null
  const items = [
    { label: '涨停', value: limitStats.limit_up_count, color: '#f5222d', icon: <ThunderboltOutlined /> },
    { label: '跌停', value: limitStats.limit_down_count, color: '#52c41a', icon: <FallOutlined /> },
    { label: '封板率', value: `${((limitStats.seal_ratio || 0) * 100).toFixed(1)}%`, color: '#faad14' },
    { label: '连板数', value: limitStats.consecutive_up_count || 0, color: '#722ed1' },
  ]

  return (
    <Card title="涨跌停统计" size="small" style={CARD_STYLE}
      extra={<Tag color="orange">{limitStats.open_limit_up_count || 0} 开板</Tag>}
    >
      <Row gutter={[12, 12]}>
        {items.map((item, i) => (
          <Col span={12} key={i}>
            <div style={{ textAlign: 'center', padding: '8px 0' }}>
              <div style={{ ...TEXT_DIM, fontSize: 12, marginBottom: 4 }}>{item.label}</div>
              <div style={{ fontSize: 28, fontWeight: 700, color: item.color }}>
                {item.value}
              </div>
            </div>
          </Col>
        ))}
      </Row>
    </Card>
  )
}

/**
 * 均线突破统计
 */
function MABreakoutCard({ maBreakout }) {
  if (!maBreakout) return null
  const ratio = ((maBreakout.above_ratio || 0) * 100).toFixed(1)
  const above = maBreakout.above_boll_mid || 0
  const total = maBreakout.total_with_boll || 0

  let status = 'normal'
  let strokeColor = '#1677ff'
  if (ratio >= 70) { status = 'success'; strokeColor = '#52c41a' }
  else if (ratio <= 30) { status = 'exception'; strokeColor = '#f5222d' }

  return (
    <Card title="均线突破" size="small" style={CARD_STYLE}
      extra={<Text style={TEXT_DIM}>布林中轨</Text>}
    >
      <div style={{ textAlign: 'center', padding: '12px 0' }}>
        <Progress
          type="dashboard"
          percent={Number(ratio)}
          strokeColor={strokeColor}
          trailColor="#262626"
          format={p => <span style={{ ...TEXT_NORMAL, fontSize: 20, fontWeight: 600 }}>{p}%</span>}
          size={140}
        />
        <div style={{ ...TEXT_SECONDARY, fontSize: 12, marginTop: 8 }}>
          {above}/{total} 只个股站上布林中轨
        </div>
      </div>
    </Card>
  )
}

/**
 * 换手率分布
 */
function TurnoverDistribution({ turnover }) {
  if (!turnover) return null

  const tiers = [
    { key: 'high_turnover', label: '高换手', color: '#f5222d', desc: '换手率 > 10%' },
    { key: 'mid_turnover', label: '中换手', color: '#faad14', desc: '5% ~ 10%' },
    { key: 'normal_turnover', label: '正常', color: '#1677ff', desc: '1% ~ 5%' },
    { key: 'low_turnover', label: '低换手', color: '#8c8c8c', desc: '< 1%' },
  ]
  const total = turnover.total || 1

  return (
    <Card title="换手率分布" size="small" style={CARD_STYLE}
      extra={<Text style={TEXT_DIM}>均值 {((turnover.avg_turnover_rate || 0) * 100).toFixed(2)}%</Text>}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {tiers.map(t => {
          const val = turnover[t.key] || 0
          const pct = (val / total * 100)
          return (
            <div key={t.key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text style={{ ...TEXT_SECONDARY, fontSize: 12 }}>{t.label}</Text>
                <Text style={{ ...TEXT_DIM, fontSize: 12 }}>{val} 只 ({pct.toFixed(1)}%)</Text>
              </div>
              <Progress
                percent={pct}
                strokeColor={t.color}
                trailColor="#262626"
                showInfo={false}
                size="small"
              />
            </div>
          )
        })}
      </div>
    </Card>
  )
}

/**
 * 近10日涨跌家数堆叠柱状图 (纯 CSS)
 */
function AdvanceDeclineChart({ history }) {
  if (!history || history.length === 0) return null

  const maxVal = Math.max(...history.map(h => (h.advance || 0) + (h.decline || 0) + (h.unchanged || 0)), 1)

  return (
    <Card title="近10日涨跌家数" size="small" style={CARD_STYLE}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 160, padding: '0 4px' }}>
        {history.map((h, i) => {
          const adv = h.advance || 0
          const dec = h.decline || 0
          const unch = h.unchanged || 0
          const total = adv + dec + unch
          const advH = (adv / maxVal) * 140
          const unchH = (unch / maxVal) * 140
          const decH = (dec / maxVal) * 140
          const dateLabel = h.trade_date ? String(h.trade_date).slice(4, 8) : ''

          return (
            <Tooltip key={i} title={`${h.trade_date}: 涨${adv} 平${unch} 跌${dec}`}>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column', width: '100%', maxWidth: 32 }}>
                  <div style={{ height: advH, background: '#f5222d', borderRadius: '2px 2px 0 0', minHeight: adv > 0 ? 2 : 0 }} />
                  <div style={{ height: unchH, background: '#434343', minHeight: unch > 0 ? 2 : 0 }} />
                  <div style={{ height: decH, background: '#52c41a', borderRadius: '0 0 2px 2px', minHeight: dec > 0 ? 2 : 0 }} />
                </div>
                <div style={{ ...TEXT_DIM, fontSize: 10, marginTop: 4, whiteSpace: 'nowrap' }}>{dateLabel}</div>
              </div>
            </Tooltip>
          )
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8 }}>
        <span style={{ fontSize: 11 }}><span style={{ display: 'inline-block', width: 8, height: 8, background: '#f5222d', borderRadius: 2, marginRight: 4 }} /><Text style={TEXT_DIM}>上涨</Text></span>
        <span style={{ fontSize: 11 }}><span style={{ display: 'inline-block', width: 8, height: 8, background: '#434343', borderRadius: 2, marginRight: 4 }} /><Text style={TEXT_DIM}>平盘</Text></span>
        <span style={{ fontSize: 11 }}><span style={{ display: 'inline-block', width: 8, height: 8, background: '#52c41a', borderRadius: 2, marginRight: 4 }} /><Text style={TEXT_DIM}>下跌</Text></span>
      </div>
    </Card>
  )
}

/**
 * 市场温度趋势折线图 (纯 CSS)
 */
function TemperatureTrend({ history }) {
  if (!history || history.length === 0) return null

  const temps = history.map(h => h.temperature || 50)
  const minT = Math.min(...temps, 0)
  const maxT = Math.max(...temps, 100)
  const range = maxT - minT || 1

  return (
    <Card title="市场温度趋势" size="small" style={CARD_STYLE}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 120, padding: '0 4px' }}>
        {temps.map((t, i) => {
          const h = ((t - minT) / range) * 100 + 10
          const color = getTempColor(t)
          const dateLabel = history[i]?.trade_date ? String(history[i].trade_date).slice(4, 8) : ''

          return (
            <Tooltip key={i} title={`${history[i]?.trade_date}: ${t} (${history[i]?.label || ''})`}>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <Text style={{ ...TEXT_DIM, fontSize: 9, marginBottom: 2 }}>{t}</Text>
                <div style={{
                  width: '100%',
                  maxWidth: 28,
                  height: h,
                  background: `linear-gradient(to top, ${color}40, ${color})`,
                  borderRadius: '3px 3px 0 0',
                  transition: 'height 0.5s ease-out',
                }} />
                <div style={{ ...TEXT_DIM, fontSize: 9, marginTop: 2, whiteSpace: 'nowrap' }}>{dateLabel}</div>
              </div>
            </Tooltip>
          )
        })}
      </div>
    </Card>
  )
}

/**
 * 市场宽度指标仪表板
 */
export default function MarketBreadth({ tradeDate }) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [tempHistory, setTempHistory] = useState([])

  const fetchData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const [breadthRes, tempRes] = await Promise.all([
        getBreadthSnapshot(tradeDate, { signal }),
        getTemperatureHistory(10, { signal }),
      ])
      if (breadthRes?.success !== false) setData(breadthRes)
      if (Array.isArray(tempRes)) setTempHistory(tempRes)
      else if (tempRes?.data) setTempHistory(tempRes.data)
    } catch (err) {
      if (err?.code !== 'ERR_CANCELED' && err?.name !== 'CanceledError') {
        console.error('Market breadth failed:', err)
      }
    } finally {
      setLoading(false)
    }
  }, [tradeDate])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(controller.signal)
    return () => controller.abort()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading && !data) {
    return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" tip="加载市场宽度数据..." /></div>
  }

  if (!data || data.error) {
    return (
      <Card style={CARD_STYLE}>
        <div style={{ textAlign: 'center', padding: 40, color: 'rgba(255,255,255,0.45)' }}>
          {data?.error || '暂无市场宽度数据'}
        </div>
      </Card>
    )
  }

  const temp = data.market_temperature || {}
  const breadth = data.breadth_distribution || {}
  const limitStats = data.limit_stats || {}
  const maBreakout = data.ma_breakout || {}
  const turnover = data.turnover_distribution || {}
  const adHistory = data.advance_decline_history || []

  // 计算分项指标值
  const adRatio = breadth.advance_decline_ratio || 0
  const sealRatio = ((limitStats.seal_ratio || 0) * 100).toFixed(1)
  const limitDownCount = limitStats.limit_down_count || 0
  const maRatio = ((maBreakout.above_ratio || 0) * 100).toFixed(1)
  const avgTurnover = ((turnover.avg_turnover_rate || 0) * 100).toFixed(2)

  return (
    <div>
      {/* 第一行：温度计 + 分项评分 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card style={CARD_STYLE} bodyStyle={{ padding: '16px 24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <Text style={TEXT_NORMAL}>市场温度</Text>
              <Text style={TEXT_DIM}>{data.trade_date}</Text>
            </div>
            <TemperatureGauge temperature={temp.temperature || 50} label={temp.label || '中性'} />
            {/* 温度分项 */}
            {temp.components && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center', marginTop: 4 }}>
                {Object.entries(temp.components).map(([k, v]) => (
                  <Tooltip key={k} title={k}>
                    <Tag style={{ margin: 0, background: '#262626', border: '1px solid #303030', color: 'rgba(255,255,255,0.65)' }}>
                      {k}: {typeof v === 'number' ? v.toFixed(1) : v}
                    </Tag>
                  </Tooltip>
                ))}
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Row gutter={[12, 12]}>
            <Col xs={12} sm={8} lg={4}>
              <SubScoreCard icon={<SwapOutlined />} title="涨跌比" value={adRatio.toFixed(2)} suffix="x" color={adRatio > 1 ? '#52c41a' : '#f5222d'} />
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <SubScoreCard icon={<ThunderboltOutlined />} title="涨停率" value={sealRatio} suffix="%" color="#f5222d" />
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <SubScoreCard icon={<FallOutlined />} title="跌停数" value={limitDownCount} color="#52c41a" />
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <SubScoreCard icon={<RiseOutlined />} title="均线突破" value={maRatio} suffix="%" color="#1677ff" />
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <SubScoreCard icon={<BarChartOutlined />} title="换手活跃" value={avgTurnover} suffix="%" color="#faad14" />
            </Col>
          </Row>
        </Col>
      </Row>

      {/* 第二行：涨跌分布 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <BreadthDistribution distribution={breadth} />
        </Col>
      </Row>

      {/* 第三行：涨跌停 + 均线突破 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <LimitStatsCard limitStats={limitStats} />
        </Col>
        <Col xs={24} md={12}>
          <MABreakoutCard maBreakout={maBreakout} />
        </Col>
      </Row>

      {/* 第四行：历史涨跌 + 温度趋势 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={14}>
          <AdvanceDeclineChart history={adHistory} />
        </Col>
        <Col xs={24} md={10}>
          <TemperatureTrend history={tempHistory} />
        </Col>
      </Row>

      {/* 第五行：换手率分布 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={10}>
          <TurnoverDistribution turnover={turnover} />
        </Col>
      </Row>
    </div>
  )
}
