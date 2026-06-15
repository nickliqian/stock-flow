import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Tabs, Space,
  Spin, Empty, Typography, message, Slider, InputNumber, Badge,
} from 'antd'
import {
  ReloadOutlined, ThunderboltOutlined, WarningOutlined,
  CheckCircleOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons'
import { getChipAnalysis } from '../services/api'

const { Text, Title } = Typography

const cardStyle = { background: '#ffffff', border: '1px solid #e8e8e8' }

/**
 * 筹码穿透率 + 股权质押风险分析页面
 */
export default function ChipIntelligence({ tradeDate }) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [activeTab, setActiveTab] = useState('penetration')

  // 质押比例筛选
  const [pledgeRatioMin, setPledgeRatioMin] = useState(0)
  const [pledgeRatioMax, setPledgeRatioMax] = useState(100)

  const fetchData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const params = {}
      if (tradeDate) params.trade_date = tradeDate
      if (pledgeRatioMin > 0) params.pledge_ratio_min = pledgeRatioMin
      if (pledgeRatioMax < 100) params.pledge_ratio_max = pledgeRatioMax

      const res = await getChipAnalysis(params, { signal })
      if (res?.success) {
        setData(res.data)
      } else {
        message.error(res?.error || '获取数据失败')
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Chip analysis failed:', err)
      message.error('筹码分析数据加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [tradeDate, pledgeRatioMin, pledgeRatioMax])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(controller.signal)
    return () => controller.abort()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const summary = data?.summary || {}
  const chipList = data?.chip_penetration || []
  const pledgeList = data?.pledge_risk || []

  // ============================================================
  // 筹码穿透率表格列
  // ============================================================
  const penetrationColumns = [
    {
      title: '排名',
      width: 50,
      render: (_, __, i) => <span style={{ color: '#aaa' }}>{i + 1}</span>,
    },
    {
      title: '股票',
      key: 'stock',
      width: 160,
      render: (_, record) => (
        <div>
          <Text code style={{ fontSize: 12 }}>{record.ts_code}</Text>
          <div>
            <Text strong style={{ fontSize: 13 }}>{record.name || record.ts_code}</Text>
          </div>
        </div>
      ),
    },
    {
      title: '收盘价',
      dataIndex: 'close',
      width: 90,
      sorter: (a, b) => (a.close || 0) - (b.close || 0),
      render: (v) => (
        <span style={{ fontWeight: 500 }}>{v != null ? `¥${Number(v).toFixed(2)}` : '--'}</span>
      ),
    },
    {
      title: '穿透率',
      dataIndex: 'penetration_pct',
      width: 100,
      sorter: (a, b) => (a.penetration_pct || 0) - (b.penetration_pct || 0),
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{
          color: v > 0 ? '#52c41a' : v < 0 ? '#ff4d4f' : '#999',
          fontWeight: 600,
          fontSize: 14,
        }}>
          {v != null ? `${v > 0 ? '+' : ''}${Number(v).toFixed(2)}%` : '--'}
        </span>
      ),
    },
    {
      title: '套牢盘压力',
      dataIndex: 'overhead_pressure_pct',
      width: 100,
      sorter: (a, b) => (a.overhead_pressure_pct || 0) - (b.overhead_pressure_pct || 0),
      render: (v) => (
        <span style={{ color: v > 30 ? '#ff4d4f' : v > 15 ? '#faad14' : '#52c41a' }}>
          {v != null ? `${Number(v).toFixed(1)}%` : '--'}
        </span>
      ),
    },
    {
      title: '获利比例',
      dataIndex: 'profit_ratio_pct',
      width: 100,
      sorter: (a, b) => (a.profit_ratio_pct || 0) - (b.profit_ratio_pct || 0),
      render: (v) => (
        <span style={{
          color: v > 70 ? '#52c41a' : v > 40 ? '#faad14' : '#ff4d4f',
          fontWeight: 500,
        }}>
          {v != null ? `${Number(v).toFixed(1)}%` : '--'}
        </span>
      ),
    },
    {
      title: '集中度',
      dataIndex: 'concentration_pct',
      width: 90,
      sorter: (a, b) => (a.concentration_pct || 0) - (b.concentration_pct || 0),
      render: (v) => (
        <span style={{ color: v > 60 ? '#52c41a' : v > 30 ? '#faad14' : '#ff4d4f' }}>
          {v != null ? `${Number(v).toFixed(1)}%` : '--'}
        </span>
      ),
    },
    {
      title: '加权均价',
      dataIndex: 'weight_avg',
      width: 90,
      sorter: (a, b) => (a.weight_avg || 0) - (b.weight_avg || 0),
      render: (v) => (
        <span style={{ color: '#666' }}>{v != null ? `¥${Number(v).toFixed(2)}` : '--'}</span>
      ),
    },
    {
      title: '50%成本',
      dataIndex: 'cost_50',
      width: 90,
      sorter: (a, b) => (a.cost_50 || 0) - (b.cost_50 || 0),
      render: (v) => (
        <span style={{ color: '#666' }}>{v != null ? `¥${Number(v).toFixed(2)}` : '--'}</span>
      ),
    },
  ]

  // ============================================================
  // 股权质押风险表格列
  // ============================================================
  const pledgeColumns = [
    {
      title: '排名',
      width: 50,
      render: (_, __, i) => <span style={{ color: '#aaa' }}>{i + 1}</span>,
    },
    {
      title: '股票',
      key: 'stock',
      width: 160,
      render: (_, record) => (
        <div>
          <Text code style={{ fontSize: 12 }}>{record.ts_code}</Text>
          <div>
            <Text strong style={{ fontSize: 13 }}>{record.name || record.ts_code}</Text>
          </div>
        </div>
      ),
    },
    {
      title: '质押比例',
      dataIndex: 'pledge_ratio',
      width: 100,
      sorter: (a, b) => (a.pledge_ratio || 0) - (b.pledge_ratio || 0),
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{
          color: v > 50 ? '#ff4d4f' : v > 30 ? '#faad14' : '#52c41a',
          fontWeight: 600,
          fontSize: 14,
        }}>
          {v != null ? `${Number(v).toFixed(2)}%` : '--'}
        </span>
      ),
    },
    {
      title: '风险等级',
      dataIndex: 'risk_level',
      width: 100,
      render: (v) => {
        const map = {
          high: { color: '#ff4d4f', label: '🔴 高风险', tag: 'error' },
          medium: { color: '#fa8c16', label: '🟠 中风险', tag: 'warning' },
          low: { color: '#52c41a', label: '🟢 低风险', tag: 'success' },
        }
        const cfg = map[v] || map.low
        return <Tag color={cfg.tag} style={{ fontWeight: 600 }}>{cfg.label}</Tag>
      },
    },
    {
      title: '风险评分',
      dataIndex: 'risk_score',
      width: 100,
      sorter: (a, b) => (a.risk_score || 0) - (b.risk_score || 0),
      render: (v) => {
        const color = v > 70 ? '#ff4d4f' : v > 40 ? '#faad14' : '#52c41a'
        return (
          <span style={{ color, fontWeight: 600, fontSize: 14 }}>
            {v != null ? Number(v).toFixed(1) : '--'}
          </span>
        )
      },
    },
    {
      title: '质押笔数',
      dataIndex: 'pledge_count',
      width: 90,
      sorter: (a, b) => (a.pledge_count || 0) - (b.pledge_count || 0),
      render: (v) => <span style={{ color: '#333' }}>{v != null ? v : '--'}</span>,
    },
    {
      title: '质押金额(亿)',
      dataIndex: 'pledge_amount_yi',
      width: 110,
      sorter: (a, b) => (a.pledge_amount_yi || 0) - (b.pledge_amount_yi || 0),
      render: (v) => (
        <span style={{ color: '#666' }}>{v != null ? `${Number(v).toFixed(2)}亿` : '--'}</span>
      ),
    },
    {
      title: '质押/市值比',
      dataIndex: 'pledge_mv_ratio_pct',
      width: 110,
      sorter: (a, b) => (a.pledge_mv_ratio_pct || 0) - (b.pledge_mv_ratio_pct || 0),
      render: (v) => (
        <span style={{
          color: v > 50 ? '#ff4d4f' : v > 25 ? '#faad14' : '#52c41a',
          fontWeight: 500,
        }}>
          {v != null ? `${Number(v).toFixed(2)}%` : '--'}
        </span>
      ),
    },
  ]

  const tabItems = [
    {
      key: 'penetration',
      label: (
        <Space>
          <ThunderboltOutlined />
          <span>筹码穿透率</span>
          {chipList.length > 0 && <Badge count={chipList.length} style={{ backgroundColor: '#1677ff' }} overflowCount={999} />}
        </Space>
      ),
      children: (
        <Table
          columns={penetrationColumns}
          dataSource={chipList.map((r, i) => ({ ...r, key: `${r.ts_code}-c-${i}` }))}
          pagination={{
            pageSize: 20,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 只股票`,
          }}
          size="small"
          scroll={{ x: 880 }}
          style={{ background: '#fff' }}
          locale={{ emptyText: <Empty description="暂无筹码穿透率数据" /> }}
        />
      ),
    },
    {
      key: 'pledge',
      label: (
        <Space>
          <WarningOutlined />
          <span>股权质押风险</span>
          {pledgeList.length > 0 && <Badge count={pledgeList.length} style={{ backgroundColor: '#ff4d4f' }} overflowCount={999} />}
        </Space>
      ),
      children: (
        <Table
          columns={pledgeColumns}
          dataSource={pledgeList.map((r, i) => ({ ...r, key: `${r.ts_code}-p-${i}` }))}
          pagination={{
            pageSize: 20,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 只股票`,
          }}
          size="small"
          scroll={{ x: 880 }}
          style={{ background: '#fff' }}
          locale={{ emptyText: <Empty description="暂无股权质押风险数据" /> }}
        />
      ),
    },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      {/* Header */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space direction="vertical" size={0}>
          <Title level={4} style={{ margin: 0, color: '#1f1f1f' }}>
            💎 筹码穿透率 + 股权质押风险分析
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            筹码分布穿透率分析与股权质押风险评估，识别低位筹码密集与高质押风险标的
          </Text>
        </Space>
      </div>

      {/* Control Panel */}
      <Card
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: { padding: '12px 16px' } }}
      >
        <Space wrap size={16} style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space wrap size={12} align="center">
            <Text style={{ color: '#aaa', fontSize: 13 }}>质押比例范围:</Text>
            <Space size={4}>
              <Text style={{ color: '#888', fontSize: 12 }}>最小:</Text>
              <InputNumber
                size="small"
                min={0}
                max={100}
                value={pledgeRatioMin}
                onChange={(v) => setPledgeRatioMin(v ?? 0)}
                style={{ width: 80 }}
                formatter={(v) => `${v}%`}
                parser={(v) => v.replace('%', '')}
              />
            </Space>
            <Space size={4}>
              <Text style={{ color: '#888', fontSize: 12 }}>最大:</Text>
              <InputNumber
                size="small"
                min={0}
                max={100}
                value={pledgeRatioMax}
                onChange={(v) => setPledgeRatioMax(v ?? 100)}
                style={{ width: 80 }}
                formatter={(v) => `${v}%`}
                parser={(v) => v.replace('%', '')}
              />
            </Space>
            <div style={{ width: 200 }}>
              <Slider
                range
                min={0}
                max={100}
                value={[pledgeRatioMin, pledgeRatioMax]}
                onChange={([min, max]) => {
                  setPledgeRatioMin(min)
                  setPledgeRatioMax(max)
                }}
              />
            </div>
          </Space>
          <Space>
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              onClick={fetchData}
              loading={loading}
            >
              刷新数据
            </Button>
          </Space>
        </Space>
      </Card>

      {/* Stats Cards */}
      <Row gutter={[16, 12]} style={{ marginBottom: 16 }}>
        <Col xs={8} sm={6}>
          <Card size="small" style={cardStyle}>
            <Statistic
              title={<span style={{ color: '#aaa' }}>穿透率分析</span>}
              value={summary.total_analyzed_chip || 0}
              suffix="只"
              valueStyle={{ color: '#1677ff' }}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col xs={8} sm={6}>
          <Card size="small" style={cardStyle}>
            <Statistic
              title={<span style={{ color: '#aaa' }}>质押风险分析</span>}
              value={summary.total_analyzed_pledge || 0}
              suffix="只"
              valueStyle={{ color: '#fa8c16' }}
              prefix={<WarningOutlined />}
            />
          </Card>
        </Col>
        <Col xs={8} sm={6}>
          <Card size="small" style={cardStyle}>
            <Statistic
              title={<span style={{ color: '#aaa' }}>高质押风险</span>}
              value={summary.high_pledge_risk_count || 0}
              suffix="只"
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card size="small" style={cardStyle}>
            <Statistic
              title={<span style={{ color: '#aaa' }}>数据日期</span>}
              value={data?.trade_date || '--'}
              valueStyle={{ color: '#666', fontSize: 18 }}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* Main Content - Tabs */}
      <Card
        title={
          <Space>
            <span style={{ color: '#e0e0e0' }}>
              分析结果
              {data && (
                <Text type="secondary" style={{ fontSize: 13, marginLeft: 8 }}>
                  {chipList.length > 0 && `穿透率 ${chipList.length} 只`}
                  {chipList.length > 0 && pledgeList.length > 0 && ' · '}
                  {pledgeList.length > 0 && `质押风险 ${pledgeList.length} 只`}
                </Text>
              )}
            </span>
          </Space>
        }
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ header: { background: '#fafafa', borderBottom: '1px solid #e8e8e8' } }}
      >
        <Spin spinning={loading}>
          {!data ? (
            <Empty
              description="加载筹码分析数据中..."
              style={{ padding: 40 }}
            />
          ) : (
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
              items={tabItems}
              style={{ marginTop: -8 }}
            />
          )}
        </Spin>
      </Card>
    </div>
  )
}
