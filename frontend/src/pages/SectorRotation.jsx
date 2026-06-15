import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Space,
  Spin, Empty, Typography, message, Tooltip, Slider, Drawer,
} from 'antd'
import {
  ReloadOutlined, SwapOutlined, ArrowUpOutlined, ArrowDownOutlined,
  ThunderboltOutlined, PauseCircleOutlined, MinusCircleOutlined,
} from '@ant-design/icons'
import { formatAmount, getColor, scoreColor, scoreTag } from '../utils/format'

const { Text, Title } = Typography

const darkCardStyle = { background: '#ffffff', border: '1px solid #e8e8e8' }
const darkTableStyle = { background: '#ffffff' }

// 信号配置
const SIGNAL_CONFIG = {
  ROTATE_IN: { color: '#52c41a', icon: <SwapOutlined />, label: '轮入', tag: 'green' },
  ACCELERATE_IN: { color: '#1890ff', icon: <ArrowUpOutlined />, label: '加速流入', tag: 'blue' },
  ROTATE_OUT: { color: '#ff4d4f', icon: <ArrowDownOutlined />, label: '轮出', tag: 'red' },
  DECELERATE: { color: '#faad14', icon: <PauseCircleOutlined />, label: '减速', tag: 'orange' },
  NEUTRAL: { color: '#8c8c8c', icon: <MinusCircleOutlined />, label: '中性', tag: 'default' },
}

/**
 * 板块轮动雷达页面
 * 分析板块资金流向趋势，检测轮动信号，发现早期轮入板块
 */
export default function SectorRotation({ tradeDate, onSelectStock }) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [lookbackDays, setLookbackDays] = useState(10)
  const [minScore, setMinScore] = useState(0)
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [selectedSector, setSelectedSector] = useState(null)
  const [sectorStocks, setSectorStocks] = useState([])
  const [loadingStocks, setLoadingStocks] = useState(false)

  // 加载轮动数据
  const loadData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const params = { lookback_days: lookbackDays }
      if (tradeDate) params.trade_date = tradeDate
      const res = await fetch(`/api/strategies/sector-rotation?${new URLSearchParams(params)}`, { signal }).then(r => r.json())
      if (res?.success) {
        setData(res.data)
      } else {
        message.error(res?.error || '加载失败')
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Load sector rotation failed:', err)
      message.error('加载板块轮动数据失败')
    } finally {
      setLoading(false)
    }
  }, [tradeDate, lookbackDays])

  useEffect(() => {
    const controller = new AbortController()
    loadData(controller.signal)
    return () => controller.abort()
  }, [loadData])

  // 加载板块成分股
  const loadSectorStocks = useCallback(async (sectorCode, sectorName) => {
    setSelectedSector({ code: sectorCode, name: sectorName })
    setDrawerVisible(true)
    setLoadingStocks(true)
    try {
      const params = {}
      if (tradeDate) params.trade_date = tradeDate
      const res = await fetch(`/api/strategies/sector-rotation/${encodeURIComponent(sectorCode)}/stocks?${new URLSearchParams(params)}`).then(r => r.json())
      if (res?.success) {
        setSectorStocks(res.data?.stocks || [])
      } else {
        setSectorStocks([])
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Load sector stocks failed:', err)
      setSectorStocks([])
    } finally {
      setLoadingStocks(false)
    }
  }, [tradeDate])

  // 筛选板块
  const filteredSectors = (data?.sectors || []).filter(s => s.rotation_score >= minScore)

  // 统计数据
  const summary = data?.summary || {}
  const signals = summary.signals || {}

  // 板块表格列
  const sectorColumns = [
    {
      title: '排名',
      width: 60,
      render: (_, __, i) => <Text style={{ color: '#8c8c8c' }}>{i + 1}</Text>,
    },
    {
      title: '板块',
      dataIndex: 'sector_name',
      key: 'sector_name',
      render: (name, record) => (
        <Button
          type="link"
          style={{ padding: 0, color: '#e6d5ac' }}
          onClick={() => loadSectorStocks(record.sector_code, name)}
        >
          {name}
        </Button>
      ),
    },
    {
      title: '轮动评分',
      dataIndex: 'rotation_score',
      key: 'rotation_score',
      width: 100,
      sorter: (a, b) => a.rotation_score - b.rotation_score,
      defaultSortOrder: 'descend',
      render: (score) => (
        <span style={{
          color: score >= 80 ? '#ff4d4f' : score >= 60 ? '#faad14' : score >= 40 ? '#1890ff' : '#8c8c8c',
          fontWeight: 'bold',
          fontSize: 14,
        }}>
          {score.toFixed(0)}
        </span>
      ),
    },
    {
      title: '信号',
      dataIndex: 'signal',
      key: 'signal',
      width: 120,
      filters: Object.entries(SIGNAL_CONFIG).map(([k, v]) => ({ text: v.label, value: k })),
      onFilter: (value, record) => record.signal === value,
      render: (signal) => {
        const config = SIGNAL_CONFIG[signal] || SIGNAL_CONFIG.NEUTRAL
        return <Tag color={config.tag} icon={config.icon}>{config.label}</Tag>
      },
    },
    {
      title: '最新流入',
      dataIndex: 'latest_flow',
      key: 'latest_flow',
      width: 130,
      sorter: (a, b) => (a.latest_flow || 0) - (b.latest_flow || 0),
      render: (v) => <span style={{ color: getColor(v) }}>{formatAmount(v)}</span>,
    },
    {
      title: '资金动量',
      dataIndex: 'flow_momentum',
      key: 'flow_momentum',
      width: 130,
      sorter: (a, b) => (a.flow_momentum || 0) - (b.flow_momentum || 0),
      render: (v) => <span style={{ color: getColor(v) }}>{formatAmount(v)}</span>,
    },
    {
      title: '资金趋势',
      dataIndex: 'flow_trend',
      key: 'flow_trend',
      width: 130,
      sorter: (a, b) => (a.flow_trend || 0) - (b.flow_trend || 0),
      render: (v) => <span style={{ color: getColor(v) }}>{formatAmount(v)}</span>,
    },
    {
      title: '信号详情',
      dataIndex: 'signal_detail',
      key: 'signal_detail',
      ellipsis: true,
      render: (text) => <Tooltip title={text}><Text style={{ color: '#bfbfbf' }} ellipsis>{text || '--'}</Text></Tooltip>,
    },
  ]

  // 成分股表格列
  const stockColumns = [
    { title: '代码', dataIndex: 'ts_code', key: 'ts_code', width: 110 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 100 },
    {
      title: '净流入',
      dataIndex: 'net_inflow',
      key: 'net_inflow',
      width: 120,
      render: (v) => <span style={{ color: getColor(v) }}>{v != null ? formatAmount(v) : '--'}</span>,
    },
    {
      title: '大单买入',
      dataIndex: 'large_buy',
      key: 'large_buy',
      width: 120,
      render: (v) => <span style={{ color: getColor(v) }}>{v != null ? formatAmount(v) : '--'}</span>,
    },
    {
      title: '涨跌幅',
      dataIndex: 'pct_change',
      key: 'pct_change',
      width: 90,
      render: (v) => <span style={{ color: getColor(v) }}>{v != null ? `${v > 0 ? '+' : ''}${v.toFixed(2)}%` : '--'}</span>,
    },
  ]

  return (
    <div style={{ padding: '0 16px' }}>
      {/* 标题栏 */}
      <Row align="middle" justify="space-between" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0, color: '#e6d5ac' }}>
            <SwapOutlined style={{ marginRight: 8 }} />
            板块轮动雷达
          </Title>
          <Text style={{ color: '#8c8c8c' }}>
            分析板块资金流向趋势，发现早期轮入板块
          </Text>
        </Col>
        <Col>
          <Space>
            <span style={{ color: '#8c8c8c' }}>回看天数:</span>
            <Slider
              min={3}
              max={20}
              value={lookbackDays}
              onChange={setLookbackDays}
              style={{ width: 120 }}
              tooltip={{ formatter: (v) => `${v}天` }}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={loadData}
              loading={loading}
            >
              刷新
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#8c8c8c' }}>分析板块数</span>}
              value={summary.total_sectors || 0}
              valueStyle={{ color: '#e6d5ac' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#8c8c8c' }}>轮入信号</span>}
              value={signals.rotate_in || 0}
              valueStyle={{ color: '#52c41a' }}
              prefix={<SwapOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#8c8c8c' }}>加速流入</span>}
              value={signals.accelerate_in || 0}
              valueStyle={{ color: '#1890ff' }}
              prefix={<ArrowUpOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#8c8c8c' }}>轮出信号</span>}
              value={signals.rotate_out || 0}
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<ArrowDownOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#8c8c8c' }}>减速流入</span>}
              value={signals.decelerate || 0}
              valueStyle={{ color: '#faad14' }}
              prefix={<PauseCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#8c8c8c' }}>数据区间</span>}
              value={summary.date_range || '--'}
              valueStyle={{ color: '#bfbfbf', fontSize: 14 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 轮入信号提示 */}
      {summary.top_rotate_in && summary.top_rotate_in.length > 0 && (
        <Card size="small" style={{ ...darkCardStyle, marginBottom: 16, borderColor: '#52c41a' }}>
          <Space>
            <ThunderboltOutlined style={{ color: '#52c41a', fontSize: 16 }} />
            <Text style={{ color: '#52c41a', fontWeight: 'bold' }}>
              重点关注轮入板块:
            </Text>
            {summary.top_rotate_in.slice(0, 8).map((s, i) => (
              <Tag
                key={i}
                color="green"
                style={{ cursor: 'pointer' }}
                onClick={() => loadSectorStocks(s.code, s.name)}
              >
                {s.name} ({s.score.toFixed(0)}分)
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      {/* 板块轮动表格 */}
      <Card
        size="small"
        title={
          <Space>
            <span style={{ color: '#e6d5ac' }}>板块轮动排行</span>
            <Text style={{ color: '#8c8c8c', fontSize: 12 }}>
              (共 {filteredSectors.length} 个板块，评分 ≥ {minScore})
            </Text>
          </Space>
        }
        extra={
          <Space>
            <span style={{ color: '#8c8c8c', fontSize: 12 }}>最低评分:</span>
            <Slider
              min={0}
              max={100}
              value={minScore}
              onChange={setMinScore}
              style={{ width: 100 }}
            />
          </Space>
        }
        style={darkCardStyle}
      >
        <Spin spinning={loading}>
          <Table
            dataSource={filteredSectors}
            columns={sectorColumns}
            rowKey="sector_code"
            size="small"
            pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 个板块` }}
            style={darkTableStyle}
            scroll={{ x: 1100 }}
          />
        </Spin>
      </Card>

      {/* 板块成分股抽屉 */}
      <Drawer
        title={
          <Space>
            <span style={{ color: '#e6d5ac' }}>{selectedSector?.name || '板块详情'}</span>
            <Text style={{ color: '#8c8c8c', fontSize: 12 }}>{selectedSector?.code}</Text>
          </Space>
        }
        placement="right"
        width={600}
        open={drawerVisible}
        onClose={() => { setDrawerVisible(false); setSelectedSector(null); setSectorStocks([]) }}
        styles={{ body: { background: '#ffffff', padding: 16 } }}
      >
        <Spin spinning={loadingStocks}>
          {sectorStocks.length > 0 ? (
            <Table
              dataSource={sectorStocks}
              columns={stockColumns}
              rowKey="ts_code"
              size="small"
              pagination={false}
              style={darkTableStyle}
              onRow={(record) => ({
                onClick: () => {
                  if (onSelectStock) {
                    onSelectStock({ ts_code: record.ts_code, name: record.name })
                  }
                },
                style: { cursor: 'pointer' },
              })}
            />
          ) : (
            <Empty description="暂无成分股数据" />
          )}
        </Spin>
      </Drawer>
    </div>
  )
}
