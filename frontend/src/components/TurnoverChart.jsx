import React from 'react'
import ReactECharts from 'echarts-for-react'
import { formatAmount, getColor } from '../utils/format'

/**
 * 全市场成交额趋势图组件
 * 基于 ECharts 柱状图，展示历史成交额走势
 */
export default function TurnoverChart({ data, compact }) {
  if (!data || !data.values || data.values.length === 0) {
    const placeholderOption = {
      backgroundColor: 'transparent',
      title: {
        text: '暂无成交额数据',
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

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: '#e8e8e8',
      textStyle: { color: '#1f1f1f', fontSize: 12 },
      formatter: function (params) {
        const p = params[0]
        return `<div>
          <div style="font-weight:600;margin-bottom:4px">${p.axisValue}</div>
          <div style="display:flex;justify-content:space-between;gap:16px">
            <span>成交额</span>
            <span style="color:#1677ff;font-weight:500">${formatAmount(p.value)}</span>
          </div>
        </div>`
      },
    },
    grid: {
      left: 10,
      right: 10,
      top: 10,
      bottom: compact ? 8 : 10,
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
    series: [
      {
        name: '成交额',
        type: 'bar',
        barMaxWidth: 32,
        data: data.values,
        itemStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: '#1677ff' },
              { offset: 1, color: '#69b1ff' },
            ],
          },
          borderRadius: [3, 3, 0, 0],
        },
        label: {
          show: data.values.length <= 10,
          position: 'top',
          fontSize: 9,
          color: '#8c8c8c',
          formatter: (p) => formatAmount(p.value),
        },
      },
      {
        name: '趋势',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: '#ff7a45', width: 2 },
        itemStyle: { color: '#ff7a45' },
        data: data.values,
        z: 10,
      },
    ],
  }

  return (
    <div style={{ width: '100%', height: compact ? 240 : 280 }}>
      <ReactECharts option={option} style={{ height: '100%' }} />
    </div>
  )
}
