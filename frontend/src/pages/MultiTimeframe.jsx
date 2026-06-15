import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Card, Table, Tag, Tooltip, Progress, Row, Col, Statistic, Segmented, Slider,
  Button, Drawer, Typography, Space, Spin, Empty, Badge,
} from 'antd'
import {
  RiseOutlined, FallOutlined, ThunderboltOutlined, ReloadOutlined,
  CheckCircleOutlined, CloseCircleOutlined, MinusCircleOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import { apiCall } from '../services/api'

const { Text, Title } = Typography

/** 评分颜色 */
function scoreColor(score) {
  if (score >= 80) return '#52c41a'
  if (score >= 60) return '#1890ff'
  if (score >= 40) return '#faad14'
  return '#ff4d4f'
}

/** 动量格式化 */
function fmtMomentum(val) {
  if (val == null) return '-'
  const prefix = val > 0 ? '+' : ''
  return `${prefix}${val.toFixed(2)}%`
}

/** 动量颜色 */
function momentumColor(val) {
  if (val == null) return '#8c8c8c'
  if (val > 0) return '#52c41a'
  if (val < 0) return '#ff4d4f'
  return '#8c8c8c'
}

/** 方向标签 */
function DirectionTag({ direction }) {
  const map = {
    bullish: { color: '#52c41a', label: '看多', icon: <RiseOutlined /> },
    bearish: { color: '#ff4d4f', label: '看空', icon: <FallOutlined /> },
    neutral: { color: '#8c8c8c', label: '中性', icon: <MinusCircleOutlined /> },
  }
  const cfg = map[direction] || map.neutral
  return <Tag color={cfg.color} icon={cfg.icon}>{cfg.label}</Tag>
}

/** 共振等级标签 */
function LevelTag({ level, label }) {
  const map = {
    strong: '#52c41a',
    moderate: '#1890ff',
    weak: '#faad14',
    none: '#ff4d4f',
  }
  return <Tag color={map[level] || '#8c8c8c'}>{label}</Tag>
}

/** 分数柱状图 */
function ScoreBar({ score, max = 100 }) {
  const color = scoreColor(score)
  const pct = Math.min((score / max) * 100, 100)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <Progress
        percent={pct}
        showInfo={false}
        strokeColor={color}
        size="small"
        style={{ flex: 1, minWidth: 60 }}
      />
      <Text style={{ color, fontWeight: 'bold', minWidth: 36, textAlign: 'right' }}>
        {score}
      </Text>
    </div>
  )
}

/** 单个时间框架卡片 */
function TimeframeCard({ tf }) {
  const dirColor = tf.direction === 'bullish' ? '#52c41a' : tf.direction === 'bearish' ? '#ff4d4f' : '#8c8c8c'
  return (
    <Card
      size="small"
      style={{
        background: '#16213e',
        border: `1px solid ${dirColor}40`,
        borderRadius: 8,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <Text strong style={{ color: '#e0e0e0', fontSize: 14 }}>{tf.label} 动量</Text>
        <Tag color={dirColor} style={{ margin: 0 }}>
          {tf.direction === 'bullish' ? '多头' : tf.direction === 'bearish' ? '空头' : '中性'}
        </Tag>
      </div>
      <Row gutter={8}>
        <Col span={12}>
          <div style={{ marginBottom: 4 }}>
            <Text type="secondary" style={{ fontSize: 11 }}>价格动量</Text>
          </div>
          <div style={{ color: momentumColor(tf.price_momentum), fontWeight: 'bold', fontSize: 16 }}>
            {fmtMomentum(tf.price_momentum)}
          </div>
        </Col>
        <Col span={12}>
          <div style={{ marginBottom: 4 }}>
            <Text type="secondary" style={{ fontSize: 11 }}>成交量动量</Text>
          </div>
          <div style={{ color: momentumColor(tf.volume_momentum - 100), fontWeight: 'bold', fontSize: 16 }}>
            {tf.volume_momentum ? `${tf.volume_momentum.toFixed(1)}%` : '-'}
          </div>
        </Col>
      </Row>
      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text type="secondary" style={{ fontSize: 11 }}>
          MA{tf.days}: {tf.ma_value || '-'}
        </Text>
        <Text style={{ fontSize: 11 }}>
          {tf.above_ma
            ? <span style={{ color: '#52c41a' }}><CheckCircleOutlined /> 价格在均线上方</span>
            : <span style={{ color: '#ff4d4f' }}><CloseCircleOutlined /> 价格在均线下方</span>
          }
        </Text>
      </div>
      {tf.volume_confirms && (
        <div style={{ marginTop: 4 }}>
          <Tag color="#52c41a" style={{ fontSize: 11 }}>✓ 量价确认</Tag>
        </div>
      )}
    </Card>
  )
}

/* =====================================================================
 * 主组件
 * ===================================================================== */
export default function MultiTimeframe() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [minScore, setMinScore] = useState(0)
  const [alignmentFilter, setAlignmentFilter] = useState('全部')
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [selectedStock, setSelectedStock] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailData, setDetailData] = useState(null)
  const [sortBy, setSortBy] = useState('score')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiCall('/multi-timeframe/analyze')
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load multi-timeframe analysis:', err)
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  // 自动刷新（60秒）
  useEffect(() => {
    const timer = setInterval(loadData, 60000)
    return () => clearInterval(timer)
  }, [loadData])

  // 筛选和排序
  const filteredResults = useMemo(() => {
    let results = data?.results || []

    // 最低分数过滤
    if (minScore > 0) {
      results = results.filter((r) => r.alignment_score >= minScore)
    }

    // 共振等级过滤
    if (alignmentFilter !== '全部') {
      const levelMap = {
        '强共振': 'strong',
        '中等': 'moderate',
        '弱': 'weak',
      }
      const target = levelMap[alignmentFilter]
      if (target) {
        results = results.filter((r) => r.signals?.level === target)
      }
    }

    // 排序
    if (sortBy === 'score') {
      results = [...results].sort((a, b) => b.alignment_score - a.alignment_score)
    } else if (sortBy === '5d') {
      results = [...results].sort((a, b) => {
        const a5 = a.timeframe_details?.[0]?.price_momentum || 0
        const b5 = b.timeframe_details?.[0]?.price_momentum || 0
        return b5 - a5
      })
    } else if (sortBy === '10d') {
      results = [...results].sort((a, b) => {
        const a10 = a.timeframe_details?.[1]?.price_momentum || 0
        const b10 = b.timeframe_details?.[1]?.price_momentum || 0
        return b10 - a10
      })
    } else if (sortBy === '20d') {
      results = [...results].sort((a, b) => {
        const a20 = a.timeframe_details?.[2]?.price_momentum || 0
        const b20 = b.timeframe_details?.[2]?.price_momentum || 0
        return b20 - a20
      })
    }

    return results
  }, [data, minScore, alignmentFilter, sortBy])

  const summary = data?.summary || {}

  // 打开详情抽屉
  const openDetail = useCallback(async (record) => {
    setSelectedStock(record)
    setDrawerVisible(true)
    setDetailLoading(true)
    setDetailData(null)
    try {
      const res = await apiCall(`/multi-timeframe/stock/${record.ts_code}`)
      setDetailData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load stock detail:', err)
    }
    setDetailLoading(false)
  }, [])

  // 表格列定义
  const columns = [
    {
      title: '代码',
      dataIndex: 'ts_code',
      width: 110,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '名称',
      dataIndex: 'name',
      width: 90,
      render: (v) => <Text strong style={{ fontSize: 13 }}>{v}</Text>,
    },
    {
      title: '共振评分',
      dataIndex: 'alignment_score',
      width: 180,
      sorter: (a, b) => a.alignment_score - b.alignment_score,
      defaultSortOrder: 'descend',
      render: (v) => <ScoreBar score={v} />,
    },
    {
      title: (
        <Tooltip title="5日价格动量"><span>5日动量</span></Tooltip>
      ),
      key: 'm5',
      width: 90,
      render: (_, r) => {
        const val = r.timeframe_details?.[0]?.price_momentum
        return <span style={{ color: momentumColor(val), fontWeight: 500 }}>{fmtMomentum(val)}</span>
      },
    },
    {
      title: (
        <Tooltip title="10日价格动量"><span>10日动量</span></Tooltip>
      ),
      key: 'm10',
      width: 90,
      render: (_, r) => {
        const val = r.timeframe_details?.[1]?.price_momentum
        return <span style={{ color: momentumColor(val), fontWeight: 500 }}>{fmtMomentum(val)}</span>
      },
    },
    {
      title: (
        <Tooltip title="20日价格动量"><span>20日动量</span></Tooltip>
      ),
      key: 'm20',
      width: 90,
      render: (_, r) => {
        const val = r.timeframe_details?.[2]?.price_momentum
        return <span style={{ color: momentumColor(val), fontWeight: 500 }}>{fmtMomentum(val)}</span>
      },
    },
    {
      title: '共振等级',
      key: 'level',
      width: 90,
      render: (_, r) => {
        const sig = r.signals || {}
        return <LevelTag level={sig.level} label={sig.level_label || '-'} />
      },
    },
    {
      title: '信号',
      key: 'direction',
      width: 80,
      render: (_, r) => <DirectionTag direction={r.signals?.direction} />,
    },
    {
      title: '操作',
      key: 'action',
      width: 60,
      align: 'center',
      render: (_, r) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => openDetail(r)}
        >
          详情
        </Button>
      ),
    },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      {/* 统计行 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small" style={{ background: '#1a1a2e', border: '1px solid #303050' }}>
            <Statistic
              title={<span style={{ color: '#a0a0b0' }}>分析股票数</span>}
              value={summary.total_analyzed || 0}
              prefix={<ThunderboltOutlined style={{ color: '#1890ff' }} />}
              valueStyle={{ color: '#e0e0e0' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" style={{ background: '#1a1a2e', border: '1px solid #303050' }}>
            <Statistic
              title={<span style={{ color: '#a0a0b0' }}>强共振数量</span>}
              value={summary.strong_alignment_count || 0}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" style={{ background: '#1a1a2e', border: '1px solid #303050' }}>
            <Statistic
              title={<span style={{ color: '#a0a0b0' }}>看多信号数</span>}
              value={summary.bullish_count || 0}
              prefix={<RiseOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" style={{ background: '#1a1a2e', border: '1px solid #303050' }}>
            <Statistic
              title={<span style={{ color: '#a0a0b0' }}>平均共振评分</span>}
              value={summary.avg_score || 0}
              precision={1}
              valueStyle={{ color: scoreColor(summary.avg_score || 0) }}
            />
          </Card>
        </Col>
      </Row>

      {/* 筛选控制 */}
      <Card
        size="small"
        style={{ marginBottom: 16, background: '#1a1a2e', border: '1px solid #303050' }}
      >
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Space size={16} wrap>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Text style={{ color: '#a0a0b0' }}>最低分数：</Text>
                <Slider
                  min={0}
                  max={100}
                  step={5}
                  value={minScore}
                  onChange={setMinScore}
                  style={{ width: 160 }}
                  tooltip={{ formatter: (v) => `${v}分` }}
                />
                <Text style={{ color: '#e0e0e0' }}>{minScore}分</Text>
              </span>
              <span>
                <Text style={{ color: '#a0a0b0' }}>共振等级：</Text>
                <Segmented
                  size="small"
                  value={alignmentFilter}
                  onChange={setAlignmentFilter}
                  options={[
                    { label: '全部', value: '全部' },
                    { label: '🔥 强共振', value: '强共振' },
                    { label: '🔵 中等', value: '中等' },
                    { label: '🟡 弱', value: '弱' },
                  ]}
                />
              </span>
              <span>
                <Text style={{ color: '#a0a0b0' }}>排序：</Text>
                <Segmented
                  size="small"
                  value={sortBy}
                  onChange={setSortBy}
                  options={[
                    { label: '评分', value: 'score' },
                    { label: '5日', value: '5d' },
                    { label: '10日', value: '10d' },
                    { label: '20日', value: '20d' },
                  ]}
                />
              </span>
            </Space>
          </Col>
          <Col>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadData}
              loading={loading}
              style={{ color: '#e0e0e0', borderColor: '#303050' }}
            >
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 结果表格 */}
      <Card
        title={
          <span style={{ color: '#e0e0e0' }}>
            <ThunderboltOutlined style={{ color: '#1890ff', marginRight: 8 }} />
            多周期动量共振排行
            <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
              共 {filteredResults.length} 只
            </Text>
          </span>
        }
        style={{ background: '#1a1a2e', border: '1px solid #303050' }}
        bodyStyle={{ padding: 0 }}
      >
        <Table
          dataSource={filteredResults}
          columns={columns}
          rowKey="ts_code"
          loading={loading}
          pagination={{
            pageSize: 20,
            showTotal: (t) => `共 ${t} 只`,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50', '100'],
          }}
          size="small"
          scroll={{ x: 960 }}
          onRow={(record) => ({
            onClick: () => openDetail(record),
            style: { cursor: 'pointer' },
          })}
          rowClassName={(record) => {
            const score = record.alignment_score
            if (score >= 80) return 'row-strong-alignment'
            if (score >= 60) return 'row-moderate-alignment'
            return ''
          }}
          style={{ background: '#1a1a2e' }}
        />
      </Card>

      {/* 图例 */}
      <Card
        size="small"
        style={{ marginTop: 16, background: '#1a1a2e', border: '1px solid #303050' }}
      >
        <Space size={24} wrap>
          <span>
            <Badge color="#52c41a" />
            <Text style={{ color: '#a0a0b0', marginLeft: 4 }}>≥80 强看多</Text>
          </span>
          <span>
            <Badge color="#1890ff" />
            <Text style={{ color: '#a0a0b0', marginLeft: 4 }}>≥60 看多</Text>
          </span>
          <span>
            <Badge color="#faad14" />
            <Text style={{ color: '#a0a0b0', marginLeft: 4 }}>≥40 中性</Text>
          </span>
          <span>
            <Badge color="#ff4d4f" />
            <Text style={{ color: '#a0a0b0', marginLeft: 4 }}>&lt;40 看空</Text>
          </span>
          <Text type="secondary" style={{ fontSize: 12 }}>
            💡 共振评分 = 各时间框架(5日/10日/20日)动量方向一致性综合得分，方向一致得分越高
          </Text>
        </Space>
      </Card>

      {/* 详情抽屉 */}
      <Drawer
        title={
          <span style={{ color: '#e0e0e0' }}>
            📐 {selectedStock?.name || ''} — 多周期共振深度分析
          </span>
        }
        placement="right"
        width={520}
        onClose={() => { setDrawerVisible(false); setDetailData(null); setSelectedStock(null) }}
        open={drawerVisible}
        styles={{ body: { background: '#0f0f23', padding: 16 } }}
        style={{ background: '#0f0f23' }}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <Spin size="large" tip="加载深度分析..." />
          </div>
        ) : detailData?.error ? (
          <Empty description={detailData.error} />
        ) : detailData ? (
          <div>
            {/* 分数仪表 */}
            <Card
              size="small"
              style={{
                background: '#1a1a2e',
                border: `2px solid ${scoreColor(detailData.alignment_score || 0)}`,
                marginBottom: 16,
                textAlign: 'center',
              }}
            >
              <div style={{ marginBottom: 8 }}>
                <Text style={{ color: '#a0a0b0', fontSize: 12 }}>共振评分</Text>
              </div>
              <Progress
                type="dashboard"
                percent={detailData.alignment_score || 0}
                strokeColor={scoreColor(detailData.alignment_score || 0)}
                format={(pct) => (
                  <span style={{ color: scoreColor(pct), fontSize: 28, fontWeight: 'bold' }}>
                    {pct}
                  </span>
                )}
                size={160}
              />
              <div style={{ marginTop: 8 }}>
                <DirectionTag direction={detailData.signals?.direction} />
                <span style={{ margin: '0 8px' }} />
                <LevelTag level={detailData.signals?.level} label={detailData.signals?.level_label || '-'} />
              </div>
              <div style={{ marginTop: 8 }}>
                <Space>
                  <Text style={{ color: '#a0a0b0', fontSize: 12 }}>
                    收盘价: <Text style={{ color: '#e0e0e0', fontWeight: 'bold' }}>{detailData.close || '-'}</Text>
                  </Text>
                  <Text style={{ color: '#a0a0b0', fontSize: 12 }}>
                    对齐数: <Text style={{ color: '#1890ff', fontWeight: 'bold' }}>{detailData.positive_timeframes || 0}/3</Text>
                  </Text>
                </Space>
              </div>
            </Card>

            {/* 时间框架卡片 */}
            <Title level={5} style={{ color: '#e0e0e0', marginBottom: 12 }}>
              📊 各时间框架详情
            </Title>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {(detailData.timeframe_details || []).map((tf) => (
                <TimeframeCard key={tf.days} tf={tf} />
              ))}
            </div>

            {/* 信号标签 */}
            {detailData.signals && (
              <Card
                size="small"
                style={{
                  marginTop: 16,
                  background: '#1a1a2e',
                  border: '1px solid #303050',
                }}
              >
                <Text strong style={{ color: '#e0e0e0', marginBottom: 8, display: 'block' }}>
                  🏷️ 信号汇总
                </Text>
                <Space wrap>
                  <Tag color={detailData.signals.direction === 'bullish' ? '#52c41a' : detailData.signals.direction === 'bearish' ? '#ff4d4f' : '#8c8c8c'}>
                    {detailData.signals.direction_label || '中性'}
                  </Tag>
                  <Tag color="#1890ff">
                    {detailData.signals.level_label || '-'}
                  </Tag>
                  <Tag color="#722ed1">
                    成交量确认: {detailData.volume_confirms_count || 0}/3
                  </Tag>
                </Space>
              </Card>
            )}
          </div>
        ) : (
          <Empty description="暂无数据" />
        )}
      </Drawer>
    </div>
  )
}
