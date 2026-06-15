import React from 'react'
import { Row, Col, Statistic, Empty, Typography } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined } from '@ant-design/icons'

const { Text } = Typography

/**
 * 涨跌分布图（Market Breadth）
 * 用分段柱状图展示全市场涨跌分布
 */
export default function BreadthChart({ data }) {
  if (!data || !data.distribution || data.distribution.length === 0) {
    return <Empty description="暂无数据" style={{ padding: '24px 0' }} />
  }

  const { distribution, up_count, down_count, flat_count, limit_up, limit_down, total_stocks, avg_pct_change } = data
  const maxCount = Math.max(...distribution.map(d => d.count), 1)

  // 区间颜色：跌绿、涨红、平灰（使用高对比度颜色）
  const getColor = (range) => {
    if (range.startsWith('-') || range === '<-9%') return '#3f8600'
    if (range.startsWith('>') || range === '>9%') return '#cf1322'
    if (range.includes('~')) {
      const sign = range.charAt(0)
      if (sign === '-') return '#52c41a'
      if (sign === '0') return '#faad14'
      return '#ff4d4f'
    }
    return '#8c8c8c'
  }

  // 今日多空比
  const bullBearRatio = down_count > 0 ? (up_count / down_count).toFixed(2) : '∞'

  return (
    <div>
      {/* 概览统计 */}
      <Row gutter={[16, 12]} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Statistic
            title="上涨"
            value={up_count}
            valueStyle={{ color: '#cf1322', fontSize: 20 }}
            prefix={<ArrowUpOutlined />}
            suffix={<Text type="secondary" style={{ fontSize: 12 }}>/ {total_stocks}</Text>}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="下跌"
            value={down_count}
            valueStyle={{ color: '#3f8600', fontSize: 20 }}
            prefix={<ArrowDownOutlined />}
            suffix={<Text type="secondary" style={{ fontSize: 12 }}>/ {total_stocks}</Text>}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="涨停"
            value={limit_up}
            valueStyle={{ color: '#cf1322', fontSize: 20 }}
          />
          <Text type="secondary" style={{ fontSize: 11 }}>跌停: {limit_down}</Text>
        </Col>
        <Col span={6}>
          <Statistic
            title="平均涨幅"
            value={avg_pct_change}
            precision={2}
            suffix="%"
            valueStyle={{ color: avg_pct_change > 0 ? '#cf1322' : avg_pct_change < 0 ? '#3f8600' : '#8c8c8c', fontSize: 20 }}
          />
          <Text type="secondary" style={{ fontSize: 11 }}>多空比: {bullBearRatio}</Text>
        </Col>
      </Row>

      {/* 分段柱状图 */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 160, padding: '0 4px' }}>
        {distribution.map((item) => {
          const maxBarHeight = 110
          const barHeight = maxCount > 0 ? (item.count / maxCount) * maxBarHeight : 0
          const color = getColor(item.range)
          return (
            <div key={item.range} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <Text style={{ fontSize: 10, color: '#8c8c8c', marginBottom: 2 }}>{item.count}</Text>
              <div
                style={{
                  width: '100%',
                  height: Math.max(barHeight, 3),
                  backgroundColor: color,
                  borderRadius: '3px 3px 0 0',
                  transition: 'height 0.3s ease',
                  minWidth: 20,
                }}
              />
              <Text style={{ fontSize: 10, marginTop: 4, whiteSpace: 'nowrap' }}>{item.range}</Text>
            </div>
          )
        })}
      </div>

      {/* 涨跌平分隔线 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, padding: '0 4px' }}>
        <Text style={{ fontSize: 11, color: '#3f8600' }}>◀ 跌 ({down_count})</Text>
        <Text style={{ fontSize: 11, color: '#faad14' }}>平 ({flat_count})</Text>
        <Text style={{ fontSize: 11, color: '#cf1322' }}>涨 ({up_count}) ▶</Text>
      </div>
    </div>
  )
}
