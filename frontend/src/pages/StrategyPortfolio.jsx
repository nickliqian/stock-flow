import React, { useState, useEffect } from 'react'
import {
  Card, Row, Col, Spin, Empty, Tag, Segmented, Tooltip, Slider, Table, Badge,
  Alert, Statistic, Space, Typography, Divider, Radio,
} from 'antd'
import {
  HeatMapOutlined, SwapOutlined, PieChartOutlined, ThunderboltOutlined,
  BulbOutlined, ApartmentOutlined, LinkOutlined,
} from '@ant-design/icons'
import {
  getStrategyOverlap, getStrategyCorrelationMatrix, getStrategyOptimize,
  getRegimeAllocation, getPortfolioSummary,
} from '../services/api'

const { Text, Title, Paragraph } = Typography

// 分类颜色映射
const CATEGORY_COLORS = {
  value: '#faad14',
  momentum: '#1677ff',
  event: '#ff4d4f',
  fund: '#52c41a',
  combo: '#722ed1',
  unknown: '#8c8c8c',
}

const CATEGORY_LABELS = {
  value: '价值',
  momentum: '动量',
  event: '事件',
  fund: '资金',
  combo: '组合',
  unknown: '其他',
}

// 体制颜色映射
const REGIME_COLORS = {
  bull: '#52c41a',
  bear: '#ff4d4f',
  sideways: '#faad14',
  extreme: '#722ed1',
}

/**
 * 策略配置仪表板 — 相关性分析 + 智能配置
 */
export default function StrategyPortfolio({ tradeDate }) {
  const [loading, setLoading] = useState(true)
  const [activeView, setActiveView] = useState('overview')
  const [summary, setSummary] = useState(null)
  const [overlap, setOverlap] = useState(null)
  const [correlation, setCorrelation] = useState(null)
  const [allocation, setAllocation] = useState(null)
  const [regimeAlloc, setRegimeAlloc] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    loadAllData(controller.signal)
    return () => controller.abort()
  }, [tradeDate])

  const loadAllData = async (signal) => {
    setLoading(true)
    try {
      // Load summary (includes all analyses)
      const res = await getPortfolioSummary(tradeDate, { signal })
      if (res.success) {
        setSummary(res)
        setOverlap(res.overlap)
        setCorrelation(res.correlation)
        setAllocation(res.allocation)
        setRegimeAlloc(res.regime_allocation)
      }
    } catch (e) {
      if (e?.name === 'CanceledError' || e?.code === 'ERR_CANCELED') return
      console.error('Failed to load portfolio data:', e)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" tip="加载策略分析数据..." />
      </div>
    )
  }

  if (!summary || !summary.success) {
    return (
      <Empty
        description="暂无策略分析数据，请先执行策略以积累数据"
        style={{ marginTop: 80 }}
      />
    )
  }

  return (
    <div>
      {/* 洞察横幅 */}
      {summary.insights && summary.insights.length > 0 && (
        <Alert
          banner
          message={
            <Space size={24} wrap>
              {summary.insights.map((insight, i) => (
                <Space key={i} size={6}>
                  <BulbOutlined style={{
                    color: insight.level === 'success' ? '#52c41a' :
                           insight.level === 'warning' ? '#faad14' : '#1677ff'
                  }} />
                  <Text strong>{insight.title}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>{insight.detail}</Text>
                </Space>
              ))}
            </Space>
          }
          type="info"
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 视图切换 */}
      <Segmented
        value={activeView}
        onChange={setActiveView}
        options={[
          { label: '📊 综合概览', value: 'overview' },
          { label: '🔗 选股重叠', value: 'overlap' },
          { label: '📈 收益相关', value: 'correlation' },
          { label: '⚖️ 配置优化', value: 'allocation' },
          { label: '🌐 体制配置', value: 'regime' },
        ]}
        style={{ marginBottom: 16 }}
      />

      {/* 综合概览 */}
      {activeView === 'overview' && (
        <OverviewView
          overlap={overlap}
          correlation={correlation}
          allocation={allocation}
          regimeAlloc={regimeAlloc}
        />
      )}

      {/* 选股重叠 */}
      {activeView === 'overlap' && (
        <OverlapView data={overlap} />
      )}

      {/* 收益相关 */}
      {activeView === 'correlation' && (
        <CorrelationView data={correlation} />
      )}

      {/* 配置优化 */}
      {activeView === 'allocation' && (
        <AllocationView data={allocation} />
      )}

      {/* 体制配置 */}
      {activeView === 'regime' && (
        <RegimeView data={regimeAlloc} />
      )}
    </div>
  )
}

// ------------------------------------------------------------------
// 综合概览视图
// ------------------------------------------------------------------
function OverviewView({ overlap, correlation, allocation, regimeAlloc }) {
  return (
    <div>
      <Row gutter={16}>
        {/* 策略数量 */}
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="注册策略数"
              value={regimeAlloc?.strategy_weights ? Object.keys(regimeAlloc.strategy_weights).length : '—'}
              suffix="个"
              valueStyle={{ fontSize: 28 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="市场状态"
              value={regimeAlloc?.regime_label || '未知'}
              valueStyle={{
                fontSize: 20,
                color: REGIME_COLORS[regimeAlloc?.regime] || '#8c8c8c',
              }}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="最优夏普策略"
              value={allocation?.sharpe_weighted ? Object.entries(allocation.sharpe_weighted).sort((a, b) => b[1] - a[1])[0]?.[0] : '—'}
              valueStyle={{ fontSize: 16 }}
              suffix={allocation?.sharpe_scores ? `(${Object.values(allocation.sharpe_scores).sort((a, b) => b - a)[0]?.toFixed(2)})` : ''}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="最高重叠对"
              value={overlap?.overlap_details?.[0] ? `${overlap.overlap_details[0].similarity * 100}%` : '—'}
              valueStyle={{ fontSize: 20 }}
              prefix={<LinkOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Divider />

      {/* 体制自适应配置饼图 */}
      {regimeAlloc?.strategy_weights && (
        <Row gutter={16}>
          <Col span={12}>
            <Card title="🌐 体制自适应配置" size="small">
              <AllocationPieChart weights={regimeAlloc.strategy_weights} categories={regimeAlloc.strategy_categories} />
            </Card>
          </Col>
          <Col span={12}>
            <Card title="📊 分类权重分布" size="small">
              <CategoryBarChart weights={regimeAlloc.category_weights} counts={regimeAlloc.category_counts} />
            </Card>
          </Col>
        </Row>
      )}

      {/* 策略配置建议 */}
      {regimeAlloc?.recommendation && (
        <Alert
          message="配置建议"
          description={regimeAlloc.recommendation}
          type="info"
          showIcon
          style={{ marginTop: 16 }}
        />
      )}
    </div>
  )
}

// ------------------------------------------------------------------
// 选股重叠视图
// ------------------------------------------------------------------
function OverlapView({ data }) {
  if (!data || data.error) {
    return <Empty description={data?.error || '暂无重叠数据'} />
  }

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card title="🔗 策略选股重叠度矩阵 (Jaccard 相似系数)" size="small">
            <MatrixTable
              strategies={data.strategies}
              matrix={data.matrix}
              format={(v) => v > 0 ? `${(v * 100).toFixed(0)}%` : '—'}
              colorScale={(v) => {
                if (v >= 0.5) return '#ff4d4f'
                if (v >= 0.3) return '#faad14'
                if (v >= 0.1) return '#1677ff'
                return '#f0f0f0'
              }}
            />
          </Card>
        </Col>
      </Row>

      {/* TOP 重叠对详情 */}
      <Card title="🎯 选股重叠 TOP 对" size="small">
        <Table
          dataSource={data.overlap_details.slice(0, 15)}
          rowKey={(r) => r.pair.join('-')}
          size="small"
          pagination={false}
          columns={[
            {
              title: '策略 A',
              dataIndex: 'pair',
              render: (_, r) => <Tag>{r.pair[0]}</Tag>,
            },
            {
              title: '策略 B',
              dataIndex: 'pair',
              render: (_, r) => <Tag>{r.pair[1]}</Tag>,
            },
            {
              title: '重叠度',
              dataIndex: 'similarity',
              sorter: (a, b) => a.similarity - b.similarity,
              render: (v) => (
                <span style={{
                  color: v >= 0.5 ? '#ff4d4f' : v >= 0.3 ? '#faad14' : '#52c41a',
                  fontWeight: 600,
                }}>
                  {(v * 100).toFixed(1)}%
                </span>
              ),
            },
            {
              title: '共享股票数',
              dataIndex: 'intersection_count',
            },
            {
              title: '共享股票',
              dataIndex: 'shared_stocks',
              render: (stocks) => (
                <Space size={2} wrap>
                  {stocks.slice(0, 6).map(s => <Tag key={s} style={{ fontSize: 11 }}>{s.replace('.SZ', '').replace('.SH', '')}</Tag>)}
                  {stocks.length > 6 && <Text type="secondary">+{stocks.length - 6}</Text>}
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------
// 收益相关视图
// ------------------------------------------------------------------
function CorrelationView({ data }) {
  if (!data || data.error) {
    return <Empty description={data?.error || '暂无相关性数据，需积累至少3个交易日的策略表现数据'} />
  }

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card
            title={`📈 策略收益率相关性矩阵 (Pearson, 近${data.period}个交易日)`}
            size="small"
          >
            <MatrixTable
              strategies={data.strategies}
              matrix={data.matrix}
              format={(v) => Math.abs(v) > 0.01 ? v.toFixed(2) : '—'}
              colorScale={(v) => {
                if (v >= 0.7) return '#ff4d4f'
                if (v >= 0.3) return '#faad14'
                if (v >= -0.1) return '#f0f0f0'
                if (v >= -0.5) return '#69c0ff'
                return '#1677ff'
              }}
            />
          </Card>
        </Col>
      </Row>

      <Alert
        message="相关性解读"
        description={
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            <li><b>正相关 (+0.5~+1.0)</b>：两个策略倾向于同时选中相似的股票，分散效果有限</li>
            <li><b>低相关 (-0.3~+0.3)</b>：策略间有较好的分散效果，适合作为组合使用</li>
            <li><b>负相关 (-1.0~-0.3)</b>：策略反向运作，可作为对冲组合降低波动</li>
          </ul>
        }
        type="info"
        showIcon
      />
    </div>
  )
}

// ------------------------------------------------------------------
// 配置优化视图
// ------------------------------------------------------------------
function AllocationView({ data }) {
  if (!data || data.error) {
    return <Empty description={data?.error || '暂无配置优化数据'} />
  }

  const allocationMethods = [
    { key: 'equal_weight', label: '等权配置', desc: '每个策略分配相同权重' },
    { key: 'risk_parity', label: '风险平价', desc: '按波动率倒数分配，低波动策略获得更高权重' },
    { key: 'min_variance', label: '最小方差', desc: '最小化组合波动率的配置方案' },
    { key: 'sharpe_weighted', label: '夏普加权', desc: '按夏普比率分配，高风险调整收益策略获得更高权重' },
  ]

  return (
    <div>
      <Row gutter={16}>
        {allocationMethods.map(({ key, label, desc }) => (
          <Col span={12} key={key} style={{ marginBottom: 16 }}>
            <Card title={`${key === 'equal_weight' ? '⚖️' : key === 'risk_parity' ? '🛡️' : key === 'min_variance' ? '📉' : '🎯'} ${label}`} size="small">
              <Paragraph type="secondary" style={{ fontSize: 12 }}>{desc}</Paragraph>
              <AllocationBarChart weights={data[key]} expectedReturns={data.expected_returns} risks={data.risk} />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 策略风险收益散点 */}
      <Card title="📊 策略风险-收益散点图" size="small" style={{ marginTop: 16 }}>
        <RiskReturnScatter data={data} />
      </Card>
    </div>
  )
}

// ------------------------------------------------------------------
// 体制配置视图
// ------------------------------------------------------------------
function RegimeView({ data }) {
  if (!data || data.error) {
    return <Empty description={data?.error || '暂无体制配置数据'} />
  }

  return (
    <div>
      {/* 状态横幅 */}
      <Card
        size="small"
        style={{
          borderLeft: `4px solid ${REGIME_COLORS[data.regime] || '#8c8c8c'}`,
          marginBottom: 16,
        }}
      >
        <Row align="middle" gutter={24}>
          <Col>
            <Title level={3} style={{ margin: 0 }}>
              {data.regime_label}
            </Title>
          </Col>
          <Col>
            <Space>
              <Text type="secondary">置信度</Text>
              <Badge
                count={`${(data.confidence * 100).toFixed(0)}%`}
                style={{
                  backgroundColor: data.confidence > 0.6 ? '#52c41a' : '#faad14',
                }}
              />
            </Space>
          </Col>
          <Col>
            <Space>
              <Text type="secondary">风险等级</Text>
              <Tag color={
                data.risk_level === '低' ? 'green' :
                data.risk_level === '中' ? 'orange' :
                data.risk_level === '高' ? 'red' : 'purple'
              }>
                {data.risk_level}
              </Tag>
            </Space>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        {/* 分类权重 */}
        <Col span={12}>
          <Card title="📊 分类权重" size="small">
            <CategoryBarChart weights={data.category_weights} counts={data.category_counts} />
          </Card>
        </Col>

        {/* 策略权重 */}
        <Col span={12}>
          <Card title="🎯 策略权重" size="small">
            <AllocationPieChart weights={data.strategy_weights} categories={data.strategy_categories} />
          </Card>
        </Col>
      </Row>

      {/* 配置建议 */}
      {data.recommendation && (
        <Alert
          message="体制配置建议"
          description={data.recommendation}
          type="info"
          showIcon
          style={{ marginTop: 16 }}
        />
      )}
    </div>
  )
}

// ------------------------------------------------------------------
// 共享组件
// ------------------------------------------------------------------

/**
 * 矩阵表格（相关性/重叠度）
 */
function MatrixTable({ strategies, matrix, format, colorScale }) {
  if (!strategies || !matrix || strategies.length === 0) {
    return <Empty description="无矩阵数据" />
  }

  // Shorten strategy names for display
  const shortName = (name) => {
    const map = {
      low_valuation_gold: '低估值',
      high_dividend: '高股息',
      broken_net_gold: '破净',
      value_fund_resonance: '价资共振',
      volume_breakthrough: '放量突破',
      ma_alignment: '均线排列',
      trend_volume_resonance: '趋量共振',
      volume_anomaly: '量能异动',
      kdj_oversold_rebound: 'KDJ超卖',
      macd_golden_cross: 'MACD金叉',
      consecutive_limit_up: '连板',
      limit_up_reseal: '涨停回封',
      block_trade_premium: '大宗溢价',
      main_fund_inflow: '主力流入',
      margin_growth: '融资增长',
      margin_fund_convergence: '融资共振',
      smart_money_tracker: '聪明钱',
      oversold_bounce: '超跌反弹',
    }
    return map[name] || name.slice(0, 6)
  }

  const columns = [
    { title: '', key: 'header', width: 80, fixed: 'left' },
    ...strategies.map(s => ({
      title: shortName(s),
      key: s,
      width: 64,
      align: 'center',
      render: (_, record) => {
        const idx = strategies.indexOf(s)
        const rowIdx = strategies.indexOf(record._name)
        const val = matrix[rowIdx]?.[idx] ?? 0
        return (
          <Tooltip title={`${record._name} vs ${s}: ${format(val)}`} placement="top">
            <div
              style={{
                width: 48,
                height: 32,
                lineHeight: '32px',
                borderRadius: 4,
                backgroundColor: colorScale(val),
                color: val >= 0.7 || val <= -0.3 ? '#fff' : '#333',
                fontWeight: 500,
                fontSize: 11,
                margin: '0 auto',
                cursor: 'default',
              }}
            >
              {format(val)}
            </div>
          </Tooltip>
        )
      },
    })),
  ]

  const dataSource = strategies.map((name, i) => ({
    key: name,
    _name: name,
    _displayName: shortName(name),
  }))

  return (
    <div style={{ overflowX: 'auto' }}>
      <Table
        dataSource={dataSource}
        columns={columns}
        size="small"
        pagination={false}
        scroll={{ x: strategies.length * 70 + 80 }}
      />
    </div>
  )
}

/**
 * 分类权重柱状图
 */
function CategoryBarChart({ weights, counts }) {
  if (!weights) return <Empty />

  return (
    <div style={{ padding: '8px 0' }}>
      {Object.entries(weights).sort((a, b) => b[1] - a[1]).map(([cat, weight]) => (
        <div key={cat} style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <Space>
              <div style={{
                width: 12, height: 12, borderRadius: 2,
                backgroundColor: CATEGORY_COLORS[cat] || '#8c8c8c',
              }} />
              <Text strong>{CATEGORY_LABELS[cat] || cat}</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>
                ({counts?.[cat] || 0}个策略)
              </Text>
            </Space>
            <Text strong>{(weight * 100).toFixed(1)}%</Text>
          </div>
          <div style={{
            height: 8,
            backgroundColor: '#f0f0f0',
            borderRadius: 4,
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${weight * 100}%`,
              backgroundColor: CATEGORY_COLORS[cat] || '#8c8c8c',
              borderRadius: 4,
              transition: 'width 0.3s',
            }} />
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * 配置权重饼图（CSS 环形图）
 */
function AllocationPieChart({ weights, categories }) {
  if (!weights) return <Empty />

  const entries = Object.entries(weights).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((s, [, w]) => s + w, 0) || 1

  // Build conic gradient
  let gradientParts = []
  let accumulated = 0
  entries.forEach(([name, weight]) => {
    const pct = (weight / total) * 100
    const color = CATEGORY_COLORS[categories?.[name] || 'unknown'] || '#8c8c8c'
    gradientParts.push(`${color} ${accumulated}% ${accumulated + pct}%`)
    accumulated += pct
  })

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      {/* 环形图 */}
      <div style={{
        width: 140,
        height: 140,
        borderRadius: '50%',
        background: `conic-gradient(${gradientParts.join(', ')})`,
        position: 'relative',
      }}>
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 80,
          height: 80,
          borderRadius: '50%',
          backgroundColor: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
        }}>
          <Text type="secondary" style={{ fontSize: 10 }}>策略数</Text>
          <Text strong style={{ fontSize: 20 }}>{entries.length}</Text>
        </div>
      </div>

      {/* 图例 */}
      <div style={{ flex: 1 }}>
        {entries.slice(0, 8).map(([name, weight]) => (
          <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <div style={{
              width: 8, height: 8, borderRadius: 2,
              backgroundColor: CATEGORY_COLORS[categories?.[name] || 'unknown'] || '#8c8c8c',
            }} />
            <Text style={{ fontSize: 11, flex: 1 }}>{name.length > 8 ? name.slice(0, 8) + '..' : name}</Text>
            <Text type="secondary" style={{ fontSize: 11 }}>{(weight * 100).toFixed(1)}%</Text>
          </div>
        ))}
        {entries.length > 8 && (
          <Text type="secondary" style={{ fontSize: 10 }}>+{entries.length - 8} 更多</Text>
        )}
      </div>
    </div>
  )
}

/**
 * 配置权重水平条形图
 */
function AllocationBarChart({ weights, expectedReturns, risks }) {
  if (!weights) return <Empty />

  const entries = Object.entries(weights).sort((a, b) => b[1] - a[1])
  const maxWeight = Math.max(...entries.map(([, w]) => w), 0.01)

  return (
    <div style={{ padding: '4px 0' }}>
      {entries.map(([name, weight]) => (
        <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <Text style={{ fontSize: 11, width: 80, textAlign: 'right' }} ellipsis>
            {name.length > 10 ? name.slice(0, 10) + '..' : name}
          </Text>
          <div style={{
            height: 16,
            width: `${(weight / maxWeight) * 120}px`,
            backgroundColor: '#1677ff',
            borderRadius: 3,
            minWidth: 4,
            transition: 'width 0.3s',
          }} />
          <Text type="secondary" style={{ fontSize: 10, width: 40 }}>
            {(weight * 100).toFixed(1)}%
          </Text>
        </div>
      ))}
    </div>
  )
}

/**
 * 风险-收益散点图（CSS 实现）
 */
function RiskReturnScatter({ data }) {
  if (!data?.risk || !data?.expected_returns) return <Empty />

  const names = data.strategies || []
  if (names.length === 0) return <Empty />

  // Compute ranges
  const returns = names.map(n => data.expected_returns[n] || 0)
  const risks_ = names.map(n => data.risk[n] || 0)
  const minR = Math.min(...risks_)
  const maxR = Math.max(...risks_) || 0.01
  const minRet = Math.min(...returns)
  const maxRet = Math.max(...returns) || 0.01

  const padR = (maxR - minR) * 0.15 || 0.001
  const padRet = (maxRet - minRet) * 0.15 || 0.001

  const shortName = (name) => {
    const map = {
      low_valuation_gold: '低估值', high_dividend: '高股息', broken_net_gold: '破净',
      value_fund_resonance: '价资共振', volume_breakthrough: '放量突破',
      ma_alignment: '均线排列', trend_volume_resonance: '趋量共振',
      volume_anomaly: '量能异动', kdj_oversold_rebound: 'KDJ超卖',
      macd_golden_cross: 'MACD金叉', consecutive_limit_up: '连板',
      limit_up_reseal: '涨停回封', block_trade_premium: '大宗溢价',
      main_fund_inflow: '主力流入', margin_growth: '融资增长',
      margin_fund_convergence: '融资共振', smart_money_tracker: '聪明钱',
      oversold_bounce: '超跌反弹',
    }
    return map[name] || name.slice(0, 6)
  }

  return (
    <div style={{ position: 'relative', height: 260, border: '1px solid #f0f0f0', borderRadius: 8, padding: 8 }}>
      {/* Axes */}
      <div style={{ position: 'absolute', bottom: 28, left: 40, right: 16, height: 1, backgroundColor: '#d9d9d9' }} />
      <div style={{ position: 'absolute', top: 8, bottom: 28, left: 40, width: 1, backgroundColor: '#d9d9d9' }} />

      {/* Axis labels */}
      <div style={{ position: 'absolute', bottom: 4, left: 0, right: 0, textAlign: 'center' }}>
        <Text type="secondary" style={{ fontSize: 10 }}>风险 (波动率)</Text>
      </div>
      <div style={{ position: 'absolute', left: 4, top: '50%', transform: 'rotate(-90deg) translateX(-50%)' }}>
        <Text type="secondary" style={{ fontSize: 10 }}>收益率</Text>
      </div>

      {/* Points */}
      {names.map((name, i) => {
        const r = data.risk[name] || 0
        const ret = data.expected_returns[name] || 0
        const x = 40 + ((r - minR + padR) / (maxR - minR + 2 * padR)) * (100 - 8)
        const y = 8 + (1 - (ret - minRet + padRet) / (maxRet - minRet + 2 * padRet)) * (260 - 36)
        return (
          <Tooltip key={name} title={`${name}\n风险: ${(r * 100).toFixed(2)}%\n收益: ${(ret * 100).toFixed(3)}%\n夏普: ${(data.sharpe_scores?.[name] || 0).toFixed(3)}`} placement="top">
            <div style={{
              position: 'absolute',
              left: `${x}%`,
              top: y,
              width: 12,
              height: 12,
              borderRadius: '50%',
              backgroundColor: '#1677ff',
              border: '2px solid #fff',
              boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
              transform: 'translate(-50%, -50%)',
              cursor: 'default',
            }}>
              <div style={{
                position: 'absolute',
                top: -16,
                left: '50%',
                transform: 'translateX(-50%)',
                fontSize: 9,
                whiteSpace: 'nowrap',
                fontWeight: 500,
              }}>
                {shortName(name)}
              </div>
            </div>
          </Tooltip>
        )
      })}
    </div>
  )
}
