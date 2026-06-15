import React from 'react'
import { Tag } from 'antd'

/**
 * 金额格式化工具
 * 中国A股：万(10^4) / 亿(10^8)
 * 颜色：红涨绿跌（中国股市惯例）
 */

/**
 * 格式化金额，自动选择万/亿单位
 * 注意：TuShare 数据单位为万元，此函数按万元处理
 * @param {number} value - 金额（单位：万元）
 * @param {number} decimals - 小数位数，默认2
 * @returns {string} 格式化后的字符串
 */
export function formatAmount(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) return '--'
  const absVal = Math.abs(value)
  const sign = value < 0 ? '-' : ''

  // 数据已经是万元，>= 10000万 显示为亿
  if (absVal >= 10000) {
    return `${sign}${(absVal / 10000).toFixed(decimals)}亿`
  }
  return `${sign}${absVal.toFixed(decimals)}万`
}

/**
 * 格式化百分比
 * @param {number} value - 百分比值（如 5.23 表示 5.23%）
 * @param {number} decimals - 小数位数，默认2
 * @returns {string}
 */
export function formatPercent(value, decimals = 2) {
  if (value === null || value === undefined || isNaN(value)) return '--'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

/**
 * 根据值返回颜色类名（红涨绿跌）
 * @param {number} value
 * @returns {string} CSS 类名
 */
export function getColorClass(value) {
  if (value === null || value === undefined || isNaN(value)) return 'text-gray'
  return value > 0 ? 'text-red' : value < 0 ? 'text-green' : 'text-gray'
}

/**
 * 根据值返回颜色值（红涨绿跌）
 * @param {number} value
 * @returns {string} 颜色 hex
 */
export function getColor(value) {
  if (value === null || value === undefined || isNaN(value)) return '#999999'
  return value > 0 ? '#e74c3c' : value < 0 ? '#27ae60' : '#999999'
}

/**
 * 获取涨跌符号
 * @param {number} value
 * @returns {string}
 */
export function getSign(value) {
  if (value === null || value === undefined || isNaN(value)) return ''
  return value > 0 ? '+' : ''
}

/**
 * debounce 函数
 * @param {Function} fn
 * @param {number} delay - 毫秒
 * @returns {Function}
 */
export function debounce(fn, delay = 300) {
  let timer = null
  const debounced = function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
  debounced.cancel = function () {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }
  return debounced
}

/**
 * 格式化日期为 YYYYMMDD
 * @param {Date} date
 * @returns {string}
 */
export function formatDate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}${m}${d}`
}

/**
 * 获取今天的日期字符串 YYYYMMDD
 */
export function getToday() {
  return formatDate(new Date())
}

// formatTurnover removed — use formatAmount directly

/**
 * 根据评分返回颜色值
 * @param {number} score
 * @returns {string} 颜色 hex
 */
export function scoreColor(score) {
  if (score >= 75) return '#52c41a'
  if (score >= 50) return '#faad14'
  return '#999'
}

/**
 * 根据评分返回带颜色的 Tag 组件
 * @param {number} score
 * @returns {React.Element}
 */
export function scoreTag(score) {
  if (typeof score !== 'number' || isNaN(score)) {
    return <Tag color="default">--</Tag>
  }
  let color = 'default'
  let text = '低'
  if (score >= 75) { color = 'success'; text = '高' }
  else if (score >= 50) { color = 'warning'; text = '中' }
  return <Tag color={color}>{text} {score.toFixed(1)}</Tag>
}
