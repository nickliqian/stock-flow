import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Row, Col, Space, Spin, Empty, Select, Tag, Tooltip,
  Typography, Table, Button, Radio, Checkbox, Divider, Alert, message,
} from 'antd'
import {
  ThunderboltOutlined, ApartmentOutlined, SwapOutlined, CheckCircleOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import { composeStrategies, getComposePresets, getStrategies } from '../services/api'

const { Text, Title } = Typography

const CATEGORY_MAP = {
  value: { label: '价值', color: 'blue' },
  momentum: { label: '动量', color: 'orange' },
  flow: { label: '资金', color: 'green' },
  event: { label: '事件', color: 'purple' },
  combo: { label: '组合', color: 'red' },
}

function scoreTag(score) {
  let color = 'default'
  let text = '低'
  if (score >= 75) { color = 'success'; text = '高' }
  else if (score >= 50) { color = 'warning'; text = '中' }
  return <Tag color={color}>{text} {score.toFixed(1)}</Tag>
}

/** 预置组合卡片 */
function PresetCard({ preset, onExecute, loading }) {
  return (
    <Card
      hoverable
      style={{ height: '100%', borderLeft: `3px solid #1890ff` }}
      actions={[
        <Button
          type="link"
          icon={<ThunderboltOutlined />}
          onClick={() => onExecute(preset)}
          loading={loading}
        >
          执行组合
        </Button>,
      ]}
    >
      <div style={{ fontSize: 28, marginBottom: 8 }}>{preset.icon}</div>
      <Title level={5} style={{ marginBottom: 4 }}>{preset.name}</Title>
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
        {preset.description}
      </Text>
      <Space size={4} wrap>
        <Tag color={preset.operator === 'AND' ? 'blue' : 'orange'}>
          {preset.operator === 'AND' ? '全部满足' : '任一满足'}
        </Tag>
        {preset.strategies.map((s) => (
          <Tag key={s} style={{ fontSize: 11 }}>{s}</Tag>
        ))}
      </Space>
    </Card>
  )
}

/** 自定义组合构建器 */
function CustomBuilder({ strategies, onExecute, loading }) {
  const [selected, setSelected] = useState([])
  const [operator, setOperator] = useState('AND')

  const options = strategies.map((s) => ({
    label: `${s.icon} ${s.description}`,
    value: s.name,
  }))

  const handlePresetExecute = useCallback((preset) => {
    onExecute(preset.strategies, preset.operator)
  }, [onExecute])

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Text strong>选择策略：</Text>
            <Select
              mode="multiple"
              placeholder="搜索并选择要组合的策略"
              style={{ width: '100%', marginTop: 8 }}
              value={selected}
              onChange={setSelected}
              options={options}
              filterOption={(input, option) =>
                option.label.toLowerCase().includes(input.toLowerCase())
              }
            />
          </div>
          <div>
            <Text strong>组合逻辑：</Text>
            <div style={{ marginTop: 8 }}>
              <Radio.Group value={operator} onChange={(e) => setOperator(e.target.value)}>
                <Radio.Button value="AND">
                  <CheckCircleOutlined /> AND（全部满足）
                </Radio.Button>
                <Radio.Button value="OR">
                  <SwapOutlined /> OR（任一满足）
                </Radio.Button>
              </Radio.Group>
            </div>
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {operator === 'AND'
                  ? 'AND：股票必须同时通过所有选中策略的筛选条件'
                  : 'OR：股票只要通过任意一个选中策略的筛选条件即可'}
              </Text>
            </div>
          </div>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={() => onExecute(selected, operator)}
            loading={loading}
            disabled={selected.length < 2}
          >
            执行组合
          </Button>
        </Space>
      </Card>
    </div>
  )
}

/** 组合结果表格 */
function ComposeResultTable({ data, loading }) {
  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40 }}>
        <Spin size="large" tip="策略组合执行中..." />
      </div>
    )
  }
  if (!data) {
    return <Empty description="选择预置组合或自定义策略后执行" />
  }
  if (!data.results || data.results.length === 0) {
    return <Empty description="未找到满足条件的股票" />
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
      render: (v) => <Text strong>{v}</Text>,
    },
    {
      title: '组合得分',
      dataIndex: 'composition_score',
      width: 100,
      sorter: (a, b) => a.composition_score - b.composition_score,
      defaultSortOrder: 'descend',
      render: (v) => scoreTag(v),
    },
    {
      title: '匹配策略数',
      dataIndex: 'num_matched',
      width: 100,
      sorter: (a, b) => a.num_matched - b.num_matched,
      render: (v, r) => (
        <Tag color={v >= 3 ? 'success' : v >= 2 ? 'warning' : 'default'}>
          {v} / {data.strategy_names?.length || 0}
        </Tag>
      ),
    },
    {
      title: '匹配详情',
      dataIndex: 'matched_strategies',
      render: (strategies) => (
        <Space size={4} wrap>
          {strategies?.map((s, i) => (
            <Tooltip key={i} title={s.reason}>
              <Tag style={{ fontSize: 11 }}>
                {s.icon} {s.description?.substring(0, 8)}...
              </Tag>
            </Tooltip>
          ))}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Space>
          <Tag color={data.operator === 'AND' ? 'blue' : 'orange'}>
            {data.operator === 'AND' ? '全部满足 (AND)' : '任一满足 (OR)'}
          </Tag>
          <Text type="secondary">
            共 {data.total} 只股票满足条件
          </Text>
        </Space>
      </div>
      <Table
        columns={columns}
        dataSource={data.results.map((r, i) => ({ ...r, key: r.ts_code + i }))}
        pagination={{ pageSize: 20, showSizeChanger: false, showTotal: (t) => `共 ${t} 只` }}
        size="small"
        scroll={{ x: 900 }}
      />
    </div>
  )
}

/** 主页面 */
export default function StrategyComposer({ tradeDate }) {
  const [strategies, setStrategies] = useState([])
  const [presets, setPresets] = useState([])
  const [loadingStrategies, setLoadingStrategies] = useState(false)
  const [loadingPresets, setLoadingPresets] = useState(false)
  const [composing, setComposing] = useState(false)
  const [composeResult, setComposeResult] = useState(null)
  const [view, setView] = useState('presets')

  useEffect(() => {
    const controller = new AbortController()
    setLoadingStrategies(true)
    setLoadingPresets(true)

    getStrategies({ signal: controller.signal })
      .then((res) => { if (res?.success && res.data) setStrategies(res.data) })
      .catch((err) => {
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        message.error('策略列表加载失败')
      })
      .finally(() => setLoadingStrategies(false))

    getComposePresets({ signal: controller.signal })
      .then((res) => { if (res?.success && res.data) setPresets(res.data) })
      .catch((err) => {
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        message.error('预置组合加载失败')
      })
      .finally(() => setLoadingPresets(false))

    return () => controller.abort()
  }, [])

  const handleCompose = useCallback(async (strategyNames, operator) => {
    if (!strategyNames || strategyNames.length < 2) {
      message.warning('请至少选择两个策略')
      return
    }
    setComposing(true)
    setComposeResult(null)
    try {
      const params = {}
      if (tradeDate) params.trade_date = tradeDate
      const res = await composeStrategies(strategyNames, operator, tradeDate)
      if (res?.success && res.data) {
        setComposeResult(res.data)
      } else {
        message.error(res?.error || '组合执行失败')
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('Compose failed:', err)
      message.error('组合执行失败，请稍后重试')
    } finally {
      setComposing(false)
    }
  }, [tradeDate])

  const handlePresetClick = useCallback((preset) => {
    handleCompose(preset.strategies, preset.operator)
  }, [handleCompose])

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Radio.Group value={view} onChange={(e) => setView(e.target.value)}>
          <Radio.Button value="presets">🎯 预置组合</Radio.Button>
          <Radio.Button value="custom">🔧 自定义组合</Radio.Button>
        </Radio.Group>
      </Space>

      {view === 'presets' && (
        <Spin spinning={loadingPresets}>
          {presets.length === 0 && !loadingPresets ? (
            <Empty description="暂无预置组合" />
          ) : (
            <Row gutter={[16, 16]}>
              {presets.map((preset, i) => (
                <Col xs={24} sm={12} md={8} lg={6} key={i}>
                  <PresetCard
                    preset={preset}
                    onExecute={handlePresetClick}
                    loading={composing}
                  />
                </Col>
              ))}
            </Row>
          )}
        </Spin>
      )}

      {view === 'custom' && (
        <CustomBuilder
          strategies={strategies}
          onExecute={handleCompose}
          loading={composing}
        />
      )}

      <Divider />

      <Title level={5}>
        <ApartmentOutlined /> 组合结果
      </Title>

      <ComposeResultTable data={composeResult} loading={composing} />
    </div>
  )
}
