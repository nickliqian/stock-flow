import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Card, Row, Col, Statistic, Table, Tag, Spin, Typography, Button,
  Segmented, Space, Drawer, Divider, Empty, Badge, Progress, Tooltip,
  Collapse,
} from 'antd'
import {
  ReloadOutlined, TrophyOutlined, RocketOutlined, FireOutlined,
  RiseOutlined, FallOutlined, WarningOutlined, BulbOutlined,
  StarOutlined, EyeOutlined, ShoppingCartOutlined,
} from '@ant-design/icons'
import { apiCall } from '../services/api'
import { formatAmount, scoreColor as baseScoreColor } from '../utils/format'

const { Text, Title, Paragraph } = Typography
const { Panel } = Collapse

// ---------------------------------------------------------------------------
// 常量
// ---------------------------------------------------------------------------
const LEVEL_CONFIG = {
  STRONG_BUY: { color: '#52c41a', label: '强推', icon: '🔥' },
  BUY: { color: '#1890ff', label: '推荐', icon: '👍' },
  HOLD: { color: '#faad14', label: '观望', icon: '👁️' },
  REDUCE: { color: '#fa8c16', label: '减仓', icon: '⚠️' },
  AVOID: { color: '#f5222d', label: '回避', icon: '🚫' },
}

const LEVEL_ORDER = ['STRONG_BUY', 'BUY', 'HOLD', 'REDUCE', 'AVOID']

const DIM_KEYS = [
  'strategy_signal', 'flow_intelligence', 'technical_momentum',
  'fundamental_value', 'insider_conviction', 'crowding_risk', 'market_regime_fit',
]

const DIM_COLORS = {
  strategy_signal: '#1890ff',
  flow_intelligence: '#52c41a',
  technical_momentum: '#722ed1',
  fundamental_value: '#faad14',
  insider_conviction: '#13c2c2',
  crowding_risk: '#f5222d',
  market_regime_fit: '#eb2f96',
}

const DIM_LABELS = {
  strategy_signal: '策略信号',
  flow_intelligence: '资金智慧',
  technical_momentum: '技术动量',
  fundamental_value: '基本面',
  insider_conviction: '内部人',
  crowding_risk: '拥挤度',
  market_regime_fit: '市场适配',
}

const DIM_ICONS = {
  strategy_signal: '🎯',
  flow_intelligence: '💰',
  technical_momentum: '📈',
  fundamental_value: '💎',
  insider_conviction: '🕵️',
  crowding_risk: '👥',
  market_regime_fit: '🌍',
}

// ---------------------------------------------------------------------------
// 工具函数
// ---------------------------------------------------------------------------

/**
 * 推荐评分颜色（5 级比 format.jsx 中的 3 级更精细，专用于推荐系统）
 * 注意：format.jsx 也有 scoreColor（3 级：≥75 绿 / ≥50 黄 / 其他灰），
 *       此处保留本地版本以提供更细致的颜色分级。
 */
function recommendationScoreColor(score) {
  if (score >= 70) return '#52c41a'
  if (score >= 55) return '#1890ff'
  if (score >= 40) return '#faad14'
  if (score >= 25) return '#fa8c16'
  return '#f5222d'
}

/* =====================================================================
 * 推荐雷达图（纯 CSS/SVG 实现七维蜘蛛图）
 * ===================================================================== */
function RadarChart({ dimensions, size = 220 }) {
  if (!dimensions || Object.keys(dimensions).length === 0) return null

  const cx = size / 2
  const cy = size / 2
  const maxR = size / 2 - 24
  const n = DIM_KEYS.length
  const angleStep = (2 * Math.PI) / n

  // 生成网格线
  const gridLevels = [25, 50, 75, 100]
  const gridPaths = gridLevels.map((level) => {
    const r = (level / 100) * maxR
    const points = DIM_KEYS.map((_, i) => {
      const angle = i * angleStep - Math.PI / 2
      return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`
    }).join(' ')
    return points
  })

  // 生成坐标轴标签
  const labels = DIM_KEYS.map((key, i) => {
    const angle = i * angleStep - Math.PI / 2
    const labelR = maxR + 16
    const x = cx + labelR * Math.cos(angle)
    const y = cy + labelR * Math.sin(angle)
    const dim = dimensions[key]
    return { x, y, label: dim?.icon || '', key }
  })

  // 生成数据多边形
  const dataPoints = DIM_KEYS.map((key, i) => {
    const score = dimensions[key]?.score || 0
    const r = (score / 100) * maxR
    const angle = i * angleStep - Math.PI / 2
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`
  }).join(' ')

  // 数据点
  const dataDots = DIM_KEYS.map((key, i) => {
    const score = dimensions[key]?.score || 0
    const r = (score / 100) * maxR
    const angle = i * angleStep - Math.PI / 2
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle), key, score }
  })

  return (
    <svg width={size} height={size} style={{ display: 'block', margin: '0 auto' }}>
      {/* 网格 */}
      {gridPaths.map((pts, idx) => (
        <polygon
          key={idx}
          points={pts}
          fill="none"
          stroke="rgba(255,255,255,0.1)"
          strokeWidth={1}
        />
      ))}
      {/* 坐标轴线 */}
      {DIM_KEYS.map((_, i) => {
        const angle = i * angleStep - Math.PI / 2
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={cx + maxR * Math.cos(angle)}
            y2={cy + maxR * Math.sin(angle)}
            stroke="rgba(255,255,255,0.08)"
            strokeWidth={1}
          />
        )
      })}
      {/* 数据多边形 */}
      <polygon
        points={dataPoints}
        fill="rgba(24,144,255,0.2)"
        stroke="#1890ff"
        strokeWidth={2}
      />
      {/* 数据点 */}
      {dataDots.map((d, i) => (
        <circle
          key={i}
          cx={d.x}
          cy={d.y}
          r={4}
          fill={DIM_COLORS[d.key]}
          stroke="#fff"
          strokeWidth={1}
        />
      ))}
      {/* 标签 */}
      {labels.map((l, i) => (
        <text
          key={i}
          x={l.x}
          y={l.y}
          textAnchor="middle"
          dominantBaseline="central"
          fill="rgba(255,255,255,0.6)"
          fontSize={14}
        >
          {l.label}
        </text>
      ))}
    </svg>
  )
}

/* =====================================================================
 * 维度得分横向条形图（用于展开行）
 * ===================================================================== */
function DimensionBars({ dimensions }) {
  if (!dimensions) return null
  return (
    <div style={{ padding: '8px 0' }}>
      <Row gutter={[16, 8]}>
        {DIM_KEYS.map((key) => {
          const dim = dimensions[key]
          if (!dim) return null
          const color = DIM_COLORS[key] || '#1890ff'
          return (
            <Col xs={24} sm={12} md={8} key={key}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text style={{ fontSize: 12, width: 80, flexShrink: 0 }}>
                  {dim.icon} {dim.label}
                </Text>
                <div style={{ flex: 1, height: 16, background: '#1f1f1f', borderRadius: 4, overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      width: `${dim.score}%`,
                      background: color,
                      borderRadius: 4,
                      transition: 'width 0.3s',
                      display: 'flex',
                      alignItems: 'center',
                      paddingLeft: 6,
                    }}
                  >
                    <Text style={{ color: '#fff', fontSize: 10, fontWeight: 600 }}>
                      {dim.score}
                    </Text>
                  </div>
                </div>
                <Text type="secondary" style={{ fontSize: 10, width: 60, flexShrink: 0 }}>
                  {dim.detail}
                </Text>
              </div>
            </Col>
          )
        })}
      </Row>
    </div>
  )
}

/* =====================================================================
 * 综合评分圆形指示器
 * ===================================================================== */
function ScoreCircle({ score, size = 80 }) {
  const color = recommendationScoreColor(score)
  const radius = (size - 8) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - score / 100)

  return (
    <div style={{ width: size, height: size, position: 'relative', flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={4}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={4}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
        />
      </svg>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Text style={{ fontSize: size > 60 ? 20 : 14, fontWeight: 'bold', color, lineHeight: 1 }}>
          {score}
        </Text>
      </div>
    </div>
  )
}

/* =====================================================================
 * 单股详情面板
 * ===================================================================== */
function StockDetail({ data }) {
  if (!data) return <Empty description="无数据" />

  const levelCfg = LEVEL_CONFIG[data.recommendation] || LEVEL_CONFIG.HOLD

  return (
    <div>
      {/* 股票头部：代码 + 名称 + 评分圆环 */}
      <Card size="small" style={{ marginBottom: 16, borderColor: levelCfg.color + '60' }}>
        <Row gutter={16} align="middle">
          <Col>
            <ScoreCircle score={data.composite_score} size={80} />
          </Col>
          <Col flex="auto">
            <Title level={4} style={{ margin: 0 }}>{data.name}</Title>
            <Text type="secondary" style={{ fontSize: 13 }}>{data.ts_code}</Text>
            <div style={{ marginTop: 6 }}>
              <Tag color={levelCfg.color} style={{ margin: 0 }}>
                {levelCfg.icon} {data.recommendation_cn}
              </Tag>
            </div>
          </Col>
          <Col>
            <div style={{ textAlign: 'center' }}>
              <Text type="secondary" style={{ fontSize: 11 }}>策略命中</Text>
              <div style={{ fontSize: 20, fontWeight: 'bold', color: '#1890ff' }}>{data.strategies_hit}</div>
            </div>
          </Col>
        </Row>
      </Card>

      {/* 七维雷达图 */}
      <Card title="📊 七维评分雷达" size="small" style={{ marginBottom: 16 }}>
        <div style={{ background: '#141414', borderRadius: 8, padding: 16 }}>
          <RadarChart dimensions={data.dimensions} size={260} />
        </div>
      </Card>

      {/* 维度得分条（大尺寸） */}
      <Card title="📈 维度得分" size="small" style={{ marginBottom: 16 }}>
        <div style={{ padding: '4px 0' }}>
          {DIM_KEYS.map((key) => {
            const dim = data.dimensions?.[key]
            if (!dim) return null
            const color = DIM_COLORS[key] || '#1890ff'
            return (
              <div key={key} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Text strong style={{ fontSize: 13 }}>
                    {DIM_ICONS[key]} {dim.label || DIM_LABELS[key]}
                    <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>
                      权重 {(dim.weight * 100).toFixed(0)}%
                    </Text>
                  </Text>
                  <Text style={{ color, fontWeight: 'bold', fontSize: 14 }}>{dim.score}</Text>
                </div>
                <Progress
                  percent={dim.score}
                  strokeColor={color}
                  showInfo={false}
                  size="small"
                />
                {dim.detail && (
                  <Text type="secondary" style={{ fontSize: 11, marginTop: 2, display: 'block' }}>
                    {dim.detail}
                  </Text>
                )}
              </div>
            )
          })}
        </div>
      </Card>

      {/* 策略命中列表 */}
      {data.strategy_names && data.strategy_names.length > 0 && (
        <Card title="🚀 命中策略" size="small" style={{ marginBottom: 16 }}>
          <Space wrap>
            {data.strategy_names.map((name) => (
              <Tag key={name} color="blue">{name}</Tag>
            ))}
          </Space>
        </Card>
      )}

      {/* 推理文本 */}
      <Card title="💡 分析推理" size="small" style={{ marginBottom: 16 }}>
        <Paragraph style={{ marginBottom: 0 }}>{data.reasoning}</Paragraph>
      </Card>

      {/* 风险因素 */}
      {data.risk_factors && data.risk_factors.length > 0 && (
        <Card
          title={<span><WarningOutlined style={{ color: '#faad14' }} /> 风险提示</span>}
          size="small"
          style={{ marginBottom: 16 }}
        >
          <Space wrap>
            {data.risk_factors.map((risk, i) => (
              <Tag key={i} color="warning" style={{ marginBottom: 4 }}>{risk}</Tag>
            ))}
          </Space>
        </Card>
      )}

      {/* 原始数据（可折叠） */}
      {data.raw_data && (
        <Collapse ghost>
          <Panel
            header={<Text strong>📋 原始指标数据</Text>}
            key="raw"
            style={{ marginBottom: 16 }}
          >
            <Card size="small">
              <Row gutter={[16, 8]}>
                {data.raw_data.flow?.net_amount != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>净流入</Text>
                    <div style={{ color: data.raw_data.flow.net_amount >= 0 ? '#52c41a' : '#f5222d', fontWeight: 'bold' }}>
                      {formatAmount(data.raw_data.flow.net_amount)}
                    </div>
                  </Col>
                )}
                {data.raw_data.technical?.macd != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>MACD</Text>
                    <div style={{ color: data.raw_data.technical.macd >= 0 ? '#52c41a' : '#f5222d', fontWeight: 'bold' }}>
                      {data.raw_data.technical.macd?.toFixed(4)}
                    </div>
                  </Col>
                )}
                {data.raw_data.technical?.kdj_k != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>KDJ-K</Text>
                    <div style={{ fontWeight: 'bold' }}>{data.raw_data.technical.kdj_k?.toFixed(1)}</div>
                  </Col>
                )}
                {data.raw_data.technical?.rsi_6 != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>RSI-6</Text>
                    <div style={{ fontWeight: 'bold' }}>{data.raw_data.technical.rsi_6?.toFixed(1)}</div>
                  </Col>
                )}
                {data.raw_data.fundamental?.pe_ttm != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>PE-TTM</Text>
                    <div style={{ fontWeight: 'bold' }}>{data.raw_data.fundamental.pe_ttm?.toFixed(1)}</div>
                  </Col>
                )}
                {data.raw_data.fundamental?.pb != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>PB</Text>
                    <div style={{ fontWeight: 'bold' }}>{data.raw_data.fundamental.pb?.toFixed(2)}</div>
                  </Col>
                )}
                {data.raw_data.fundamental?.dv_ttm != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>股息率</Text>
                    <div style={{ color: '#52c41a', fontWeight: 'bold' }}>{data.raw_data.fundamental.dv_ttm?.toFixed(2)}%</div>
                  </Col>
                )}
                {data.raw_data.fundamental?.total_mv != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>总市值</Text>
                    <div style={{ fontWeight: 'bold' }}>{formatAmount(data.raw_data.fundamental.total_mv)}</div>
                  </Col>
                )}
                {data.raw_data.insider?.net_buy_count != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>净买入次数</Text>
                    <div style={{ fontWeight: 'bold' }}>{data.raw_data.insider.net_buy_count}</div>
                  </Col>
                )}
                {data.raw_data.crowding?.crowding_score != null && (
                  <Col span={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>拥挤度评分</Text>
                    <div style={{ color: data.raw_data.crowding.crowding_score > 70 ? '#f5222d' : '#52c41a', fontWeight: 'bold' }}>
                      {data.raw_data.crowding.crowding_score}
                    </div>
                  </Col>
                )}
              </Row>
            </Card>
          </Panel>
        </Collapse>
      )}
    </div>
  )
}

/* =====================================================================
 * Tab 1 — 推荐排行
 * ===================================================================== */
function RecommendationList({ tradeDate }) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [levelFilter, setLevelFilter] = useState('全部')
  const [minScore, setMinScore] = useState(0)
  const [detailStock, setDetailStock] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailData, setDetailData] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (tradeDate) params.set('trade_date', tradeDate)
      if (minScore > 0) params.set('min_score', String(minScore))
      params.set('limit', '100')
      const qs = params.toString() ? `?${params.toString()}` : ''
      const res = await apiCall(`/recommendations${qs}`)
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load recommendations:', err)
    }
    setLoading(false)
  }, [tradeDate, minScore])

  useEffect(() => { loadData() }, [loadData])

  // 点击行加载详情
  const handleRowClick = useCallback(async (record) => {
    setDetailStock(record.ts_code)
    setDetailLoading(true)
    try {
      const params = tradeDate ? `?trade_date=${tradeDate}` : ''
      const res = await apiCall(`/recommendations/${record.ts_code}${params}`)
      setDetailData(res?.data || null)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load stock detail:', err)
    }
    setDetailLoading(false)
  }, [tradeDate])

  const stocks = useMemo(() => {
    if (!data?.stocks) return []
    if (levelFilter === '全部') return data.stocks
    const labelMap = {
      '强推': 'STRONG_BUY',
      '推荐': 'BUY',
      '观望': 'HOLD',
      '减仓': 'REDUCE',
      '回避': 'AVOID',
    }
    const target = labelMap[levelFilter]
    if (!target) return data.data.stocks
    return data.stocks.filter((s) => s.recommendation === target)
  }, [data, levelFilter])

  const columns = [
    {
      title: '排名',
      dataIndex: 'rank',
      width: 55,
      align: 'center',
      render: (v, r, i) => {
        const rank = v || i + 1
        const badgeStyle = rank <= 3
          ? {
              background: rank === 1 ? '#faad14' : rank === 2 ? '#bfbfbf' : '#d48806',
              color: '#000',
              borderRadius: '50%',
              width: 24,
              height: 24,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 12,
              fontWeight: 'bold',
            }
          : {}
        return <span style={badgeStyle}>{rank}</span>
      },
    },
    {
      title: '代码 / 名称',
      key: 'stock',
      width: 140,
      render: (_, r) => (
        <div>
          <Text code style={{ fontSize: 11 }}>{r.ts_code}</Text>
          <br />
          <Text strong style={{ fontSize: 13 }}>{r.name}</Text>
        </div>
      ),
    },
    {
      title: '综合评分',
      dataIndex: 'composite_score',
      width: 110,
      sorter: (a, b) => a.composite_score - b.composite_score,
      defaultSortOrder: 'descend',
      render: (v) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Progress
            type="circle"
            percent={v}
            size={36}
            strokeColor={recommendationScoreColor(v)}
            format={() => (
              <span style={{ fontSize: 11, fontWeight: 'bold', color: recommendationScoreColor(v) }}>{v}</span>
            )}
          />
        </div>
      ),
    },
    {
      title: '推荐等级',
      dataIndex: 'recommendation',
      width: 90,
      render: (v, r) => {
        const cfg = LEVEL_CONFIG[v] || LEVEL_CONFIG.HOLD
        return (
          <Tag color={cfg.color} style={{ margin: 0 }}>
            {cfg.icon} {r.recommendation_cn || cfg.label}
          </Tag>
        )
      },
    },
    {
      title: '策略命中',
      dataIndex: 'strategies_hit',
      width: 120,
      align: 'center',
      sorter: (a, b) => a.strategies_hit - b.strategies_hit,
      render: (v, r) => (
        <div>
          <Badge
            count={v}
            showZero
            style={{
              backgroundColor: v > 3 ? '#52c41a' : v > 0 ? '#1890ff' : '#d9d9d9',
            }}
          />
          {r.strategy_names && r.strategy_names.length > 0 && (
            <Tooltip title={r.strategy_names.join(', ')}>
              <Text type="secondary" style={{ fontSize: 10, display: 'block', marginTop: 2 }}>
                {r.strategy_names.slice(0, 2).join(' / ')}
                {r.strategy_names.length > 2 ? '...' : ''}
              </Text>
            </Tooltip>
          )}
        </div>
      ),
    },
    {
      title: '关键信号',
      dataIndex: 'reasoning',
      ellipsis: true,
      render: (v) => (
        <Tooltip title={v}>
          <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>
        </Tooltip>
      ),
    },
    {
      title: '风险提示',
      dataIndex: 'risk_factors',
      width: 180,
      render: (v) => {
        if (!v || v.length === 0) return <Text type="secondary">-</Text>
        return (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            {v.slice(0, 3).map((r, i) => (
              <Tag
                key={i}
                color="warning"
                style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: 0 }}
              >
                {r}
              </Tag>
            ))}
            {v.length > 3 && (
              <Tooltip title={v.slice(3).join('; ')}>
                <Tag
                  style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px', margin: 0 }}
                >
                  +{v.length - 3}
                </Tag>
              </Tooltip>
            )}
          </div>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 60,
      render: (_, r) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={(e) => {
            e.stopPropagation()
            handleRowClick(r)
          }}
        >
          详情
        </Button>
      ),
    },
  ]

  return (
    <div>
      {/* 筛选器 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Space size={16} wrap>
              <span>
                <Text type="secondary">推荐级别：</Text>
                <Segmented
                  size="small"
                  value={levelFilter}
                  onChange={setLevelFilter}
                  options={[
                    { label: '全部', value: '全部' },
                    { label: '🔥 强推', value: '强推' },
                    { label: '👍 推荐', value: '推荐' },
                    { label: '👁️ 观望', value: '观望' },
                    { label: '⚠️ 减仓', value: '减仓' },
                    { label: '🚫 回避', value: '回避' },
                  ]}
                />
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Text type="secondary">最低评分：</Text>
                <Progress
                  type="slider"
                  min={0}
                  max={100}
                  value={minScore}
                  onChange={setMinScore}
                  style={{ width: 140 }}
                  strokeColor={recommendationScoreColor(minScore)}
                  tooltip={{ formatter: (val) => `${val}分` }}
                />
                <Text style={{ minWidth: 30 }}>{minScore}分</Text>
              </span>
            </Space>
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading} size="small">
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 数据表 */}
      <Card title="🎯 智能荐股排行" bodyStyle={{ padding: 0 }}>
        <Table
          dataSource={stocks}
          columns={columns}
          rowKey="ts_code"
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 只` }}
          size="small"
          scroll={{ x: 1100 }}
          onRow={(record) => ({
            onClick: () => handleRowClick(record),
            style: { cursor: 'pointer' },
          })}
          expandable={{
            expandedRowRender: (record) => (
              <DimensionBars dimensions={record.dimensions} />
            ),
            rowExpandable: (record) => record.dimensions,
          }}
        />
      </Card>

      {/* 详情抽屉 */}
      <Drawer
        title={
          detailData
            ? `${detailData.name} (${detailData.ts_code})`
            : '股票详情'
        }
        width={520}
        open={!!detailStock}
        onClose={() => {
          setDetailStock(null)
          setDetailData(null)
        }}
        footer={null}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" tip="加载详情..." />
          </div>
        ) : detailData ? (
          <StockDetail data={detailData} />
        ) : (
          <Empty description="无数据" />
        )}
      </Drawer>
    </div>
  )
}

/* =====================================================================
 * Tab 2 — 市场概览
 * ===================================================================== */
function MarketOverview({ tradeDate }) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [detailStock, setDetailStock] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailData, setDetailData] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const params = tradeDate ? `?trade_date=${tradeDate}` : ''
      const res = await apiCall(`/recommendations/summary${params}`)
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load summary:', err)
    }
    setLoading(false)
  }, [tradeDate])

  useEffect(() => { loadData() }, [loadData])

  const summary = data || {}
  const dist = summary.level_distribution || {}
  const dimAvgs = summary.avg_dimension_scores || {}
  const total = LEVEL_ORDER.reduce((sum, k) => sum + (dist[k] || 0), 0)
  const buyCount = (dist.STRONG_BUY || 0) + (dist.BUY || 0)

  // 点击 Top Pick 加载详情
  const handleTopPickClick = useCallback(async (record) => {
    setDetailStock(record.ts_code)
    setDetailLoading(true)
    try {
      const params = tradeDate ? `?trade_date=${tradeDate}` : ''
      const res = await apiCall(`/recommendations/${record.ts_code}${params}`)
      setDetailData(res?.data || null)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load stock detail:', err)
    }
    setDetailLoading(false)
  }, [tradeDate])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" tip="加载市场概览..." />
      </div>
    )
  }

  return (
    <div>
      {/* 4 个核心统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="总分析股票数"
              value={summary.total_analyzed || 0}
              prefix={<TrophyOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="强推 / 推荐数"
              value={buyCount}
              valueStyle={{ color: '#52c41a' }}
              prefix={<RocketOutlined />}
            />
            <Text type="secondary" style={{ fontSize: 11 }}>
              强推 {dist.STRONG_BUY || 0} / 推荐 {dist.BUY || 0}
            </Text>
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="观望数"
              value={dist.HOLD || 0}
              valueStyle={{ color: '#faad14' }}
              prefix={<EyeOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="平均综合评分"
              value={summary.avg_composite_score || 0}
              precision={1}
              valueStyle={{ color: recommendationScoreColor(summary.avg_composite_score || 0) }}
            />
          </Card>
        </Col>
      </Row>

      {/* 推荐级别分布 — 水平堆叠条 */}
      <Card title="📊 推荐级别分布" size="small" style={{ marginBottom: 16 }}>
        {total > 0 ? (
          <>
            {/* 堆叠条 */}
            <div
              style={{
                display: 'flex',
                height: 32,
                borderRadius: 6,
                overflow: 'hidden',
                marginBottom: 12,
              }}
            >
              {LEVEL_ORDER.map((key) => {
                const count = dist[key] || 0
                if (count === 0) return null
                const pct = (count / total) * 100
                return (
                  <Tooltip
                    key={key}
                    title={`${LEVEL_CONFIG[key].label}: ${count} 只 (${pct.toFixed(1)}%)`}
                  >
                    <div
                      style={{
                        width: `${pct}%`,
                        background: LEVEL_CONFIG[key].color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'width 0.3s',
                      }}
                    >
                      {pct > 8 && (
                        <Text style={{ color: '#fff', fontSize: 11, fontWeight: 600 }}>
                          {count}
                        </Text>
                      )}
                    </div>
                  </Tooltip>
                )
              })}
            </div>
            {/* 图例 */}
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 12,
                justifyContent: 'center',
              }}
            >
              {LEVEL_ORDER.map((key) => {
                const count = dist[key] || 0
                const pct = total > 0 ? ((count / total) * 100).toFixed(1) : '0'
                return (
                  <Space key={key} size={4}>
                    <div
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: 2,
                        background: LEVEL_CONFIG[key].color,
                      }}
                    />
                    <Text style={{ fontSize: 12 }}>
                      {LEVEL_CONFIG[key].icon} {LEVEL_CONFIG[key].label}:{' '}
                      {count} ({pct}%)
                    </Text>
                  </Space>
                )
              })}
            </div>
          </>
        ) : (
          <Empty description="暂无分布数据" />
        )}
      </Card>

      {/* 各维度平均得分 */}
      <Card title="📈 各维度平均得分" size="small" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          {DIM_KEYS.map((key) => {
            const score = dimAvgs[key] || 0
            const color = DIM_COLORS[key] || '#1890ff'
            return (
              <Col xs={12} sm={8} md={6} key={key}>
                <Card
                  size="small"
                  style={{ background: '#141414', borderColor: color + '30' }}
                >
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 20, marginBottom: 4 }}>
                      {DIM_ICONS[key]}
                    </div>
                    <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                      {DIM_LABELS[key]}
                    </Text>
                    <div
                      style={{
                        fontSize: 22,
                        fontWeight: 'bold',
                        color,
                        marginBottom: 6,
                      }}
                    >
                      {typeof score === 'number' ? score.toFixed(1) : score}
                    </div>
                    <Progress
                      percent={typeof score === 'number' ? score : 0}
                      strokeColor={color}
                      size="small"
                      showInfo={false}
                    />
                  </div>
                </Card>
              </Col>
            )
          })}
        </Row>
      </Card>

      {/* Top 推荐 */}
      {summary.top_picks && summary.top_picks.length > 0 && (
        <Card title="🏆 Top 推荐" size="small">
          <Table
            dataSource={summary.top_picks}
            rowKey="ts_code"
            size="small"
            pagination={false}
            onRow={(record) => ({
              onClick: () => handleTopPickClick(record),
              style: { cursor: 'pointer' },
            })}
            columns={[
              {
                title: '排名',
                key: 'rank',
                width: 50,
                render: (_, __, i) => {
                  const rank = i + 1
                  const badgeStyle =
                    rank <= 3
                      ? {
                          background:
                            rank === 1
                              ? '#faad14'
                              : rank === 2
                              ? '#bfbfbf'
                              : '#d48806',
                          color: '#000',
                          borderRadius: '50%',
                          width: 24,
                          height: 24,
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: 12,
                          fontWeight: 'bold',
                        }
                      : {}
                  return <span style={badgeStyle}>{rank}</span>
                },
              },
              {
                title: '代码 / 名称',
                key: 'stock',
                render: (_, r) => (
                  <span>
                    <Text code style={{ fontSize: 11 }}>
                      {r.ts_code}
                    </Text>{' '}
                    <Text strong>{r.name}</Text>
                  </span>
                ),
              },
              {
                title: '综合评分',
                dataIndex: 'composite_score',
                render: (v) => (
                  <span
                    style={{
                      color: recommendationScoreColor(v),
                      fontWeight: 'bold',
                      fontSize: 16,
                    }}
                  >
                    {v}
                  </span>
                ),
              },
              {
                title: '推荐',
                dataIndex: 'recommendation',
                render: (v, r) => {
                  const cfg = LEVEL_CONFIG[v] || LEVEL_CONFIG.HOLD
                  return (
                    <Tag color={cfg.color}>
                      {cfg.icon} {r.recommendation_cn || cfg.label}
                    </Tag>
                  )
                },
              },
              {
                title: '核心信号',
                dataIndex: 'reasoning',
                ellipsis: true,
                render: (v) => (
                  <Tooltip title={v}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {v}
                    </Text>
                  </Tooltip>
                ),
              },
            ]}
          />
        </Card>
      )}

      {/* 说明 */}
      <Card size="small" style={{ marginTop: 16 }}>
        <Text type="secondary">
          💡 <strong>说明</strong>：智能荐股引擎综合7维度评分（策略信号25% +
          资金智慧20% + 技术动量15% + 基本面价值15% + 内部人信念10% +
          拥挤风险10% + 市场适配5%）， 自动生成推荐级别和分析推理。仅供参考，
          不构成投资建议。
        </Text>
      </Card>

      {/* 详情抽屉（Top Picks 用） */}
      <Drawer
        title={
          detailData
            ? `${detailData.name} (${detailData.ts_code})`
            : '股票详情'
        }
        width={520}
        open={!!detailStock}
        onClose={() => {
          setDetailStock(null)
          setDetailData(null)
        }}
        footer={null}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" tip="加载详情..." />
          </div>
        ) : detailData ? (
          <StockDetail data={detailData} />
        ) : (
          <Empty description="无数据" />
        )}
      </Drawer>
    </div>
  )
}

/* =====================================================================
 * 主组件
 * ===================================================================== */
export default function Recommendation({ tradeDate }) {
  const [activeTab, setActiveTab] = useState('list')

  const tabs = [
    { label: '🎯 荐股排行', value: 'list' },
    { label: '📊 市场概览', value: 'overview' },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      <Segmented
        value={activeTab}
        onChange={setActiveTab}
        options={tabs}
        style={{ marginBottom: 16 }}
      />

      {activeTab === 'list' && <RecommendationList tradeDate={tradeDate} />}
      {activeTab === 'overview' && <MarketOverview tradeDate={tradeDate} />}
    </div>
  )
}
