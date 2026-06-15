import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Tabs, Space,
  Spin, Input, Segmented, Empty, message, Badge, Typography,
} from 'antd'
import {
  ReloadOutlined, SearchOutlined, ArrowUpOutlined, ArrowDownOutlined,
  RiseOutlined, FallOutlined,
} from '@ant-design/icons'
import { apiCall } from '../services/api'

const { Text, Title } = Typography

const API_BASE = ''

const COLORS = {
  increase: '#cf1322',
  decrease: '#3f8600',
  primary: '#1677ff',
  warning: '#faad14',
  muted: '#999999',
}

const cardStyle = { background: '#ffffff', border: '1px solid #e8e8e8' }

/**
 * 股东情报仪表板
 * 从股东增减持、人数变动、前十大股东三个维度洞察市场
 */
export default function ShareholderIntelligence() {
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('trade')
  const [lookbackDays, setLookbackDays] = useState(30)

  // Tab 1: Holder Trade
  const [tradeData, setTradeData] = useState(null)
  const [tradeFilter, setTradeFilter] = useState('all')

  // Tab 2: Holder Number
  const [holderNumData, setHolderNumData] = useState(null)
  const [holderNumCode, setHolderNumCode] = useState('')

  // Tab 3: Top Holders
  const [topHoldersData, setTopHoldersData] = useState(null)
  const [topHoldersCode, setTopHoldersCode] = useState('')

  // Tab 4: Comprehensive
  const [comprehensiveData, setComprehensiveData] = useState(null)

  // ============================================================
  // Data Fetching
  // ============================================================

  const fetchTradeData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const res = await apiCall(`${API_BASE}/shareholder/holder-trade?lookback_days=${lookbackDays}`)
      if (res?.data) {
        setTradeData(res.data)
      } else if (res?.success === false) {
        message.error(res?.error || '获取增减持数据失败')
      } else {
        setTradeData(res)
      }
    } catch (err) {
      console.error('Failed to load holder trade data:', err)
      message.error('增减持数据加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [lookbackDays])

  const fetchHolderNumData = useCallback(async (tsCode, signal) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ lookback_days: String(lookbackDays) })
      if (tsCode) params.set('ts_code', tsCode)
      const res = await apiCall(`${API_BASE}/shareholder/holder-num?${params.toString()}`)
      const d = res?.data || res
      setHolderNumData(d)
    } catch (err) {
      console.error('Failed to load holder num data:', err)
      message.error('股东人数数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [lookbackDays])

  const fetchTopHoldersData = useCallback(async (tsCode, signal) => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (tsCode) params.set('ts_code', tsCode)
      const res = await apiCall(`${API_BASE}/shareholder/top-holders?${params.toString()}`)
      const d = res?.data || res
      setTopHoldersData(d)
    } catch (err) {
      console.error('Failed to load top holders data:', err)
      message.error('股权结构数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchComprehensiveData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const res = await apiCall(`${API_BASE}/shareholder/comprehensive?lookback_days=${lookbackDays}`)
      const d = res?.data || res
      setComprehensiveData(d)
    } catch (err) {
      console.error('Failed to load comprehensive data:', err)
      message.error('综合评分数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [lookbackDays])

  // Auto-fetch on lookbackDays change for tabs that use it
  useEffect(() => {
    if (activeTab === 'trade') fetchTradeData()
    if (activeTab === 'comprehensive') fetchComprehensiveData()
  }, [lookbackDays, activeTab, fetchTradeData, fetchComprehensiveData])

  // Tab change triggers load for that tab
  useEffect(() => {
    if (activeTab === 'trade' && !tradeData) fetchTradeData()
    if (activeTab === 'holderNum' && !holderNumData) fetchHolderNumData('')
    if (activeTab === 'topHolders' && !topHoldersData) fetchTopHoldersData('')
    if (activeTab === 'comprehensive' && !comprehensiveData) fetchComprehensiveData()
  }, [activeTab]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = () => {
    if (activeTab === 'trade') fetchTradeData()
    if (activeTab === 'holderNum') fetchHolderNumData(holderNumCode)
    if (activeTab === 'topHolders') fetchTopHoldersData(topHoldersCode)
    if (activeTab === 'comprehensive') fetchComprehensiveData()
  }

  // ============================================================
  // Tab 1: 增减持动态 (Holder Trade)
  // ============================================================

  const filteredTradeStocks = (() => {
    if (!tradeData?.stocks) return []
    let list = tradeData.stocks
    if (tradeFilter === 'increase') list = list.filter(s => s.change_type === '增持' || s.change_type === 'increase')
    if (tradeFilter === 'decrease') list = list.filter(s => s.change_type === '减持' || s.change_type === 'decrease')
    return [...list].sort((a, b) => Math.abs(b.change_shares || 0) - Math.abs(a.change_shares || 0))
  })()

  const tradeSummary = tradeData?.summary || {}

  const tradeColumns = [
    {
      title: '股票代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '股东名称',
      dataIndex: 'holder_name',
      key: 'holder_name',
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'change_type',
      key: 'change_type',
      width: 80,
      render: (v) => {
        const isIncrease = v === '增持' || v === 'increase'
        return (
          <Tag color={isIncrease ? COLORS.increase : COLORS.decrease}>
            {isIncrease ? '增持' : '减持'}
          </Tag>
        )
      },
    },
    {
      title: '变动股数',
      dataIndex: 'change_shares',
      key: 'change_shares',
      width: 140,
      sorter: (a, b) => (a.change_shares || 0) - (b.change_shares || 0),
      defaultSortOrder: 'descend',
      render: (v) => {
        if (v == null) return '--'
        const isIncrease = v > 0
        return (
          <span style={{ color: isIncrease ? COLORS.increase : COLORS.decrease, fontWeight: 600 }}>
            {isIncrease ? '+' : ''}{v.toLocaleString()}
          </span>
        )
      },
    },
    {
      title: '变动比例%',
      dataIndex: 'change_ratio_pct',
      key: 'change_ratio_pct',
      width: 100,
      render: (v) => v != null ? `${Number(v).toFixed(2)}%` : '--',
    },
    {
      title: '持股比例%',
      dataIndex: 'after_ratio_pct',
      key: 'after_ratio_pct',
      width: 100,
      render: (v) => v != null ? `${Number(v).toFixed(2)}%` : '--',
    },
    {
      title: '公告日期',
      dataIndex: 'ann_date',
      key: 'ann_date',
      width: 110,
    },
  ]

  // ============================================================
  // Tab 2: 筹码集中度 (Holder Number)
  // ============================================================

  const holderNumStocks = holderNumData?.stocks || []
  const holderNumSummary = holderNumData?.summary || {}

  const holderNumColumns = [
    {
      title: '股票代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '最新股东户数',
      dataIndex: 'latest_holder_num',
      key: 'latest_holder_num',
      width: 120,
      render: (v) => v != null ? v.toLocaleString() : '--',
    },
    {
      title: '最初股东户数',
      dataIndex: 'earliest_holder_num',
      key: 'earliest_holder_num',
      width: 120,
      render: (v) => v != null ? v.toLocaleString() : '--',
    },
    {
      title: '变化幅度%',
      dataIndex: 'change_pct',
      key: 'change_pct',
      width: 100,
      render: (v) => {
        if (v == null) return '--'
        const color = v < 0 ? COLORS.decrease : v > 0 ? COLORS.increase : COLORS.muted
        return <span style={{ color, fontWeight: 600 }}>{Number(v).toFixed(2)}%</span>
      },
    },
    {
      title: '趋势',
      dataIndex: 'trend_label',
      key: 'trend_label',
      width: 100,
      render: (v, record) => {
        const trend = record.trend || v
        const colorMap = {
          concentrating: 'blue',
          集中: 'blue',
          dispersing: 'orange',
          分散: 'orange',
          stable: 'default',
          稳定: 'default',
        }
        return <Tag color={colorMap[trend] || 'default'}>{v || trend || '--'}</Tag>
      },
    },
    {
      title: '趋势历史',
      dataIndex: 'history',
      key: 'history',
      ellipsis: true,
      render: (history) => {
        if (!history || !Array.isArray(history) || history.length === 0) return '--'
        // Show last 5 data points as text
        const recent = history.slice(-5)
        return (
          <Space size={2}>
            {recent.map((h, i) => {
              const num = h.holder_num || h
              const prevNum = i > 0 ? (recent[i - 1].holder_num || recent[i - 1]) : null
              const diff = prevNum != null ? num - prevNum : 0
              const color = diff < 0 ? COLORS.decrease : diff > 0 ? COLORS.increase : COLORS.muted
              return (
                <span key={i} style={{ fontSize: 11, color }}>
                  {typeof num === 'number' ? num.toLocaleString() : num}
                </span>
              )
            })}
          </Space>
        )
      },
    },
  ]

  // ============================================================
  // Tab 3: 股权结构 (Top Holders)
  // ============================================================

  const topHoldersStocks = topHoldersData?.stocks || []
  const topHoldersSummary = topHoldersData?.summary || {}

  const topHoldersColumns = [
    {
      title: '股票代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: 'TOP10集中度%',
      dataIndex: 'top10_ratio_pct',
      key: 'top10_ratio_pct',
      width: 130,
      render: (v) => v != null ? `${Number(v).toFixed(2)}%` : '--',
    },
    {
      title: '集中度等级',
      dataIndex: 'concentration_level',
      key: 'concentration_level',
      width: 110,
      render: (v) => {
        const colorMap = {
          high: 'red', 高: 'red',
          medium: 'orange', 中: 'orange',
          low: 'blue', 低: 'blue',
        }
        return v ? <Tag color={colorMap[v] || 'default'}>{v}</Tag> : '--'
      },
    },
    {
      title: '机构占比%',
      dataIndex: 'institutional_ratio_pct',
      key: 'institutional_ratio_pct',
      width: 100,
      render: (v) => v != null ? `${Number(v).toFixed(2)}%` : '--',
    },
    {
      title: '国有占比%',
      dataIndex: 'state_ratio_pct',
      key: 'state_ratio_pct',
      width: 100,
      render: (v) => v != null ? `${Number(v).toFixed(2)}%` : '--',
    },
  ]

  const topHoldersExpandedRow = (record) => {
    const holders = record.holders || []
    if (holders.length === 0) return <Empty description='暂无股东明细' image={Empty.PRESENTED_IMAGE_SIMPLE} />

    const holderColumns = [
      { title: '股东名称', dataIndex: 'holder_name', key: 'holder_name', ellipsis: true },
      {
        title: '持股比例%',
        dataIndex: 'hold_ratio_pct',
        key: 'hold_ratio_pct',
        render: (v) => v != null ? `${Number(v).toFixed(2)}%` : '--',
      },
      {
        title: '持股数量',
        dataIndex: 'hold_amount',
        key: 'hold_amount',
        render: (v) => v != null ? v.toLocaleString() : '--',
      },
      {
        title: '机构',
        dataIndex: 'is_institutional',
        key: 'is_institutional',
        width: 70,
        render: (v) => v ? <Tag color={COLORS.primary}>机构</Tag> : <Tag>非机构</Tag>,
      },
      {
        title: '国有',
        dataIndex: 'is_state',
        key: 'is_state',
        width: 70,
        render: (v) => v ? <Tag color={COLORS.decrease}>国有</Tag> : null,
      },
    ]

    return (
      <Table
        dataSource={holders}
        columns={holderColumns}
        rowKey={(r, i) => r.holder_name || i}
        size='small'
        pagination={false}
        style={{ background: '#fafafa' }}
      />
    )
  }

  // ============================================================
  // Tab 4: 综合评分 (Comprehensive)
  // ============================================================

  const renderScoreGauge = (score) => {
    if (score == null) return <Empty description='暂无评分数据' image={Empty.PRESENTED_IMAGE_SIMPLE} />

    const scoreColor = score > 70 ? COLORS.decrease : score >= 40 ? COLORS.warning : COLORS.increase
    const signalMap = {
      bullish: { label: '看多', color: COLORS.decrease },
      bearish: { label: '看空', color: COLORS.increase },
      neutral: { label: '中性', color: COLORS.muted },
    }
    const signalInfo = signalMap[comprehensiveData?.signal] || { label: '--', color: COLORS.muted }

    return (
      <Card style={{ textAlign: 'center', marginBottom: 24, ...cardStyle }}>
        <div style={{ marginBottom: 16 }}>
          <Text style={{ fontSize: 14, color: '#666' }}>综合股东情报评分</Text>
        </div>
        <div style={{ fontSize: 72, fontWeight: 700, color: scoreColor, lineHeight: 1 }}>
          {score}
        </div>
        <div style={{ fontSize: 16, color: '#999', marginBottom: 16 }}>/ 100</div>
        <Badge
          count={signalInfo.label}
          style={{
            backgroundColor: signalInfo.color,
            fontSize: 16,
            padding: '4px 16px',
            borderRadius: 12,
            height: 'auto',
          }}
        />
        {comprehensiveData?.trade_date && (
          <div style={{ marginTop: 12, color: '#999', fontSize: 13 }}>
            数据日期：{comprehensiveData.trade_date}
          </div>
        )}
      </Card>
    )
  }

  const renderComponentCards = () => {
    if (!comprehensiveData?.components) return null

    const { components, details } = comprehensiveData
    const ht = components.holder_trade || {}
    const hn = components.holder_num || {}
    const th = components.top_holders || {}

    const detailHt = details?.holder_trade || {}
    const detailHn = details?.holder_num || {}
    const detailTh = details?.top_holders || {}

    return (
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card
            title='📊 增减持'
            size='small'
            extra={<Tag color={COLORS.primary}>{ht.score ?? '--'}分</Tag>}
            style={cardStyle}
          >
            <Space direction='vertical' style={{ width: '100%' }}>
              <Statistic
                title='净增减数量'
                value={detailHt.net_increase != null ? detailHt.net_increase : detailHt.net_increase_amount ?? '--'}
                valueStyle={{ fontSize: 20, color: (detailHt.net_increase || 0) >= 0 ? COLORS.increase : COLORS.decrease }}
              />
              <Row gutter={8}>
                <Col span={12}>
                  <Statistic
                    title='增持次数'
                    value={detailHt.increase_count ?? ht.increase_count ?? '--'}
                    valueStyle={{ fontSize: 16, color: COLORS.increase }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title='减持次数'
                    value={detailHt.decrease_count ?? ht.decrease_count ?? '--'}
                    valueStyle={{ fontSize: 16, color: COLORS.decrease }}
                  />
                </Col>
              </Row>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card
            title='📈 筹码集中'
            size='small'
            extra={<Tag color={COLORS.primary}>{hn.score ?? '--'}分</Tag>}
            style={cardStyle}
          >
            <Space direction='vertical' style={{ width: '100%' }}>
              <Statistic
                title='股东人数'
                value={detailHn.total_holders ?? hn.total_holders ?? '--'}
                valueStyle={{ fontSize: 20, color: COLORS.primary }}
              />
              <Row gutter={8}>
                <Col span={12}>
                  <Statistic
                    title='户均持股'
                    value={detailHn.avg_hold ?? hn.avg_hold ?? '--'}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title='集中度变化'
                    value={detailHn.concentration_change ?? hn.concentration_change ?? '--'}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Col>
              </Row>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card
            title='🏆 十大股东'
            size='small'
            extra={<Tag color={COLORS.primary}>{th.score ?? '--'}分</Tag>}
            style={cardStyle}
          >
            <Space direction='vertical' style={{ width: '100%' }}>
              <Statistic
                title='机构持股比例'
                value={detailHt.institution_ratio ?? th.institution_ratio ?? '--'}
                valueStyle={{ fontSize: 20, color: COLORS.primary }}
              />
              <Row gutter={8}>
                <Col span={12}>
                  <Statistic
                    title='新增机构'
                    value={detailHt.new_institution_count ?? th.new_institution_count ?? '--'}
                    valueStyle={{ fontSize: 16, color: COLORS.increase }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title='退出机构'
                    value={detailHt.exit_institution_count ?? th.exit_institution_count ?? '--'}
                    valueStyle={{ fontSize: 16, color: COLORS.decrease }}
                  />
                </Col>
              </Row>
            </Space>
          </Card>
        </Col>
      </Row>
    )
  }

  // ============================================================
  // Tab definitions
  // ============================================================

  const tabItems = [
    {
      key: 'trade',
      label: '📊 增减持动态',
      children: (
        <div>
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            {[
              { label: '全部', value: 'all' },
              { label: '增持', value: 'increase' },
              { label: '减持', value: 'decrease' },
            ].map(f => (
              <Col key={f.value}>
                <Button
                  type={tradeFilter === f.value ? 'primary' : 'default'}
                  onClick={() => setTradeFilter(f.value)}
                >
                  {f.label}
                </Button>
              </Col>
            ))}
          </Row>
          <Table
            dataSource={filteredTradeStocks}
            columns={tradeColumns}
            rowKey={(r, i) => `${r.ts_code}-${i}`}
            size='small'
            pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
          />
        </div>
      ),
    },
    {
      key: 'holderNum',
      label: '👥 股东人数',
      children: (
        <div>
          <Input.Search
            placeholder='输入股票代码（如 000001.SZ）'
            value={holderNumCode}
            onChange={e => setHolderNumCode(e.target.value)}
            onSearch={() => fetchHolderNumData(holderNumCode)}
            style={{ marginBottom: 16, maxWidth: 400 }}
          />
          {holderNumData ? (
            <Table
              dataSource={holderNumData.history || []}
              columns={holderNumColumns}
              rowKey='trade_date'
              size='small'
              pagination={{ pageSize: 10 }}
            />
          ) : (
            <Empty description='请输入股票代码查询' image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </div>
      ),
    },
    {
      key: 'topHolders',
      label: '🏆 十大股东',
      children: (
        <div>
          <Input.Search
            placeholder='输入股票代码（如 000001.SZ）'
            value={topHoldersCode}
            onChange={e => setTopHoldersCode(e.target.value)}
            onSearch={() => fetchTopHoldersData(topHoldersCode)}
            style={{ marginBottom: 16, maxWidth: 400 }}
          />
          {topHoldersData ? (
            <Table
              dataSource={topHoldersData.holders || []}
              columns={topHoldersColumns}
              rowKey={(r, i) => `${r.holder_name}-${i}`}
              size='small'
              pagination={{ pageSize: 10 }}
            />
          ) : (
            <Empty description='请输入股票代码查询' image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </div>
      ),
    },
    {
      key: 'comprehensive',
      label: '🎯 综合分析',
      children: (
        <div>
          {renderScoreGauge(comprehensiveData?.total_score)}
          {renderComponentCards()}
        </div>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Card
        title='🔬 股东情报中心'
        extra={
          <Space>
            <Segmented
              options={[
                { label: '增减持', value: 'trade' },
                { label: '股东人数', value: 'holderNum' },
                { label: '十大股东', value: 'topHolders' },
                { label: '综合分析', value: 'comprehensive' },
              ]}
              value={activeTab}
              onChange={setActiveTab}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={handleRefresh}
              loading={loading}
            >
              刷新
            </Button>
          </Space>
        }
        style={cardStyle}
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <Spin size='large' tip='加载中...' />
          </div>
        ) : (
          <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
        )}
      </Card>
    </div>
  )
}
