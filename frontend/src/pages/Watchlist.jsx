import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Space, Modal, Input,
  Spin, Empty, Badge, Segmented, Typography, message, Popconfirm, Progress, Tabs,
} from 'antd'
import {
  StarOutlined, StarFilled, PlusOutlined, ReloadOutlined, DeleteOutlined,
  ThunderboltOutlined, WarningOutlined, CheckCircleOutlined, InfoCircleOutlined,
  RadarChartOutlined, SettingOutlined,
} from '@ant-design/icons'
import {
  getWatchlist, addToWatchlist, removeFromWatchlist,
  getWatchlistStats, getStockSignals,
} from '../services/api'
import { getColor, formatPercent } from '../utils/format'
import StockSearch from '../components/StockSearch'

const { Text, Title } = Typography

// 策略类别颜色
const CATEGORY_COLORS = {
  value: 'blue',
  momentum: 'orange',
  flow: 'green',
  event: 'purple',
  combo: 'red',
}

// 分组选项
const GROUP_OPTIONS = [
  { label: '全部', value: '' },
  { label: '默认', value: 'default' },
  { label: '观察仓', value: '观察仓' },
  { label: '重仓', value: '重仓' },
  { label: '长线', value: '长线' },
]

// 置信度颜色映射
const CONVICTION_CONFIG = {
  none: { color: '#d9d9d9', icon: <InfoCircleOutlined />, label: '无信号' },
  low: { color: '#d9d9d9', icon: <InfoCircleOutlined />, label: '低' },
  medium: { color: '#faad14', icon: <WarningOutlined />, label: '中' },
  high: { color: '#ff4d4f', icon: <ThunderboltOutlined />, label: '高' },
}

/**
 * 自选股页面（含子 Tab：管理 / 信号雷达）
 */
export default function Watchlist({ tradeDate, onSelectStock }) {
  const [activeTab, setActiveTab] = useState('manage')

  return (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      type="card"
      items={[
        {
          key: 'manage',
          label: <span><SettingOutlined /> 管理</span>,
          children: <WatchlistContent tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
        {
          key: 'radar',
          label: <span><RadarChartOutlined /> 信号雷达</span>,
          children: <WatchlistRadar tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
      ]}
    />
  )
}

/** 信号雷达子组件 — 聚焦信号检测 */
function WatchlistRadar({ tradeDate, onSelectStock }) {
  const [watchlist, setWatchlist] = useState([])
  const [loading, setLoading] = useState(false)
  const [expandedRowKeys, setExpandedRowKeys] = useState([])
  const [signalDetails, setSignalDetails] = useState({})
  const [loadingSignals, setLoadingSignals] = useState({})

  const fetchWatchlist = useCallback(async (signal) => {
    setLoading(true)
    try {
      const res = await getWatchlist(undefined, { signal })
      if (res?.success) setWatchlist(res.data || [])
    } catch (err) {
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
      console.error('Failed to load watchlist:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    fetchWatchlist(controller.signal)
    return () => controller.abort()
  }, [fetchWatchlist])

  const handleExpand = async (expanded, record) => {
    if (expanded) {
      setExpandedRowKeys((prev) => [...prev, record.ts_code])
      if (!signalDetails[record.ts_code]) {
        setLoadingSignals((prev) => ({ ...prev, [record.ts_code]: true }))
        try {
          const res = await getStockSignals(record.ts_code)
          if (res?.success && res.data) {
            setSignalDetails((prev) => ({ ...prev, [record.ts_code]: res.data }))
          }
        } catch (err) {
          if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
          console.error('Failed to load signals:', err)
        } finally {
          setLoadingSignals((prev) => ({ ...prev, [record.ts_code]: false }))
        }
      }
    } else {
      setExpandedRowKeys((prev) => prev.filter((k) => k !== record.ts_code))
    }
  }

  const columns = [
    {
      title: '信号',
      dataIndex: 'conviction',
      width: 80,
      render: (conviction, record) => {
        const config = { none: { icon: <InfoCircleOutlined /> }, low: { icon: <InfoCircleOutlined /> }, medium: { icon: <WarningOutlined /> }, high: { icon: <ThunderboltOutlined /> } }
        const c = config[conviction] || config.none
        return <Badge count={record.signal_count || 0} style={{ backgroundColor: conviction === 'high' ? '#ff4d4f' : conviction === 'medium' ? '#faad14' : '#d9d9d9', boxShadow: 'none' }}><span style={{ fontSize: 16 }}>{c.icon}</span></Badge>
      },
    },
    {
      title: '股票',
      key: 'stock',
      render: (_, record) => (
        <div>
          <Text strong style={{ cursor: 'pointer', color: '#1677ff' }} onClick={() => onSelectStock?.({ ts_code: record.ts_code, name: record.name })}>
            {record.name || record.ts_code}
          </Text>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>{record.ts_code}</Text>
        </div>
      ),
    },
    {
      title: '涨跌幅',
      dataIndex: 'pct_change',
      width: 100,
      sorter: (a, b) => (a.pct_change || 0) - (b.pct_change || 0),
      defaultSortOrder: 'descend',
      render: (v) => <Text style={{ color: getColor(v), fontWeight: 500 }}>{formatPercent(v)}</Text>,
    },
    {
      title: '触发策略',
      key: 'signals',
      render: (_, record) => {
        const signals = record.signals || []
        if (signals.length === 0) return <Text type="secondary">--</Text>
        return (
          <Space size={[4, 4]} wrap>
            {signals.slice(0, 3).map((s, i) => (
              <Tag key={i} color={CATEGORY_COLORS[s.category] || 'default'} style={{ fontSize: 11 }}>{s.icon} {s.name}</Tag>
            ))}
            {signals.length > 3 && <Tag style={{ fontSize: 11 }}>+{signals.length - 3}</Tag>}
          </Space>
        )
      },
    },
    {
      title: '置信度',
      dataIndex: 'signal_count',
      width: 120,
      sorter: (a, b) => (a.signal_count || 0) - (b.signal_count || 0),
      render: (count) => {
        const maxScore = Math.min((count || 0) / 5 * 100, 100)
        let color = '#d9d9d9'
        if (count >= 3) color = '#ff4d4f'
        else if (count >= 2) color = '#faad14'
        else if (count >= 1) color = '#1677ff'
        return <Progress percent={maxScore} strokeColor={color} size="small" format={() => `${count || 0}个`} />
      },
    },
  ]

  const radarStocks = watchlist.filter((s) => (s.signal_count || 0) > 0)

  return (
    <div style={{ padding: '0 4px' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <RadarChartOutlined style={{ fontSize: 18 }} />
          <Text strong style={{ fontSize: 16 }}>信号雷达</Text>
          <Tag>{radarStocks.length} 只有信号</Tag>
        </Space>
        <Button icon={<ReloadOutlined />} onClick={() => fetchWatchlist()} size="small">刷新</Button>
      </div>
      <Card size="small">
        <Table
          columns={columns}
          dataSource={radarStocks.map((item) => ({ ...item, key: item.ts_code }))}
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: false, showTotal: (t) => `共 ${t} 只` }}
          size="small"
          scroll={{ x: 700 }}
          expandable={{
            expandedRowKeys,
            onExpand: handleExpand,
            expandedRowRender: (record) => {
              const detail = signalDetails[record.ts_code]
              if (loadingSignals[record.ts_code]) return <div style={{ padding: 20, textAlign: 'center' }}><Spin size="small" /></div>
              if (!detail?.signals?.length) return <Empty description="今日无策略信号" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              return (
                <div style={{ padding: '8px 0' }}>
                  <Table
                    columns={[
                      { title: '策略', key: 'strategy', render: (_, r) => <Space><span style={{ fontSize: 16 }}>{r.icon}</span><Text strong>{r.name}</Text></Space> },
                      { title: '类别', dataIndex: 'category', width: 80, render: (v) => <Tag color={CATEGORY_COLORS[v] || 'default'}>{v}</Tag> },
                      { title: '评分', dataIndex: 'score', width: 100, render: (v) => <Text style={{ fontWeight: 500 }}>{v.toFixed(1)}</Text> },
                      { title: '触发原因', dataIndex: 'reason', render: (v) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text> },
                    ]}
                    dataSource={detail.signals.map((s, i) => ({ ...s, key: i }))}
                    pagination={false}
                    size="small"
                  />
                </div>
              )
            },
          }}
          locale={{ emptyText: <Empty description="暂无有信号的自选股" /> }}
        />
      </Card>
    </div>
  )
}

/** 自选股管理子组件 */
function WatchlistContent({ tradeDate, onSelectStock }) {
  const [watchlist, setWatchlist] = useState([])
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [activeGroup, setActiveGroup] = useState('')
  const [addModalVisible, setAddModalVisible] = useState(false)
  const [addingStock, setAddingStock] = useState(null)
  const [addingGroup, setAddingGroup] = useState('default')
  const [addingNotes, setAddingNotes] = useState('')
  const [addingLoading, setAddingLoading] = useState(false)
  const [expandedRowKeys, setExpandedRowKeys] = useState([])
  const [signalDetails, setSignalDetails] = useState({})
  const [loadingSignals, setLoadingSignals] = useState({})

  // 加载自选股列表
  const fetchWatchlist = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getWatchlist(activeGroup || undefined)
      if (res?.success) {
        setWatchlist(res.data || [])
      } else {
        message.error(res?.error || '加载失败')
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load watchlist:', err)
      message.error('加载自选股列表失败')
    } finally {
      setLoading(false)
    }
  }, [activeGroup])

  // 加载统计
  const fetchStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const res = await getWatchlistStats()
      if (res?.success) {
        setStats(res.data)
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load stats:', err)
    } finally {
      setStatsLoading(false)
    }
  }, [])

  // 初始化加载
  useEffect(() => {
    fetchWatchlist()
    fetchStats()
  }, [fetchWatchlist, fetchStats])

  // 添加自选股
  const handleAdd = async () => {
    if (!addingStock) {
      message.warning('请先搜索并选择一只股票')
      return
    }
    setAddingLoading(true)
    try {
      const res = await addToWatchlist(addingStock.ts_code, addingGroup, addingNotes)
      if (res?.success) {
        message.success(`已添加 ${addingStock.name || addingStock.ts_code}`)
        setAddModalVisible(false)
        setAddingStock(null)
        setAddingGroup('default')
        setAddingNotes('')
        fetchWatchlist()
        fetchStats()
      } else {
        message.warning(res?.error || '添加失败')
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to add stock:', err)
      message.error('添加失败')
    } finally {
      setAddingLoading(false)
    }
  }

  // 删除自选股
  const handleRemove = async (tsCode) => {
    try {
      const res = await removeFromWatchlist(tsCode)
      if (res?.success) {
        message.success('已删除')
        fetchWatchlist()
        fetchStats()
      } else {
        message.error(res?.error || '删除失败')
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to remove:', err)
      message.error('删除失败')
    }
  }

  // 展开行加载信号详情
  const handleExpand = async (expanded, record) => {
    if (expanded) {
      setExpandedRowKeys((prev) => [...prev, record.ts_code])
      if (!signalDetails[record.ts_code]) {
        setLoadingSignals((prev) => ({ ...prev, [record.ts_code]: true }))
        try {
          const res = await getStockSignals(record.ts_code)
          if (res?.success && res.data) {
            setSignalDetails((prev) => ({ ...prev, [record.ts_code]: res.data }))
          }
        } catch (err) {
          if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
          console.error('Failed to load signals:', err)
        } finally {
          setLoadingSignals((prev) => ({ ...prev, [record.ts_code]: false }))
        }
      }
    } else {
      setExpandedRowKeys((prev) => prev.filter((k) => k !== record.ts_code))
    }
  }

  // 表格列定义
  const columns = [
    {
      title: '信号',
      dataIndex: 'conviction',
      width: 80,
      render: (conviction, record) => {
        const config = CONVICTION_CONFIG[conviction] || CONVICTION_CONFIG.none
        return (
          <Badge
            count={record.signal_count || 0}
            style={{
              backgroundColor: config.color,
              boxShadow: 'none',
            }}
            overflowCount={99}
          >
            <span style={{ fontSize: 16 }}>{config.icon}</span>
          </Badge>
        )
      },
    },
    {
      title: '股票',
      key: 'stock',
      render: (_, record) => (
        <div>
          <Text
            strong
            style={{ cursor: 'pointer', color: '#1677ff' }}
            onClick={() => onSelectStock && onSelectStock({ ts_code: record.ts_code, name: record.name })}
          >
            {record.name || record.ts_code}
          </Text>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>{record.ts_code}</Text>
        </div>
      ),
    },
    {
      title: '最新价',
      dataIndex: 'close',
      width: 100,
      render: (v) => (
        <Text style={{ color: getColor(v), fontWeight: 500 }}>
          {v ? v.toFixed(2) : '--'}
        </Text>
      ),
    },
    {
      title: '涨跌幅',
      dataIndex: 'pct_change',
      width: 100,
      sorter: (a, b) => (a.pct_change || 0) - (b.pct_change || 0),
      defaultSortOrder: 'descend',
      render: (v) => (
        <Text style={{ color: getColor(v), fontWeight: 500 }}>
          {formatPercent(v)}
        </Text>
      ),
    },
    {
      title: '触发策略',
      key: 'signals',
      render: (_, record) => {
        const signals = record.signals || []
        if (signals.length === 0) {
          return <Text type="secondary">--</Text>
        }
        return (
          <Space size={[4, 4]} wrap>
            {signals.slice(0, 3).map((s, i) => (
              <Tag key={i} color={CATEGORY_COLORS[s.category] || 'default'} style={{ fontSize: 11 }}>
                {s.icon} {s.name}
              </Tag>
            ))}
            {signals.length > 3 && (
              <Tag style={{ fontSize: 11 }}>+{signals.length - 3}</Tag>
            )}
          </Space>
        )
      },
    },
    {
      title: '置信度',
      dataIndex: 'signal_count',
      width: 120,
      sorter: (a, b) => (a.signal_count || 0) - (b.signal_count || 0),
      render: (count) => {
        const maxScore = Math.min((count || 0) / 5 * 100, 100)
        let color = '#d9d9d9'
        if (count >= 3) color = '#ff4d4f'
        else if (count >= 2) color = '#faad14'
        else if (count >= 1) color = '#1677ff'
        return (
          <Progress
            percent={maxScore}
            strokeColor={color}
            size="small"
            format={() => `${count || 0}个`}
          />
        )
      },
    },
    {
      title: '分组',
      dataIndex: 'group_name',
      width: 90,
      render: (v) => (
        <Tag>{v || 'default'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 60,
      render: (_, record) => (
        <Popconfirm
          title="确定删除该自选股？"
          onConfirm={() => handleRemove(record.ts_code)}
          okText="确定"
          cancelText="取消"
        >
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ]

  // 展开行渲染
  const expandedRowRender = (record) => {
    const detail = signalDetails[record.ts_code]
    const isLoading = loadingSignals[record.ts_code]

    if (isLoading) {
      return <div style={{ padding: 20, textAlign: 'center' }}><Spin size="small" /></div>
    }

    if (!detail || !detail.signals || detail.signals.length === 0) {
      return <Empty description="今日无策略信号" image={Empty.PRESENTED_IMAGE_SIMPLE} />
    }

    return (
      <div style={{ padding: '8px 0' }}>
        <Table
          columns={[
            { title: '策略', key: 'strategy', render: (_, r) => (
              <Space>
                <span style={{ fontSize: 16 }}>{r.icon}</span>
                <Text strong>{r.name}</Text>
              </Space>
            )},
            { title: '类别', dataIndex: 'category', width: 80, render: (v) => (
              <Tag color={CATEGORY_COLORS[v] || 'default'}>{v}</Tag>
            )},
            { title: '评分', dataIndex: 'score', width: 100, render: (v) => (
              <Text style={{ fontWeight: 500 }}>{v.toFixed(1)}</Text>
            )},
            { title: '触发原因', dataIndex: 'reason', render: (v) => (
              <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>
            )},
          ]}
          dataSource={detail.signals.map((s, i) => ({ ...s, key: i }))}
          pagination={false}
          size="small"
        />
      </div>
    )
  }

  return (
    <div style={{ padding: '0 4px' }}>
      {/* 顶部标题栏 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Title level={4} style={{ margin: 0 }}>
            <StarFilled style={{ color: '#faad14' }} /> 自选股信号雷达
          </Title>
          {tradeDate && <Tag>{tradeDate}</Tag>}
        </Space>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddModalVisible(true)}>
            添加自选股
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => { fetchWatchlist(); fetchStats() }}>
            刷新
          </Button>
        </Space>
      </div>

      {/* 统计卡片 */}
      <Spin spinning={statsLoading}>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="自选股总数"
                value={stats?.total || 0}
                prefix={<StarOutlined style={{ color: '#faad14' }} />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="高置信 (3+策略)"
                value={stats?.convictions?.high || 0}
                valueStyle={{ color: '#ff4d4f' }}
                prefix={<ThunderboltOutlined />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="中置信 (2策略)"
                value={stats?.convictions?.medium || 0}
                valueStyle={{ color: '#faad14' }}
                prefix={<WarningOutlined />}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small">
              <Statistic
                title="今日有信号"
                value={stats?.with_signals || 0}
                valueStyle={{ color: '#52c41a' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
        </Row>
      </Spin>

      {/* 分组筛选 */}
      <div style={{ marginBottom: 16 }}>
        <Segmented
          options={GROUP_OPTIONS}
          value={activeGroup}
          onChange={setActiveGroup}
        />
      </div>

      {/* 股票列表 */}
      <Card size="small">
        <Table
          columns={columns}
          dataSource={watchlist.map((item) => ({ ...item, key: item.ts_code }))}
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: false, showTotal: (t) => `共 ${t} 只` }}
          size="small"
          scroll={{ x: 900 }}
          expandable={{
            expandedRowKeys,
            onExpand: handleExpand,
            expandedRowRender,
          }}
          locale={{
            emptyText: <Empty description="暂无自选股，点击「添加自选股」开始" />,
          }}
        />
      </Card>

      {/* 添加自选股 Modal */}
      <Modal
        title="添加自选股"
        open={addModalVisible}
        onOk={handleAdd}
        onCancel={() => {
          setAddModalVisible(false)
          setAddingStock(null)
          setAddingGroup('default')
          setAddingNotes('')
        }}
        confirmLoading={addingLoading}
        okText="添加"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>搜索股票</Text>
          <StockSearch onSelect={(item) => setAddingStock(item)} />
        </div>
        {addingStock && (
          <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 6 }}>
            <Text strong>{addingStock.name}</Text>
            <Text type="secondary" style={{ marginLeft: 8 }}>{addingStock.ts_code}</Text>
          </div>
        )}
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>分组</Text>
          <Segmented
            options={GROUP_OPTIONS.filter((o) => o.value !== '')}
            value={addingGroup}
            onChange={setAddingGroup}
            block
          />
        </div>
        <div>
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>备注</Text>
          <Input.TextArea
            placeholder="备注信息（可选）"
            value={addingNotes}
            onChange={(e) => setAddingNotes(e.target.value)}
            rows={2}
          />
        </div>
      </Modal>
    </div>
  )
}
