import React from 'react'
import ReactECharts from 'echarts-for-react'
import { formatAmount, getColor } from '../utils/format'

/**
 * 北向资金趋势图组件
 * 基于 ECharts 折线图，展示北向合计/沪股通/深股通趋势
 */
export default function TrendChart({ data, compact }) {
  if (!data || !data.series || Object.keys(data.series).length === 0) {
    const placeholderOption = {
      backgroundColor: 'transparent',
      title: {
        text: '暂无趋势数据',
        left: 'center',
        top: 'center',
        textStyle: { color: '#bfbfbf', fontSize: 14, fontWeight: 'normal' },
      },
    }
    return (
      <div style={{ width: '100%', height: compact ? 240 : 280 }}>
        <ReactECharts option={placeholderOption} style={{ height: '100%' }} />
      </div>
    )
  }

  const seriesColors = {
    north_money: '#cf1322',
    hgt: '#1677ff',
    sgt: '#3f8600',
  }

  const seriesLabels = {
    north_money: '北向合计',
    hgt: '沪股通',
    sgt: '深股通',
  }

  const series = Object.entries(data.series).map(([key, values]) => ({
    name: seriesLabels[key] || key,
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 4,
    lineStyle: { width: 2 },
    areaStyle: { opacity: 0.08 },
    data: values,
    itemStyle: { color: seriesColors[key] || '#8c8c8c' },
  }))

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: '#e8e8e8',
      textStyle: { color: '#1f1f1f', fontSize: 12 },
      formatter: function (params) {
        let html = `<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`
        params.forEach((p) => {
          const color = getColor(p.value)
          html += `<div style="display:flex;justify-content:space-between;gap:16px">
            <span>${p.marker} ${p.seriesName}</span>
            <span style="color:${color};font-weight:500">${formatAmount(p.value)}</span>
          </div>`
        })
        return html
      },
    },
    legend: {
      data: series.map((s) => s.name),
      bottom: 0,
      textStyle: { fontSize: 11, color: '#595959' },
      itemWidth: 12,
      itemHeight: 8,
    },
    grid: {
      left: 10,
      right: 10,
      top: 10,
      bottom: compact ? 30 : 40,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: data.labels || [],
      axisLine: { lineStyle: { color: '#e8e8e8' } },
      axisLabel: { fontSize: 10, color: '#8c8c8c', interval: 'auto' },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        fontSize: 10,
        color: '#8c8c8c',
        formatter: (v) => formatAmount(v),
      },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
    },
    series,
  }

  return (
    <div style={{ width: '100%', height: compact ? 240 : 280 }}>
      <ReactECharts option={option} style={{ height: '100%' }} />
    </div>
  )
}
