import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Space,
  Spin, Empty, Tooltip, Badge, Tabs, Typography, message,
} from 'antd'
import {
  ReloadOutlined, ThunderboltOutlined, TrophyOutlined,
  FundOutlined, DollarOutlined, AimOutlined, RadarChartOutlined, LineChartOutlined, BulbOutlined, ApartmentOutlined,
} from '@ant-design/icons'
import { getStrategies, executeStrategy, executeAllStrategies } from '../services/api'
import { formatAmount, getColor, scoreColor, scoreTag } from '../utils/format'
import StrategyConfluence from './StrategyConfluence'
import StrategyBacktest from './StrategyBacktest'
import StrategySectorHeatmap from '../components/StrategySectorHeatmap'
import StrategyIntelligence from './StrategyIntelligence'
import StrategyComposer from './StrategyComposer'

const { Text, Title } = Typography

// 策略类别标签
const CATEGORY_MAP = {
  value: { label: '价值', color: 'blue' },
  momentum: { label: '动量', color: 'orange' },
  flow: { label: '资金', color: 'green' },
  event: { label: '事件', color: 'purple' },
  combo: { label: '组合', color: 'red' },
}

/** 策略总览卡片 */
function StrategyCard({ strategy, onExecute, loading }) {
  const cat = CATEGORY_MAP[strategy.category] || { label: strategy.category, color: 'default' }
  return (
    <Card
      hoverable
      style={{ height: '100%' }}
      actions={[
        <Button type="link" icon={<ThunderboltOutlined />} onClick={() => onExecute(strategy.name)} loading={loading}>
          执行
        </Button>,
      ]}
    >
      <div style={{ fontSize: 32, marginBottom: 8 }}>{strategy.icon}</div>
      <Title level={5} style={{ marginBottom: 4 }}>{strategy.description}</Title>
      <Space size={4}>
        <Tag color={cat.color}>{cat.label}</Tag>
        <Tag>{strategy.data_required?.length || 0}个数据源</Tag>
      </Space>
    </Card>
  )
}

/** 单策略结果表格 */
function StrategyResultTable({ result, loading }) {
  if (loading) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Spin tip="策略执行中..." /></div>
  }
  if (!result) {
    return <Empty description="点击「执行」按钮运行策略" />
  }
  if (result.error) {
    return <Empty description={`执行失败：${result.error}`} />
  }
  if (!result.results || result.results.length === 0) {
    return <Empty description="未找到符合条件的股票" />
  }

  const columns = [
    {
      title: '排名',
      width: 60,
      render: (_, __, i) => i + 1,
    },
    {
      title: '代码',
      dataIndex: 'ts_code',
      width: 120,
      render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '名称',
      dataIndex: 'name',
      width: 100,
      render: (v, r) => (
        <Tooltip title={r.reason}>
          <Text strong>{v || r.ts_code}</Text>
        </Tooltip>
      ),
    },
    {
      title: '得分',
      dataIndex: 'score',
      width: 100,
      sorter: (a, b) => a.score - b.score,
      defaultSortOrder: 'descend',
      render: (v) => scoreTag(v),
    },
    {
      title: '关键指标',
      key: 'signals',
      render: (_, record) => <SignalsCell signals={record.signals} />,
    },
    {
      title: '策略理由',
      dataIndex: 'reason',
      ellipsis: true,
      render: (v) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>,
    },
  ]

  return (
    <Table
      columns={columns}
      dataSource={result.results.map((r, i) => ({ ...r, key: r.ts_code + i }))}
      pagination={{ pageSize: 20, showSizeChanger: false, showTotal: (t) => `共 ${t} 只` }}
      size="small"
      scroll={{ x: 800 }}
    />
  )
}

/** 关键指标展示 */
function SignalsCell({ signals }) {
  if (!signals) return '--'
  const items = []
  if (signals.pe_ttm != null) items.push(`PE ${signals.pe_ttm}`)
  if (signals.pb != null) items.push(`PB ${signals.pb}`)
  if (signals.dv_ratio != null) items.push(`股息 ${signals.dv_ratio}%`)
  if (signals.total_mv_yi != null) items.push(`市值 ${signals.total_mv_yi}亿`)
  if (signals.consecutive_days != null) items.push(`连续${signals.consecutive_days}日`)
  if (signals.net_inflow_3d_yi != null) items.push(`净入${signals.net_inflow_3d_yi}亿`)
  if (signals.turnover_rate != null) items.push(`换手 ${signals.turnover_rate}%`)
  if (signals.total_main_inflow_yi != null) items.push(`主力 ${signals.total_main_inflow_yi}亿`)
  if (items.length === 0) return '--'
  return (
    <Space size={4} wrap>
      {items.slice(0, 4).map((t, i) => <Tag key={i} style={{ fontSize: 11 }}>{t}</Tag>)}
    </Space>
  )
}

/** 主页面 */
export default function StrategyDashboard({ tradeDate }) {
  const [strategies, setStrategies] = useState([])
  const [loadingList, setLoadingList] = useState(false)
  const [activeStrategy, setActiveStrategy] = useState(null)
  const [strategyResult, setStrategyResult] = useState(null)
  const [executing, setExecuting] = useState(false)
  const [allResults, setAllResults] = useState(null)
  const [loadingAll, setLoadingAll] = useState(false)
  const [activeTab, setActiveTab] = useState('list')
  const [innerTab, setInnerTab] = useState('overview')

  // 加载策略列表
  useEffect(() => {
    const controller = new AbortController()
    setLoadingList(true)
    getStrategies({ signal: controller.signal })
      .then((res) => {
        if (res?.success && res.data) {
          setStrategies(res.data)
        }
      })
      .catch((err) => {
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        console.error('Failed to load strategies:', err)
        message.error('策略列表加载失败')
      })
      .finally(() => setLoadingList(false))
    return () => controller.abort()
  }, [])

  // 执行单个策略
  const handleExecute = useCallback(async (strategyName) => {
    setExecuting(true)
    setStrategyResult(null)
    setActiveStrategy(strategyName)
    setInnerTab('result')
    try {
      const params = {}
      if (tradeDate) params.trade_date = tradeDate
      const res = await executeStrategy(strategyName, params)
      if (res?.success) {
        setStrategyResult(res.data)
      } else {
        message.error(res?.error || '执行失败')
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Strategy execution failed:', err)
      message.error('策略执行失败，请稍后重试')
    } finally {
      setExecuting(false)
    }
  }, [tradeDate])

  // 执行全部策略
  const handleExecuteAll = useCallback(async () => {
    setLoadingAll(true)
    setAllResults(null)
    setInnerTab('all')
    try {
      const params = {}
      if (tradeDate) params.trade_date = tradeDate
      const res = await executeAllStrategies(params)
      if (res?.success) {
        setAllResults(res.data)
      } else {
        message.error('执行失败')
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Execute all failed:', err)
      message.error('批量执行失败，请稍后重试')
    } finally {
      setLoadingAll(false)
    }
  }, [tradeDate])

  // 内部 Tab（策略列表下的子 Tab）
  const innerTabItems = [
    {
      key: 'overview',
      label: <span>📋 策略总览</span>,
      children: (
        <Spin spinning={loadingList}>
          {strategies.length === 0 && !loadingList ? (
            <Empty description="暂无可用策略" />
          ) : (
            <Row gutter={[16, 16]}>
              {strategies.map((s) => (
                <Col xs={24} sm={12} md={8} lg={6} key={s.name}>
                  <StrategyCard
                    strategy={s}
                    onExecute={handleExecute}
                    loading={executing && activeStrategy === s.name}
                  />
                </Col>
              ))}
            </Row>
          )}
        </Spin>
      ),
    },
    {
      key: 'result',
      label: (
        <span>
          📊 单策略结果
          {strategyResult && (
            <Badge count={strategyResult.total_matches} style={{ marginLeft: 4 }} />
          )}
        </span>
      ),
      children: (
        <>
          {activeStrategy && (
            <div style={{ marginBottom: 12 }}>
              <Space>
                <Tag color="blue">{strategyResult?.strategy?.icon}</Tag>
                <Text strong>{strategyResult?.strategy?.description || activeStrategy}</Text>
                {strategyResult?.trade_date && <Tag>{strategyResult.trade_date}</Tag>}
              </Space>
            </div>
          )}
          <StrategyResultTable result={strategyResult} loading={executing} />
        </>
      ),
    },
    {
      key: 'all',
      label: (
        <span>
          🚀 全部策略
          {allResults && <Badge count={Object.keys(allResults.strategies || {}).length} style={{ marginLeft: 4 }} />}
        </span>
      ),
      children: <AllStrategiesView data={allResults} loading={loadingAll} />,
    },
    {
      key: 'heatmap',
      label: <span>🗺️ 板块热力图</span>,
      children: <StrategySectorHeatmap tradeDate={tradeDate} />,
    },
    {
      key: 'intelligence',
      label: (
        <span>
          <BulbOutlined /> 策略洞察
        </span>
      ),
      children: <StrategyIntelligence />,
    },
    {
      key: 'composer',
      label: (
        <span>
          <ApartmentOutlined /> 策略组合
        </span>
      ),
      children: <StrategyComposer tradeDate={tradeDate} />,
    },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      {/* 外层 Tab：策略列表 / 策略共振 / 策略回测 */}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          setActiveTab(key)
          // 切换到外层 tab 时重置内部状态
          if (key !== 'result') setStrategyResult(null)
          if (key !== 'all') setAllResults(null)
        }}
        type="card"
        items={[
          {
            key: 'list',
            label: <span>📋 策略列表</span>,
            children: (
              <div>
                {/* 顶部操作栏 */}
                <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Space>
                    <Title level={4} style={{ margin: 0 }}>🎯 策略选股</Title>
                    {tradeDate && <Tag>{tradeDate}</Tag>}
                  </Space>
                  <Space>
                    <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleExecuteAll} loading={loadingAll}>
                      全部执行
                    </Button>
                    <Button icon={<ReloadOutlined />} onClick={() => { setStrategyResult(null); setAllResults(null) }}>
                      重置
                    </Button>
                  </Space>
                </div>

                {/* 内层 Tab */}
                <Tabs
                  activeKey={innerTab}
                  onChange={setInnerTab}
                  items={innerTabItems}
                />
              </div>
            ),
          },
          {
            key: 'confluence',
            label: (
              <span>
                <RadarChartOutlined /> 策略共振
              </span>
            ),
            children: <StrategyConfluence tradeDate={tradeDate} />,
          },
          {
            key: 'backtest',
            label: (
              <span>
                <LineChartOutlined /> 策略回测
              </span>
            ),
            children: <StrategyBacktest strategies={strategies} />,
          },
        ]}
      />
    </div>
  )
}

/** 全部策略执行结果视图 */
function AllStrategiesView({ data, loading }) {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" tip="所有策略执行中，请耐心等待..." />
      </div>
    )
  }
  if (!data) {
    return <Empty description="点击「全部执行」按钮运行所有策略" />
  }

  const strategies = data.strategies || {}
  const stratEntries = Object.entries(strategies)

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Tag color="blue">交易日：{data.trade_date}</Tag>
          <Tag>{stratEntries.length} 个策略</Tag>
        </Space>
      </div>
      {stratEntries.map(([key, strat]) => (
        <Card
          key={key}
          style={{ marginBottom: 16 }}
          title={
            <Space>
              <span style={{ fontSize: 20 }}>{strat.icon}</span>
              <Text strong>{strat.description || strat.name}</Text>
              <Badge count={strat.total_matches || 0} showZero style={{ backgroundColor: strat.total_matches > 0 ? '#52c41a' : '#d9d9d9' }} />
            </Space>
          }
        >
          {strat.error ? (
            <Empty description={`执行失败：${strat.error}`} />
          ) : !strat.results || strat.results.length === 0 ? (
            <Empty description="未找到符合条件的股票" />
          ) : (
            <Table
              columns={[
                { title: '#', width: 50, render: (_, __, i) => i + 1 },
                { title: '代码', dataIndex: 'ts_code', width: 120, render: (v) => <Text code style={{ fontSize: 12 }}>{v}</Text> },
                { title: '名称', dataIndex: 'name', width: 100, render: (v) => <Text strong>{v}</Text> },
                { title: '得分', dataIndex: 'score', width: 90, sorter: (a, b) => a.score - b.score, defaultSortOrder: 'descend', render: (v) => scoreTag(v) },
                { title: '关键指标', key: 'signals', render: (_, r) => <SignalsCell signals={r.signals} /> },
                { title: '理由', dataIndex: 'reason', ellipsis: true, render: (v) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text> },
              ]}
              dataSource={(strat.results || []).map((r, i) => ({ ...r, key: r.ts_code + i }))}
              pagination={{ pageSize: 10, showSizeChanger: false, showTotal: (t) => `共 ${t} 只` }}
              size="small"
              scroll={{ x: 800 }}
            />
          )}
        </Card>
      ))}
    </div>
  )
}
