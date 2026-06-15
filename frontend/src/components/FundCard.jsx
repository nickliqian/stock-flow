import React from 'react'
import { Card, Row, Col, Statistic, Tag } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined } from '@ant-design/icons'
import { formatAmount, getColor } from '../utils/format'

/**
 * 资金总览卡片组件
 * 展示主力/超大单/大单/中单/小单净流入
 */
export default function FundCard({ data }) {
  if (!data) {
    return <Card size="small"><div style={{ textAlign: 'center', padding: 20, color: '#8c8c8c' }}>暂无数据</div></Card>
  }

  const items = [
    { label: '主力净流入', value: data.main_net_inflow, color: getColor(data.main_net_inflow) },
    { label: '超大单', value: data.super_large_net, color: getColor(data.super_large_net) },
    { label: '大单', value: data.large_net, color: getColor(data.large_net) },
    { label: '中单', value: data.medium_net, color: getColor(data.medium_net) },
    { label: '小单', value: data.small_net, color: getColor(data.small_net) },
  ]

  return (
    <Card
      className="chart-card"
      title="📊 资金流向明细"
      size="small"
    >
      <Row gutter={[8, 12]}>
        {items.map((item) => (
          <Col xs={8} sm={8} md={4} key={item.label}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>{item.label}</div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  color: item.color,
                }}
              >
                {formatAmount(item.value)}
              </div>
            </div>
          </Col>
        ))}
      </Row>
    </Card>
  )
}
