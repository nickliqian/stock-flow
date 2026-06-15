import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Card, Row, Col, Statistic, Table, Tag, Spin, Typography, Tooltip, Button,
  Segmented, Slider, Input, Empty, Space, Drawer, Divider, Badge,
} from 'antd'
import {
  ReloadOutlined, SearchOutlined, SwapOutlined, LineChartOutlined,
  RiseOutlined, FallOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ExperimentOutlined, ThunderboltOutlined,
} from '@ant-design/icons'
import { apiCall } from '../services/api'

const { Text, Title } = Typography

/* =====================================================================
 * 工具函数
 * ===================================================================== */

/** z-score 颜色 */
function zscoreColor(z) {
  const abs = Math.abs(z)
  if (abs > 2.5) return '#f5222d'
  if (abs > 2.0) return '#fa8c16'
  if (abs > 1.0) return '#faad14'
  return '#52c41a'
}

/** 信号标签 */
const SIGNAL_MAP = {
  long_spread: { color: '#52c41a', label: '做多价差', icon: <RiseOutlined /> },
  short_spread: { color: '#f5222d', label: '做空价差', icon: <FallOutlined /> },
  close: { color: '#1890ff', label: '平仓', icon: <SwapOutlined /> },
  hold: { color: '#8c8c8c', label: '持有', icon: <CheckCircleOutlined /> },
}

/** 格式化数字 */
function fmtNum(val, decimals = 2) {
  if (val == null || isNaN(val)) return '-'
  return Number(val).toFixed(decimals)
}

/** 格式化市值（万元→亿） */
function fmtMv(val) {
  if (val == null) return '-'
  const yi = val / 10000
  if (yi >= 1) return `${yi.toFixed(0)}亿`
  return `${val.toFixed(0)}万`
}

/* =====================================================================
 * Tab 1 — 配对发现
 * ===================================================================== */
function PairDiscovery() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [lookback, setLookback] = useState(90)
  const [minCorr, setMinCorr] = useState(0.7)
  const [minMv, setMinMv] = useState(50)
  const [universeSize, setUniverseSize] = useState(80)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const params = `?lookback_days=${lookback}&min_correlation=${minCorr}&min_market_cap=${minMv}&universe_size=${universeSize}`
      const res = await apiCall(`/pair-trading/discover${params}`)
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to discover pairs:', err)
    }
    setLoading(false)
  }, [lookback, minCorr, minMv, universeSize])

  useEffect(() => { loadData() }, [loadData])

  const columns = [
    {
      title: '股票A',
      key: 'code1',
      width: 160,
      render: (_, r) => (
        <div>
          <Text strong style={{ fontSize: 13 }}>{r.code1}</Text>
        </div>
      ),
    },
    {
      title: '股票B',
      key: 'code2',
      width: 160,
      render: (_, r) => (
        <div>
          <Text strong style={{ fontSize: 13 }}>{r.code2}</Text>
        </div>
      ),
    },
    {
      title: '相关性',
      dataIndex: 'correlation',
      sorter: (a, b) => a.correlation - b.correlation,
      render: (v) => (
        <span style={{ color: v > 0.8 ? '#52c41a' : '#faad14', fontWeight: 600 }}>
          {fmtNum(v, 4)}
        </span>
      ),
    },
    {
      title: '协整P值',
      dataIndex: 'cointegration_pvalue',
      sorter: (a, b) => a.cointegration_pvalue - b.cointegration_pvalue,
      render: (v) => (
        <span style={{ color: v < 0.01 ? '#52c41a' : v < 0.05 ? '#faad14' : '#f5222d' }}>
          {fmtNum(v, 4)}
        </span>
      ),
    },
    {
      title: '半衰期(天)',
      dataIndex: 'half_life_days',
      render: (v) => v ? <Tag color="blue">{fmtNum(v, 1)}天</Tag> : <Tag>N/A</Tag>,
    },
    {
      title: '价差均值',
      dataIndex: 'spread_mean',
      render: (v) => fmtNum(v, 4),
    },
    {
      title: '价差标准差',
      dataIndex: 'spread_std',
      render: (v) => fmtNum(v, 4),
    },
  ]

  const summary = data?.summary || {}

  return (
    <div>
      {/* 参数面板 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <span>回看天数：</span>
          <Slider
            min={30} max={200} value={lookback}
            onChange={setLookback}
            style={{ width: 120 }}
            tooltip={{ formatter: (v) => `${v}天` }}
          />
          <span>最小相关性：</span>
          <Slider
            min={0.3} max={0.95} step={0.05} value={minCorr}
            onChange={setMinCorr}
            style={{ width: 120 }}
            tooltip={{ formatter: (v) => v.toFixed(2) }}
          />
          <span>最小市值：</span>
          <Slider
            min={10} max={500} value={minMv}
            onChange={setMinMv}
            style={{ width: 120 }}
            tooltip={{ formatter: (v) => `${v}亿` }}
          />
          <span>股票池：</span>
          <Slider
            min={20} max={200} value={universeSize}
            onChange={setUniverseSize}
            style={{ width: 120 }}
            tooltip={{ formatter: (v) => `${v}只` }}
          />
          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
            重新发现
          </Button>
        </Space>
      </Card>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card size="small">
            <Statistic title="股票池" value={summary.universe_size || 0} suffix="只" />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="检查配对" value={summary.total_pairs_checked || 0} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="高相关配对" value={summary.correlated_pairs || 0} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="协整配对"
              value={summary.cointegrated_pairs || 0}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="平均相关性" value={fmtNum(summary.avg_correlation, 3)} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="数据天数" value={summary.price_data_days || 0} suffix="天" />
          </Card>
        </Col>
      </Row>

      {/* 配对表格 */}
      <Card
        title={`📊 协整配对列表 (${(data?.pairs || []).length}对)`}
        extra={<Text type="secondary">按协整P值排序，P值越小越显著</Text>}
      >
        <Table
          dataSource={data?.pairs || []}
          columns={columns}
          rowKey={(r) => `${r.code1}-${r.code2}`}
          loading={loading}
          size="small"
          pagination={{ pageSize: 15, showSizeChanger: true }}
          scroll={{ x: 900 }}
        />
      </Card>
    </div>
  )
}

/* =====================================================================
 * Tab 2 — 交易信号
 * ===================================================================== */
function TradingSignals() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [zscoreEntry, setZscoreEntry] = useState(2.0)
  const [zscoreExit, setZscoreExit] = useState(0.5)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const params = `?zscore_entry=${zscoreEntry}&zscore_exit=${zscoreExit}`
      const res = await apiCall(`/pair-trading/signals${params}`)
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to load signals:', err)
    }
    setLoading(false)
  }, [zscoreEntry, zscoreExit])

  useEffect(() => { loadData() }, [loadData])

  const summary = data?.summary || {}

  const columns = [
    {
      title: '配对',
      key: 'pair',
      width: 200,
      render: (_, r) => (
        <div>
          <Text strong>{r.code1}</Text>
          <SwapOutlined style={{ margin: '0 6px', color: '#8c8c8c' }} />
          <Text strong>{r.code2}</Text>
          {r.pair_info && (
            <div style={{ fontSize: 11, color: '#8c8c8c' }}>
              r={fmtNum(r.pair_info.correlation, 3)} p={fmtNum(r.pair_info.cointegration_pvalue, 4)}
            </div>
          )}
        </div>
      ),
    },
    {
      title: 'Z-Score',
      dataIndex: 'zscore',
      sorter: (a, b) => Math.abs(a.zscore) - Math.abs(b.zscore),
      render: (v) => (
        <span style={{ color: zscoreColor(v), fontWeight: 700, fontSize: 14 }}>
          {v > 0 ? '+' : ''}{fmtNum(v, 3)}
        </span>
      ),
    },
    {
      title: '信号',
      dataIndex: 'signal',
      render: (v) => {
        const m = SIGNAL_MAP[v] || { color: '#8c8c8c', label: v }
        return <Tag color={m.color} icon={m.icon}>{m.label}</Tag>
      },
    },
    {
      title: '价格A',
      dataIndex: 'price1',
      render: (v) => `¥${fmtNum(v)}`,
    },
    {
      title: '价格B',
      dataIndex: 'price2',
      render: (v) => `¥${fmtNum(v)}`,
    },
    {
      title: '价差比',
      dataIndex: 'ratio',
      render: (v) => fmtNum(v, 4),
    },
    {
      title: '描述',
      dataIndex: 'signal_desc',
      ellipsis: true,
    },
  ]

  return (
    <div>
      {/* 参数面板 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <span>入场阈值(z)：</span>
          <Slider
            min={1.0} max={3.0} step={0.1} value={zscoreEntry}
            onChange={setZscoreEntry}
            style={{ width: 120 }}
            tooltip={{ formatter: (v) => `±${v.toFixed(1)}` }}
          />
          <span>出场阈值(z)：</span>
          <Slider
            min={0} max={1.5} step={0.1} value={zscoreExit}
            onChange={setZscoreExit}
            style={{ width: 120 }}
            tooltip={{ formatter: (v) => `±${v.toFixed(1)}` }}
          />
          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
            刷新信号
          </Button>
        </Space>
      </Card>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card size="small">
            <Statistic title="配对总数" value={summary.total_pairs || 0} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="信号总数" value={summary.total_signals || 0} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="做多价差"
              value={summary.long_spread_count || 0}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="做空价差"
              value={summary.short_spread_count || 0}
              valueStyle={{ color: '#f5222d' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="平仓信号" value={summary.close_count || 0} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic
              title="强信号(|z|>2.5)"
              value={summary.strong_signals || 0}
              valueStyle={{ color: '#f5222d' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 信号表格 */}
      <Card
        title={`⚡ 实时交易信号 (${(data?.signals || []).length}个)`}
        extra={<Text type="secondary">z-score 越大，价差偏离越远，均值回复机会越大</Text>}
      >
        <Table
          dataSource={data?.signals || []}
          columns={columns}
          rowKey={(r) => `${r.code1}-${r.code2}`}
          loading={loading}
          size="small"
          pagination={{ pageSize: 15, showSizeChanger: true }}
          scroll={{ x: 1000 }}
        />
      </Card>
    </div>
  )
}

/* =====================================================================
 * Tab 3 — 配对回测
 * ===================================================================== */
function PairBacktest() {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [code1, setCode1] = useState('601398.SH')
  const [code2, setCode2] = useState('601288.SH')
  const [holdDays, setHoldDays] = useState(5)
  const [zscoreEntry, setZscoreEntry] = useState(2.0)

  const runBacktest = useCallback(async () => {
    if (!code1 || !code2) return
    setLoading(true)
    try {
      const params = `?code1=${code1}&code2=${code2}&hold_days=${holdDays}&zscore_entry=${zscoreEntry}`
      const res = await apiCall(`/pair-trading/backtest${params}`)
      setData(res?.data || res)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Failed to backtest:', err)
    }
    setLoading(false)
  }, [code1, code2, holdDays, zscoreEntry])

  const metrics = data?.metrics || {}
  const trades = data?.trades || []
  const equityCurve = data?.equity_curve || []

  const tradeColumns = [
    { title: '入场日', dataIndex: 'entry_date', width: 100 },
    { title: '出场日', dataIndex: 'exit_date', width: 100 },
    {
      title: '方向',
      dataIndex: 'direction',
      render: (v) => (
        <Tag color={v === 'long_spread' ? '#52c41a' : '#f5222d'}>
          {v === 'long_spread' ? '做多价差' : '做空价差'}
        </Tag>
      ),
    },
    { title: '入场Z', dataIndex: 'entry_zscore', render: (v) => fmtNum(v, 2) },
    { title: '出场Z', dataIndex: 'exit_zscore', render: (v) => fmtNum(v, 2) },
    {
      title: '盈亏',
      dataIndex: 'pnl',
      render: (v) => (
        <span style={{ color: v >= 0 ? '#52c41a' : '#f5222d', fontWeight: 600 }}>
          ¥{v >= 0 ? '+' : ''}{fmtNum(v)}
        </span>
      ),
    },
    {
      title: '收益率',
      dataIndex: 'return_pct',
      render: (v) => (
        <span style={{ color: v >= 0 ? '#52c41a' : '#f5222d' }}>
          {v >= 0 ? '+' : ''}{fmtNum(v)}%
        </span>
      ),
    },
  ]

  return (
    <div>
      {/* 参数面板 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <Input
            addonBefore="股票A"
            value={code1}
            onChange={(e) => setCode1(e.target.value)}
            style={{ width: 200 }}
            placeholder="如 601398.SH"
          />
          <Input
            addonBefore="股票B"
            value={code2}
            onChange={(e) => setCode2(e.target.value)}
            style={{ width: 200 }}
            placeholder="如 601288.SH"
          />
          <span>持有天数：</span>
          <Slider
            min={1} max={20} value={holdDays}
            onChange={setHoldDays}
            style={{ width: 100 }}
          />
          <span>入场z：</span>
          <Slider
            min={1.0} max={3.0} step={0.1} value={zscoreEntry}
            onChange={setZscoreEntry}
            style={{ width: 100 }}
          />
          <Button
            type="primary"
            icon={<ExperimentOutlined />}
            onClick={runBacktest}
            loading={loading}
          >
            运行回测
          </Button>
        </Space>
      </Card>

      {data && (
        <>
          {/* 性能指标 */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={3}>
              <Card size="small">
                <Statistic title="总交易" value={metrics.total_trades || 0} suffix="次" />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic
                  title="胜率"
                  value={metrics.win_rate || 0}
                  suffix="%"
                  valueStyle={{ color: (metrics.win_rate || 0) > 50 ? '#52c41a' : '#f5222d' }}
                />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic
                  title="总收益"
                  value={metrics.total_return || 0}
                  suffix="%"
                  valueStyle={{ color: (metrics.total_return || 0) >= 0 ? '#52c41a' : '#f5222d' }}
                />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic title="最大回撤" value={metrics.max_drawdown || 0} suffix="%" valueStyle={{ color: '#f5222d' }} />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic title="夏普比率" value={fmtNum(metrics.sharpe_ratio, 3)} />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic title="盈亏比" value={fmtNum(metrics.profit_factor, 2)} />
              </Card>
            </Col>
            <Col span={3}>
              <Card size="small">
                <Statistic title="最终资金" value={fmtNum(metrics.final_equity)} prefix="¥" />
              </Card>
            </Col>
          </Row>

          {/* 净值曲线 */}
          {equityCurve.length > 0 && (
            <Card title="📈 净值曲线" size="small" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'flex-end', height: 120, gap: 1, overflow: 'hidden' }}>
                {equityCurve.map((pt, i) => {
                  const initial = equityCurve[0]?.equity || 1000000
                  const height = Math.max(2, (pt.equity / initial) * 100 - 50)
                  const color = pt.equity >= initial ? '#52c41a' : '#f5222d'
                  return (
                    <Tooltip key={i} title={`${pt.date}: ¥${fmtNum(pt.equity)} (z=${fmtNum(pt.zscore, 2)})`}>
                      <div
                        style={{
                          flex: 1,
                          height: `${height}%`,
                          backgroundColor: color,
                          opacity: pt.position !== 0 ? 1 : 0.3,
                          borderRadius: 2,
                          minWidth: 2,
                        }}
                      />
                    </Tooltip>
                  )
                })}
              </div>
            </Card>
          )}

          {/* 交易明细 */}
          <Card title={`📋 交易明细 (${trades.length}笔)`}>
            <Table
              dataSource={trades}
              columns={tradeColumns}
              rowKey={(_, i) => i}
              size="small"
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </>
      )}

      {!data && !loading && (
        <Empty description="输入配对代码后点击「运行回测」" />
      )}
    </div>
  )
}

/* =====================================================================
 * 主组件
 * ===================================================================== */
export default function PairTrading() {
  const [activeTab, setActiveTab] = useState('discover')

  const tabItems = [
    { key: 'discover', label: '🔍 配对发现' },
    { key: 'signals', label: '⚡ 交易信号' },
    { key: 'backtest', label: '📈 回测验证' },
  ]

  return (
    <div style={{ padding: '0 16px' }}>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <SwapOutlined style={{ marginRight: 8 }} />
          协整配对交易
        </Title>
        <Text type="secondary">
          基于 Engle-Granger 协整检验，寻找统计套利机会——价差偏离均值时入场，回归均值时出场
        </Text>
      </div>

      <Segmented
        options={tabItems}
        value={activeTab}
        onChange={setActiveTab}
        style={{ marginBottom: 16 }}
      />

      {activeTab === 'discover' && <PairDiscovery />}
      {activeTab === 'signals' && <TradingSignals />}
      {activeTab === 'backtest' && <PairBacktest />}
    </div>
  )
}
