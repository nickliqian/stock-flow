import React, { useState, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Space,
  Spin, Empty, Typography, message, Select, Drawer, Descriptions,
} from 'antd'
import {
  ReloadOutlined, SearchOutlined, ArrowUpOutlined, ArrowDownOutlined,
  LineChartOutlined, FundOutlined,
} from '@ant-design/icons'
import { getDivergenceScan, analyzeStockFlow } from '../services/api'
import { formatAmount, getColor, scoreColor, scoreTag } from '../utils/format'

const { Text, Title, Paragraph } = Typography

const darkCardStyle = { background: '#ffffff', border: '1px solid #e8e8e8' }
const darkTableStyle = { background: '#ffffff' }

export default function FlowIntelligence({ tradeDate, onSelectStock }) {
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [lookbackDays, setLookbackDays] = useState(10)
  const [signalType, setSignalType] = useState('all')
  const [minStrength, setMinStrength] = useState(50)
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [selectedStock, setSelectedStock] = useState(null)
  const [stockDetail, setStockDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const handleScan = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        lookback_days: lookbackDays,
        signal_type: signalType,
        min_strength: minStrength,
      }
      if (tradeDate) params.trade_date = tradeDate
      const res = await getDivergenceScan(params)
      if (res?.success) {
        setResults(res.data)
        message.success('背离扫描完成')
      } else {
        message.error(res?.error || '扫描失败')
      }
    } catch (err) {
      console.error('Divergence scan failed:', err)
      message.error('扫描失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [tradeDate, lookbackDays, signalType, minStrength])

  const handleViewDetail = useCallback(async (record) => {
    setSelectedStock(record)
    setDrawerVisible(true)
    setDetailLoading(true)
    try {
      const res = await analyzeStockFlow(record.ts_code, lookbackDays)
      if (res?.success) {
        setStockDetail(res.data)
      } else {
        setStockDetail(null)
        message.error('加载详情失败')
      }
    } catch (err) {
      console.error('Load stock detail failed:', err)
      setStockDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }, [lookbackDays])

  const summary = results?.summary || {}
  const resultList = results?.results || []
  const hasResults = resultList.length > 0

  // 表格列
  const columns = [
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
          <div>
            <Text code style={{ fontSize: 12 }}>{record.ts_code}</Text>
          </div>
          <div>
            <Text strong style={{ fontSize: 13 }}>{record.name || record.ts_code}</Text>
          </div>
          {record.industry && (
            <div>
              <Tag style={{ fontSize: 11, marginTop: 2 }}>{record.industry}</Tag>
            </div>
          )}
        </div>
      ),
    },
    {
      title: '信号',
      dataIndex: 'signal_type',
      width: 100,
      render: (v) => (
        <Tag color={v === 'bullish' ? 'green' : 'red'} style={{ fontWeight: 600 }}>
          {v === 'bullish' ? '🟢 看涨' : '🔴 看跌'}
        </Tag>
      ),
    },
    {
      title: '强度',
      dataIndex: 'signal_strength',
      width: 100,
      sorter: (a, b) => a.signal_strength - b.signal_strength,
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ color: scoreColor(v), fontWeight: 600, fontSize: 14 }}>
          {v.toFixed(1)}
        </span>
      ),
    },
    {
      title: '价格趋势',
      dataIndex: 'price_trend',
      width: 110,
      render: (v) => (
        <span style={{ color: getColor(v), fontWeight: 500 }}>
          {v > 0 ? '+' : ''}{(v || 0).toFixed(2)}%
        </span>
      ),
    },
    {
      title: '资金趋势',
      dataIndex: 'flow_trend',
      width: 130,
      render: (v) => (
        <span style={{ color: getColor(v), fontWeight: 500 }}>
          {formatAmount(v)}
        </span>
      ),
    },
    {
      title: '详情',
      width: 80,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<SearchOutlined />}
          onClick={(e) => {
            e.stopPropagation()
            handleViewDetail(record)
          }}
        >
          分析
        </Button>
      ),
    },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      {/* Header */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space direction="vertical" size={0}>
          <Title level={4} style={{ margin: 0, color: '#1f1f1f' }}>
            📊 资金流向背离分析
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            检测价格与资金流向的背离信号，提前识别机构吸筹/出货行为
          </Text>
        </Space>
      </div>

      {/* Controls */}
      <Card
        style={{ ...darkCardStyle, marginBottom: 16 }}
        styles={{ body: { padding: '12px 16px' } }}
      >
        <Space wrap size={16} style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space wrap size={12}>
            <Space size={4}>
              <Text style={{ color: '#aaa', fontSize: 13 }}>回看天数:</Text>
              <Select
                value={lookbackDays}
                onChange={setLookbackDays}
                size="small"
                style={{ width: 80 }}
                options={[
                  { value: 5, label: '5天' },
                  { value: 10, label: '10天' },
                  { value: 15, label: '15天' },
                  { value: 20, label: '20天' },
                ]}
              />
            </Space>
            <Space size={4}>
              <Text style={{ color: '#aaa', fontSize: 13 }}>信号类型:</Text>
              <Select
                value={signalType}
                onChange={setSignalType}
                size="small"
                style={{ width: 120 }}
                options={[
                  { value: 'all', label: '全部' },
                  { value: 'bullish', label: '看涨背离' },
                  { value: 'bearish', label: '看跌背离' },
                ]}
              />
            </Space>
            <Space size={4}>
              <Text style={{ color: '#aaa', fontSize: 13 }}>最低强度:</Text>
              <Select
                value={minStrength}
                onChange={setMinStrength}
                size="small"
                style={{ width: 80 }}
                options={[
                  { value: 30, label: '30' },
                  { value: 50, label: '50' },
                  { value: 70, label: '70' },
                  { value: 80, label: '80' },
                ]}
              />
            </Space>
          </Space>
          <Space>
            <Button
              type="primary"
              icon={<LineChartOutlined />}
              onClick={handleScan}
              loading={loading}
            >
              开始扫描
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                setResults(null)
                setLookbackDays(10)
                setSignalType('all')
                setMinStrength(50)
              }}
            >
              重置
            </Button>
          </Space>
        </Space>
      </Card>

      {/* Stats Cards */}
      <Row gutter={[16, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#aaa' }}>总扫描股票</span>}
              value={summary.total_scanned || 0}
              suffix="只"
              valueStyle={{ color: '#e0e0e0' }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#aaa' }}>看涨背离</span>}
              value={summary.bullish_divergence || 0}
              suffix="只"
              valueStyle={{ color: '#52c41a' }}
              prefix={<ArrowUpOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#aaa' }}>看跌背离</span>}
              value={summary.bearish_divergence || 0}
              suffix="只"
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<ArrowDownOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" style={darkCardStyle}>
            <Statistic
              title={<span style={{ color: '#aaa' }}>强信号</span>}
              value={summary.strong_signals || 0}
              suffix="只"
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Results Table */}
      <Card
        title={
          <Space>
            <FundOutlined />
            <span style={{ color: '#e0e0e0' }}>
              背离信号列表
              {hasResults && <Text type="secondary" style={{ fontSize: 13, marginLeft: 8 }}>共 {resultList.length} 只</Text>}
            </span>
          </Space>
        }
        style={{ ...darkCardStyle, marginBottom: 16 }}
        styles={{ header: { background: '#fafafa', borderBottom: '1px solid #e8e8e8' } }}
      >
        <Spin spinning={loading}>
          {!results ? (
            <Empty
              description="点击「开始扫描」检测资金流向背离信号"
              style={{ padding: 40 }}
            />
          ) : !hasResults ? (
            <Empty description="当前筛选条件下未发现背离信号" />
          ) : (
            <Table
              columns={columns}
              dataSource={resultList.map((r, i) => ({ ...r, key: `${r.ts_code}-${i}` }))}
              pagination={{
                pageSize: 20,
                showSizeChanger: false,
                showTotal: (t) => `共 ${t} 只股票`,
              }}
              size="small"
              scroll={{ x: 750 }}
              style={darkTableStyle}
              onRow={(record) => ({
                onClick: () => handleViewDetail(record),
                style: { cursor: 'pointer' },
              })}
              rowClassName={() => 'dark-table-row'}
            />
          )}
        </Spin>
      </Card>

      {/* Detail Drawer */}
      <Drawer
        title={
          <Space>
            <span>📊</span>
            <span style={{ color: '#e0e0e0' }}>
              {selectedStock?.name || selectedStock?.ts_code} 资金背离分析
            </span>
          </Space>
        }
        placement="right"
        width={600}
        open={drawerVisible}
        onClose={() => {
          setDrawerVisible(false)
          setSelectedStock(null)
          setStockDetail(null)
        }}
        styles={{
          header: { background: '#fafafa', borderBottom: '1px solid #e8e8e8' },
          body: { background: '#ffffff', padding: '16px 24px' },
        }}
      >
        <Spin spinning={detailLoading}>
          {stockDetail ? (
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              {/* 基本信息 */}
              <Card
                size="small"
                style={darkCardStyle}
                title={<span style={{ color: '#aaa', fontSize: 13 }}>基本信息</span>}
                styles={{ header: { background: '#fafafa' } }}
              >
                <Descriptions column={2} size="small">
                  <Descriptions.Item label={<span style={{ color: '#aaa' }}>股票代码</span>}>
                    <Text code>{stockDetail.ts_code}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={<span style={{ color: '#aaa' }}>股票名称</span>}>
                    <Text strong>{stockDetail.name}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={<span style={{ color: '#aaa' }}>行业</span>}>
                    {stockDetail.industry || '--'}
                  </Descriptions.Item>
                  <Descriptions.Item label={<span style={{ color: '#aaa' }}>总市值</span>}>
                    {stockDetail.total_mv_yi ? `${stockDetail.total_mv_yi}亿` : '--'}
                  </Descriptions.Item>
                  <Descriptions.Item label={<span style={{ color: '#aaa' }}>当前信号</span>}>
                    <Tag color={stockDetail.current_signal === 'bullish' ? 'green' : stockDetail.current_signal === 'bearish' ? 'red' : 'default'}>
                      {stockDetail.current_signal === 'bullish' ? '🟢 看涨背离' : stockDetail.current_signal === 'bearish' ? '🔴 看跌背离' : '无信号'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label={<span style={{ color: '#aaa' }}>信号强度</span>}>
                    {scoreTag(stockDetail.signal_strength || 0)}
                  </Descriptions.Item>
                </Descriptions>
              </Card>

              {/* 背离分析 */}
              {stockDetail.divergence_analysis && (
                <Card
                  size="small"
                  style={darkCardStyle}
                  title={<span style={{ color: '#aaa', fontSize: 13 }}>背离分析</span>}
                  styles={{ header: { background: '#fafafa' } }}
                >
                  <Row gutter={16}>
                    <Col span={8}>
                      <Statistic
                        title={<span style={{ color: '#aaa', fontSize: 12 }}>价格趋势</span>}
                        value={stockDetail.price_trend || 0}
                        suffix="%"
                        valueStyle={{ color: getColor(stockDetail.price_trend || 0), fontSize: 16 }}
                        precision={2}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title={<span style={{ color: '#aaa', fontSize: 12 }}>资金趋势</span>}
                        value={formatAmount(stockDetail.flow_trend || 0)}
                        valueStyle={{ color: getColor(stockDetail.flow_trend || 0), fontSize: 16 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title={<span style={{ color: '#aaa', fontSize: 12 }}>5日趋势</span>}
                        value={stockDetail.price_trend_5d || 0}
                        suffix="%"
                        valueStyle={{ color: getColor(stockDetail.price_trend_5d || 0), fontSize: 16 }}
                        precision={2}
                      />
                    </Col>
                  </Row>
                  <Paragraph style={{ marginTop: 12, color: '#ccc', fontSize: 13, marginBottom: 0 }}>
                    {stockDetail.divergence_analysis.interpretation}
                  </Paragraph>
                </Card>
              )}

              {/* 流量动量与持续性 */}
              <Row gutter={16}>
                <Col span={12}>
                  <Card
                    size="small"
                    style={darkCardStyle}
                    title={<span style={{ color: '#aaa', fontSize: 13 }}>流量动量</span>}
                    styles={{ header: { background: '#fafafa' } }}
                  >
                    {stockDetail.flow_momentum && (
                      <Descriptions column={1} size="small">
                        <Descriptions.Item label={<span style={{ color: '#aaa' }}>加速度</span>}>
                          <Text style={{ color: stockDetail.flow_momentum.acceleration > 1 ? '#52c41a' : stockDetail.flow_momentum.acceleration < 1 ? '#ff4d4f' : '#999' }}>
                            {stockDetail.flow_momentum.acceleration?.toFixed(2) || '--'}
                          </Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={<span style={{ color: '#aaa' }}>趋势</span>}>
                          <Tag color={stockDetail.flow_momentum.trend === 'up' ? 'green' : stockDetail.flow_momentum.trend === 'down' ? 'red' : 'default'}>
                            {stockDetail.flow_momentum.trend === 'up' ? '加速' : stockDetail.flow_momentum.trend === 'down' ? '减速' : '平稳'}
                          </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label={<span style={{ color: '#aaa' }}>动量评分</span>}>
                          {scoreTag(stockDetail.flow_momentum.momentum_score || 0)}
                        </Descriptions.Item>
                      </Descriptions>
                    )}
                  </Card>
                </Col>
                <Col span={12}>
                  <Card
                    size="small"
                    style={darkCardStyle}
                    title={<span style={{ color: '#aaa', fontSize: 13 }}>流量持续性</span>}
                    styles={{ header: { background: '#fafafa' } }}
                  >
                    {stockDetail.flow_persistence && (
                      <Descriptions column={1} size="small">
                        <Descriptions.Item label={<span style={{ color: '#aaa' }}>流入天数</span>}>
                          <Text style={{ color: '#52c41a' }}>{stockDetail.flow_persistence.inflow_days || 0} 天</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={<span style={{ color: '#aaa' }}>流出天数</span>}>
                          <Text style={{ color: '#ff4d4f' }}>{stockDetail.flow_persistence.outflow_days || 0} 天</Text>
                        </Descriptions.Item>
                        <Descriptions.Item label={<span style={{ color: '#aaa' }}>持续性评分</span>}>
                          {scoreTag(stockDetail.flow_persistence.persistence_score || 0)}
                        </Descriptions.Item>
                      </Descriptions>
                    )}
                  </Card>
                </Col>
              </Row>

              {/* 每日明细 */}
              {stockDetail.daily_detail && stockDetail.daily_detail.length > 0 && (
                <Card
                  size="small"
                  style={darkCardStyle}
                  title={<span style={{ color: '#aaa', fontSize: 13 }}>每日明细</span>}
                  styles={{ header: { background: '#fafafa' } }}
                >
                  <Table
                    dataSource={stockDetail.daily_detail.map((d, i) => ({ ...d, key: i }))}
                    columns={[
                      {
                        title: <span style={{ color: '#aaa', fontSize: 12 }}>日期</span>,
                        dataIndex: 'trade_date',
                        width: 100,
                        render: (v) => <Text style={{ color: '#ccc', fontSize: 12 }}>{v}</Text>,
                      },
                      {
                        title: <span style={{ color: '#aaa', fontSize: 12 }}>收盘价</span>,
                        dataIndex: 'close',
                        width: 80,
                        render: (v) => <Text style={{ color: '#ccc', fontSize: 12 }}>{v}</Text>,
                      },
                      {
                        title: <span style={{ color: '#aaa', fontSize: 12 }}>涨跌幅</span>,
                        dataIndex: 'pct_change',
                        width: 80,
                        render: (v) => (
                          <Text style={{ color: getColor(v), fontSize: 12, fontWeight: 500 }}>
                            {v > 0 ? '+' : ''}{v}%
                          </Text>
                        ),
                      },
                      {
                        title: <span style={{ color: '#aaa', fontSize: 12 }}>主力净流入</span>,
                        dataIndex: 'main_fund_net',
                        render: (v) => (
                          <Text style={{ color: getColor(v), fontSize: 12 }}>
                            {formatAmount(v)}
                          </Text>
                        ),
                      },
                    ]}
                    pagination={false}
                    size="small"
                    scroll={{ x: 400 }}
                    style={darkTableStyle}
                  />
                </Card>
              )}
            </Space>
          ) : (
            <Empty description="暂无详情数据" />
          )}
        </Spin>
      </Drawer>

      {/* Dark table row styling */}
      <style>{`
        .dark-table-row:hover > td {
          background: #fafafa !important;
        }
        .ant-table-wrapper .ant-table {
          background: #ffffff !important;
        }
        .ant-table-wrapper .ant-table-thead > tr > th {
          background: #fafafa !important;
          color: #666 !important;
          border-bottom: 1px solid #e8e8e8 !important;
        }
        .ant-table-wrapper .ant-table-tbody > tr > td {
          border-bottom: 1px solid #f0f0f0 !important;
          color: #333 !important;
        }
        .ant-table-wrapper .ant-table-tbody > tr:hover > td {
          background: #fafafa !important;
        }
        .ant-statistic-title {
          color: #666 !important;
        }
      `}</style>
    </div>
  )
}
