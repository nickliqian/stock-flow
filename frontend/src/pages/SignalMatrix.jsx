import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Space, Spin, Empty,
  Tooltip, Slider, Select, Typography, message,
} from 'antd'
import {
  ReloadOutlined, DashboardOutlined, TrophyOutlined,
  BarChartOutlined, TeamOutlined,
} from '@ant-design/icons'
import { getSignalMatrix } from '../services/api'
import { scoreColor } from '../utils/format'

const { Text, Title } = Typography

// 策略类别映射
const CATEGORY_MAP = {
  value: { label: '价值', color: 'blue' },
  momentum: { label: '动量', color: 'orange' },
  flow: { label: '资金', color: 'green' },
  event: { label: '事件', color: 'purple' },
  combo: { label: '组合', color: 'red' },
}

// 策略缩写映射（用于列标题，避免过长）
const STRATEGY_ABBR = {
  high_dividend: '高股息',
  low_valuation_gold: '低估值',
  broken_net_gold: '破净',
  value_fund_resonance: '价金共振',
  volume_breakthrough: '量突破',
  ma_alignment: '均线多头',
  trend_volume_resonance: '量价共振',
  volume_anomaly: '量异动',
  kdj_oversold_rebound: 'KDJ超卖',
  macd_golden_cross: 'MACD金叉',
  oversold_bounce: '超跌反弹',
  block_trade_premium: '大宗溢价',
  consecutive_limit_up: '连板',
  limit_up_reseal: '涨停封板',
  main_fund_inflow: '主力流入',
  margin_growth: '融资增长',
  margin_fund_convergence: '融券收敛',
  smart_money_tracker: '聪明钱',
}

/** 分数单元格渲染 */
function ScoreCell({ signal }) {
  if (!signal) {
    return <Text type="secondary">-</Text>
  }
  const score = signal.score
  let bgColor = 'transparent'
  if (score >= 80) bgColor = 'rgba(82, 196, 26, 0.15)'
  else if (score >= 50) bgColor = 'rgba(250, 173, 20, 0.15)'
  else bgColor = 'rgba(255, 77, 79, 0.1)'

  return (
    <Tooltip title={signal.reason || ''}>
      <div
        style={{
          padding: '2px 6px',
          borderRadius: 4,
          backgroundColor: bgColor,
          textAlign: 'center',
          fontWeight: 500,
          color: scoreColor(score),
          cursor: signal.reason ? 'help' : 'default',
          minWidth: 50,
        }}
      >
        {score.toFixed(1)}
      </div>
    </Tooltip>
  )
}

/** 分布柱状图（纯 CSS 实现，无额外依赖） */
function DistributionChart({ distribution, maxStrategies }) {
  if (!distribution || Object.keys(distribution).length === 0) return null

  const entries = []
  for (let i = 1; i <= Math.max(maxStrategies || 1, 6); i++) {
    entries.push({ label: `${i}个`, count: distribution[String(i)] || 0 })
  }
  const maxCount = Math.max(...entries.map(e => e.count), 1)

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 120, padding: '0 8px' }}>
      {entries.map((entry, idx) => (
        <div key={idx} style={{ flex: 1, textAlign: 'center' }}>
          <div
            style={{
              height: `${(entry.count / maxCount) * 80}px`,
              minHeight: entry.count > 0 ? 4 : 0,
              backgroundColor: entry.count > 0 ? '#1677ff' : '#f5f5f5',
              borderRadius: '4px 4px 0 0',
              transition: 'height 0.3s',
            }}
          />
          <div style={{ marginTop: 4 }}>
            <Text type="secondary" style={{ fontSize: 11 }}>{entry.label}</Text>
            <br />
            <Text strong style={{ fontSize: 12 }}>{entry.count}</Text>
          </div>
        </div>
      ))}
    </div>
  )
}

/**
 * 策略信号矩阵页面
 * 统一展示所有策略的信号，Stock × Strategy 矩阵视图
 */
export default function SignalMatrix({ tradeDate, onSelectStock }) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState(null)
  const [minStrategies, setMinStrategies] = useState(1)
  const [category, setCategory] = useState(null)

  const fetchData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const result = await getSignalMatrix(tradeDate, minStrategies, category, { signal })
      setData(result)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Signal matrix load failed:', err)
      message.error('加载信号矩阵失败')
    } finally {
      setLoading(false)
    }
  }, [tradeDate, minStrategies, category])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(controller.signal)
    return () => controller.abort()
  }, [fetchData])

  // 构建动态列：策略列
  const strategyColumns = useMemo(() => {
    if (!data?.strategies) return []
    return data.strategies.map((strat) => ({
      title: (
        <Tooltip title={strat.description}>
          <Space size={2}>
            <span>{strat.icon}</span>
            <span>{STRATEGY_ABBR[strat.name] || strat.name}</span>
          </Space>
        </Tooltip>
      ),
      dataIndex: ['signals', strat.name],
      key: strat.name,
      width: 80,
      align: 'center',
      sorter: (a, b) => {
        const sa = a.signals?.[strat.name]?.score || 0
        const sb = b.signals?.[strat.name]?.score || 0
        return sa - sb
      },
      render: (signal) => <ScoreCell signal={signal} />,
    }))
  }, [data?.strategies])

  // 主表格列定义
  const columns = useMemo(() => {
    const fixedCols = [
      {
        title: '股票代码',
        dataIndex: 'ts_code',
        key: 'ts_code',
        width: 110,
        fixed: 'left',
        render: (text, record) => (
          <a
            onClick={() => onSelectStock?.({ ts_code: record.ts_code, name: record.name })}
            style={{ color: '#1677ff' }}
          >
            {text}
          </a>
        ),
      },
      {
        title: '名称',
        dataIndex: 'name',
        key: 'name',
        width: 90,
        fixed: 'left',
        render: (text, record) => (
          <a
            onClick={() => onSelectStock?.({ ts_code: record.ts_code, name: record.name })}
            style={{ color: '#1677ff' }}
          >
            {text}
          </a>
        ),
      },
      {
        title: '行业',
        dataIndex: 'industry',
        key: 'industry',
        width: 80,
      },
      {
        title: '综合分',
        dataIndex: 'total_score',
        key: 'total_score',
        width: 80,
        sorter: (a, b) => a.total_score - b.total_score,
        defaultSortOrder: 'descend',
        render: (val) => (
          <span style={{ color: scoreColor(val), fontWeight: 600 }}>
            {val.toFixed(1)}
          </span>
        ),
      },
      {
        title: '策略数',
        dataIndex: 'strategy_count',
        key: 'strategy_count',
        width: 70,
        sorter: (a, b) => a.strategy_count - b.strategy_count,
        render: (val) => (
          <Tag color={val >= 3 ? 'success' : val >= 2 ? 'warning' : 'default'}>
            {val}
          </Tag>
        ),
      },
    ]
    return [...fixedCols, ...strategyColumns]
  }, [strategyColumns, onSelectStock])

  const summary = data?.summary

  return (
    <div>
      {/* 标题栏 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <DashboardOutlined style={{ fontSize: 20, color: '#1677ff' }} />
          <Title level={4} style={{ margin: 0 }}>策略信号矩阵</Title>
        </Space>
        <Space>
          <Text type="secondary">
            {data?.trade_date
              ? `${data.trade_date.slice(0, 4)}-${data.trade_date.slice(4, 6)}-${data.trade_date.slice(6, 8)}`
              : ''}
          </Text>
        </Space>
      </div>

      {/* 汇总统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic
              title="触发信号的股票数"
              value={summary?.total_stocks || 0}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic
              title="平均每只股票触发策略数"
              value={summary?.avg_strategies_per_stock || 0}
              prefix={<BarChartOutlined />}
              precision={1}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic
              title="最多触发策略数"
              value={summary?.max_strategies || 0}
              prefix={<TrophyOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 筛选控件 + 分布图 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={16}>
          <Card size="small" title="筛选条件" extra={
            <a onClick={fetchData} style={{ fontSize: 13 }}>
              <ReloadOutlined /> 刷新
            </a>
          }>
            <Space wrap size="large">
              <Space>
                <Text>最少策略数:</Text>
                <Slider
                  min={1}
                  max={6}
                  value={minStrategies}
                  onChange={setMinStrategies}
                  style={{ width: 120 }}
                  marks={{ 1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6' }}
                />
              </Space>
              <Space>
                <Text>策略分类:</Text>
                <Select
                  value={category}
                  onChange={setCategory}
                  allowClear
                  placeholder="全部"
                  style={{ width: 120 }}
                  options={[
                    { value: null, label: '全部' },
                    ...Object.entries(CATEGORY_MAP).map(([k, v]) => ({
                      value: k,
                      label: v.label,
                    })),
                  ]}
                />
              </Space>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small" title="策略数分布">
            <DistributionChart
              distribution={summary?.strategy_distribution}
              maxStrategies={summary?.max_strategies}
            />
          </Card>
        </Col>
      </Row>

      {/* 信号矩阵表格 */}
      <Card size="small" bodyStyle={{ padding: 0 }}>
        <Table
          columns={columns}
          dataSource={data?.stocks || []}
          rowKey="ts_code"
          loading={loading}
          size="small"
          scroll={{ x: 'max-content' }}
          pagination={{
            pageSize: 30,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 只股票`,
            pageSizeOptions: ['20', '30', '50', '100'],
          }}
          locale={{ emptyText: <Empty description="暂无信号数据" /> }}
          rowClassName={(record) =>
            record.strategy_count >= 3 ? 'ant-table-row-highlight' : ''
          }
        />
      </Card>

      {/* 策略图例 */}
      {data?.strategies?.length > 0 && (
        <Card size="small" title="策略图例" style={{ marginTop: 16 }}>
          <Space wrap size={[8, 8]}>
            {data.strategies.map((strat) => (
              <Tooltip key={strat.name} title={`${strat.description} — 平均分 ${strat.avg_score}，选中 ${strat.pick_count} 只`}>
                <Tag color={CATEGORY_MAP[strat.category]?.color || 'default'}>
                  {strat.icon} {STRATEGY_ABBR[strat.name] || strat.name}
                  <Text type="secondary" style={{ marginLeft: 4, fontSize: 11 }}>
                    ({strat.pick_count})
                  </Text>
                </Tag>
              </Tooltip>
            ))}
          </Space>
        </Card>
      )}

      <style>{`
        .ant-table-row-highlight td {
          background: rgba(22, 119, 255, 0.04) !important;
        }
      `}</style>
    </div>
  )
}
