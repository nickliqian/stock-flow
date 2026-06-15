import React, { useEffect, useState, useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import { Card, Button, Table, Segmented, Spin, Empty, Typography, Row, Col, Statistic, Tag } from 'antd'
import { ArrowLeftOutlined, ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons'
import { formatAmount, formatPercent, getColorClass, getSign, getColor } from '../utils/format'
import { getSectorTrend } from '../services/api'

const { Text, Title } = Typography

function formatVol(vol) {
  if (vol === null || vol === undefined || isNaN(vol)) return '--'
  const wanShou = vol / 10000
  if (wanShou >= 10000) return `${(wanShou / 10000).toFixed(2)}亿手`
  return `${wanShou.toFixed(2)}万手`
}

/**
 * 板块详情组件
 * 使用 antd 构建
 */
export default function SectorDetail({ sector, members = [], loading, onClose, onSelectStock }) {
  const [trendData, setTrendData] = useState([])
  const [trendLoading, setTrendLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('combined')
  const [trendDays, setTrendDays] = useState(30)

  useEffect(() => {
    if (!sector?.sector_code) return
    let cancelled = false
    setTrendLoading(true)
    getSectorTrend(sector.sector_code, trendDays)
      .then((res) => {
        if (!cancelled) {
          setTrendData(res.data || [])
          setTrendLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTrendData([])
          setTrendLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [sector?.sector_code, trendDays])

  const chartData = useMemo(() => [...trendData].reverse(), [trendData])
  const tableData = useMemo(() => [...trendData].reverse(), [trendData])

  if (!sector) return null

  const dates = chartData.map((d) => d.trade_date)
  const hasFlowData = chartData.some((d) => d.net_inflow != null)
  const hasPriceData = chartData.some((d) => d.pct_change != null)

  // Charts config (same logic as before, but with updated styling)
  const combinedOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.96)',
      borderColor: '#e8e8e8',
      textStyle: { color: '#1f1f1f', fontSize: 12 },
      formatter(params) {
        let html = `<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`
        params.forEach((p) => {
          let display = ''
          if (p.seriesName === '涨跌幅') {
            display = p.value != null ? `${p.value > 0 ? '+' : ''}${p.value.toFixed(2)}%` : '--'
          } else if (p.seriesName === '成交量') {
            display = formatVol(p.value)
          } else if (p.seriesName === '换手率') {
            display = p.value != null ? `${p.value.toFixed(2)}%` : '--'
          } else {
            display = formatAmount(p.value)
          }
          const color = p.seriesName === '涨跌幅'
            ? (p.value > 0 ? '#cf1322' : p.value < 0 ? '#3f8600' : '#8c8c8c')
            : getColor(p.value)
          html += `<div style="display:flex;justify-content:space-between;gap:16px">
            <span>${p.marker} ${p.seriesName}</span>
            <span style="color:${color};font-weight:500">${display}</span>
          </div>`
        })
        return html
      },
    },
    legend: {
      data: ['主力净流入', '涨跌幅', '成交量'],
      bottom: 0,
      textStyle: { fontSize: 11, color: '#595959' },
      itemWidth: 12, itemHeight: 8,
    },
    grid: { left: 10, right: 10, top: 10, bottom: 50, containLabel: true },
    xAxis: {
      type: 'category', data: dates,
      axisLine: { lineStyle: { color: '#e8e8e8' } },
      axisLabel: { fontSize: 10, color: '#8c8c8c', interval: 'auto', rotate: dates.length > 10 ? 30 : 0 },
      axisTick: { show: false },
    },
    yAxis: [
      {
        type: 'value', name: '净流入(万)',
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { fontSize: 10, color: '#8c8c8c', formatter: (v) => formatAmount(v) },
        splitLine: { lineStyle: { color: '#f0f0f0' } },
      },
      {
        type: 'value', name: '涨跌幅(%)',
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { fontSize: 10, color: '#8c8c8c', formatter: (v) => `${v}%` },
        splitLine: { show: false },
      },
    ],
    series: [
      ...(hasFlowData ? [{
        name: '主力净流入', type: 'bar', barMaxWidth: 20, yAxisIndex: 0,
        data: chartData.map((d) => d.net_inflow),
        itemStyle: { color: (params) => getColor(params.value), borderRadius: [2, 2, 0, 0] },
      }] : []),
      ...(hasPriceData ? [{
        name: '涨跌幅', type: 'line', yAxisIndex: 1, smooth: true, symbol: 'circle', symbolSize: 4,
        lineStyle: { width: 2, color: '#fa8c16' }, itemStyle: { color: '#fa8c16' },
        data: chartData.map((d) => d.pct_change),
      }] : []),
      ...(hasPriceData ? [{
        name: '成交量', type: 'bar', barMaxWidth: 16, yAxisIndex: 0,
        data: chartData.map((d) => d.vol),
        itemStyle: { color: 'rgba(22,119,255,0.3)', borderRadius: [2, 2, 0, 0] },
      }] : []),
    ],
  }

  const currentOption = combinedOption

  // Member table columns
  const memberColumns = [
    { title: '代码', key: 'ts_code', render: (_, r) => <Text type="secondary" style={{ fontSize: 12 }}>{r.ts_code || '--'}</Text> },
    { title: '名称', key: 'name', render: (_, r) => <Text strong style={{ fontSize: 13 }}>{r.member_name || r.name || '--'}</Text> },
    {
      title: '涨跌幅', key: 'pct_change', align: 'right',
      render: (_, r) => <Text style={{ color: getColor(r.pct_change) }}>{r.pct_change != null ? formatPercent(r.pct_change) : '--'}</Text>,
    },
    {
      title: '净流入', key: 'net_mf_amount', align: 'right',
      render: (_, r) => <Text style={{ color: getColor(r.net_mf_amount), fontWeight: 500 }}>
        {r.net_mf_amount != null ? `${getSign(r.net_mf_amount)}${formatAmount(r.net_mf_amount)}` : '--'}
      </Text>,
    },
  ]

  // Trend table columns
  const trendColumns = [
    { title: '日期', key: 'trade_date', render: (_, r) => <Text type="secondary" style={{ fontSize: 12 }}>{r.trade_date}</Text> },
    { title: '收盘价', key: 'close', render: (_, r) => <Text style={{ fontSize: 12 }}>{r.close?.toFixed(2) ?? '--'}</Text> },
    {
      title: '涨跌幅', key: 'pct_change', align: 'right',
      render: (_, r) => <Text style={{ color: getColor(r.pct_change) }}>{r.pct_change != null ? formatPercent(r.pct_change) : '--'}</Text>,
    },
    {
      title: '主力净流入', key: 'net_inflow', align: 'right',
      render: (_, r) => <Text style={{ color: getColor(r.net_inflow), fontWeight: 500 }}>
        {r.net_inflow != null ? `${getSign(r.net_inflow)}${formatAmount(r.net_inflow)}` : '--'}
      </Text>,
    },
    { title: '成交量', key: 'vol', render: (_, r) => <Text type="secondary" style={{ fontSize: 12 }}>{formatVol(r.vol)}</Text> },
    { title: '换手率', key: 'turnover_rate', render: (_, r) => <Text type="secondary" style={{ fontSize: 12 }}>{r.turnover_rate != null ? `${r.turnover_rate.toFixed(2)}%` : '--'}</Text> },
  ]

  return (
    <div>
      {/* 返回按钮 */}
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={onClose}
        style={{ padding: '4px 0', marginBottom: 12 }}
      >
        返回板块列表
      </Button>

      {/* 板块概览 */}
      <Card className="chart-card" size="small">
        <Row justify="space-between" align="middle">
          <Col>
            <Title level={5} style={{ margin: 0 }}>
              {sector.sector_name}
              <Text type="secondary" style={{ fontSize: 12, fontWeight: 400, marginLeft: 6 }}>
                {sector.sector_code}
              </Text>
            </Title>
          </Col>
          <Col>
            <Text type="secondary" style={{ fontSize: 12 }}>
              领涨: {sector.lead_stock_name || '--'}
              {sector.lead_chg != null && (
                <Text style={{ color: getColor(sector.lead_chg), marginLeft: 4 }}>
                  {getSign(sector.lead_chg)}{sector.lead_chg.toFixed(2)}%
                </Text>
              )}
            </Text>
          </Col>
        </Row>
        <Row gutter={16} style={{ marginTop: 12 }}>
          <Col span={12}>
            <Statistic
              title="主力净流入"
              value={sector.net_inflow}
              precision={2}
              formatter={(val) => formatAmount(val)}
              valueStyle={{ color: getColor(sector.net_inflow), fontSize: 18 }}
            />
          </Col>
          <Col span={12}>
            <Statistic
              title="大单净流入"
              value={sector.large_net}
              precision={2}
              formatter={(val) => formatAmount(val)}
              valueStyle={{ color: getColor(sector.large_net), fontSize: 18 }}
            />
          </Col>
        </Row>
      </Card>

      {/* 趋势图表 */}
      <Card
        className="chart-card"
        size="small"
        title="📈 多维度趋势"
        extra={
          <Segmented
            size="small"
            value={trendDays}
            onChange={setTrendDays}
            options={[
              { label: '7天', value: 7 },
              { label: '15天', value: 15 },
              { label: '30天', value: 30 },
            ]}
          />
        }
      >
        {trendLoading ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}><Spin size="small" /></div>
        ) : chartData.length === 0 ? (
          <Empty description="暂无趋势数据" />
        ) : (
          <div style={{ height: 300 }}>
            <ReactECharts option={currentOption} style={{ height: '100%' }} />
          </div>
        )}
      </Card>

      {/* 趋势数据表 */}
      {!trendLoading && tableData.length > 0 && (
        <Card className="chart-card" size="small" title="📊 逐日数据">
          <Table
            dataSource={tableData}
            columns={trendColumns}
            rowKey="trade_date"
            pagination={false}
            size="small"
            scroll={{ x: 600 }}
          />
        </Card>
      )}

      {/* 成分股列表 */}
      <Card
        className="chart-card"
        size="small"
        title="成分股"
        extra={<Text type="secondary" style={{ fontSize: 12 }}>共 {members.length} 只</Text>}
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}><Spin size="small" /></div>
        ) : members.length === 0 ? (
          <Empty description="暂无成分股数据" />
        ) : (
          <Table
            dataSource={members}
            columns={memberColumns}
            rowKey="ts_code"
            pagination={false}
            size="small"
            scroll={{ x: 500 }}
            onRow={(record) => onSelectStock ? {
              onClick: () => onSelectStock(record),
              style: { cursor: 'pointer' },
            } : {}}
          />
        )}
      </Card>
    </div>
  )
}
