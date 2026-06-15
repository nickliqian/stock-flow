import React, { useState, useEffect, useCallback } from 'react'
import { Card, Table, Segmented, Tag, Typography, Empty, Spin } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons'
import { getStockRanking } from '../services/api'
import { formatAmount, formatPercent, getColor, getColorClass } from '../utils/format'

const { Text } = Typography

/**
 * 个股资金流向排行榜
 * 使用 antd Table + Segmented 切换净流入/净流出
 */
export default function StockRanking({ tradeDate, onSelectStock }) {
  const [type, setType] = useState('net_inflow')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getStockRanking(tradeDate, type, 20)
      setData(result)
    } catch (err) {
      console.error('加载排行数据失败:', err)
      setData({ items: [] })
    } finally {
      setLoading(false)
    }
  }, [tradeDate, type])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const items = data?.items || []

  const columns = [
    {
      title: '#',
      key: 'rank',
      width: 40,
      render: (_, __, index) => (
        <Text type="secondary" style={{ fontSize: 12 }}>{index + 1}</Text>
      ),
    },
    {
      title: '名称',
      key: 'name',
      render: (_, record) => (
        <div>
          <div style={{ fontWeight: 500, fontSize: 13 }}>{record.name}</div>
          <div style={{ fontSize: 11, color: '#8c8c8c' }}>{record.ts_code}</div>
        </div>
      ),
    },
    {
      title: '收盘',
      key: 'close',
      width: 80,
      align: 'right',
      render: (_, record) => (
        <Text style={{ fontSize: 13 }}>{record.close?.toFixed(2) ?? '--'}</Text>
      ),
    },
    {
      title: '涨跌',
      key: 'pct_change',
      width: 80,
      align: 'right',
      render: (_, record) => (
        <Text style={{ fontSize: 13, color: getColor(record.pct_change), fontWeight: 500 }}>
          {formatPercent(record.pct_change)}
        </Text>
      ),
    },
    {
      title: '净流入',
      key: 'net_amount',
      width: 100,
      align: 'right',
      render: (_, record) => (
        <Text style={{ fontSize: 13, color: getColor(record.net_amount), fontWeight: 600 }}>
          {formatAmount(record.net_amount)}
        </Text>
      ),
    },
  ]

  return (
    <Card
      className="chart-card"
      title={
        <span>📊 个股资金排行</span>
      }
      size="small"
      extra={
        <Segmented
          className="day-segmented"
          size="small"
          value={type}
          onChange={setType}
          options={[
            { label: '净流入', value: 'net_inflow' },
            { label: '净流出', value: 'net_outflow' },
          ]}
        />
      }
    >
      <Table
        dataSource={items}
        columns={columns}
        rowKey="ts_code"
        loading={loading}
        pagination={false}
        size="small"
        locale={{ emptyText: <Empty description="暂无数据" /> }}
        onRow={(record) => ({
          onClick: () => {
            if (onSelectStock) {
              onSelectStock({ ts_code: record.ts_code, name: record.name })
            }
          },
          style: { cursor: 'pointer' },
        })}
      />
    </Card>
  )
}
