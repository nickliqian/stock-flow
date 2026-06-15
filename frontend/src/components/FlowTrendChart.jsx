import React from 'react'
import ReactECharts from 'echarts-for-react'
import { formatAmount, getColor } from '../utils/format'

/**
 * 大盘资金流向趋势图组件
 * 基于 ECharts 折线图，展示主力/超大/大/中/小单净流入趋势
 */
export default function FlowTrendChart({ data, compact }) {
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

  const seriesConfig = {
    main_net: { color: '#cf1322', label: '主力净流入' },
    super_large: { color: '#ff4d4f', label: '超大单净流入' },
    large: { color: '#fa8c16', label: '大单净流入' },
    medium: { color: '#1677ff', label: '中单净流入' },
    small: { color: '#52c41a', label: '小单净流入' },
  }

  const series = Object.entries(data.series).map(([key, values]) => {
    const config = seriesConfig[key] || { color: '#8c8c8c', label: key }
    return {
      name: config.label,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { width: 2 },
      areaStyle: { opacity: 0.08 },
      data: values,
      itemStyle: { color: (params) => getColor(params.value) },
    }
  })

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
