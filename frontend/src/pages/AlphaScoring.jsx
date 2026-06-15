import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Card, Row, Col, Statistic, Table, Tag, Spin, Typography, Tooltip, Button,
  Segmented, Slider, Input, Empty, Progress, Space, Divider,
} from 'antd'
import {
  ReloadOutlined, SearchOutlined, TrophyOutlined, FireOutlined,
  SwapOutlined, RiseOutlined, FallOutlined,
} from '@ant-design/icons'
import { apiCall, searchStocks } from '../services/api'

const { Text, Title } = Typography

const FACTOR_LABELS = {
  value: '价值因子',
  momentum: '动量因子',
  flow: '资金因子',
  quality: '质量因子',
  size: '市值因子',
}

const FACTOR_ICONS = {
  value: '💎',
  momentum: '🚀',
  flow: '💰',
  quality: '⭐',
  size: '🏢',
}

const SIGNAL_MAP = {
  ROTATION_IN: { color: '#52c41a', label: '轮入', icon: <RiseOutlined /> },
  ROTATION_OUT: { color: '#f5222d', label: '轮出', icon: <FallOutlined /> },
  ACCELERATION: { color: '#1890ff', label: '加速', icon: <FireOutlined /> },
  DECELERATION: { color: '#fa8c16', label: '减速', icon: <FallOutlined /> },
  NEUTRAL: { color: '#8c8c8c', label: '中性', icon: <SwapOutlined /> },
}

/** Alpha Score 色彩 */
function alphaColor(score) {
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#faad14'
  return '#f5222d'
}

/** 格式化资金（万元 → 亿） */
function fmtFlow(val) {
  if (val == null) return '-'
  const yi = val / 10000
  if (Math.abs(yi) >= 1) return `${yi.toFixed(2)}亿`
  const wan = val
  return `${wan.toFixed(0)}万`
}

/* =====================================================================
 * Tab 1 — Alpha 排行
 * ===================================================================== */
function AlphaRankings() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [industryFilter, setIndustryFilter] = useState(null)
  const [minMv, setMinMv] = useState(20)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const params = `?limit=50&min_mv=${minMv}${industryFilter ? `&industry=${encodeURIComponent(industryFilter)}` : ''}`
      const res = await apiCall(`/alpha/score${params}`)
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load alpha scores:', err)
    }
    setLoading(false)
  }, [minMv, industryFilter])

  useEffect(() => { loadData() }, [loadData])

  const industries = useMemo(() => {
    if (!data?.stocks) return []
    const set = new Set(data.stocks.map((s) => s.industry).filter(Boolean))
    return [...set].sort()
  }, [data])

  const summary = data?.summary || {}
  const topIndustry = summary.top_industries
    ? Object.entries(summary.top_industries).sort((a, b) => b[1] - a[1])[0]
    : null

  const columns = [
    {
      title: '序号',
      dataIndex: 'rank',
      width: 60,
      align: 'center',
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
      title: '综合评分',
      dataIndex: 'alpha_score',
      width: 100,
      sorter: (a, b) => a.alpha_score - b.alpha_score,
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ color: alphaColor(v), fontWeight: 'bold', fontSize: 16 }}>
          {v}
        </span>
      ),
    },
    {
      title: '行业',
      dataIndex: 'industry',
      width: 100,
    },
    ...['value', 'momentum', 'flow', 'quality', 'size'].map((f) => ({
      title: (
        <Tooltip title={`${FACTOR_LABELS[f]}（权重 ${(f === 'value' ? 30 : f === 'momentum' || f === 'flow' ? 25 : 10)}%）`}>
          <span>{FACTOR_ICONS[f]} {FACTOR_LABELS[f].replace('因子', '')}</span>
        </Tooltip>
      ),
      key: f,
      width: 90,
      sorter: (a, b) => (a.factors?.[f]?.score ?? 0) - (b.factors?.[f]?.score ?? 0),
      render: (_, r) => {
        const s = r.factors?.[f]?.score
        if (s == null) return <Text type="secondary">-</Text>
        return <span style={{ color: alphaColor(s) }}>{s}</span>
      },
    })),
    {
      title: '行业百分位',
      key: 'pctile',
      width: 100,
      render: (_, r) => {
        // industry_rank is 1-based; approximate percentile
        if (!r.rank) return '-'
        const total = summary.total_stocks || 50
        const pct = Math.round((1 - (r.rank - 1) / Math.max(total, 1)) * 100)
        return (
          <Progress
            percent={pct}
            size="small"
            strokeColor={pct >= 80 ? '#52c41a' : pct >= 50 ? '#faad14' : '#f5222d'}
            format={(p) => `Top ${100 - p}%`}
          />
        )
      },
    },
  ]

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="评分股票数"
              value={summary.total_stocks || 0}
              prefix={<TrophyOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="平均 Alpha 评分"
              value={summary.avg_alpha_score || 0}
              precision={1}
              valueStyle={{ color: alphaColor(summary.avg_alpha_score || 0) }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="平均总市值"
              value={summary.avg_market_cap_yi || 0}
              precision={1}
              suffix="亿"
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="最热行业"
              value={topIndustry ? topIndustry[0] : '-'}
              valueStyle={{ fontSize: 16 }}
            />
            {topIndustry && (
              <Text type="secondary" style={{ fontSize: 12 }}>{topIndustry[1]} 只股票</Text>
            )}
          </Card>
        </Col>
      </Row>

      {/* 筛选器 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Space size={16} wrap>
              <span>
                <Text type="secondary">行业：</Text>
                <Segmented
                  size="small"
                  value={industryFilter || '全部'}
                  onChange={(v) => setIndustryFilter(v === '全部' ? null : v)}
                  options={[
                    { label: '全部', value: '全部' },
                    ...industries.map((i) => ({ label: i, value: i })),
                  ]}
                  style={{ maxWidth: 600 }}
                />
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Text type="secondary">最低市值：</Text>
                <Slider
                  min={0}
                  max={500}
                  step={10}
                  value={minMv}
                  onChange={setMinMv}
                  style={{ width: 200 }}
                  tooltip={{ formatter: (v) => `${v}亿` }}
                />
                <Text>{minMv}亿</Text>
              </span>
            </Space>
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 数据表 */}
      <Card title="🏆 Alpha 排行榜" bodyStyle={{ padding: 0 }}>
        <Table
          dataSource={data?.stocks || []}
          columns={columns}
          rowKey="ts_code"
          loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 只` }}
          size="small"
          scroll={{ x: 1100 }}
        />
      </Card>
    </div>
  )
}

/* =====================================================================
 * Tab 2 — 行业热力图
 * ===================================================================== */
function IndustryHeatmap() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [expandedIndustry, setExpandedIndustry] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailData, setDetailData] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiCall('/alpha/industry-heatmap')
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load heatmap:', err)
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const loadIndustryDetail = useCallback(async (industry) => {
    if (expandedIndustry === industry) {
      setExpandedIndustry(null)
      setDetailData(null)
      return
    }
    setExpandedIndustry(industry)
    setDetailLoading(true)
    try {
      // Use alpha scoring endpoint to get stocks in this industry
      const res = await apiCall(`/alpha/score?limit=30&industry=${encodeURIComponent(industry)}&min_mv=0`)
      setDetailData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load industry detail:', err)
    }
    setDetailLoading(false)
  }, [expandedIndustry])

  const industries = data?.industries || []
  const summary = data?.summary || {}
  const maxStocks = Math.max(...industries.map((i) => i.stock_count), 1)

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="行业总数" value={summary.total_industries || 0} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="轮入行业"
              value={summary.rotation_in || 0}
              valueStyle={{ color: '#52c41a' }}
              prefix={<RiseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="轮出行业"
              value={summary.rotation_out || 0}
              valueStyle={{ color: '#f5222d' }}
              prefix={<FallOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="加速/减速"
              value={`${summary.acceleration || 0} / ${summary.deceleration || 0}`}
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
      </Row>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" tip="加载行业热力图..." />
        </div>
      ) : industries.length === 0 ? (
        <Empty description="暂无行业数据" />
      ) : (
        <>
          {/* 热力图网格 */}
          <Card
            title="🗺️ 行业资金流向热力图"
            extra={<Button icon={<ReloadOutlined />} onClick={loadData} loading={loading} size="small">刷新</Button>}
            bodyStyle={{ padding: 16 }}
          >
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                gap: 8,
              }}
            >
              {industries.map((ind) => {
                const signal = SIGNAL_MAP[ind.signal] || SIGNAL_MAP.NEUTRAL
                const sizeScale = 0.6 + 0.4 * (ind.stock_count / maxStocks)
                return (
                  <div
                    key={ind.industry}
                    onClick={() => loadIndustryDetail(ind.industry)}
                    style={{
                      background: `${signal.color}15`,
                      border: expandedIndustry === ind.industry
                        ? `2px solid ${signal.color}`
                        : `1px solid ${signal.color}40`,
                      borderRadius: 8,
                      padding: '12px 10px',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      opacity: sizeScale,
                      transform: `scale(${sizeScale * 0.3 + 0.7})`,
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>
                      {ind.industry}
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 'bold', color: signal.color }}>
                      {ind.rotation_score > 0 ? '+' : ''}{(ind.rotation_score * 100).toFixed(1)}%
                    </div>
                    <div style={{ fontSize: 11, color: 'rgba(0,0,0,0.45)' }}>
                      {ind.stock_count} 只 · <Tag color={signal.color} style={{ fontSize: 10, lineHeight: '14px', padding: '0 4px', margin: 0 }}>{signal.label}</Tag>
                    </div>
                    <div style={{ fontSize: 11, color: 'rgba(0,0,0,0.45)', marginTop: 2 }}>
                      近期 {fmtFlow(ind.recent_flow)}
                    </div>
                  </div>
                )
              })}
            </div>
          </Card>

          {/* 展开的行业详情 */}
          {expandedIndustry && (
            <Card
              title={`📊 ${expandedIndustry} — 行业成分股`}
              style={{ marginTop: 16 }}
              extra={
                <Button size="small" onClick={() => { setExpandedIndustry(null); setDetailData(null) }}>
                  关闭
                </Button>
              }
            >
              {detailLoading ? (
                <Spin tip="加载行业成分股..." />
              ) : detailData?.stocks ? (
                <Table
                  dataSource={detailData.stocks}
                  rowKey="ts_code"
                  size="small"
                  pagination={{ pageSize: 10 }}
                  columns={[
                    { title: '排名', dataIndex: 'rank', width: 50 },
                    {
                      title: '代码 / 名称',
                      key: 'stock',
                      render: (_, r) => (
                        <span>
                          <Text code style={{ fontSize: 11 }}>{r.ts_code}</Text>{' '}
                          <Text strong>{r.name}</Text>
                        </span>
                      ),
                    },
                    {
                      title: 'Alpha 评分',
                      dataIndex: 'alpha_score',
                      render: (v) => (
                        <span style={{ color: alphaColor(v), fontWeight: 'bold' }}>{v}</span>
                      ),
                    },
                    ...['value', 'momentum', 'flow', 'quality', 'size'].map((f) => ({
                      title: FACTOR_ICONS[f],
                      key: f,
                      width: 60,
                      render: (_, r) => {
                        const s = r.factors?.[f]?.score
                        return s != null ? <span style={{ color: alphaColor(s) }}>{s}</span> : '-'
                      },
                    })),
                  ]}
                />
              ) : (
                <Empty description="无数据" />
              )}
            </Card>
          )}
        </>
      )}
    </div>
  )
}

/* =====================================================================
 * Tab 3 — 同业对比
 * ===================================================================== */
function PeerComparison() {
  const [searchValue, setSearchValue] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [selectedCode, setSelectedCode] = useState(null)
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)

  // Debounced search
  useEffect(() => {
    if (!searchValue || searchValue.length < 1) {
      setSearchResults([])
      return
    }
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await searchStocks(searchValue)
        setSearchResults(res?.data?.slice(0, 10) || [])
      } catch (err) {
        if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
        console.error('Search failed:', err)
      }
      setSearching(false)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchValue])

  // Load peer comparison when a stock is selected
  useEffect(() => {
    if (!selectedCode) return
    setLoading(true)
    setData(null)
    const load = async () => {
      try {
        const res = await apiCall(`/alpha/peer-comparison/${selectedCode}`)
        setData(res?.data || res)
      } catch (err) {
        if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
        console.error('Failed to load peer comparison:', err)
      }
      setLoading(false)
    }
    load()
  }, [selectedCode])

  const target = data?.target
  const peers = data?.peers || []
  const peerAvg = data?.peer_average || {}

  const peerColumns = [
    {
      title: '排名',
      dataIndex: 'rank',
      width: 50,
      align: 'center',
    },
    {
      title: '代码 / 名称',
      key: 'stock',
      render: (_, r) => (
        <span>
          <Text code style={{ fontSize: 11 }}>{r.ts_code}</Text>{' '}
          <Text strong style={{ fontSize: 13 }}>{r.name}</Text>
        </span>
      ),
    },
    {
      title: 'Alpha 评分',
      dataIndex: 'alpha_score',
      sorter: (a, b) => a.alpha_score - b.alpha_score,
      render: (v) => (
        <span style={{ color: alphaColor(v), fontWeight: 'bold' }}>{v}</span>
      ),
    },
    ...['value', 'momentum', 'flow', 'quality', 'size'].map((f) => ({
      title: `${FACTOR_ICONS[f]} ${FACTOR_LABELS[f].replace('因子', '')}`,
      key: f,
      width: 100,
      sorter: (a, b) => (a.factors?.[f]?.score ?? 0) - (b.factors?.[f]?.score ?? 0),
      render: (_, r) => {
        const s = r.factors?.[f]?.score
        if (s == null) return '-'
        const isTarget = r.ts_code === selectedCode
        return (
          <span style={{ color: alphaColor(s), fontWeight: isTarget ? 'bold' : 'normal' }}>
            {s} {isTarget && '◀'}
          </span>
        )
      },
    })),
  ]

  // Factor bar comparison data
  const factorBars = ['value', 'momentum', 'flow', 'quality', 'size'].map((f) => {
    const targetScore = target?.factors?.[f]?.score || 0
    const avgKey = f === 'value' ? 'avg_alpha_score' : null // No direct avg per factor in peerAvg
    const avgScore = 50 // Use 50 as midpoint for comparison
    return { factor: f, label: FACTOR_LABELS[f], icon: FACTOR_ICONS[f], targetScore, avgScore }
  })

  return (
    <div>
      {/* 搜索框 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="输入股票代码或名称搜索（如 000001 或 平安银行）"
          size="large"
          loading={searching}
          value={searchValue}
          onChange={(e) => { setSearchValue(e.target.value); setSelectedCode(null) }}
          onSearch={(v) => {
            if (searchResults.length > 0) {
              setSelectedCode(searchResults[0].ts_code)
              setSearchValue(searchResults[0].name || searchResults[0].ts_code)
            }
          }}
          prefix={<SearchOutlined style={{ color: '#999' }} />}
        />
        {searchResults.length > 0 && !selectedCode && (
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {searchResults.map((s) => (
              <Tag
                key={s.ts_code}
                style={{ cursor: 'pointer' }}
                color={selectedCode === s.ts_code ? 'blue' : undefined}
                onClick={() => {
                  setSelectedCode(s.ts_code)
                  setSearchValue(s.name || s.ts_code)
                }}
              >
                {s.ts_code} {s.name}
              </Tag>
            ))}
          </div>
        )}
      </Card>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" tip="加载同业对比数据..." />
        </div>
      ) : !data || data.error ? (
        <Empty description={data?.error || '请搜索并选择一只股票进行同业对比'} />
      ) : (
        <>
          {/* 目标股票卡片 */}
          {target && (
            <Card
              style={{
                marginBottom: 16,
                border: `2px solid ${alphaColor(target.alpha_score)}`,
                background: `${alphaColor(target.alpha_score)}08`,
              }}
            >
              <Row gutter={16} align="middle">
                <Col>
                  <div style={{ fontSize: 32 }}>🎯</div>
                </Col>
                <Col flex="auto">
                  <Title level={4} style={{ margin: 0 }}>
                    {target.name}
                    <Text type="secondary" style={{ fontSize: 14, marginLeft: 8 }}>
                      {target.ts_code}
                    </Text>
                  </Title>
                  <Space style={{ marginTop: 4 }}>
                    <Tag color="blue">{target.industry || data.industry}</Tag>
                    <span style={{ color: alphaColor(target.alpha_score), fontWeight: 'bold', fontSize: 20 }}>
                      Alpha: {target.alpha_score}
                    </span>
                  </Space>
                </Col>
                <Col>
                  <Statistic title="同业数量" value={peerAvg.peer_count || peers.length + 1} />
                </Col>
              </Row>
            </Card>
          )}

          {/* 因子对比柱状图 */}
          <Card title="📊 因子维度对比" size="small" style={{ marginBottom: 16 }}>
            <Row gutter={[16, 12]}>
              {factorBars.map((fb) => {
                const maxScore = 100
                const barWidth = Math.max(5, (fb.targetScore / maxScore) * 100)
                return (
                  <Col xs={24} sm={12} md={8} key={fb.factor}>
                    <div style={{ marginBottom: 4 }}>
                      <Text strong>{fb.icon} {fb.label}</Text>
                    </div>
                    <div style={{ position: 'relative', height: 24, background: '#1f1f1f', borderRadius: 4 }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${barWidth}%`,
                          background: alphaColor(fb.targetScore),
                          borderRadius: 4,
                          transition: 'width 0.5s ease',
                          display: 'flex',
                          alignItems: 'center',
                          paddingLeft: 8,
                        }}
                      >
                        <Text style={{ color: '#fff', fontSize: 12, fontWeight: 600 }}>
                          {fb.targetScore}
                        </Text>
                      </div>
                    </div>
                    <div style={{ marginTop: 2 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        同业平均: {peerAvg.avg_alpha_score || '-'}
                      </Text>
                    </div>
                  </Col>
                )
              })}
            </Row>
          </Card>

          {/* 同业对比表 */}
          <Card
            title={`📋 同业对比 — ${data.industry || ''}`}
            bodyStyle={{ padding: 0 }}
          >
            <Table
              dataSource={[target, ...peers]}
              columns={peerColumns}
              rowKey="ts_code"
              size="small"
              pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 只` }}
              scroll={{ x: 1000 }}
              rowClassName={(r) => r.ts_code === selectedCode ? 'ant-table-row-selected' : ''}
            />
          </Card>
        </>
      )}
    </div>
  )
}

/* =====================================================================
 * Tab 4 — 轮动信号
 * ===================================================================== */
function RotationSignals() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [filter, setFilter] = useState('全部')
  const [lookbackDays, setLookbackDays] = useState(10)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiCall(`/alpha/rotation-signals?lookback_days=${lookbackDays}`)
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load rotation signals:', err)
    }
    setLoading(false)
  }, [lookbackDays])

  useEffect(() => { loadData() }, [loadData])

  const summary = data?.summary || {}
  const signals = data?.signals || []

  const filteredSignals = useMemo(() => {
    if (filter === '全部') return signals
    const typeMap = {
      '轮入': 'ROTATION_IN',
      '轮出': 'ROTATION_OUT',
      '加速': 'ACCELERATION',
      '减速': 'DECELERATION',
    }
    return signals.filter((s) => s.signal === typeMap[filter])
  }, [signals, filter])

  // Mini bar chart for daily flow
  function MiniFlowChart({ dailyFlow }) {
    if (!dailyFlow || dailyFlow.length === 0) return <Text type="secondary">-</Text>
    const maxAbs = Math.max(...dailyFlow.map((d) => Math.abs(d.net_amount)), 1)
    return (
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 1, height: 28 }}>
        {dailyFlow.map((d, i) => {
          const h = Math.max(2, (Math.abs(d.net_amount) / maxAbs) * 24)
          const color = d.net_amount >= 0 ? '#52c41a' : '#f5222d'
          return (
            <Tooltip key={i} title={`${d.trade_date}: ${fmtFlow(d.net_amount)}`}>
              <div
                style={{
                  width: 8,
                  height: h,
                  background: color,
                  borderRadius: 1,
                  opacity: 0.8,
                }}
              />
            </Tooltip>
          )
        })}
      </div>
    )
  }

  const columns = [
    {
      title: '行业',
      dataIndex: 'industry',
      width: 100,
      render: (v) => <Text strong>{v}</Text>,
    },
    {
      title: '信号',
      dataIndex: 'signal',
      width: 90,
      render: (v) => {
        const s = SIGNAL_MAP[v] || SIGNAL_MAP.NEUTRAL
        return (
          <Tag color={s.color} icon={s.icon}>
            {s.label}
          </Tag>
        )
      },
    },
    {
      title: '轮动评分',
      dataIndex: 'rotation_score',
      width: 100,
      sorter: (a, b) => a.rotation_score - b.rotation_score,
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ color: v > 0 ? '#52c41a' : v < 0 ? '#f5222d' : '#8c8c8c', fontWeight: 'bold' }}>
          {v > 0 ? '+' : ''}{(v * 100).toFixed(1)}%
        </span>
      ),
    },
    {
      title: '近期流入',
      dataIndex: 'recent_flow',
      width: 110,
      render: (v) => (
        <span style={{ color: v >= 0 ? '#52c41a' : '#f5222d' }}>{fmtFlow(v)}</span>
      ),
    },
    {
      title: '远期流入',
      dataIndex: 'older_flow',
      width: 110,
      render: (v) => (
        <span style={{ color: v >= 0 ? '#52c41a' : '#f5222d' }}>{fmtFlow(v)}</span>
      ),
    },
    {
      title: '成分股数',
      dataIndex: 'stock_count',
      width: 80,
      align: 'center',
    },
    {
      title: '近期日流（柱状）',
      key: 'daily_flow',
      width: 160,
      render: (_, r) => <MiniFlowChart dailyFlow={r.daily_flow} />,
    },
  ]

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="发出信号行业"
              value={summary.signaling || 0}
              prefix={<FireOutlined style={{ color: '#fa8c16' }} />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="轮入"
              value={summary.rotation_in || 0}
              valueStyle={{ color: '#52c41a' }}
              prefix={<RiseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="轮出"
              value={summary.rotation_out || 0}
              valueStyle={{ color: '#f5222d' }}
              prefix={<FallOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="加速 / 减速"
              value={`${summary.acceleration || 0} / ${summary.deceleration || 0}`}
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 筛选器 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Space>
              <Text type="secondary">信号类型：</Text>
              <Segmented
                value={filter}
                onChange={setFilter}
                options={[
                  { label: '全部', value: '全部' },
                  { label: '🟢 轮入', value: '轮入' },
                  { label: '🔴 轮出', value: '轮出' },
                  { label: '🔵 加速', value: '加速' },
                  { label: '🟠 减速', value: '减速' },
                ]}
              />
            </Space>
          </Col>
          <Col>
            <Space>
              <Text type="secondary">回看天数：</Text>
              <Slider
                min={3}
                max={30}
                value={lookbackDays}
                onChange={setLookbackDays}
                style={{ width: 120 }}
              />
              <Text>{lookbackDays}天</Text>
              <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading} size="small">
                刷新
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 信号表 */}
      <Card title="🔄 行业轮动信号" bodyStyle={{ padding: 0 }}>
        <Table
          dataSource={filteredSignals}
          columns={columns}
          rowKey="industry"
          loading={loading}
          pagination={{ pageSize: 15, showTotal: (t) => `共 ${t} 个行业` }}
          size="small"
          scroll={{ x: 900 }}
        />
      </Card>

      {/* 图例 */}
      <Card size="small" style={{ marginTop: 16 }}>
        <Text type="secondary">
          💡 <strong>信号解读</strong>：轮入（🟢）= 资金近期加速流入；轮出（🔴）= 资金近期加速流出；
          加速（🔵）= 流入速度加快；减速（🟠）= 流出速度放缓。
          评分基于近期段与远期段资金流向的相对变化。
        </Text>
      </Card>
    </div>
  )
}

/* =====================================================================
 * 主组件
 * ===================================================================== */
export default function AlphaScoring({ tradeDate }) {
  const [activeTab, setActiveTab] = useState('rankings')

  const tabs = [
    { label: '🏆 Alpha 排行', value: 'rankings' },
    { label: '🗺️ 行业热力图', value: 'heatmap' },
    { label: '🔍 同业对比', value: 'peer' },
    { label: '🔄 轮动信号', value: 'rotation' },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      <Segmented
        value={activeTab}
        onChange={setActiveTab}
        options={tabs}
        style={{ marginBottom: 16 }}
      />

      {activeTab === 'rankings' && <AlphaRankings />}
      {activeTab === 'heatmap' && <IndustryHeatmap />}
      {activeTab === 'peer' && <PeerComparison />}
      {activeTab === 'rotation' && <RotationSignals />}
    </div>
  )
}