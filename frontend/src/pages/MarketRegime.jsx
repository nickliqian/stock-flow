import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Row, Col, Tag, Button, Space, Spin, Typography, Progress,
  Statistic, Tooltip, Divider, Alert, message, Badge,
} from 'antd'
import {
  ReloadOutlined, RocketOutlined, ShieldOutlined, WarningOutlined,
  ArrowUpOutlined, ArrowDownOutlined, SwapOutlined, ThunderboltOutlined,
  CheckCircleOutlined, CloseCircleOutlined, PlayCircleOutlined,
  ExperimentOutlined, BankOutlined, RiseOutlined, FallOutlined,
} from '@ant-design/icons'
import { getMarketRegime, executeStrategy, composeStrategies } from '../services/api'

const { Title, Text, Paragraph } = Typography

// 市场状态配色方案
const REGIME_CONFIG = {
  bull: {
    color: '#52c41a',
    bg: 'linear-gradient(135deg, #f6ffed 0%, #d9f7be 100%)',
    borderColor: '#b7eb8f',
    icon: <ArrowUpOutlined />,
    label: '牛市',
    emoji: '🐂',
  },
  bear: {
    color: '#ff4d4f',
    bg: 'linear-gradient(135deg, #fff1f0 0%, #ffccc7 100%)',
    borderColor: '#ffa39e',
    icon: <ArrowDownOutlined />,
    label: '熊市',
    emoji: '🐻',
  },
  sideways: {
    color: '#faad14',
    bg: 'linear-gradient(135deg, #fffbe6 0%, #fff1b8 100%)',
    borderColor: '#ffe58f',
    icon: <SwapOutlined />,
    label: '震荡',
    emoji: '📊',
  },
  extreme: {
    color: '#722ed1',
    bg: 'linear-gradient(135deg, #f9f0ff 0%, #efdbff 100%)',
    borderColor: '#d3adf7',
    icon: <ThunderboltOutlined />,
    label: '极端',
    emoji: '⚡',
  },
}

// 风险等级配色
const RISK_CONFIG = {
  low: { color: '#52c41a', label: '低风险', percent: 25 },
  moderate: { color: '#faad14', label: '中等风险', percent: 50 },
  high: { color: '#ff7a45', label: '高风险', percent: 75 },
  extreme: { color: '#ff4d4f', label: '极高风险', percent: 100 },
}

// 信号分数颜色
function scoreColor(score) {
  if (score > 100) return '#52c41a'
  if (score > 30) return '#73d13d'
  if (score > -30) return '#faad14'
  if (score > -100) return '#ff7a45'
  return '#ff4d4f'
}

function scoreLabel(score) {
  if (score > 100) return '强烈看多'
  if (score > 30) return '偏多'
  if (score > -30) return '中性'
  if (score > -100) return '偏空'
  return '强烈看空'
}

/**
 * 市场状态仪表盘页面
 */
export default function MarketRegime() {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [executingCompose, setExecutingCompose] = useState(false)

  const fetchData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const result = await getMarketRegime({ signal })
      if (result?.success) {
        setData(result.data)
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('获取市场状态失败:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(controller.signal)
    return () => controller.abort()
  }, [fetchData])

  const handleExecuteCompose = async () => {
    if (!data?.recommendations?.suggested_compose) return
    const compose = data.recommendations.suggested_compose
    setExecutingCompose(true)
    try {
      await composeStrategies(compose.strategies, compose.operator)
      message.success('策略组合执行成功！')
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      message.error('执行失败: ' + (err.message || '未知错误'))
    } finally {
      setExecutingCompose(false)
    }
  }

  const handleExecuteStrategy = async (name) => {
    try {
      await executeStrategy(name)
      message.success(`${name} 执行成功！`)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      message.error('执行失败: ' + (err.message || '未知错误'))
    }
  }

  if (loading && !data) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" tip="正在分析市场状态..." />
      </div>
    )
  }

  const regime = data?.regime || 'sideways'
  const config = REGIME_CONFIG[regime] || REGIME_CONFIG.sideways
  const signals = data?.signals || {}
  const recs = data?.recommendations || {}
  const riskConfig = RISK_CONFIG[recs.risk_level] || RISK_CONFIG.moderate

  return (
    <div style={{ padding: '0 16px' }}>
      {/* 顶部操作栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          {config.emoji} 市场定性分析
        </Title>
        <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
          刷新
        </Button>
      </div>

      {/* 市场状态横幅 */}
      <Card
        style={{
          background: config.bg,
          border: `2px solid ${config.borderColor}`,
          marginBottom: 16,
        }}
        bodyStyle={{ padding: '24px 32px' }}
      >
        <Row align="middle" gutter={24}>
          <Col flex="auto">
            <Space align="center" size={16}>
              <span style={{ fontSize: 48 }}>{config.emoji}</span>
              <div>
                <Title level={2} style={{ margin: 0, color: config.color }}>
                  {config.label}
                </Title>
                <Text style={{ fontSize: 14, color: '#666' }}>
                  {data?.description || '分析中...'}
                </Text>
              </div>
            </Space>
          </Col>
          <Col>
            <div style={{ textAlign: 'center' }}>
              <Progress
                type="circle"
                percent={Math.round((data?.confidence || 0) * 100)}
                strokeColor={config.color}
                format={(p) => <span style={{ fontSize: 18, fontWeight: 600 }}>{p}%</span>}
                size={100}
              />
              <div style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>置信度</Text>
              </div>
            </div>
          </Col>
          <Col>
            <Statistic
              title="综合评分"
              value={data?.total_score || 0}
              precision={0}
              valueStyle={{ color: scoreColor(data?.total_score || 0), fontSize: 28 }}
              prefix={data?.total_score > 0 ? <RiseOutlined /> : <FallOutlined />}
            />
          </Col>
        </Row>
      </Card>

      {/* 信号分解卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} lg={6}>
          <SignalCard
            title="📈 指数趋势"
            subtitle="权重30%"
            signal={signals.index_trend}
            icon={<BarChartOutlined />}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <SignalCard
            title="🏆 策略表现"
            subtitle="权重30%"
            signal={signals.strategy_performance}
            icon={<TrophyOutlined />}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <SignalCard
            title="🌐 市场广度"
            subtitle="权重20%"
            signal={signals.breadth}
            icon={<BankOutlined />}
          />
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <SignalCard
            title="🔗 策略共振"
            subtitle="权重20%"
            signal={signals.confluence}
            icon={<ExperimentOutlined />}
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* 策略推荐 */}
        <Col xs={24} lg={14}>
          <Card title="🎯 策略推荐" bodyStyle={{ padding: '16px 24px' }}>
            {/* 风险等级 */}
            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ marginRight: 8 }}>风险等级：</Text>
              <Progress
                percent={riskConfig.percent}
                strokeColor={riskConfig.color}
                format={() => riskConfig.label}
                style={{ width: 200 }}
                size="small"
              />
            </div>

            {/* 最佳策略 */}
            <div style={{ marginBottom: 12 }}>
              <Text strong style={{ color: '#52c41a' }}>
                <CheckCircleOutlined /> 推荐使用
              </Text>
              <div style={{ marginTop: 4 }}>
                <Space wrap>
                  {(recs.best_strategies || []).map((s) => (
                    <Tag key={s} color="success" style={{ cursor: 'pointer' }}
                         onClick={() => handleExecuteStrategy(s)}>
                      {formatStrategyName(s)}
                    </Tag>
                  ))}
                </Space>
              </div>
            </div>

            {/* 可选策略 */}
            <div style={{ marginBottom: 12 }}>
              <Text strong style={{ color: '#1677ff' }}>
                <RocketOutlined /> 可选使用
              </Text>
              <div style={{ marginTop: 4 }}>
                <Space wrap>
                  {(recs.good_strategies || []).map((s) => (
                    <Tag key={s} color="blue" style={{ cursor: 'pointer' }}
                         onClick={() => handleExecuteStrategy(s)}>
                      {formatStrategyName(s)}
                    </Tag>
                  ))}
                </Space>
              </div>
            </div>

            {/* 建议回避 */}
            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ color: '#ff4d4f' }}>
                <CloseCircleOutlined /> 建议回避
              </Text>
              <div style={{ marginTop: 4 }}>
                <Space wrap>
                  {(recs.avoid_strategies || []).map((s) => (
                    <Tag key={s} color="error">
                      {formatStrategyName(s)}
                    </Tag>
                  ))}
                </Space>
              </div>
            </div>

            <Divider style={{ margin: '12px 0' }} />

            {/* 建议 */}
            <Alert
              message={recs.advice || '暂无建议'}
              type="info"
              showIcon
              style={{ marginBottom: 16 }}
            />

            {/* 一键执行推荐组合 */}
            {recs.suggested_compose && (
              <div style={{ textAlign: 'center' }}>
                <Button
                  type="primary"
                  size="large"
                  icon={<PlayCircleOutlined />}
                  onClick={handleExecuteCompose}
                  loading={executingCompose}
                  style={{ minWidth: 240 }}
                >
                  一键执行推荐组合 ({recs.suggested_compose.operator})
                </Button>
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {recs.suggested_compose.strategies.map(formatStrategyName).join(' + ')}
                  </Text>
                </div>
              </div>
            )}
          </Card>
        </Col>

        {/* 状态历史 */}
        <Col xs={24} lg={10}>
          <Card title="📅 状态历史" bodyStyle={{ padding: '16px 24px' }}>
            {(data?.regime_history || []).length === 0 ? (
              <div style={{ textAlign: 'center', padding: 24 }}>
                <Text type="secondary">暂无历史数据</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  执行策略后将自动记录市场状态
                </Text>
              </div>
            ) : (
              <div style={{ maxHeight: 400, overflow: 'auto' }}>
                {(data?.regime_history || []).map((item, idx) => {
                  const histConfig = REGIME_CONFIG[item.regime] || REGIME_CONFIG.sideways
                  return (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 12px',
                        borderBottom: '1px solid #f0f0f0',
                      }}
                    >
                      <Space>
                        <Badge color={histConfig.color} />
                        <Text>{item.date}</Text>
                      </Space>
                      <Space>
                        <Tag color={histConfig.color === '#52c41a' ? 'success' :
                                    histConfig.color === '#ff4d4f' ? 'error' :
                                    histConfig.color === '#faad14' ? 'warning' : 'purple'}>
                          {histConfig.label}
                        </Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {Math.round((item.confidence || 0) * 100)}%
                        </Text>
                      </Space>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}

/** 信号卡片组件 */
function SignalCard({ title, subtitle, signal, icon }) {
  const score = signal?.score || 0
  const detail = signal?.detail || '暂无数据'

  return (
    <Card
      bodyStyle={{ padding: '16px 20px' }}
      style={{ height: '100%' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Text strong style={{ fontSize: 14 }}>{title}</Text>
          <br />
          <Text type="secondary" style={{ fontSize: 11 }}>{subtitle}</Text>
        </div>
        <Tooltip title={scoreLabel(score)}>
          <Tag color={score > 30 ? 'success' : score < -30 ? 'error' : 'warning'}
               style={{ fontSize: 16, padding: '2px 10px', fontWeight: 600 }}>
            {score > 0 ? '+' : ''}{score.toFixed(0)}
          </Tag>
        </Tooltip>
      </div>
      <Divider style={{ margin: '8px 0' }} />
      <Progress
        percent={Math.min(100, Math.abs(score) / 2)}
        strokeColor={scoreColor(score)}
        showInfo={false}
        size="small"
      />
      <Paragraph
        ellipsis={{ rows: 2, tooltip: detail }}
        style={{ marginTop: 8, marginBottom: 0, fontSize: 12, color: '#666' }}
      >
        {detail}
      </Paragraph>
    </Card>
  )
}

/** 格式化策略名称（snake_case → 中文） */
function formatStrategyName(name) {
  const nameMap = {
    volume_breakthrough: '放量突破',
    ma_alignment: '均线多头排列',
    trend_volume_resonance: '趋势量价共振',
    volume_anomaly: '量能异动',
    kdj_oversold_rebound: 'KDJ超卖反弹',
    macd_golden_cross: 'MACD金叉',
    consecutive_limit_up: '连板',
    limit_up_reseal: '涨停封板',
    main_fund_inflow: '主力资金流入',
    value_fund_resonance: '价值资金共振',
    high_dividend: '高股息',
    low_valuation_gold: '低估值淘金',
    broken_net_gold: '破净淘金',
    oversold_bounce: '超跌反弹',
    block_trade_premium: '大宗交易溢价',
    margin_growth: '融资增长',
  }
  return nameMap[name] || name
}
