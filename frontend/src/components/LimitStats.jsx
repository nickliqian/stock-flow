import React, { useState, useEffect, useMemo } from 'react'
import { Card, Row, Col, Statistic, Tabs, Table, Tag, Empty, Spin, Select } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons'
import { getLimitStats } from '../services/api'
import { formatAmount } from '../utils/format'

const PAGE_SIZE = 20

/**
 * 涨跌停监控组件
 * 展示涨停/跌停股票列表及统计
 * 支持：分页、按行业/概念/连板分组
 */
export default function LimitStats({ tradeDate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('up')
  const [viewMode, setViewMode] = useState('all') // all / industry / concept / consecutive
  const [page, setPage] = useState(1)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getLimitStats(tradeDate)
      .then((res) => {
        if (!cancelled) setData(res?.data || res)
      })
      .catch(() => {
        if (!cancelled) setData(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [tradeDate])

  // 重置分页和模式当数据变化时
  useEffect(() => {
    setPage(1)
  }, [activeTab, viewMode, tradeDate])

  // === 所有 hooks 必须在此之前，下面可以有条件 return ===

  // 按行业分组
  const groupByIndustry = (list) => {
    const groups = {}
    list.forEach(item => {
      const industry = item.industry || '未知'
      if (!groups[industry]) {
        groups[industry] = { industry, count: 0, stocks: [], leadStock: null }
      }
      groups[industry].count++
      groups[industry].stocks.push(item)
      if (!groups[industry].leadStock || (item.amount || 0) > (groups[industry].leadStock.amount || 0)) {
        groups[industry].leadStock = item
      }
    })
    return Object.values(groups).sort((a, b) => b.count - a.count)
  }

  // 按连板天数分组
  const groupByConsecutive = (list) => {
    const groups = {}
    list.forEach(item => {
      const days = item.limit_times || 1
      if (!groups[days]) {
        groups[days] = { days, count: 0, stocks: [] }
      }
      groups[days].count++
      groups[days].stocks.push(item)
    })
    return Object.values(groups).sort((a, b) => b.days - a.days)
  }

  // 为列表数据添加 _limit 标记
  const upList = useMemo(() => (data?.up_list || []).map((item) => ({ ...item, _limit: 'U' })), [data])
  const downList = useMemo(() => (data?.down_list || []).map((item) => ({ ...item, _limit: 'D' })), [data])

  // 根据当前 tab 和模式构建表格内容
  const currentList = activeTab === 'up' ? upList : downList
  const listLabel = activeTab === 'up' ? '涨停' : '跌停'

  // 构建分组数据
  const groupedData = useMemo(() => {
    if (viewMode === 'industry') return groupByIndustry(currentList)
    if (viewMode === 'consecutive') return groupByConsecutive(currentList)
    return currentList
  }, [currentList, viewMode])

  if (loading) {
    return (
      <Card className="chart-card" title="📊 涨跌停监控" size="small">
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="small" />
        </div>
      </Card>
    )
  }

  if (!data) {
    return (
      <Card className="chart-card" title="📊 涨跌停监控" size="small">
        <Empty description="暂无数据" />
      </Card>
    )
  }

  // 模式切换选项
  const modeOptions = [
    { label: '全部', value: 'all' },
    { label: '按行业', value: 'industry' },
    { label: '连板', value: 'consecutive' },
  ]

  const columns = [
    {
      title: '股票名称',
      dataIndex: 'name',
      key: 'name',
      width: 100,
      fixed: 'left',
    },
    {
      title: '代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 100,
    },
    {
      title: '收盘价',
      dataIndex: 'close',
      key: 'close',
      width: 80,
      align: 'right',
      render: (v) => v?.toFixed(2) ?? '-',
    },
    {
      title: '涨跌幅',
      dataIndex: 'pct_chg',
      key: 'pct_chg',
      width: 80,
      align: 'right',
      render: (v, record) => {
        const color = record._limit === 'U' ? '#cf1322' : '#3f8600'
        return <span style={{ color, fontWeight: 600 }}>{v?.toFixed(2)}%</span>
      },
    },
    {
      title: '成交额',
      dataIndex: 'amount',
      key: 'amount',
      width: 90,
      align: 'right',
      render: (v) => formatAmount(v),
    },
    {
      title: '首次封板',
      dataIndex: 'first_time',
      key: 'first_time',
      width: 80,
      align: 'center',
    },
    {
      title: '开板次数',
      dataIndex: 'open_times',
      key: 'open_times',
      width: 80,
      align: 'center',
      render: (v) => v ?? 0,
    },
    {
      title: '连板天数',
      dataIndex: 'limit_times',
      key: 'limit_times',
      width: 80,
      align: 'center',
      render: (v) => {
        if (!v || v <= 1) return <span>1</span>
        return <Tag color="red">{v}板</Tag>
      },
    },
  ]

  // 行业分组列
  const industryColumns = [
    {
      title: '行业',
      dataIndex: 'industry',
      key: 'industry',
      width: 120,
      render: (v) => <span style={{ fontWeight: 600 }}>{v || '未知'}</span>,
    },
    {
      title: '涨停数',
      dataIndex: 'count',
      key: 'count',
      width: 80,
      align: 'center',
      render: (v) => <Tag color="red">{v}</Tag>,
    },
    {
      title: '领涨股',
      dataIndex: 'leadStock',
      key: 'leadStock',
      render: (v, record) => (
        <span>
          {v?.name || '--'}
          {v?.pct_chg != null && (
            <span style={{ marginLeft: 8, color: '#cf1322', fontWeight: 500 }}>
              {v.pct_chg > 0 ? '+' : ''}{v.pct_chg.toFixed(2)}%
            </span>
          )}
        </span>
      ),
    },
    {
      title: '个股列表',
      dataIndex: 'stocks',
      key: 'stocks',
      render: (stocks) => (
        <span style={{ fontSize: 12, color: '#8c8c8c' }}>
          {stocks?.slice(0, 3).map(s => s.name).join('、')}
          {stocks?.length > 3 ? ` 等${stocks.length}只` : ''}
        </span>
      ),
    },
  ]

  // 连板分组列
  const consecutiveColumns = [
    {
      title: '连板天数',
      dataIndex: 'days',
      key: 'days',
      width: 100,
      render: (v) => (
        <Tag color={v >= 4 ? 'gold' : v >= 3 ? 'orange' : 'red'} style={{ fontSize: 14, padding: '2px 8px' }}>
          {v}连板
        </Tag>
      ),
    },
    {
      title: '数量',
      dataIndex: 'count',
      key: 'count',
      width: 80,
      align: 'center',
      render: (v) => <span style={{ fontWeight: 600 }}>{v}只</span>,
    },
    {
      title: '个股列表',
      dataIndex: 'stocks',
      key: 'stocks',
      render: (stocks) => (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {stocks?.map((s, i) => (
            <Tag key={i}>
              {s.name} <span style={{ color: '#cf1322', marginLeft: 4 }}>{s.pct_chg?.toFixed(2)}%</span>
            </Tag>
          ))}
        </div>
      ),
    },
  ]

  const renderTable = () => {
    if (viewMode === 'industry') {
      return (
        <Table
          columns={industryColumns}
          dataSource={groupedData}
          rowKey="industry"
          size="small"
          pagination={false}
          locale={{ emptyText: `暂无${listLabel}数据` }}
        />
      )
    }

    if (viewMode === 'consecutive') {
      return (
        <Table
          columns={consecutiveColumns}
          dataSource={groupedData}
          rowKey="days"
          size="small"
          pagination={false}
          locale={{ emptyText: `暂无${listLabel}数据` }}
        />
      )
    }

    // 全部模式 — 带分页
    return (
      <Table
        columns={columns}
        dataSource={currentList}
        rowKey="ts_code"
        size="small"
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total: currentList.length,
          onChange: setPage,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 只`,
        }}
        scroll={{ x: 700 }}
        locale={{ emptyText: `暂无${listLabel}数据` }}
      />
    )
  }

  const tabItems = [
    {
      key: 'up',
      label: <span style={{ color: '#cf1322' }}>涨停 ({data.up_count})</span>,
      children: (
        <>
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'flex-end' }}>
            <Select
              size="small"
              value={viewMode}
              onChange={setViewMode}
              options={modeOptions}
              style={{ width: 100 }}
            />
          </div>
          {renderTable()}
        </>
      ),
    },
    {
      key: 'down',
      label: <span style={{ color: '#3f8600' }}>跌停 ({data.down_count})</span>,
      children: (
        <>
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'flex-end' }}>
            <Select
              size="small"
              value={viewMode}
              onChange={setViewMode}
              options={modeOptions}
              style={{ width: 100 }}
            />
          </div>
          {renderTable()}
        </>
      ),
    },
  ]

  return (
    <Card className="chart-card" title="📊 涨跌停监控" size="small">
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Statistic
            title="涨停数量"
            value={data.up_count}
            valueStyle={{ color: '#cf1322' }}
            prefix={<ArrowUpOutlined />}
            suffix="只"
          />
        </Col>
        <Col span={12}>
          <Statistic
            title="跌停数量"
            value={data.down_count}
            valueStyle={{ color: '#3f8600' }}
            prefix={<ArrowDownOutlined />}
            suffix="只"
          />
        </Col>
      </Row>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        size="small"
      />
    </Card>
  )
}
