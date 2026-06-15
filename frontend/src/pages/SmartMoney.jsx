import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Row, Col, Statistic, Button, Space,
  Spin, Empty, Typography, message, Segmented,
} from 'antd'
import {
  ReloadOutlined, BulbOutlined, FundOutlined, ThunderboltOutlined, SafetyOutlined,
} from '@ant-design/icons'
import { executeStrategy, executeAllStrategies } from '../services/api'
import { formatAmount, getColor, scoreColor, scoreTag } from '../utils/format'

const { Text, Title, Paragraph } = Typography

// 策略配置
const STRATEGIES = {
  margin_fund_convergence: {
    icon: '🧠',
    title: '融资+资金共振',
    description: '融资余额增长+主力资金流入双重确认',
  },
  smart_money_tracker: {
    icon: '🐋',
    title: '聪明钱追踪',
    description: '大宗交易溢价+大单资金主导',
  },
}

// 策略映射到显示标签
const STRATEGY_LABELS = {
  margin_fund_convergence: '融资共振',
  smart_money_tracker: '聪明钱追踪',
}

// 策略颜色
const STRATEGY_COLORS = {
  margin_fund_convergence: 'green',
  smart_money_tracker: 'blue',
}

const lightCardStyle = { background: '#fff', border: '1px solid #f0f0f0' }
const lightTableStyle = { background: '#fff' }

export default function SmartMoney({ tradeDate, onSelectStock }) {
  const [loadingAll, setLoadingAll] = useState(false)
  const [allResults, setAllResults] = useState(null)
  const [executingStrategy, setExecutingStrategy] = useState(null)
  const [individualResults, setIndividualResults] = useState({})
  const [activeFilter, setActiveFilter] = useState('全部')
  const [expandedRow, setExpandedRow] = useState(null)

  // 执行全部策略
  const handleExecuteAll = useCallback(async () => {
    setLoadingAll(true)
    try {
      const params = {}
      if (tradeDate) params.trade_date = tradeDate
      const res = await executeAllStrategies(params)
      if (res?.success) {
        setAllResults(res.data)
        message.success('聪明钱策略执行完成')
      } else {
        message.error(res?.error || '执行失败')
      }
    } catch (err) {
      console.error('Execute all smart money strategies failed:', err)
      message.error('策略执行失败，请稍后重试')
    } finally {
      setLoadingAll(false)
    }
  }, [tradeDate])

  // 执行单个策略
  const handleExecuteStrategy = useCallback(async (strategyName) => {
    setExecutingStrategy(strategyName)
    try {
      const params = {}
      if (tradeDate) params.trade_date = tradeDate
      const res = await executeStrategy(strategyName, params)
      if (res?.success) {
        setIndividualResults((prev) => ({ ...prev, [strategyName]: res.data }))
        message.success(`${STRATEGIES[strategyName]?.title || strategyName} 执行完成`)
      } else {
        message.error(res?.error || '执行失败')
      }
    } catch (err) {
      console.error(`Strategy ${strategyName} execution failed:`, err)
      message.error('策略执行失败，请稍后重试')
    } finally {
      setExecutingStrategy(null)
    }
  }, [tradeDate])

  // 合并结果数据
  const getMergedResults = useCallback(() => {
    // 优先使用 allResults
    if (allResults?.strategies) {
      const merged = []
      Object.entries(allResults.strategies).forEach(([stratName, strat]) => {
        if (strat.results) {
          strat.results.forEach((item) => {
            merged.push({ ...item, _strategy: stratName })
          })
        }
      })
      return merged
    }
    // 否则合并 individualResults
    const merged = []
    Object.entries(individualResults).forEach(([stratName, stratData]) => {
      if (stratData?.results) {
        stratData.results.forEach((item) => {
          merged.push({ ...item, _strategy: stratName })
        })
      }
    })
    // 去重（按 ts_code 合并策略标签）
    const byCode = {}
    merged.forEach((item) => {
      if (!byCode[item.ts_code]) {
        byCode[item.ts_code] = { ...item, _strategies: [item._strategy] }
      } else {
        if (!byCode[item.ts_code]._strategies.includes(item._strategy)) {
          byCode[item.ts_code]._strategies.push(item._strategy)
        }
        // 保留更高得分
        if (item.score > byCode[item.ts_code].score) {
          byCode[item.ts_code] = { ...item, _strategies: byCode[item.ts_code]._strategies }
        }
      }
    })
    return Object.values(byCode)
  }, [allResults, individualResults])

  // 按过滤条件筛选
  const getFilteredResults = useCallback(() => {
    const merged = getMergedResults()
    if (activeFilter === '全部') return merged
    if (activeFilter === '融资共振') {
      return merged.filter((r) => r._strategy === 'margin_fund_convergence' || (r._strategies && r._strategies.includes('margin_fund_convergence')))
    }
    if (activeFilter === '聪明钱追踪') {
      return merged.filter((r) => r._strategy === 'smart_money_tracker' || (r._strategies && r._strategies.includes('smart_money_tracker')))
    }
    return merged
  }, [getMergedResults, activeFilter])

  // 信号分布统计
  const getSignalDistribution = useCallback(() => {
    const merged = getMergedResults()
    const dist = { margin_fund_convergence: 0, smart_money_tracker: 0 }
    merged.forEach((item) => {
      if (item._strategies) {
        item._strategies.forEach((s) => {
          if (dist[s] !== undefined) dist[s]++
        })
      } else if (item._strategy && dist[item._strategy] !== undefined) {
        dist[item._strategy]++
      }
    })
    return dist
  }, [getMergedResults])

  const filteredResults = getFilteredResults()
  const signalDist = getSignalDistribution()
  const hasAnyResults = getMergedResults().length > 0

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
        </div>
      ),
    },
    {
      title: '评分',
      dataIndex: 'score',
      width: 100,
      sorter: (a, b) => a.score - b.score,
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ color: scoreColor(v), fontWeight: 600, fontSize: 14 }}>
          {v.toFixed(1)}
        </span>
      ),
    },
    {
      title: '策略',
      key: 'strategy',
      width: 150,
      render: (_, record) => {
        const strategies = record._strategies || (record._strategy ? [record._strategy] : [])
        return (
          <Space size={4} wrap>
            {strategies.map((s) => (
              <Tag key={s} color={STRATEGY_COLORS[s] || 'default'}>
                {STRATEGY_LABELS[s] || s}
              </Tag>
            ))}
          </Space>
        )
      },
    },
    {
      title: '理由',
      dataIndex: 'reason',
      ellipsis: true,
      render: (v) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>,
    },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      {/* 1. Header row */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space direction="vertical" size={0}>
          <Title level={4} style={{ margin: 0, color: '#333' }}>
            💡 聪明钱雷达
          </Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            融合融资数据、大宗交易、主力资金多维度信号，追踪聪明钱动向
          </Text>
        </Space>
        <Space>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={handleExecuteAll}
            loading={loadingAll}
          >
            全部执行
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              setAllResults(null)
              setIndividualResults({})
              setActiveFilter('全部')
            }}
          >
            重置
          </Button>
        </Space>
      </div>

      {/* 2. Strategy cards row */}
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        {Object.entries(STRATEGIES).map(([key, strat]) => (
          <Col xs={24} sm={12} key={key}>
            <Card
              hoverable
              style={lightCardStyle}
              actions={[
                <Button
                  type="link"
                  icon={<ThunderboltOutlined />}
                  onClick={() => handleExecuteStrategy(key)}
                  loading={executingStrategy === key}
                >
                  执行
                </Button>,
              ]}
            >
              <div style={{ fontSize: 28, marginBottom: 8 }}>{strat.icon}</div>
              <Title level={5} style={{ color: '#333', marginBottom: 4 }}>
                {strat.title}
              </Title>
              <Paragraph type="secondary" style={{ marginBottom: 0, fontSize: 13 }}>
                {strat.description}
              </Paragraph>
              {individualResults[key] && (
                <div style={{ marginTop: 8 }}>
                  <Tag color={STRATEGY_COLORS[key]}>
                    {individualResults[key].total_matches || individualResults[key].results?.length || 0} 只股票
                  </Tag>
                </div>
              )}
            </Card>
          </Col>
        ))}
      </Row>

      {/* 3. Combined results section */}
      <Card
        title={
          <Space>
            <FundOutlined />
            <span style={{ color: '#333' }}>综合信号结果</span>
          </Space>
        }
        style={{ ...lightCardStyle, marginBottom: 16 }}
        styles={{ header: { background: '#fafafa', borderBottom: '1px solid #e8e8e8' } }}
      >
        <div style={{ marginBottom: 12 }}>
          <Segmented
            options={['全部', '融资共振', '聪明钱追踪']}
            value={activeFilter}
            onChange={setActiveFilter}
            style={{ background: '#fafafa' }}
          />
        </div>

        <Spin spinning={loadingAll || !!executingStrategy}>
          {!hasAnyResults ? (
            <Empty
              description="点击「全部执行」或策略卡片的「执行」按钮"
              style={{ padding: 40 }}
            />
          ) : filteredResults.length === 0 ? (
            <Empty description="当前筛选条件下无结果" />
          ) : (
            <Table
              columns={columns}
              dataSource={filteredResults.map((r, i) => ({ ...r, key: `${r.ts_code}-${i}` }))}
              pagination={{
                pageSize: 20,
                showSizeChanger: false,
                showTotal: (t) => `共 ${t} 只股票`,
              }}
              size="small"
              scroll={{ x: 700 }}
              style={lightTableStyle}
              onRow={(record) => ({
                onClick: () => onSelectStock && onSelectStock({ ts_code: record.ts_code, name: record.name }),
                style: { cursor: 'pointer' },
              })}
              rowClassName={() => 'dark-table-row'}
            />
          )}
        </Spin>
      </Card>

      {/* 4. Signal distribution */}
      {hasAnyResults && (
        <Card
          title={
            <Space>
              <BulbOutlined />
              <span style={{ color: '#e0e0e0' }}>信号分布</span>
            </Space>
          }
          style={lightCardStyle}
          styles={{ header: { background: '#fafafa', borderBottom: '1px solid #e8e8e8' } }}
        >
          <Row gutter={[16, 16]}>
            {Object.entries(STRATEGIES).map(([key, strat]) => (
              <Col xs={24} sm={12} key={key}>
                <Card
                  size="small"
                  style={{ background: '#fafafa', border: '1px solid #e8e8e8' }}
                >
                  <Statistic
                    title={
                      <span style={{ color: '#aaa' }}>
                        {strat.icon} {strat.title}
                      </span>
                    }
                    value={signalDist[key] || 0}
                    suffix="只"
                    valueStyle={{ color: signalDist[key] > 0 ? '#52c41a' : '#999' }}
                  />
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

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
        .ant-segmented {
          background: #f5f5f5 !important;
        }
        .ant-segmented-item {
          color: #666 !important;
        }
        .ant-segmented-item-selected {
          background: #ffffff !important;
          color: #333 !important;
        }
        .ant-statistic-title {
          color: #666 !important;
        }
      `}</style>
    </div>
  )
}
