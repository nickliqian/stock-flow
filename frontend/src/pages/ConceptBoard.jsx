import React, { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Input, Button, Space, Tag, Typography, Spin, Drawer, Descriptions, Tabs
} from 'antd'
import {
  SearchOutlined, ReloadOutlined, AppstoreOutlined, RiseOutlined, FallOutlined
} from '@ant-design/icons'
import { getConcepts, getConceptDetail, getConceptMembers } from '../services/api'

const { Text, Title } = Typography

/** 概念板块追踪页面 */
export default function ConceptBoard({ onSelectStock }) {
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [sortBy, setSortBy] = useState('pct_change')
  const [sortOrder, setSortOrder] = useState('desc')
  const [searchName, setSearchName] = useState('')

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedConcept, setSelectedConcept] = useState(null)
  const [conceptDetail, setConceptDetail] = useState(null)
  const [conceptMembers, setConceptMembers] = useState([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailTab, setDetailTab] = useState('daily')

  const fetchData = useCallback(async (signal) => {
    setLoading(true)
    try {
      const result = await getConcepts(page, pageSize, sortBy, sortOrder, searchName || undefined, { signal })
      setData(result.data || [])
      setTotal(result.total || 0)
    } catch (err) {
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
      console.error('获取概念板块失败:', err)
      setData([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, sortBy, sortOrder, searchName])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(controller.signal)
    return () => controller.abort()
  }, [fetchData])

  const handleSortChange = (field) => {
    if (sortBy === field) {
      setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
    setPage(1)
  }

  const handleRowClick = async (record) => {
    setSelectedConcept(record)
    setDrawerOpen(true)
    setDetailLoading(true)
    setDetailTab('daily')
    try {
      const [detail, members] = await Promise.all([
        getConceptDetail(record.ts_code),
        getConceptMembers(record.ts_code),
      ])
      setConceptDetail(detail)
      setConceptMembers(members.members || [])
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('获取概念详情失败:', err)
    } finally {
      setDetailLoading(false)
    }
  }

  const columns = [
    {
      title: '概念名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      fixed: 'left',
      render: (v, record) => (
        <div>
          <div style={{ fontWeight: 600, fontSize: 13, color: '#1677ff' }}>{v || '--'}</div>
          <div style={{ fontSize: 11, color: '#8c8c8c' }}>{record.ts_code}</div>
        </div>
      ),
    },
    {
      title: '成分股数',
      dataIndex: 'member_count',
      key: 'member_count',
      width: 80,
      sorter: true,
      render: (v) => <span style={{ fontWeight: 500 }}>{v || 0}</span>,
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
      title: '涨跌幅',
      dataIndex: 'pct_change',
      key: 'pct_change',
      width: 100,
      sorter: true,
      defaultSortOrder: 'descend',
      render: (v) => {
        if (!v) return '--'
        const color = v > 0 ? '#cf1322' : v < 0 ? '#3f8600' : '#8c8c8c'
        const sign = v > 0 ? '+' : ''
        return (
          <span style={{ color, fontWeight: 600, fontSize: 14 }}>
            {sign}{v.toFixed(2)}%
          </span>
        )
      },
    },
    {
      title: '成交额',
      dataIndex: 'vol',
      key: 'vol',
      width: 100,
      sorter: true,
      render: (v) => {
        if (!v) return '--'
        if (v >= 100000000) return `${(v / 100000000).toFixed(2)}亿`
        if (v >= 10000) return `${(v / 10000).toFixed(2)}万`
        return v.toFixed(2)
      },
    },
    {
      title: '换手率',
      dataIndex: 'turnover_rate',
      key: 'turnover_rate',
      width: 80,
      sorter: true,
      render: (v) => {
        if (!v) return '--'
        return <span>{v.toFixed(2)}%</span>
      },
    },
  ]

  const memberColumns = [
    {
      title: '股票名称',
      dataIndex: 'name',
      key: 'name',
      width: 120,
      render: (v, record) => (
        <div>
          <div style={{ fontWeight: 600, fontSize: 12 }}>{v || '--'}</div>
          <div style={{ fontSize: 10, color: '#8c8c8c' }}>{record.ts_code}</div>
        </div>
      ),
    },
    {
      title: '收盘价',
      dataIndex: 'close',
      key: 'close',
      width: 80,
      render: (v) => v ? v.toFixed(2) : '--',
    },
    {
      title: 'PE(TTM)',
      dataIndex: 'pe_ttm',
      key: 'pe_ttm',
      width: 80,
      render: (v) => {
        if (!v || v === 0) return '--'
        return v.toFixed(2)
      },
    },
    {
      title: 'PB',
      dataIndex: 'pb',
      key: 'pb',
      width: 70,
      render: (v) => v ? v.toFixed(2) : '--',
    },
    {
      title: '总市值(亿)',
      dataIndex: 'total_mv',
      key: 'total_mv',
      width: 100,
      render: (v) => {
        if (!v) return '--'
        return `${(v / 10000).toFixed(0)}亿`
      },
    },
  ]

  return (
    <div>
      {/* 搜索栏 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space size={8}>
          <Text type="secondary" style={{ fontSize: 12 }}>🔍 搜索概念:</Text>
          <Input
            placeholder="输入概念名称搜索"
            prefix={<SearchOutlined />}
            value={searchName}
            onChange={e => setSearchName(e.target.value)}
            onPressEnter={() => { setPage(1); fetchData() }}
            allowClear
            style={{ width: 240 }}
            size="small"
          />
          <Button size="small" icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
            刷新
          </Button>
        </Space>
      </Card>

      {/* 概念列表 */}
      <Card size="small">
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            共 <Text strong>{total.toLocaleString()}</Text> 个概念板块
            <span style={{ marginLeft: 8 }}>
              排序: <Tag color="blue">{sortBy === 'pct_change' ? '涨跌幅' : sortBy === 'member_count' ? '成分股数' : sortBy}</Tag>
              {sortOrder === 'desc' ? <RiseOutlined /> : <FallOutlined />}
            </span>
          </Text>
        </div>

        <Table
          dataSource={data}
          columns={columns}
          rowKey="ts_code"
          loading={loading}
          size="small"
          scroll={{ x: 700 }}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            pageSizeOptions: ['20', '50', '100'],
            showTotal: (total) => `共 ${total} 条`,
            size: 'small',
          }}
          onChange={(pagination, filters, sorter) => {
            setPage(pagination.current)
            setPageSize(pagination.pageSize)
            if (sorter.field) {
              handleSortChange(sorter.field)
            }
          }}
          onRow={(record) => ({
            onClick: () => handleRowClick(record),
            style: { cursor: 'pointer' },
          })}
          rowClassName={(record, index) => index % 2 === 0 ? 'row-light' : 'row-dark'}
        />
      </Card>

      {/* 概念详情抽屉 */}
      <Drawer
        title={selectedConcept ? `${selectedConcept.name} (${selectedConcept.ts_code})` : '概念详情'}
        placement="right"
        width={720}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : (
          <Tabs
            activeKey={detailTab}
            onChange={setDetailTab}
            items={[
              {
                key: 'daily',
                label: '近10日行情',
                children: (
                  <Table
                    dataSource={[...(conceptDetail?.daily || [])].reverse()}
                    rowKey="trade_date"
                    size="small"
                    pagination={false}
                    columns={[
                      {
                        title: '日期',
                        dataIndex: 'trade_date',
                        key: 'trade_date',
                        render: (v) => v ? `${v.slice(0, 4)}-${v.slice(4, 6)}-${v.slice(6, 8)}` : '--',
                      },
                      { title: '收盘价', dataIndex: 'close', key: 'close', render: (v) => v?.toFixed(2) || '--' },
                      {
                        title: '涨跌幅',
                        dataIndex: 'pct_change',
                        key: 'pct_change',
                        render: (v) => {
                          if (!v) return '--'
                          const color = v > 0 ? '#cf1322' : v < 0 ? '#3f8600' : '#8c8c8c'
                          const sign = v > 0 ? '+' : ''
                          return <span style={{ color, fontWeight: 600 }}>{sign}{v.toFixed(2)}%</span>
                        },
                      },
                      { title: '成交量', dataIndex: 'vol', key: 'vol', render: (v) => v?.toFixed(0) || '--' },
                      { title: '换手率', dataIndex: 'turnover_rate', key: 'turnover_rate', render: (v) => v ? `${v.toFixed(2)}%` : '--' },
                    ]}
                  />
                ),
              },
              {
                key: 'members',
                label: `成分股 (${conceptMembers.length})`,
                children: (
                  <Table
                    dataSource={conceptMembers}
                    columns={memberColumns}
                    rowKey="ts_code"
                    size="small"
                    pagination={{ pageSize: 20, size: 'small' }}
                    onRow={(record) => ({
                      onClick: () => {
                        setDrawerOpen(false)
                        onSelectStock && onSelectStock(record)
                      },
                      style: { cursor: 'pointer' },
                    })}
                  />
                ),
              },
            ]}
          />
        )}
      </Drawer>
    </div>
  )
}
