import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Input, InputNumber, Row, Col, Button, Space, Tag,
  Select, Collapse, Slider, Form, Typography, Spin, Tooltip, Segmented, Tabs
} from 'antd'
import {
  SearchOutlined, FilterOutlined, SortAscendingOutlined,
  SortDescendingOutlined, ReloadOutlined, ThunderboltOutlined,
  LineChartOutlined
} from '@ant-design/icons'
import { screenStocks, screenBySignals } from '../services/api'
import { formatAmount, getColorClass, getColor } from '../utils/format'

const { Text } = Typography
const { Panel } = Collapse

/** 专业多维度选股筛选器 */
export default function StockScreener({ tradeDate, onSelectStock }) {
  const [activeTab, setActiveTab] = useState('basic')

  return (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      items={[
        {
          key: 'basic',
          label: <span><FilterOutlined /> 条件选股</span>,
          children: <BasicScreener tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
        {
          key: 'technical',
          label: <span><LineChartOutlined /> 技术指标选股</span>,
          children: <TechnicalScreener tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
      ]}
    />
  )
}

/** 条件选股子组件 */
function BasicScreener({ tradeDate, onSelectStock }) {
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [sortBy, setSortBy] = useState('total_mv')
  const [sortOrder, setSortOrder] = useState('desc')
  const [filterText, setFilterText] = useState('')
  const [activePreset, setActivePreset] = useState(null)

  // Filter state
  const [filters, setFilters] = useState({
    pe_min: null, pe_max: null,
    pb_min: null, pb_max: null,
    mv_min: null, mv_max: null,
    turnover_min: null, turnover_max: null,
    volume_ratio_min: null, volume_ratio_max: null,
    dv_min: null, dv_max: null,
    net_inflow_min: null,
    name: '',
    industry: '',
  })

  const fetchData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const params = {
        trade_date: tradeDate || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: pageSize,
      }
      // Add non-null filters
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== '') {
          params[k] = v
        }
      })
      if (filterText) params.name = filterText

      const result = await screenStocks(params, { signal })
      setData(result.data || [])
      setTotal(result.total || 0)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('选股筛选失败:', err)
      setData([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [tradeDate, filters, filterText, sortBy, sortOrder, page, pageSize])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(controller.signal)
    return () => controller.abort()
  }, [fetchData])

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setPage(1)
    setActivePreset(null)
  }

  const handleReset = () => {
    setFilters({
      pe_min: null, pe_max: null,
      pb_min: null, pb_max: null,
      mv_min: null, mv_max: null,
      turnover_min: null, turnover_max: null,
      volume_ratio_min: null, volume_ratio_max: null,
      dv_min: null, dv_max: null,
      net_inflow_min: null,
      name: '',
      industry: '',
    })
    setFilterText('')
    setPage(1)
    setActivePreset(null)
  }

  const applyPreset = (preset) => {
    setActivePreset(preset.name)
    setFilters({ ...preset.filters })
    setPage(1)
  }

  const presets = [
    {
      name: '低估值',
      label: '💎 低估值',
      filters: { pe_min: 0, pe_max: 15, pb_min: 0, pb_max: 2 },
    },
    {
      name: '高股息',
      label: '💰 高股息',
      filters: { dv_min: 3 },
    },
    {
      name: '高换手',
      label: '🔥 高换手',
      filters: { turnover_min: 5 },
    },
    {
      name: '大市值',
      label: '🏦 大市值',
      filters: { mv_min: 500 },
    },
    {
      name: '小盘股',
      label: '🚀 小盘股',
      filters: { mv_max: 50 },
    },
    {
      name: '放量上涨',
      label: '📈 放量',
      filters: { volume_ratio_min: 2, net_inflow_min: 5000 },
    },
  ]

  const handleTableChange = (pagination, filters, sorter) => {
    setPage(pagination.current)
    setPageSize(pagination.pageSize)
    if (sorter.field) {
      setSortBy(sorter.field)
      setSortOrder(sorter.order === 'ascend' ? 'asc' : 'desc')
    }
  }

  const columns = [
    {
      title: '股票',
      key: 'stock',
      width: 160,
      fixed: 'left',
      render: (_, record) => (
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{record.name || '--'}</div>
          <div style={{ fontSize: 11, color: '#8c8c8c' }}>{record.ts_code}</div>
        </div>
      ),
    },
    {
      title: '行业',
      dataIndex: 'industry',
      key: 'industry',
      width: 80,
      render: (v) => <Tag style={{ fontSize: 11 }}>{v || '--'}</Tag>,
    },
    {
      title: '收盘价',
      dataIndex: 'close',
      key: 'close',
      width: 80,
      sorter: true,
      render: (v) => <span style={{ fontWeight: 500 }}>{v ? v.toFixed(2) : '--'}</span>,
    },
    {
      title: 'PE(TTM)',
      dataIndex: 'pe_ttm',
      key: 'pe_ttm',
      width: 90,
      sorter: true,
      render: (v) => {
        if (!v || v === 0) return <span style={{ color: '#8c8c8c' }}>--</span>
        const color = v < 0 ? '#cf1322' : v < 15 ? '#3f8600' : v < 30 ? '#d48806' : '#cf1322'
        return <span style={{ color, fontWeight: 500 }}>{v.toFixed(2)}</span>
      },
    },
    {
      title: 'PB',
      dataIndex: 'pb',
      key: 'pb',
      width: 70,
      sorter: true,
      render: (v) => {
        if (!v || v === 0) return <span style={{ color: '#8c8c8c' }}>--</span>
        return <span style={{ fontWeight: 500 }}>{v.toFixed(2)}</span>
      },
    },
    {
      title: '总市值(亿)',
      dataIndex: 'total_mv',
      key: 'total_mv',
      width: 100,
      sorter: true,
      defaultSortOrder: 'descend',
      render: (v) => {
        if (!v) return '--'
        const yi = v / 10000
        return <span>{yi >= 1000 ? `${(yi / 1000).toFixed(1)}千亿` : `${yi.toFixed(0)}亿`}</span>
      },
    },
    {
      title: '流通市值(亿)',
      dataIndex: 'circ_mv',
      key: 'circ_mv',
      width: 100,
      sorter: true,
      render: (v) => {
        if (!v) return '--'
        const yi = v / 10000
        return <span>{yi >= 1000 ? `${(yi / 1000).toFixed(1)}千亿` : `${yi.toFixed(0)}亿`}</span>
      },
    },
    {
      title: '换手率(%)',
      dataIndex: 'turnover_rate',
      key: 'turnover_rate',
      width: 90,
      sorter: true,
      render: (v) => {
        if (!v) return '--'
        const color = v > 10 ? '#cf1322' : v > 5 ? '#d48806' : '#3f8600'
        return <span style={{ color, fontWeight: 500 }}>{v.toFixed(2)}%</span>
      },
    },
    {
      title: '量比',
      dataIndex: 'volume_ratio',
      key: 'volume_ratio',
      width: 70,
      sorter: true,
      render: (v) => {
        if (!v) return '--'
        const color = v > 2 ? '#cf1322' : v > 1.5 ? '#d48806' : '#8c8c8c'
        return <span style={{ color }}>{v.toFixed(2)}</span>
      },
    },
    {
      title: '股息率(%)',
      dataIndex: 'dv_ttm',
      key: 'dv_ttm',
      width: 90,
      sorter: true,
      render: (v) => {
        if (!v) return '--'
        return <span style={{ color: v > 3 ? '#3f8600' : '#8c8c8c', fontWeight: v > 3 ? 600 : 400 }}>{v.toFixed(2)}%</span>
      },
    },
    {
      title: '净流入(万)',
      dataIndex: 'net_amount',
      key: 'net_amount',
      width: 110,
      sorter: true,
      render: (v) => {
        if (!v) return <span style={{ color: '#8c8c8c' }}>--</span>
        const color = v > 0 ? '#cf1322' : '#3f8600'
        const sign = v > 0 ? '+' : ''
        return (
          <Tooltip title={`${sign}${(v / 10000).toFixed(2)}亿`}>
            <span style={{ color, fontWeight: 600 }}>{sign}{(v / 10000).toFixed(2)}亿</span>
          </Tooltip>
        )
      },
    },
  ]

  return (
    <div>
      {/* 快速筛选预设 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap size={[8, 8]}>
          <Text type="secondary" style={{ fontSize: 12, marginRight: 4 }}>⚡ 快速筛选:</Text>
          {presets.map(p => (
            <Button
              key={p.name}
              size="small"
              type={activePreset === p.name ? 'primary' : 'default'}
              onClick={() => applyPreset(p)}
            >
              {p.label}
            </Button>
          ))}
          <Button size="small" onClick={handleReset} icon={<ReloadOutlined />}>
            重置
          </Button>
        </Space>
      </Card>

      {/* 筛选条件面板 */}
      <Collapse
        defaultActiveKey={['filters']}
        style={{ marginBottom: 12 }}
        size="small"
      >
        <Panel
          header={
            <Space>
              <FilterOutlined />
              <span>筛选条件</span>
              {Object.values(filters).some(v => v !== null && v !== '') && (
                <Tag color="blue" style={{ marginLeft: 8 }}>
                  已启用
                </Tag>
              )}
            </Space>
          }
          key="filters"
        >
          <Form layout="vertical" size="small">
            <Row gutter={[16, 8]}>
              {/* 名称搜索 */}
              <Col xs={24} sm={12} md={8} lg={6}>
                <Form.Item label="股票名称/代码" style={{ marginBottom: 0 }}>
                  <Input
                    placeholder="如: 贵州茅台 / 600519"
                    prefix={<SearchOutlined />}
                    value={filterText}
                    onChange={e => { setFilterText(e.target.value); setPage(1) }}
                    allowClear
                  />
                </Form.Item>
              </Col>

              {/* PE(TTM) */}
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="PE(TTM) 最小" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 0"
                    value={filters.pe_min}
                    onChange={v => handleFilterChange('pe_min', v)}
                    min={0}
                  />
                </Form.Item>
              </Col>
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="PE(TTM) 最大" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 30"
                    value={filters.pe_max}
                    onChange={v => handleFilterChange('pe_max', v)}
                    min={0}
                  />
                </Form.Item>
              </Col>

              {/* PB */}
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="PB 最小" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 0"
                    value={filters.pb_min}
                    onChange={v => handleFilterChange('pb_min', v)}
                    min={0}
                  />
                </Form.Item>
              </Col>
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="PB 最大" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 5"
                    value={filters.pb_max}
                    onChange={v => handleFilterChange('pb_max', v)}
                    min={0}
                  />
                </Form.Item>
              </Col>

              {/* 总市值 */}
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="总市值 ≥ (亿)" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 100"
                    value={filters.mv_min}
                    onChange={v => handleFilterChange('mv_min', v)}
                    min={0}
                  />
                </Form.Item>
              </Col>
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="总市值 ≤ (亿)" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 1000"
                    value={filters.mv_max}
                    onChange={v => handleFilterChange('mv_max', v)}
                    min={0}
                  />
                </Form.Item>
              </Col>

              {/* 换手率 */}
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="换手率 ≥ (%)" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 1"
                    value={filters.turnover_min}
                    onChange={v => handleFilterChange('turnover_min', v)}
                    min={0}
                    step={0.5}
                  />
                </Form.Item>
              </Col>
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="换手率 ≤ (%)" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 10"
                    value={filters.turnover_max}
                    onChange={v => handleFilterChange('turnover_max', v)}
                    min={0}
                    step={0.5}
                  />
                </Form.Item>
              </Col>

              {/* 量比 */}
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="量比 ≥" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 1.5"
                    value={filters.volume_ratio_min}
                    onChange={v => handleFilterChange('volume_ratio_min', v)}
                    min={0}
                    step={0.1}
                  />
                </Form.Item>
              </Col>
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="量比 ≤" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 3"
                    value={filters.volume_ratio_max}
                    onChange={v => handleFilterChange('volume_ratio_max', v)}
                    min={0}
                    step={0.1}
                  />
                </Form.Item>
              </Col>

              {/* 股息率 */}
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="股息率 ≥ (%)" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 2"
                    value={filters.dv_min}
                    onChange={v => handleFilterChange('dv_min', v)}
                    min={0}
                    step={0.5}
                  />
                </Form.Item>
              </Col>
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="股息率 ≤ (%)" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 10"
                    value={filters.dv_max}
                    onChange={v => handleFilterChange('dv_max', v)}
                    min={0}
                    step={0.5}
                  />
                </Form.Item>
              </Col>

              {/* 净流入 */}
              <Col xs={12} sm={6} md={4} lg={3}>
                <Form.Item label="净流入 ≥ (万)" style={{ marginBottom: 0 }}>
                  <InputNumber
                    style={{ width: '100%' }}
                    placeholder="如: 1000"
                    value={filters.net_inflow_min}
                    onChange={v => handleFilterChange('net_inflow_min', v)}
                  />
                </Form.Item>
              </Col>
            </Row>
          </Form>
        </Panel>
      </Collapse>

      {/* 结果表格 */}
      <Card size="small">
        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            共 <Text strong>{total.toLocaleString()}</Text> 只股票符合条件
            {tradeDate && <span> | 交易日: {tradeDate.slice(0, 4)}-{tradeDate.slice(4, 6)}-{tradeDate.slice(6, 8)}</span>}
          </Text>
          <Space size={4}>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={fetchData}
              loading={loading}
            >
              刷新
            </Button>
          </Space>
        </div>

        <Table
          dataSource={data}
          columns={columns}
          rowKey="ts_code"
          loading={loading}
          size="small"
          scroll={{ x: 1200 }}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            pageSizeOptions: ['20', '50', '100'],
            showTotal: (total) => `共 ${total} 条`,
            size: 'small',
          }}
          onChange={handleTableChange}
          onRow={(record) => ({
            onClick: () => onSelectStock && onSelectStock(record),
            style: { cursor: 'pointer' },
          })}
          rowClassName={(record, index) => index % 2 === 0 ? 'row-light' : 'row-dark'}
        />
      </Card>

      {/* 使用说明 */}
      <Card size="small" style={{ marginTop: 12 }}>
        <Space direction="vertical" size={2}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            📌 使用方法: 设置筛选条件后自动筛选，点击表头可排序
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            📌 数据来源: TuShare daily_basic + 东方财富资金流向
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            📌 点击股票行可跳转到个股详情
          </Text>
        </Space>
      </Card>
    </div>
  )
}

/** 技术指标选股子组件 */
function TechnicalScreener({ tradeDate, onSelectStock }) {
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  // Active signals
  const [activeSignals, setActiveSignals] = useState(new Set())

  const signalButtons = [
    { key: 'macd_golden', label: 'MACD金叉', color: '#cf1322' },
    { key: 'macd_dead', label: 'MACD死叉', color: '#3f8600' },
    { key: 'kdj_oversold', label: 'KDJ超卖', color: '#cf1322' },
    { key: 'kdj_overbought', label: 'KDJ超买', color: '#3f8600' },
    { key: 'rsi_oversold', label: 'RSI超卖', color: '#cf1322' },
    { key: 'rsi_overbought', label: 'RSI超买', color: '#3f8600' },
    { key: 'boll_break_upper', label: '突破上轨', color: '#cf1322' },
    { key: 'boll_break_lower', label: '跌破下轨', color: '#3f8600' },
    { key: 'cci_oversold', label: 'CCI超卖', color: '#cf1322' },
    { key: 'cci_overbought', label: 'CCI超买', color: '#3f8600' },
  ]

  const toggleSignal = (key) => {
    setActiveSignals(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
    setPage(1)
  }

  const fetchData = useCallback(async (signal) => {
    if (activeSignals.size === 0) {
      setData([])
      setTotal(0)
      return
    }
    setLoading(true)
    try {
      const params = {
        trade_date: tradeDate || undefined,
        page,
        page_size: pageSize,
      }
      activeSignals.forEach(s => { params[s] = true })

      const result = await screenBySignals(params, { signal })
      setData(result.data || [])
      setTotal(result.total || 0)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('技术指标选股失败:', err)
      setData([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [tradeDate, activeSignals, page, pageSize])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(controller.signal)
    return () => controller.abort()
  }, [fetchData])

  const columns = [
    {
      title: '股票',
      key: 'stock',
      width: 140,
      fixed: 'left',
      render: (_, record) => (
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{record.name || '--'}</div>
          <div style={{ fontSize: 11, color: '#8c8c8c' }}>{record.ts_code}</div>
        </div>
      ),
    },
    {
      title: '行业',
      dataIndex: 'industry',
      key: 'industry',
      width: 70,
      render: (v) => <Tag style={{ fontSize: 11 }}>{v || '--'}</Tag>,
    },
    {
      title: '收盘价',
      dataIndex: 'close',
      key: 'close',
      width: 80,
      render: (v) => <span style={{ fontWeight: 500 }}>{v ? v.toFixed(2) : '--'}</span>,
    },
    {
      title: '涨跌幅',
      dataIndex: 'pct_change',
      key: 'pct_change',
      width: 80,
      render: (v) => {
        if (!v) return '--'
        const color = v > 0 ? '#cf1322' : v < 0 ? '#3f8600' : '#8c8c8c'
        const sign = v > 0 ? '+' : ''
        return <span style={{ color, fontWeight: 600 }}>{sign}{v.toFixed(2)}%</span>
      },
    },
    {
      title: 'MACD',
      key: 'macd',
      width: 150,
      render: (_, record) => (
        <div style={{ fontSize: 11, lineHeight: 1.4 }}>
          <div>DIF: {(record.macd_dif || 0).toFixed(4)}</div>
          <div>DEA: {(record.macd_dea || 0).toFixed(4)}</div>
          <div style={{ color: (record.macd || 0) > 0 ? '#cf1322' : '#3f8600' }}>
            MACD: {(record.macd || 0).toFixed(4)}
          </div>
        </div>
      ),
    },
    {
      title: 'KDJ',
      key: 'kdj',
      width: 100,
      render: (_, record) => (
        <div style={{ fontSize: 11, lineHeight: 1.4 }}>
          <div>K: {(record.kdj_k || 0).toFixed(2)}</div>
          <div>D: {(record.kdj_d || 0).toFixed(2)}</div>
          <div>J: {(record.kdj_j || 0).toFixed(2)}</div>
        </div>
      ),
    },
    {
      title: 'RSI',
      key: 'rsi',
      width: 100,
      render: (_, record) => (
        <div style={{ fontSize: 11, lineHeight: 1.4 }}>
          <div>RSI6: {(record.rsi_6 || 0).toFixed(2)}</div>
          <div>RSI12: {(record.rsi_12 || 0).toFixed(2)}</div>
          <div>RSI24: {(record.rsi_24 || 0).toFixed(2)}</div>
        </div>
      ),
    },
    {
      title: '布林带',
      key: 'boll',
      width: 120,
      render: (_, record) => (
        <div style={{ fontSize: 11, lineHeight: 1.4 }}>
          <div>上: {(record.boll_upper || 0).toFixed(2)}</div>
          <div>中: {(record.boll_mid || 0).toFixed(2)}</div>
          <div>下: {(record.boll_lower || 0).toFixed(2)}</div>
        </div>
      ),
    },
    {
      title: 'CCI',
      dataIndex: 'cci',
      key: 'cci',
      width: 70,
      render: (v) => {
        if (!v) return '--'
        const color = v > 100 ? '#cf1322' : v < -100 ? '#3f8600' : '#8c8c8c'
        return <span style={{ color, fontWeight: 500 }}>{v.toFixed(2)}</span>
      },
    },
    {
      title: '信号',
      key: 'signals',
      width: 180,
      render: (_, record) => (
        <Space size={[4, 4]} wrap>
          {(record.signal_summary || []).map((sig, i) => (
            <Tag key={i} color={
              sig.includes('超买') || sig.includes('死叉') || sig.includes('空头') || sig.includes('跌破') ? 'green' :
              sig.includes('超卖') || sig.includes('金叉') || sig.includes('多头') || sig.includes('突破') ? 'red' : 'blue'
            } style={{ fontSize: 10, margin: 0 }}>
              {sig}
            </Tag>
          ))}
        </Space>
      ),
    },
  ]

  return (
    <div>
      {/* 信号快捷按钮 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap size={[8, 8]}>
          <Text type="secondary" style={{ fontSize: 12, marginRight: 4 }}>⚡ 信号筛选（可多选组合）:</Text>
          {signalButtons.map(btn => (
            <Button
              key={btn.key}
              size="small"
              type={activeSignals.has(btn.key) ? 'primary' : 'default'}
              style={activeSignals.has(btn.key) ? { backgroundColor: btn.color, borderColor: btn.color } : {}}
              onClick={() => toggleSignal(btn.key)}
            >
              {btn.label}
            </Button>
          ))}
          {activeSignals.size > 0 && (
            <Button size="small" onClick={() => { setActiveSignals(new Set()); setPage(1) }} icon={<ReloadOutlined />}>
              清除全部
            </Button>
          )}
        </Space>
      </Card>

      {/* 结果表格 */}
      <Card size="small">
        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {activeSignals.size === 0 ? (
              '请选择至少一个技术信号'
            ) : (
              <>
                共 <Text strong>{total.toLocaleString()}</Text> 只股票符合条件
                {tradeDate && <span> | 交易日: {tradeDate.slice(0, 4)}-{tradeDate.slice(4, 6)}-{tradeDate.slice(6, 8)}</span>}
              </>
            )}
          </Text>
          <Space size={4}>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={fetchData}
              loading={loading}
              disabled={activeSignals.size === 0}
            >
              刷新
            </Button>
          </Space>
        </div>

        <Table
          dataSource={data}
          columns={columns}
          rowKey="ts_code"
          loading={loading}
          size="small"
          scroll={{ x: 1400 }}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            pageSizeOptions: ['20', '50', '100'],
            showTotal: (total) => `共 ${total} 条`,
            size: 'small',
          }}
          onChange={(pagination) => {
            setPage(pagination.current)
            setPageSize(pagination.pageSize)
          }}
          onRow={(record) => ({
            onClick: () => onSelectStock && onSelectStock(record),
            style: { cursor: 'pointer' },
          })}
          rowClassName={(record, index) => index % 2 === 0 ? 'row-light' : 'row-dark'}
        />
      </Card>

      {/* 使用说明 */}
      <Card size="small" style={{ marginTop: 12 }}>
        <Space direction="vertical" size={2}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            📌 使用方法: 点击信号按钮可多选组合，同时满足所有条件的股票会被筛选出来
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            📌 金叉/死叉信号需要对比前一交易日数据判断
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            📌 数据来源: TuShare stk_factor 技术指标接口
          </Text>
        </Space>
      </Card>
    </div>
  )
}
