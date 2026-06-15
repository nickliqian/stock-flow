import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Row, Col, Spin, Empty, Tag, Segmented, Slider, Table, Badge,
  Alert, Statistic, Space, Typography, Divider, Radio, Tooltip, Button,
  Progress, Drawer, Tabs,
} from 'antd'
import {
  PieChartOutlined, BarChartOutlined, ThunderboltOutlined,
  SwapOutlined, FundOutlined, WarningOutlined, InfoCircleOutlined,
  TrophyOutlined, ApartmentOutlined, BulbOutlined,
} from '@ant-design/icons'
import {
  optimizePortfolio, comparePortfolios, getPortfolioAttribution,
} from '../services/api'

const { Text, Title, Paragraph } = Typography

const METHOD_LABELS = {
  equal_weight: '⚖️ 等权配置',
  risk_parity: '🎯 风险平价',
  mean_variance: '📈 均值方差',
  max_sharpe: '🚀 最大夏普',
}

const METHOD_COLORS = {
  equal_weight: '#8c8c8c',
  risk_parity: '#1677ff',
  mean_variance: '#52c41a',
  max_sharpe: '#faad14',
}

const INDUSTRY_COLORS = [
  '#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#a0d911', '#2f54eb',
  '#f5222d', '#9254de', '#36cfc9', '#ff7a45', '#ffc53d',
]

function formatAmount(val) {
  if (val == null) return '-'
  if (Math.abs(val) >= 10000) return (val / 10000).toFixed(1) + '亿'
  return val.toFixed(0) + '万'
}

function formatPercent(val) {
  if (val == null) return '-'
  return (val >= 0 ? '+' : '') + val.toFixed(2) + '%'
}

function getColorClass(val) {
  if (val > 0) return '#ff4d4f'
  if (val < 0) return '#52c41a'
  return '#8c8c8c'
}

export default function PortfolioBuilder() {
  const [loading, setLoading] = useState(false)
  const [method, setMethod] = useState('mean_variance')
  const [maxStocks, setMaxStocks] = useState(15)
  const [maxSectorPct, setMaxSectorPct] = useState(30)
  const [portfolioData, setPortfolioData] = useState(null)
  const [compareData, setCompareData] = useState(null)
  const [attributionData, setAttributionData] = useState(null)
  const [activeTab, setActiveTab] = useState('optimize')
  const [drawerStock, setDrawerStock] = useState(null)

  const fetchOptimize = useCallback(async () => {
    setLoading(true)
    try {
      const res = await optimizePortfolio(method, maxStocks, maxSectorPct / 100)
      setPortfolioData(res.data || res)
    } catch (e) {
      console.error('Optimize error:', e)
    } finally {
      setLoading(false)
    }
  }, [method, maxStocks, maxSectorPct])

  const fetchCompare = useCallback(async () => {
    setLoading(true)
    try {
      const res = await comparePortfolios()
      setCompareData(res.data || res)
    } catch (e) {
      console.error('Compare error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchAttribution = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getPortfolioAttribution(method)
      setAttributionData(res.data || res)
    } catch (e) {
      console.error('Attribution error:', e)
    } finally {
      setLoading(false)
    }
  }, [method])

  useEffect(() => {
    if (activeTab === 'optimize') fetchOptimize()
    else if (activeTab === 'compare') fetchCompare()
    else if (activeTab === 'attribution') fetchAttribution()
  }, [activeTab, fetchOptimize, fetchCompare, fetchAttribution])

  const portfolio = portfolioData?.portfolio || []
  const analysis = portfolioData?.analysis || {}

  // ==================== 组合持仓表格 ====================
  const portfolioColumns = [
    {
      title: '代码',
      dataIndex: 'ts_code',
      width: 110,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '名称',
      dataIndex: 'name',
      width: 100,
      render: (v, r) => (
        <Tooltip title={`${r.ts_code} | ${r.industry}`}>
          <Text strong>{v}</Text>
        </Tooltip>
      ),
    },
    {
      title: '行业',
      dataIndex: 'industry',
      width: 90,
      render: (v) => <Tag color="blue" style={{ fontSize: 11 }}>{v}</Tag>,
    },
    {
      title: '配置比例',
      dataIndex: 'allocation_pct',
      width: 140,
      sorter: (a, b) => a.allocation_pct - b.allocation_pct,
      defaultSortOrder: 'descend',
      render: (v) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Progress
            percent={v}
            size="small"
            strokeColor={v > 10 ? '#ff4d4f' : v > 7 ? '#faad14' : '#52c41a'}
            style={{ width: 80, margin: 0 }}
            format={() => ''}
          />
          <Text strong style={{ color: v > 10 ? '#ff4d4f' : undefined }}>{v}%</Text>
        </div>
      ),
    },
    {
      title: 'PE(TTM)',
      dataIndex: 'pe_ttm',
      width: 90,
      sorter: (a, b) => (a.pe_ttm || 0) - (b.pe_ttm || 0),
      render: (v) => v != null ? v.toFixed(1) : '-',
    },
    {
      title: '策略数',
      dataIndex: 'strategy_count',
      width: 80,
      sorter: (a, b) => a.strategy_count - b.strategy_count,
      render: (v) => <Badge count={v} style={{ backgroundColor: v >= 3 ? '#ff4d4f' : '#1677ff' }} />,
    },
    {
      title: '评分',
      dataIndex: 'score',
      width: 80,
      sorter: (a, b) => a.score - b.score,
      render: (v) => <Text style={{ color: getColorClass(v - 50) }}>{v}</Text>,
    },
  ]

  // ==================== 分析卡片 ====================
  const renderAnalysisCards = () => {
    if (!analysis || !analysis.stock_count) return null
    return (
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card size="small">
            <Statistic title="持仓数" value={analysis.stock_count} suffix="只" />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="组合PE" value={analysis.weighted_pe} precision={1} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="组合市值" value={analysis.weighted_mv_yi} precision={1} suffix="亿" />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="股息率" value={analysis.weighted_dv_ratio} precision={2} suffix="%" />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="分散度"
              value={analysis.diversification_score}
              precision={1}
              suffix="/100"
              valueStyle={{ color: analysis.diversification_score > 60 ? '#52c41a' : '#faad14' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="最大单只" value={analysis.max_single_weight} precision={1} suffix="%" />
          </Card>
        </Col>
      </Row>
    )
  }

  // ==================== 行业分布 ====================
  const renderSectorDistribution = () => {
    const sectors = analysis.sector_concentration || {}
    const entries = Object.entries(sectors)
    if (entries.length === 0) return null

    return (
      <Card size="small" title="行业分布" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {entries.map(([name, pct], i) => (
            <Tooltip key={name} title={`${name}: ${pct}%`}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 10px', borderRadius: 4,
                background: `${INDUSTRY_COLORS[i % INDUSTRY_COLORS.length]}15`,
                border: `1px solid ${INDUSTRY_COLORS[i % INDUSTRY_COLORS.length]}40`,
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: INDUSTRY_COLORS[i % INDUSTRY_COLORS.length],
                }} />
                <Text style={{ fontSize: 12 }}>{name}</Text>
                <Text strong style={{ fontSize: 12, color: INDUSTRY_COLORS[i % INDUSTRY_COLORS.length] }}>
                  {pct}%
                </Text>
              </div>
            </Tooltip>
          ))}
        </div>
      </Card>
    )
  }

  // ==================== 对比视图 ====================
  const renderCompareView = () => {
    if (!compareData) return <Spin spinning={loading} />

    const methods = Object.keys(compareData)
    const summaryData = methods.map(m => ({
      method: m,
      label: METHOD_LABELS[m] || m,
      count: compareData[m]?.portfolio?.length || 0,
      pe: compareData[m]?.analysis?.weighted_pe,
      mv: compareData[m]?.analysis?.weighted_mv_yi,
      sectors: compareData[m]?.analysis?.sector_count,
      diversification: compareData[m]?.analysis?.diversification_score,
      top5: compareData[m]?.analysis?.top5_concentration_pct,
      maxSingle: compareData[m]?.analysis?.max_single_weight,
    }))

    const compareColumns = [
      { title: '方法', dataIndex: 'label', width: 130, render: (v, r) => <Text strong style={{ color: METHOD_COLORS[r.method] }}>{v}</Text> },
      { title: '持仓数', dataIndex: 'count', width: 80 },
      { title: '组合PE', dataIndex: 'pe', width: 90, render: (v) => v?.toFixed(1) || '-' },
      { title: '市值(亿)', dataIndex: 'mv', width: 90, render: (v) => v?.toFixed(1) || '-' },
      { title: '行业数', dataIndex: 'sectors', width: 80 },
      { title: '分散度', dataIndex: 'diversification', width: 90, render: (v) => v?.toFixed(1) || '-' },
      { title: 'Top5集中', dataIndex: 'top5', width: 90, render: (v) => v?.toFixed(1) + '%' || '-' },
      { title: '最大单只', dataIndex: 'maxSingle', width: 90, render: (v) => v?.toFixed(1) + '%' || '-' },
    ]

    return (
      <div>
        <Card size="small" title="📊 四种优化方法对比" style={{ marginBottom: 16 }}>
          <Table
            dataSource={summaryData}
            columns={compareColumns}
            rowKey="method"
            pagination={false}
            size="small"
            bordered
          />
        </Card>

        <Row gutter={16}>
          {methods.map(m => {
            const p = compareData[m]?.portfolio || []
            const a = compareData[m]?.analysis || {}
            return (
              <Col span={12} key={m}>
                <Card
                  size="small"
                  title={METHOD_LABELS[m]}
                  style={{ marginBottom: 16 }}
                  headStyle={{ color: METHOD_COLORS[m] }}
                  extra={<Tag color={METHOD_COLORS[m]}>{p.length}只</Tag>}
                >
                  {p.slice(0, 8).map((s, i) => (
                    <div key={s.ts_code} style={{
                      display: 'flex', justifyContent: 'space-between',
                      padding: '3px 0', borderBottom: '1px solid #f0f0f0',
                    }}>
                      <Text style={{ fontSize: 12 }}>
                        <span style={{ color: '#8c8c8c', marginRight: 4 }}>{i + 1}.</span>
                        {s.name}
                      </Text>
                      <Text strong style={{ fontSize: 12, color: METHOD_COLORS[m] }}>
                        {s.allocation_pct}%
                      </Text>
                    </div>
                  ))}
                  {p.length > 8 && (
                    <Text type="secondary" style={{ fontSize: 11 }}>...还有{p.length - 8}只</Text>
                  )}
                </Card>
              </Col>
            )
          })}
        </Row>
      </div>
    )
  }

  // ==================== 归因视图 ====================
  const renderAttributionView = () => {
    if (!attributionData) return <Spin spinning={loading} />

    const { stock_attribution = [], industry_attribution = [], factor_exposure = {}, total_contribution_1d } = attributionData

    return (
      <div>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="组合日收益"
                value={total_contribution_1d}
                precision={4}
                suffix="%"
                valueStyle={{ color: getColorClass(total_contribution_1d) }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic title="平均PE" value={factor_exposure.avg_pe} precision={1} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic title="平均市值" value={factor_exposure.avg_mv_yi} precision={1} suffix="亿" />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic title="风格偏向" value={factor_exposure.growth_bias === 'value' ? '价值' : '成长'} />
            </Card>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={12}>
            <Card size="small" title="📈 个股贡献" style={{ marginBottom: 16 }}>
              {stock_attribution.filter(s => s.contribution_1d != null).slice(0, 15).map((s, i) => (
                <div key={s.ts_code} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '4px 0', borderBottom: '1px solid #f0f0f0',
                }}>
                  <Text style={{ fontSize: 12 }}>
                    <span style={{ color: '#8c8c8c', marginRight: 4 }}>{i + 1}.</span>
                    {s.ts_code}
                  </Text>
                  <Space size={12}>
                    <Text type="secondary" style={{ fontSize: 11 }}>权重{s.weight}%</Text>
                    <Text style={{ fontSize: 12, color: getColorClass(s.contribution_1d) }}>
                      {s.contribution_1d > 0 ? '+' : ''}{s.contribution_1d.toFixed(4)}%
                    </Text>
                  </Space>
                </div>
              ))}
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="🏭 行业贡献" style={{ marginBottom: 16 }}>
              {industry_attribution.map((ind, i) => (
                <div key={ind.industry} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '4px 0', borderBottom: '1px solid #f0f0f0',
                }}>
                  <Space>
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: INDUSTRY_COLORS[i % INDUSTRY_COLORS.length],
                    }} />
                    <Text style={{ fontSize: 12 }}>{ind.industry}</Text>
                    <Text type="secondary" style={{ fontSize: 11 }}>({ind.stock_count}只)</Text>
                  </Space>
                  <Text style={{ fontSize: 12, color: getColorClass(ind.contribution_1d) }}>
                    {ind.contribution_1d > 0 ? '+' : ''}{ind.contribution_1d.toFixed(4)}%
                  </Text>
                </div>
              ))}
            </Card>
          </Col>
        </Row>
      </div>
    )
  }

  return (
    <div style={{ padding: '0 16px' }}>
      {/* 控制面板 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col>
            <Text strong>优化方法：</Text>
            <Segmented
              value={method}
              onChange={setMethod}
              options={Object.entries(METHOD_LABELS).map(([k, v]) => ({ label: v, value: k }))}
              size="small"
            />
          </Col>
          <Col>
            <Text strong>最大持仓：</Text>
            <Slider
              value={maxStocks}
              onChange={setMaxStocks}
              min={5}
              max={30}
              style={{ width: 120 }}
              tooltip={{ formatter: (v) => `${v}只` }}
            />
          </Col>
          <Col>
            <Text strong>行业上限：</Text>
            <Slider
              value={maxSectorPct}
              onChange={setMaxSectorPct}
              min={10}
              max={50}
              step={5}
              style={{ width: 120 }}
              tooltip={{ formatter: (v) => `${v}%` }}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={fetchOptimize} loading={loading}>
              🔄 重新优化
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 标签页 */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'optimize',
            label: '📈 组合优化',
            children: (
              <Spin spinning={loading}>
                {renderAnalysisCards()}
                {renderSectorDistribution()}
                <Card size="small" title="组合持仓">
                  <Table
                    dataSource={portfolio}
                    columns={portfolioColumns}
                    rowKey="ts_code"
                    pagination={false}
                    size="small"
                    scroll={{ x: 700 }}
                  />
                </Card>
              </Spin>
            ),
          },
          {
            key: 'compare',
            label: '⚖️ 方法对比',
            children: renderCompareView(),
          },
          {
            key: 'attribution',
            label: '📊 绩效归因',
            children: renderAttributionView(),
          },
        ]}
      />

      {/* 创新说明 */}
      <Alert
        message="量化组合构建器"
        description="将策略信号转化为最优组合配置：均值方差优化（Markowitz）、风险平价（Risk Parity）、最大夏普比率、等权基准。支持行业约束、风险预算和绩效归因分析。"
        type="info"
        showIcon
        icon={<BulbOutlined />}
        style={{ marginTop: 16 }}
      />
    </div>
  )
}
