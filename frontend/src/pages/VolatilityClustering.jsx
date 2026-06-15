import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Card, Row, Col, Statistic, Table, Tag, Spin, Typography, Input, Empty, Progress,
  Space, Divider, Tooltip, Badge, Tabs, Button, Segmented,
} from 'antd'
import {
  ReloadOutlined, SearchOutlined, WarningOutlined, ExperimentOutlined,
  ThunderboltOutlined, BarChartOutlined, SafetyOutlined, RiseOutlined,
  FallOutlined, InfoCircleOutlined, DotChartOutlined,
} from '@ant-design/icons'
import { apiCall, searchStocks } from '../services/api'

const { Text, Title, Paragraph } = Typography

/* =====================================================================
 * 常量 & 工具函数
 * ===================================================================== */

const RISK_COLORS = {
  1: '#52c41a',
  2: '#73d13d',
  3: '#faad14',
  4: '#ff7a45',
  5: '#f5222d',
}

const RISK_LABELS = {
  1: '极低风险',
  2: '低风险',
  3: '中等风险',
  4: '高风险',
  5: '极高风险',
}

const RISK_EMOJI = {
  1: '🟢',
  2: '🟢',
  3: '🟡',
  4: '🟠',
  5: '🔴',
}

function volColor(vol) {
  if (vol >= 60) return '#f5222d'
  if (vol >= 40) return '#ff7a45'
  if (vol >= 25) return '#faad14'
  if (vol >= 15) return '#73d13d'
  return '#52c41a'
}

function riskTag(zone) {
  if (!zone) return <Tag>-</Tag>
  return (
    <Tag color={zone.color} style={{ borderRadius: 4, fontWeight: 600 }}>
      {zone.emoji} {zone.label}
    </Tag>
  )
}

/* =====================================================================
 * Tab 1 — 全市场波动率概览
 * ===================================================================== */

function MarketVolatilityOverview() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [tab, setTab] = useState('stocks')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiCall('/volatility/market')
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load volatility data:', err)
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" tip="正在计算全市场波动率..." />
      </div>
    )
  }

  if (data?.error) {
    return <Empty description={data.error} />
  }

  const stats = data?.market_stats || {}
  const zones = data?.zone_distribution || []
  const industries = data?.industry_summary || []
  const stocks = data?.stock_results || []

  // 风险分区最大值（用于进度条宽度计算）
  const maxZoneCount = Math.max(...zones.map(z => z.count), 1)

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={8} md={4}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic title="分析股票数" value={stats.total_stocks} valueStyle={{ color: '#1677ff' }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic title="平均波动率" value={stats.avg_volatility} suffix="%" valueStyle={{ color: volColor(stats.avg_volatility) }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic title="中位数波动率" value={stats.median_volatility} suffix="%" valueStyle={{ color: volColor(stats.median_volatility) }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic title="最高波动率" value={stats.max_volatility} suffix="%" valueStyle={{ color: '#f5222d' }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic title="最低波动率" value={stats.min_volatility} suffix="%" valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic title="波动率标准差" value={stats.vol_std} suffix="%" valueStyle={{ color: '#8c8c8c' }} />
          </Card>
        </Col>
      </Row>

      {/* 风险分区分布 */}
      <Card
        title="📊 风险分区分布"
        size="small"
        style={{ marginTop: 16 }}
        bordered={false}
      >
        {zones.map(zone => (
          <div key={zone.level} style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ width: 110, textAlign: 'right', paddingRight: 12, flexShrink: 0 }}>
              <Text style={{ color: zone.color, fontWeight: 600, fontSize: 13 }}>
                {zone.emoji} {zone.label}
              </Text>
            </div>
            <div style={{ flex: 1, position: 'relative', height: 24, background: 'rgba(255,255,255,0.04)', borderRadius: 4 }}>
              <div
                style={{
                  width: `${(zone.count / maxZoneCount) * 100}%`,
                  height: '100%',
                  background: zone.color,
                  borderRadius: 4,
                  opacity: 0.85,
                  transition: 'width 0.6s ease',
                }}
              />
              <span style={{
                position: 'absolute',
                right: 8,
                top: '50%',
                transform: 'translateY(-50%)',
                fontSize: 12,
                fontWeight: 600,
                color: 'rgba(0,0,0,0.75)',
              }}>
                {zone.count} 只 ({zone.percentage}%)
              </span>
            </div>
          </div>
        ))}
      </Card>

      {/* Tabs: 行业热力图 / 高波动股票 */}
      <Card
        size="small"
        style={{ marginTop: 16 }}
        bordered={false}
        tabList={[
          { key: 'stocks', tab: '🔴 高波动股票 TOP 100' },
          { key: 'industries', tab: '🏭 行业波动率排名' },
        ]}
        activeTabKey={tab}
        onTabChange={setTab}
      >
        {tab === 'stocks' ? (
          <StockVolatilityTable stocks={stocks} />
        ) : (
          <IndustryVolatilityTable industries={industries} />
        )}
      </Card>
    </div>
  )
}


/* =====================================================================
 * 股票波动率排行表格
 * ===================================================================== */

function StockVolatilityTable({ stocks }) {
  const columns = [
    {
      title: '序号',
      key: 'idx',
      width: 55,
      align: 'center',
      render: (_, __, i) => i + 1,
    },
    {
      title: '代码 / 名称',
      key: 'stock',
      render: (_, r) => (
        <div>
          <Text code style={{ fontSize: 12 }}>{r.ts_code}</Text>
          <br />
          <Text strong style={{ fontSize: 13 }}>{r.name}</Text>
        </div>
      ),
    },
    {
      title: '行业',
      dataIndex: 'industry',
      width: 110,
    },
    {
      title: '年化波动率',
      dataIndex: 'volatility',
      width: 130,
      sorter: (a, b) => a.volatility - b.volatility,
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ color: volColor(v), fontWeight: 'bold', fontSize: 15 }}>
          {v}%
        </span>
      ),
    },
    {
      title: '波动率条',
      dataIndex: 'volatility',
      width: 180,
      render: (v) => (
        <Progress
          percent={Math.min(v, 100)}
          strokeColor={volColor(v)}
          size="small"
          showInfo={false}
        />
      ),
    },
    {
      title: '风险分区',
      dataIndex: 'risk_zone',
      width: 130,
      render: (zone) => riskTag(zone),
    },
  ]

  return (
    <Table
      dataSource={stocks}
      columns={columns}
      rowKey="ts_code"
      size="small"
      pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 只` }}
      scroll={{ x: 650 }}
    />
  )
}


/* =====================================================================
 * 行业波动率排行表格
 * ===================================================================== */

function IndustryVolatilityTable({ industries }) {
  const columns = [
    {
      title: '序号',
      key: 'idx',
      width: 55,
      align: 'center',
      render: (_, __, i) => i + 1,
    },
    {
      title: '行业',
      dataIndex: 'industry',
      width: 140,
    },
    {
      title: '平均波动率',
      dataIndex: 'avg_volatility',
      width: 130,
      sorter: (a, b) => a.avg_volatility - b.avg_volatility,
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ color: volColor(v), fontWeight: 'bold', fontSize: 15 }}>
          {v}%
        </span>
      ),
    },
    {
      title: '波动率条',
      dataIndex: 'avg_volatility',
      width: 180,
      render: (v) => (
        <Progress
          percent={Math.min(v, 100)}
          strokeColor={volColor(v)}
          size="small"
          showInfo={false}
        />
      ),
    },
    {
      title: '股票数',
      dataIndex: 'stock_count',
      width: 80,
      sorter: (a, b) => a.stock_count - b.stock_count,
    },
    {
      title: '风险分区',
      dataIndex: 'risk_zone',
      width: 130,
      render: (zone) => riskTag(zone),
    },
  ]

  return (
    <Table
      dataSource={industries}
      columns={columns}
      rowKey="industry"
      size="small"
      pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 个行业` }}
      scroll={{ x: 600 }}
    />
  )
}


/* =====================================================================
 * Tab 2 — 单股波动率详情
 * ===================================================================== */

function StockVolatilityDetail() {
  const [searchValue, setSearchValue] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [detail, setDetail] = useState(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const handleSearch = useCallback(async (val) => {
    if (!val || val.length < 1) {
      setSearchResults([])
      return
    }
    setSearching(true)
    try {
      const res = await searchStocks(val)
      setSearchResults((res?.data || res || []).slice(0, 10))
    } catch {
      setSearchResults([])
    }
    setSearching(false)
  }, [])

  const handleSelectStock = useCallback(async (tsCode) => {
    setLoadingDetail(true)
    setSearchResults([])
    try {
      const res = await apiCall(`/volatility/stock/${tsCode}`)
      setDetail(res)
    } catch (err) {
      console.error('Failed to load stock detail:', err)
    }
    setLoadingDetail(false)
  }, [])

  if (loadingDetail) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" tip="正在加载股票波动率详情..." />
      </div>
    )
  }

  return (
    <div>
      {/* 搜索框 */}
      <Card size="small" bordered={false} style={{ marginBottom: 16 }}>
        <Space>
          <Input
            prefix={<SearchOutlined />}
            placeholder="输入股票代码或名称搜索"
            value={searchValue}
            onChange={(e) => {
              setSearchValue(e.target.value)
              handleSearch(e.target.value)
            }}
            style={{ width: 300 }}
            allowClear
          />
          {searching && <Spin size="small" />}
        </Space>
        {searchResults.length > 0 && (
          <div style={{
            marginTop: 8,
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            background: '#fff',
            maxHeight: 240,
            overflow: 'auto',
          }}>
            {searchResults.map(s => (
              <div
                key={s.ts_code}
                onClick={() => {
                  handleSelectStock(s.ts_code)
                  setSearchValue(`${s.name} (${s.ts_code})`)
                }}
                style={{
                  padding: '8px 12px',
                  cursor: 'pointer',
                  borderBottom: '1px solid #f0f0f0',
                  display: 'flex',
                  justifyContent: 'space-between',
                }}
              >
                <span>
                  <Text code style={{ fontSize: 12, marginRight: 8 }}>{s.ts_code}</Text>
                  <Text strong>{s.name}</Text>
                </span>
                <Text type="secondary" style={{ fontSize: 12 }}>{s.industry || ''}</Text>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 详情展示 */}
      {detail?.error && <Empty description={detail.error} />}

      {detail && !detail.error && (
        <StockDetailContent detail={detail} />
      )}

      {!detail && (
        <Empty
          description="请搜索并选择一只股票查看波动率详情"
          style={{ marginTop: 60 }}
        />
      )}
    </div>
  )
}


/* =====================================================================
 * 股票详情内容
 * ===================================================================== */

function StockDetailContent({ detail }) {
  const zone = detail.risk_zone || {}
  const returns = detail.daily_returns || []
  const priceSeries = detail.price_series || []
  const ctx = detail.market_context || {}

  return (
    <div>
      {/* 头部信息 */}
      <Card size="small" bordered={false} style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col>
            <Title level={4} style={{ margin: 0 }}>
              {detail.name}
              <Text code style={{ marginLeft: 8, fontSize: 13 }}>{detail.ts_code}</Text>
            </Title>
          </Col>
          <Col>
            <Tag color="blue">{detail.industry}</Tag>
          </Col>
          <Col>
            {riskTag(zone)}
          </Col>
        </Row>
      </Card>

      {/* 核心指标 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic
              title="年化波动率"
              value={detail.volatility}
              suffix="%"
              valueStyle={{ color: volColor(detail.volatility), fontSize: 24, fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic
              title="全市场百分位"
              value={detail.percentile}
              suffix="%"
              valueStyle={{ color: '#1677ff', fontSize: 24, fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic
              title="市场平均波动率"
              value={ctx.market_avg_vol}
              suffix="%"
              valueStyle={{ color: '#8c8c8c', fontSize: 24, fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Statistic
              title="市场中位数波动率"
              value={ctx.market_median_vol}
              suffix="%"
              valueStyle={{ color: '#8c8c8c', fontSize: 24, fontWeight: 700 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 波动率在市场中的位置 */}
      <Card size="small" title="📊 波动率市场位置" bordered={false} style={{ marginTop: 16 }}>
        <div style={{ position: 'relative', height: 40, background: 'linear-gradient(90deg, #52c41a 0%, #faad14 50%, #f5222d 100%)', borderRadius: 6, opacity: 0.3 }}>
          <div
            style={{
              position: 'absolute',
              left: `${Math.min(detail.percentile, 100)}%`,
              top: -4,
              transform: 'translateX(-50%)',
              width: 4,
              height: 48,
              background: '#1677ff',
              borderRadius: 2,
              boxShadow: '0 0 8px rgba(22,119,255,0.5)',
            }}
          />
          <span style={{
            position: 'absolute',
            left: `${Math.min(detail.percentile, 100)}%`,
            top: -22,
            transform: 'translateX(-50%)',
            fontSize: 12,
            fontWeight: 700,
            color: '#1677ff',
            whiteSpace: 'nowrap',
          }}>
            {detail.volatility}% (P{detail.percentile})
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>🟢 低波动</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>🟡 中等</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>🔴 高波动</Text>
        </div>
      </Card>

      {/* 价格序列 & 日收益率 */}
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card size="small" title="📈 价格序列" bordered={false}>
            <Table
              dataSource={priceSeries}
              rowKey="date"
              size="small"
              pagination={false}
              columns={[
                { title: '日期', dataIndex: 'date', width: 100 },
                { title: '收盘价', dataIndex: 'close', render: v => <Text strong>¥{v}</Text> },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card size="small" title="📊 日收益率" bordered={false}>
            <Table
              dataSource={returns}
              rowKey="date"
              size="small"
              pagination={false}
              columns={[
                { title: '日期', dataIndex: 'date', width: 100 },
                {
                  title: '收益率',
                  dataIndex: 'return',
                  render: v => (
                    <span style={{ color: v >= 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>
                      {v >= 0 ? '+' : ''}{v}%
                    </span>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}


/* =====================================================================
 * Tab 3 — 板块风险分布
 * ===================================================================== */

function SectorRiskSummary() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiCall('/volatility/sectors')
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load sector risk data:', err)
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" tip="正在计算板块风险分布..." />
      </div>
    )
  }

  if (data?.error) {
    return <Empty description={data.error} />
  }

  const sectors = data?.sectors || []

  const columns = [
    {
      title: '序号',
      key: 'idx',
      width: 55,
      align: 'center',
      render: (_, __, i) => i + 1,
    },
    {
      title: '板块名称',
      dataIndex: 'sector_name',
      width: 150,
    },
    {
      title: '平均波动率',
      dataIndex: 'avg_volatility',
      width: 130,
      sorter: (a, b) => a.avg_volatility - b.avg_volatility,
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ color: volColor(v), fontWeight: 'bold', fontSize: 15 }}>
          {v}%
        </span>
      ),
    },
    {
      title: '波动率条',
      dataIndex: 'avg_volatility',
      width: 160,
      render: (v) => (
        <Progress
          percent={Math.min(v, 100)}
          strokeColor={volColor(v)}
          size="small"
          showInfo={false}
        />
      ),
    },
    {
      title: '成分股数',
      dataIndex: 'stock_count',
      width: 90,
      sorter: (a, b) => a.stock_count - b.stock_count,
    },
    {
      title: '高风险股',
      dataIndex: 'high_risk_count',
      width: 90,
      render: (v) => v > 0 ? <Tag color="red">{v}</Tag> : <Text type="secondary">0</Text>,
    },
    {
      title: '低风险股',
      dataIndex: 'low_risk_count',
      width: 90,
      render: (v) => v > 0 ? <Tag color="green">{v}</Tag> : <Text type="secondary">0</Text>,
    },
    {
      title: 'Top 高波动股',
      key: 'top_stocks',
      render: (_, r) => (
        <Space size={4} wrap>
          {(r.top_stocks || []).slice(0, 3).map(s => (
            <Tooltip key={s.ts_code} title={`${s.ts_code} — 波动率 ${s.volatility}%`}>
              <Tag style={{ fontSize: 11, cursor: 'default' }}>
                {s.ts_code.split('.')[0]} {s.volatility}%
              </Tag>
            </Tooltip>
          ))}
        </Space>
      ),
    },
  ]

  return (
    <Card size="small" bordered={false}>
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">
          共 {data.sector_count} 个板块 · 分析日期 {data.trade_dates?.join(', ')}
        </Text>
      </div>
      <Table
        dataSource={sectors}
        columns={columns}
        rowKey="sector_code"
        size="small"
        pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 个板块` }}
        scroll={{ x: 850 }}
      />
    </Card>
  )
}


/* =====================================================================
 * 主页面
 * ===================================================================== */

export default function VolatilityClustering() {
  const [activeTab, setActiveTab] = useState('overview')

  const tabItems = [
    {
      key: 'overview',
      label: '📊 全市场概览',
      children: <MarketVolatilityOverview />,
    },
    {
      key: 'stock',
      label: '🔍 单股波动率',
      children: <StockVolatilityDetail />,
    },
    {
      key: 'sectors',
      label: '🎯 板块风险分布',
      children: <SectorRiskSummary />,
    },
  ]

  return (
    <div>
      {/* 页面标题 */}
      <Card
        bordered={false}
        style={{ marginBottom: 16 }}
        bodyStyle={{ paddingBottom: 0 }}
      >
        <Row justify="space-between" align="middle">
          <Col>
            <Space align="center">
              <ThunderboltOutlined style={{ fontSize: 22, color: '#1677ff' }} />
              <Title level={4} style={{ margin: 0 }}>波动率聚类与风险分区</Title>
              <Tooltip title="基于价格序列计算年化波动率，按百分位分为5个风险等级，辅助投资组合风险管理">
                <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
              </Tooltip>
            </Space>
          </Col>
        </Row>
        <Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 13 }}>
          计算全市场股票的历史波动率，聚类为 5 个风险等级（极低/低/中/高/极高），
          按行业和板块聚合风险分布，提供基于风险的板块配置建议
        </Paragraph>
      </Card>

      {/* Tab 内容 */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        destroyInactiveTabPane
      />
    </div>
  )
}
