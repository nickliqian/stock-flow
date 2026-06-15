import React, { useState, useEffect, useCallback } from 'react'
import { Card, Table, Tag, Space, Spin, Empty, Select, Statistic, Row, Col, Typography, message } from 'antd'
import { getStrategySectorHeatmap } from '../services/api'

const { Text } = Typography

// 策略类别标签
const CATEGORY_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'value', label: '价值' },
  { value: 'momentum', label: '动量' },
  { value: 'flow', label: '资金' },
  { value: 'event', label: '事件' },
  { value: 'combo', label: '组合' },
]

// 单元格颜色映射
function cellStyle(ratio) {
  if (ratio >= 0.7) return { background: '#ff4d4f', color: '#fff' }
  if (ratio >= 0.4) return { background: '#faad14' }
  if (ratio >= 0.2) return { background: '#52c41a' }
  if (ratio > 0) return { background: '#91d5ff' }
  return {}
}

function cellText(ratio) {
  if (ratio >= 0.7) return { color: '#fff' }
  return {}
}

export default function StrategySectorHeatmap({ tradeDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [category, setCategory] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (tradeDate) params.trade_date = tradeDate
      const res = await getStrategySectorHeatmap(params)
      if (res?.success) {
        setData(res.data)
      } else {
        message.error(res?.error || '加载失败')
      }
    } catch (err) {
      console.error('Sector heatmap load failed:', err)
      message.error('板块热力图加载失败')
    } finally {
      setLoading(false)
    }
  }, [tradeDate])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" tip="加载板块热力图..." />
      </div>
    )
  }

  if (!data || !data.sectors || data.sectors.length === 0) {
    return <Empty description="暂无板块热力图数据" />
  }

  const { sectors, strategies } = data

  // 按类别过滤策略
  const filteredStrategies = category
    ? strategies.filter(s => s.category === category)
    : strategies

  // 找最大值用于 ratio 计算
  const maxTotal = Math.max(...sectors.map(s => s.total), 1)

  // 构建列
  const columns = [
    {
      title: '行业',
      dataIndex: 'industry',
      width: 100,
      fixed: 'left',
      render: (v) => <Text strong style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '合计',
      dataIndex: 'total',
      width: 60,
      fixed: 'left',
      sorter: (a, b) => a.total - b.total,
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ fontWeight: 700, fontSize: 14, color: v > 10 ? '#ff4d4f' : '#333' }}>
          {v}
        </span>
      ),
    },
    ...filteredStrategies.map(s => ({
      title: <span style={{ fontSize: 11 }}>{s.icon} {s.description?.slice(0, 4)}</span>,
      dataIndex: s.name,
      width: 70,
      render: (v) => {
        const val = v || 0
        const ratio = val / maxTotal
        const style = cellStyle(ratio)
        return (
          <div style={{
            ...style,
            textAlign: 'center',
            borderRadius: 4,
            padding: '2px 4px',
            fontSize: 12,
            fontWeight: val > 0 ? 600 : 400,
            ...cellText(ratio),
          }}>
            {val > 0 ? val : '-'}
          </div>
        )
      },
    })),
  ]

  // 数据源
  const dataSource = sectors.map((s, i) => ({ ...s, key: i }))

  // 统计概览
  const topSector = sectors[0]
  const totalStrategies = filteredStrategies.length

  return (
    <div>
      {/* 统计概览 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="行业数" value={sectors.length} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="策略数" value={totalStrategies} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="最强行业" value={topSector?.industry || '-'} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="最强行业合计" value={topSector?.total || 0} />
          </Card>
        </Col>
      </Row>

      {/* 过滤 + 表格 */}
      <Card size="small">
        <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Text type="secondary">筛选类别：</Text>
            <Select
              value={category}
              onChange={setCategory}
              options={CATEGORY_OPTIONS}
              style={{ width: 100 }}
              size="small"
            />
          </Space>
          {data.trade_date && <Tag>{data.trade_date}</Tag>}
        </div>
        <Table
          columns={columns}
          dataSource={dataSource}
          pagination={false}
          size="small"
          scroll={{ x: filteredStrategies.length * 70 + 160 }}
          bordered
        />
      </Card>
    </div>
  )
}
