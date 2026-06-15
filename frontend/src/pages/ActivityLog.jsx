import React, { useState, useEffect, useCallback } from 'react'
import { Card, Table, Tag, Typography, Space, Select, Statistic, Row, Col, Drawer, Empty, Button, Tabs } from 'antd'
import { RobotOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, ReloadOutlined, BarChartOutlined, FileTextOutlined } from '@ant-design/icons'
import { getActivityLogs } from '../services/api'

const { Text, Paragraph } = Typography

const TASK_TYPE_MAP = {
  evolution: { label: '自进化', color: 'blue', icon: '🚀' },
  review: { label: '审查', color: 'green', icon: '🔍' },
  sync: { label: '同步', color: 'orange', icon: '🔄' },
  manual: { label: '手动', color: 'purple', icon: '👤' },
  research: { label: '搜集', color: 'cyan', icon: '📰' },
  compile: { label: '编译', color: 'magenta', icon: '📚' },
}

const STATUS_MAP = {
  success: { label: '成功', color: 'success', icon: <CheckCircleOutlined /> },
  failed: { label: '失败', color: 'error', icon: <CloseCircleOutlined /> },
  partial: { label: '部分完成', color: 'warning', icon: <ClockCircleOutlined /> },
}

function formatDuration(seconds) {
  if (!seconds) return '--'
  if (seconds < 60) return `${seconds}秒`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}分${s}秒`
}

function formatTime(isoStr) {
  if (!isoStr) return '--'
  try {
    const d = new Date(isoStr)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return isoStr
  }
}

/** AI 日志页面（含子 Tab：日志 / 统计） */
export default function ActivityLog() {
  const [activeTab, setActiveTab] = useState('logs')

  return (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      type="card"
      items={[
        {
          key: 'logs',
          label: <span><FileTextOutlined /> 日志</span>,
          children: <ActivityLogContent />,
        },
        {
          key: 'stats',
          label: <span><BarChartOutlined /> 统计</span>,
          children: <ActivityStats />,
        },
      ]}
    />
  )
}

/** 日志统计子组件 */
function ActivityStats() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    const fetchLogs = async () => {
      setLoading(true)
      try {
        const resp = await getActivityLogs({ page: 1, page_size: 200 }, { signal: controller.signal })
        setLogs(resp.items || [])
      } catch (err) {
        if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
        console.error('Failed to load stats:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchLogs()
    return () => controller.abort()
  }, [])

  // 按类型统计
  const typeStats = {}
  const statusStats = { success: 0, failed: 0, partial: 0 }
  let totalDuration = 0
  logs.forEach((log) => {
    typeStats[log.task_type] = (typeStats[log.task_type] || 0) + 1
    statusStats[log.status] = (statusStats[log.status] || 0) + 1
    totalDuration += log.duration_seconds || 0
  })

  const TYPE_LABELS = { evolution: '自进化', review: '审查', sync: '同步', manual: '手动' }
  const TYPE_ICONS = { evolution: '🚀', review: '🔍', sync: '🔄', manual: '👤' }

  return (
    <div style={{ padding: '0 4px' }}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <BarChartOutlined style={{ fontSize: 18 }} />
          <Text strong style={{ fontSize: 16 }}>工作统计</Text>
          <Tag>{logs.length} 条记录</Tag>
        </Space>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="总记录数" value={logs.length} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="成功" value={statusStats.success} valueStyle={{ color: '#52c41a' }} prefix={<CheckCircleOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="失败" value={statusStats.failed} valueStyle={{ color: '#ff4d4f' }} prefix={<CloseCircleOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="总耗时"
              value={totalDuration < 60 ? `${totalDuration}秒` : `${Math.floor(totalDuration / 60)}分${totalDuration % 60}秒`}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card size="small" title="📊 按类型统计">
        {Object.entries(typeStats).length === 0 ? (
          <Empty description="暂无统计数据" />
        ) : (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {Object.entries(typeStats).sort((a, b) => b[1] - a[1]).map(([type, count]) => (
              <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 16 }}>{TYPE_ICONS[type] || '📋'}</span>
                <Text strong style={{ width: 80 }}>{TYPE_LABELS[type] || type}</Text>
                <div style={{ flex: 1, height: 20, background: '#f0f0f0', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${(count / logs.length) * 100}%`, background: '#1677ff', borderRadius: 4, transition: 'width 0.3s' }} />
                </div>
                <Text style={{ width: 60, textAlign: 'right' }}>{count} 次</Text>
              </div>
            ))}
          </Space>
        )}
      </Card>
    </div>
  )
}

/** AI 工作日志内容 */
function ActivityLogContent() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [filterType, setFilterType] = useState(null)
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [selectedLog, setSelectedLog] = useState(null)

  const fetchLogs = useCallback(async (signal) => {
    setLoading(true)
    try {
      const params = { page, page_size: 20 }
      if (filterType) params.task_type = filterType
      const resp = await getActivityLogs(params, { signal })
      setLogs(resp.items || [])
      setTotal(resp.total || 0)
    } catch (err) {
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
      console.error('Failed to load activity logs:', err)
    } finally {
      setLoading(false)
    }
  }, [page, filterType])

  useEffect(() => {
    const controller = new AbortController()
    fetchLogs(controller.signal)
    return () => controller.abort()
  }, [fetchLogs])

  const columns = [
    {
      title: '类型',
      dataIndex: 'task_type',
      key: 'task_type',
      width: 100,
      render: (v) => {
        const info = TASK_TYPE_MAP[v] || { label: v, color: 'default', icon: '📋' }
        return <Tag color={info.color}>{info.icon} {info.label}</Tag>
      },
    },
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      width: 200,
      render: (v) => <Text strong style={{ fontSize: 13 }}>{v || '--'}</Text>,
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      ellipsis: true,
      render: (v) => <Text type="secondary" style={{ fontSize: 12 }}>{v || '--'}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v) => {
        const info = STATUS_MAP[v] || { label: v, color: 'default' }
        return <Tag color={info.color} icon={info.icon}>{info.label}</Tag>
      },
    },
    {
      title: '耗时',
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      width: 80,
      render: (v) => <Text type="secondary" style={{ fontSize: 12 }}>{formatDuration(v)}</Text>,
    },
    {
      title: '执行时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 120,
      render: (v) => <Text type="secondary" style={{ fontSize: 12 }}>{formatTime(v)}</Text>,
    },
    {
      title: '操作',
      key: 'action',
      width: 60,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => {
            setSelectedLog(record)
            setDrawerVisible(true)
          }}
        >
          详情
        </Button>
      ),
    },
  ]

  return (
    <div style={{ padding: '0 4px' }}>
      {/* 顶部标题 + 筛选 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <RobotOutlined style={{ fontSize: 18 }} />
          <Text strong style={{ fontSize: 16 }}>AI 工作日志</Text>
          <Tag>{total} 条记录</Tag>
        </Space>
        <Space>
          <Select
            placeholder="筛选类型"
            allowClear
            style={{ width: 120 }}
            value={filterType}
            onChange={(v) => { setFilterType(v); setPage(1) }}
            options={Object.entries(TASK_TYPE_MAP).map(([k, v]) => ({
              value: k,
              label: `${v.icon} ${v.label}`,
            }))}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchLogs} size="small" />
        </Space>
      </div>

      {/* 日志列表 */}
      <Card size="small">
        <Table
          dataSource={logs}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{
            current: page,
            total,
            pageSize: 20,
            onChange: setPage,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 条`,
          }}
          locale={{ emptyText: <Empty description="暂无工作日志" /> }}
        />
      </Card>

      {/* 详情抽屉 */}
      <Drawer
        title={selectedLog ? `${TASK_TYPE_MAP[selectedLog.task_type]?.icon || ''} ${selectedLog.task_name || '日志详情'}` : '日志详情'}
        placement="right"
        width={600}
        open={drawerVisible}
        onClose={() => { setDrawerVisible(false); setSelectedLog(null) }}
      >
        {selectedLog && (
          <div>
            {/* 基本信息 */}
            <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
              <Col span={8}>
                <Statistic title="类型" value={TASK_TYPE_MAP[selectedLog.task_type]?.label || selectedLog.task_type} />
              </Col>
              <Col span={8}>
                <Statistic title="状态" value={STATUS_MAP[selectedLog.status]?.label || selectedLog.status} />
              </Col>
              <Col span={8}>
                <Statistic title="耗时" value={formatDuration(selectedLog.duration_seconds)} />
              </Col>
            </Row>

            <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
              <Col span={12}>
                <Statistic title="开始时间" value={formatTime(selectedLog.started_at)} />
              </Col>
              <Col span={12}>
                <Statistic title="结束时间" value={formatTime(selectedLog.finished_at)} />
              </Col>
            </Row>

            {/* 摘要 */}
            <Card size="small" title="📋 执行摘要" style={{ marginBottom: 16 }}>
              <Paragraph>{selectedLog.summary || '无摘要'}</Paragraph>
            </Card>

            {/* 修改的文件 */}
            {selectedLog.files_changed && selectedLog.files_changed.length > 0 && (
              <Card size="small" title="📁 修改的文件" style={{ marginBottom: 16 }}>
                <Space direction="vertical" size={4}>
                  {selectedLog.files_changed.map((f, i) => (
                    <Tag key={i} style={{ margin: 0 }}>{f}</Tag>
                  ))}
                </Space>
              </Card>
            )}

            {/* 详细报告 */}
            {selectedLog.details && (
              <Card size="small" title="📝 详细报告">
                <Paragraph
                  style={{
                    whiteSpace: 'pre-wrap',
                    fontSize: 13,
                    lineHeight: 1.8,
                    maxHeight: 400,
                    overflow: 'auto',
                    background: '#fafafa',
                    padding: 12,
                    borderRadius: 6,
                  }}
                >
                  {selectedLog.details}
                </Paragraph>
              </Card>
            )}
          </div>
        )}
      </Drawer>
    </div>
  )
}
