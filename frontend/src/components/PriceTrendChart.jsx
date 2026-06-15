import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Card } from 'antd'

/**
 * K线图组件 - 显示个股日线行情数据
 * 颜色：红涨绿跌（中国股市惯例）
 */
export default function PriceTrendChart({ data }) {
  const option = useMemo(() => {
    if (!data || data.length === 0) return null

    const dates = data.map(d => d.trade_date)
    const ohlc = data.map(d => [d.open, d.close, d.low, d.high])
    const volumes = data.map(d => d.vol)

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross', crossStyle: { color: '#8c8c8c' } },
        backgroundColor: 'rgba(255,255,255,0.96)',
        borderColor: '#e8e8e8',
        textStyle: { color: '#1f1f1f', fontSize: 12 },
        formatter: (params) => {
          const kLine = params.find(p => p.seriesName === 'K线')
          if (!kLine) return ''
          const data = kLine.data
          const date = kLine.axisValue
          return `
            <div><b>${date}</b></div>
            <div>开盘: ${data[0].toFixed(2)}</div>
            <div>收盘: ${data[1].toFixed(2)}</div>
            <div>最低: ${data[2].toFixed(2)}</div>
            <div>最高: ${data[3].toFixed(2)}</div>
          `
        },
      },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      grid: [
        { left: 60, right: 20, top: 10, height: '60%' },
        { left: 60, right: 20, top: '75%', height: '18%' },
      ],
      xAxis: [
        {
          type: 'category', data: dates,
          axisLine: { lineStyle: { color: '#e8e8e8' } },
          axisLabel: { fontSize: 10, color: '#8c8c8c' },
          axisTick: { show: false },
        },
        {
          type: 'category', gridIndex: 1, data: dates,
          axisLabel: { show: false },
          axisTick: { show: false },
          axisLine: { lineStyle: { color: '#e8e8e8' } },
        },
      ],
      yAxis: [
        {
          scale: true,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { fontSize: 10, color: '#8c8c8c' },
          splitLine: { lineStyle: { color: '#f0f0f0' } },
        },
        {
          scale: true, gridIndex: 1,
          axisLabel: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
        },
      ],
      dataZoom: [{ type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 }],
      series: [
        {
          name: 'K线', type: 'candlestick', data: ohlc,
          itemStyle: {
            color: '#ef232a',
            color0: '#14b143',
            borderColor: '#ef232a',
            borderColor0: '#14b143',
          },
        },
        {
          name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
          data: volumes.map((v, i) => ({
            value: v,
            itemStyle: {
              color: ohlc[i][1] >= ohlc[i][0] ? 'rgba(239,35,42,0.5)' : 'rgba(20,177,67,0.5)',
            },
          })),
          barWidth: '60%',
        },
      ],
    }
  }, [data])

  if (!option) return null

  return (
    <Card className="chart-card" title="📈 价格走势（K线图）" size="small">
      <div style={{ height: 300 }}>
        <ReactECharts option={option} style={{ height: '100%' }} />
      </div>
    </Card>
  )
}
