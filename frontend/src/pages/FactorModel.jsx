import React, { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Table, Tag, Progress, Spin, Typography, Tooltip, Button, Segmented, Empty } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { apiCall } from '../services/api'

const { Title, Text } = Typography

// 因子颜色映射
const FACTOR_COLORS = {
  value: '#1890ff',
  momentum: '#52c41a',
  flow: '#faad14',
  event: '#f5222d',
  combo: '#722ed1',
}

// 轮动状态颜色
const REGIME_COLORS = {
  VALUE_DOMINANT: '#1890ff',
  MOMENTUM_DOMINANT: '#52c41a',
  FLOW_DOMINANT: '#faad14',
  EVENT_DOMINANT: '#f5222d',
  BALANCED: '#8c8c8c',
}

/**
 * 量化因子模型 + 因子轮动仪表板
 * 
 * 功能：
 * 1. 因子表现概览 - 各因子的收益率和胜率
 * 2. 因子动量信号 - 哪些因子正在改善
 * 3. 因子轮动状态 - 当前主导因子
 * 4. 轮动选股结果 - 基于因子动量的选股
 */
export default function FactorModel({ tradeDate }) {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [rotationData, setRotationData] = useState(null)
  const [rotationLoading, setRotationLoading] = useState(false)
  const [activeView, setActiveView] = useState('overview')
  const [selectedStock, setSelectedStock] = useState(null)

  // 加载因子模型数据
  const loadData = async (signal) => {
    setLoading(true)
    try {
      const [perfRes, momRes, regimeRes] = await Promise.all([
        apiCall(`/api/strategies/factor-model/performance?lookback_days=20`, { signal }),
        apiCall(`/api/strategies/factor-model/momentum`, { signal }),
        apiCall(`/api/strategies/factor-model/regime`, { signal }),
      ])
      setData({
        performance: perfRes?.data || {},
        momentum: momRes?.data || {},
        regime: regimeRes?.data || {},
      })
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load factor model data:', err)
    }
    setLoading(false)
  }

  // 加载轮动选股
  const loadRotation = async () => {
    setRotationLoading(true)
    try {
      const res = await apiCall(`/api/strategies/factor-model/rotation?top_factors=2&limit=30`)
      setRotationData(res?.data || {})
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load rotation picks:', err)
    }
    setRotationLoading(false)
  }

  useEffect(() => {
    const controller = new AbortController()
    loadData(controller.signal)
    return () => controller.abort()
  }, [tradeDate])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" tip="加载因子模型数据..." />
      </div>
    )
  }

  if (!data) {
    return <Empty description="暂无因子模型数据" />
  }

  const { performance, momentum, regime } = data
  const factors = performance?.factors || {}
  const momentumList = momentum?.momentum || []

  return (
    <div style={{ padding: '0 12px' }}>
      {/* 因子轮动状态横幅 */}
      <Card
        style={{
          marginBottom: 16,
          background: `linear-gradient(135deg, ${REGIME_COLORS[regime?.regime] || '#8c8c8c'}22, ${REGIME_COLORS[regime?.regime] || '#8c8c8c'}11)`,
          border: `1px solid ${REGIME_COLORS[regime?.regime] || '#8c8c8c'}44`,
        }}
      >
        <Row align="middle" gutter={16}>
          <Col>
            <div style={{ fontSize: 48 }}>{regime?.regime_info?.icon || '⚖️'}</div>
          </Col>
          <Col flex="auto">
            <Title level={4} style={{ margin: 0, color: REGIME_COLORS[regime?.regime] }}>
              {regime?.regime_info?.label || '均衡'}
            </Title>
            <Text type="secondary">{regime?.regime_info?.desc || '各因子表现均衡'}</Text>
            {regime?.dominant_factor && (
              <div style={{ marginTop: 4 }}>
                <Tag color={FACTOR_COLORS[regime.dominant_factor]}>
                  主导因子: {regime.dominant_factor_name} {regime.dominant_factor_icon}
                </Tag>
                <Tag>动量: {(regime.dominant_momentum * 100).toFixed(1)}%</Tag>
                <Tag>置信度: {(regime.confidence * 100).toFixed(0)}%</Tag>
              </div>
            )}
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} onClick={() => loadData()} loading={loading}>
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 因子表现卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {Object.entries(factors).map(([fname, fdata]) => (
          <Col xs={24} sm={12} md={8} lg={4} key={fname}>
            <Card
              size="small"
              style={{
                borderTop: `3px solid ${FACTOR_COLORS[fname]}`,
              }}
            >
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 24, marginBottom: 4 }}>{fdata.icon}</div>
                <Text strong>{fdata.name}</Text>
                <div style={{ marginTop: 8 }}>
                  <Statistic
                    title="1日收益"
                    value={fdata.avg_return_1d * 100}
                    precision={2}
                    suffix="%"
                    valueStyle={{ color: fdata.avg_return_1d >= 0 ? '#f5222d' : '#52c41a', fontSize: 16 }}
                  />
                </div>
                <div>
                  <Statistic
                    title="胜率"
                    value={fdata.win_rate}
                    precision={1}
                    suffix="%"
                    valueStyle={{ fontSize: 14 }}
                  />
                </div>
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {fdata.stock_count} 只选股 | {fdata.strategies?.length || 0} 个策略
                  </Text>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 视图切换 */}
      <Segmented
        value={activeView}
        onChange={setActiveView}
        options={[
          { label: '📊 因子表现', value: 'overview' },
          { label: '🚀 动量信号', value: 'momentum' },
          { label: '🎯 轮动选股', value: 'rotation' },
        ]}
        style={{ marginBottom: 16 }}
      />

      {/* 因子表现视图 */}
      {activeView === 'overview' && (
        <Card title="因子表现详情" extra={<Text type="secondary">回看 {performance?.lookback_days || 20} 个交易日</Text>}>
          <Table
            dataSource={Object.entries(factors).map(([fname, fdata]) => ({ key: fname, ...fdata }))}
            columns={[
              {
                title: '因子',
                dataIndex: 'name',
                render: (name, record) => (
                  <span>
                    <span style={{ marginRight: 8 }}>{record.icon}</span>
                    {name}
                  </span>
                ),
              },
              {
                title: '1日收益',
                dataIndex: 'avg_return_1d',
                render: (v) => (
                  <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>
                    {v >= 0 ? '+' : ''}{(v * 100).toFixed(2)}%
                  </span>
                ),
                sorter: (a, b) => a.avg_return_1d - b.avg_return_1d,
              },
              {
                title: '5日收益',
                dataIndex: 'avg_return_5d',
                render: (v) => (
                  <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>
                    {v >= 0 ? '+' : ''}{(v * 100).toFixed(2)}%
                  </span>
                ),
                sorter: (a, b) => a.avg_return_5d - b.avg_return_5d,
              },
              {
                title: '胜率',
                dataIndex: 'win_rate',
                render: (v) => (
                  <Progress
                    percent={v}
                    size="small"
                    strokeColor={v >= 50 ? '#52c41a' : '#f5222d'}
                    format={(p) => `${p.toFixed(1)}%`}
                  />
                ),
                sorter: (a, b) => a.win_rate - b.win_rate,
              },
              {
                title: '平均评分',
                dataIndex: 'avg_score',
                render: (v) => v.toFixed(1),
                sorter: (a, b) => a.avg_score - b.avg_score,
              },
              {
                title: '选股数',
                dataIndex: 'stock_count',
                sorter: (a, b) => a.stock_count - b.stock_count,
              },
              {
                title: '包含策略',
                dataIndex: 'strategies',
                render: (strats) => (
                  <div style={{ maxWidth: 200 }}>
                    {strats?.map(s => (
                      <Tag key={s} style={{ marginBottom: 2, fontSize: 11 }}>
                        {s.replace(/_/g, ' ')}
                      </Tag>
                    ))}
                  </div>
                ),
              },
            ]}
            pagination={false}
            size="small"
          />
        </Card>
      )}

      {/* 动量信号视图 */}
      {activeView === 'momentum' && (
        <Card
          title="因子动量信号"
          extra={
            <Text type="secondary">
              近期: {momentum?.recent_period} | 历史: {momentum?.older_period}
            </Text>
          }
        >
          <Table
            dataSource={momentumList}
            columns={[
              {
                title: '因子',
                dataIndex: 'name',
                render: (name, record) => (
                  <span>
                    <span style={{ marginRight: 8 }}>{record.icon}</span>
                    {name}
                  </span>
                ),
              },
              {
                title: '动量得分',
                dataIndex: 'momentum_score',
                render: (v) => (
                  <span style={{
                    color: v > 0.1 ? '#f5222d' : v < -0.1 ? '#52c41a' : '#8c8c8c',
                    fontWeight: 'bold',
                  }}>
                    {v > 0 ? '+' : ''}{(v * 100).toFixed(1)}%
                  </span>
                ),
                sorter: (a, b) => a.momentum_score - b.momentum_score,
                defaultSortOrder: 'descend',
              },
              {
                title: '趋势',
                dataIndex: 'trend',
                render: (v) => {
                  const map = {
                    improving: { color: '#f5222d', icon: <ArrowUpOutlined />, text: '改善' },
                    declining: { color: '#52c41a', icon: <ArrowDownOutlined />, text: '衰减' },
                    stable: { color: '#8c8c8c', icon: <MinusOutlined />, text: '稳定' },
                  }
                  const info = map[v] || map.stable
                  return <Tag color={info.color}>{info.icon} {info.text}</Tag>
                },
              },
              {
                title: '近期收益',
                dataIndex: 'recent_return',
                render: (v) => (
                  <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>
                    {(v * 100).toFixed(2)}%
                  </span>
                ),
              },
              {
                title: '历史收益',
                dataIndex: 'older_return',
                render: (v) => (
                  <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a' }}>
                    {(v * 100).toFixed(2)}%
                  </span>
                ),
              },
            ]}
            pagination={false}
            size="small"
            rowClassName={(record) => record.trend === 'improving' ? 'row-highlight' : ''}
          />
          <div style={{ marginTop: 16, padding: 12, background: '#1a1a1a', borderRadius: 8 }}>
            <Text type="secondary">
              💡 <strong>动量信号解读</strong>：正动量 = 因子正在改善，适合重点关注；负动量 = 因子正在衰减，建议回避。
              趋势标签基于动量得分阈值（±10%）判断。
            </Text>
          </div>
        </Card>
      )}

      {/* 轮动选股视图 */}
      {activeView === 'rotation' && (
        <Card
          title="因子轮动选股"
          extra={
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={loadRotation}
              loading={rotationLoading}
            >
              执行轮动选股
            </Button>
          }
        >
          {rotationData?.selected_factors && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>选中因子：</Text>
              {rotationData.selected_factors.map((f) => (
                <Tag key={f.factor} color={FACTOR_COLORS[f.factor]} style={{ marginLeft: 8 }}>
                  {f.icon} {f.name} (动量: {(f.momentum * 100).toFixed(1)}%)
                </Tag>
              ))}
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">
                  执行策略：{rotationData.strategies_executed?.join(', ')}
                </Text>
              </div>
            </div>
          )}

          {rotationData?.stocks ? (
            <Table
              dataSource={rotationData.stocks}
              columns={[
                {
                  title: '排名',
                  render: (_, __, i) => i + 1,
                  width: 60,
                },
                {
                  title: '股票代码',
                  dataIndex: 'ts_code',
                  render: (code) => <Text code>{code}</Text>,
                },
                {
                  title: '名称',
                  dataIndex: 'name',
                  render: (name) => <Text strong>{name}</Text>,
                },
                {
                  title: '综合评分',
                  dataIndex: 'total_score',
                  render: (v) => (
                    <span style={{
                      color: v >= 80 ? '#f5222d' : v >= 50 ? '#faad14' : '#52c41a',
                      fontWeight: 'bold',
                      fontSize: 16,
                    }}>
                      {v.toFixed(1)}
                    </span>
                  ),
                  sorter: (a, b) => a.total_score - b.total_score,
                  defaultSortOrder: 'descend',
                },
                {
                  title: '因子命中',
                  dataIndex: 'factor_hits',
                  render: (v) => (
                    <Tag color={v >= 3 ? 'red' : v >= 2 ? 'orange' : 'blue'}>
                      {v} 个因子
                    </Tag>
                  ),
                },
                {
                  title: '命中因子',
                  dataIndex: 'factors',
                  render: (factors) => (
                    <div>
                      {factors?.map(f => (
                        <Tag key={f} color={FACTOR_COLORS[f]} style={{ marginBottom: 2 }}>
                          {f}
                        </Tag>
                      ))}
                    </div>
                  ),
                },
                {
                  title: '策略详情',
                  dataIndex: 'strategy_details',
                  render: (details) => (
                    <Tooltip
                      title={
                        <div>
                          {details?.map((d, i) => (
                            <div key={i} style={{ marginBottom: 4 }}>
                              <Text strong style={{ color: '#fff' }}>{d.strategy}</Text>
                              <br />
                              <Text style={{ color: '#ddd', fontSize: 12 }}>{d.reason}</Text>
                            </div>
                          ))}
                        </div>
                      }
                    >
                      <Button size="small" type="link">
                        {details?.length || 0} 个策略
                      </Button>
                    </Tooltip>
                  ),
                },
              ]}
              pagination={{ pageSize: 15 }}
              size="small"
              onRow={(record) => ({
                onClick: () => setSelectedStock(record.ts_code),
                style: { cursor: 'pointer' },
              })}
            />
          ) : (
            <Empty description="点击「执行轮动选股」获取结果" />
          )}
        </Card>
      )}
    </div>
  )
}
