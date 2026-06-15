import React from 'react'
import { Card, Statistic, Row, Col, Divider } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined } from '@ant-design/icons'
import { formatAmount, formatPercent, getColor } from '../utils/format'

/**
 * 北向资金卡片组件
 * 展示今日/昨日/5日均值对比
 */
export default function NorthFundCard({ data }) {
  if (!data) {
    return <Card size="small"><div style={{ textAlign: 'center', padding: 20, color: '#8c8c8c' }}>暂无数据</div></Card>
  }

  const northMoney = data.north_money || 0

  return (
    <Card
      className="chart-card"
      title="🌏 北向资金"
      size="small"
    >
      {/* 今日净买入 — 大号数字 */}
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>今日净买入</div>
        <Statistic
          value={northMoney}
          precision={2}
          formatter={(val) => formatAmount(val)}
          valueStyle={{
            fontSize: 28,
            fontWeight: 700,
            color: northMoney > 0 ? '#cf1322' : northMoney < 0 ? '#3f8600' : '#8c8c8c',
          }}
          prefix={northMoney > 0 ? <ArrowUpOutlined /> : northMoney < 0 ? <ArrowDownOutlined /> : <MinusOutlined />}
        />
      </div>

      <Divider style={{ margin: '8px 0 12px' }} />

      {/* 对比信息 */}
      <Row gutter={[0, 8]}>
        <Col span={12}>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>沪股通净买入</div>
          <div style={{ fontSize: 14, fontWeight: 500, color: getColor(data.hgt) }}>
            {formatAmount(data.hgt)}
          </div>
        </Col>
        <Col span={12}>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>深股通净买入</div>
          <div style={{ fontSize: 14, fontWeight: 500, color: getColor(data.sgt) }}>
            {formatAmount(data.sgt)}
          </div>
        </Col>
      </Row>

      <Divider style={{ margin: '8px 0' }} />

      <Row gutter={[0, 8]}>
        <Col span={12}>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>较昨日</div>
          <div style={{ fontSize: 13, fontWeight: 500, color: getColor(data.vs_yesterday) }}>
            {formatAmount(data.vs_yesterday)}
            <span style={{ fontSize: 11, marginLeft: 4 }}>
              ({formatPercent(data.vs_yesterday_pct)})
            </span>
          </div>
        </Col>
        <Col span={12}>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>近5日均值</div>
          <div style={{ fontSize: 13, fontWeight: 500 }}>
            {formatAmount(data.avg_5day)}
          </div>
        </Col>
      </Row>

      <Divider style={{ margin: '8px 0' }} />

      <Row>
        <Col span={24}>
          <div style={{ fontSize: 12, color: '#8c8c8c' }}>较5日均值</div>
          <div style={{ fontSize: 13, fontWeight: 500, color: getColor(data.vs_5day_pct) }}>
            {formatPercent(data.vs_5day_pct)}
          </div>
        </Col>
      </Row>
    </Card>
  )
}
