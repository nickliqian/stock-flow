import React, { useState, useEffect, useCallback } from 'react'
import { Card, Table, Segmented, Typography, Empty } from 'antd'
import { getSectors } from '../services/api'
import { formatAmount, getColor, getColorClass, getSign } from '../utils/format'

const { Text } = Typography

/**
 * 板块资金流向排行榜
 * 使用 antd Table + Segmented 切换净流入/净流出 TOP10
 */
export default function SectorRanking({ tradeDate, onSelectSector }) {
  const [type, setType] = useState('net_inflow')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      // [修改] 问题8：净流出排行使用 sort_order=asc 参数，后端直接按 net_inflow ASC 排序，
      // 无需前端请求 300 条再排序截取，只请求 10 条即可。
      const pageSize = 10
      const sortOrder = type === 'net_outflow' ? 'asc' : 'desc'
      const result = await getSectors(1, pageSize, tradeDate, sortOrder)
      setData(result)
    } catch (err) {
      console.error('加载板块排行数据失败:', err)
      setData({ data: [] })
    } finally {
      setLoading(false)
    }
  }, [type, tradeDate])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const items = data?.data || []

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
      title: '板块名称',
      key: 'sector_name',
      render: (_, record) => (
        <Text style={{ fontWeight: 500, fontSize: 13 }}>{record.sector_name}</Text>
      ),
    },
    {
      title: '主力净流入',
      key: 'net_inflow',
      width: 110,
      align: 'right',
      render: (_, record) => (
        <Text style={{ fontSize: 13, color: getColor(record.net_inflow), fontWeight: 600 }}>
          {getSign(record.net_inflow)}{formatAmount(record.net_inflow)}
        </Text>
      ),
    },
    {
      title: '大单净流入',
      key: 'large_net',
      width: 110,
      align: 'right',
      render: (_, record) => (
        <Text style={{ fontSize: 13, color: getColor(record.large_net) }}>
          {getSign(record.large_net)}{formatAmount(record.large_net)}
        </Text>
      ),
    },
    {
      title: '领涨股',
      key: 'lead_stock',
      width: 120,
      render: (_, record) => (
        <div style={{ fontSize: 12 }}>
          <span>{record.lead_stock_name || '--'}</span>
          {record.lead_chg != null && (
            <span className={getColorClass(record.lead_chg)} style={{ marginLeft: 4 }}>
              {getSign(record.lead_chg)}{record.lead_chg.toFixed(2)}%
            </span>
          )}
        </div>
      ),
    },
  ]

  return (
    <Card
      className="chart-card"
      title={<span>📊 板块资金流向排行</span>}
      size="small"
      extra={
        <Segmented
          className="day-segmented"
          size="small"
          value={type}
          onChange={setType}
          options={[
            { label: '净流入TOP10', value: 'net_inflow' },
            { label: '净流出TOP10', value: 'net_outflow' },
          ]}
        />
      }
    >
      <Table
        dataSource={items}
        columns={columns}
        rowKey="sector_code"
        loading={loading}
        pagination={false}
        size="small"
        locale={{ emptyText: <Empty description="暂无数据" /> }}
        onRow={(record) => ({
          onClick: () => {
            if (onSelectSector) {
              onSelectSector({ sector_code: record.sector_code, sector_name: record.sector_name })
            }
          },
          style: { cursor: onSelectSector ? 'pointer' : 'default' },
        })}
      />
    </Card>
  )
}
