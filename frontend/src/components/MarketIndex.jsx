import React, { useState, useMemo } from 'react'
import { Card, Row, Col, Statistic, Spin, Typography, Space, Drawer, Descriptions } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined, StockOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { formatAmount, getColor } from '../utils/format'
import api from '../services/api'

const { Text } = Typography

// 指数简介信息
const INDEX_INFO = {
  '000001.SH': {
    name: '上证指数',
    desc: '上海证券综合指数，简称"上证指数"或"综指"，其样本股是在上海证券交易所全部上市股票，包括了A股和B股，反映了上海证券交易所上市股票价格的变动情况，自1991年7月15日起正式发布。',
  },
  '399001.SZ': {
    name: '深证成指',
    desc: '深证成份指数，简称"深证成指"，是深圳证券交易所编制的主要成份股指数，以深交所上市的500家有代表性的股票为样本，以流通股本为权数计算得出的加权综合股价指数。',
  },
  '399006.SZ': {
    name: '创业板指',
    desc: '创业板指数由创业板中市值大、流动性好的100只股票组成，反映创业板市场的运行情况。创业板于2009年10月30日正式开市，定位于服务成长型创新创业企业。',
  },
  '000688.SH': {
    name: '科创50',
    desc: '上证科创板50成份指数，由科创板中市值大、流动性好的50只证券组成，反映最具市场代表性的一批科创企业的整体表现。科创板于2019年7月22日正式开市。',
  },
}

/**
 * 大盘指数卡片组件
 * 显示上证指数、深证成指、创业板指、科创50的实时行情
 * 点击卡片弹出 Drawer 显示详情 + 30日K线
 */
export default function MarketIndex({ data, loading }) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(null)
  const [klineData, setKlineData] = useState(null)
  const [klineLoading, setKlineLoading] = useState(false)

  // K线图配置 — hooks 必须在所有条件 return 之前
  const klineOption = useMemo(() => {
    if (!klineData || klineData.length === 0) return null
    const dates = klineData.map(d => d.trade_date)
    const closes = klineData.map(d => d.close)
    const vols = klineData.map(d => d.vol)

    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255,255,255,0.96)',
        borderColor: '#e8e8e8',
        textStyle: { color: '#1f1f1f', fontSize: 12 },
        formatter: (params) => {
          const date = params[0]?.axisValue
          const close = params[0]?.value
          const vol = params[1]?.value
          return `<div><b>${date}</b></div>
                  <div>收盘: ${close?.toFixed(2)}</div>
                  <div>成交量: ${vol ? (vol / 10000).toFixed(0) + '万手' : '--'}</div>`
        },
      },
      grid: { left: 60, right: 20, top: 20, bottom: 60 },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { fontSize: 10, color: '#8c8c8c', rotate: 30 },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#e8e8e8' } },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { fontSize: 10, color: '#8c8c8c' },
        splitLine: { lineStyle: { color: '#f0f0f0' } },
      },
      dataZoom: [{ type: 'inside', start: 0, end: 100 }],
      series: [
        {
          name: '收盘价',
          type: 'line',
          data: closes,
          smooth: true,
          symbol: 'circle',
          symbolSize: 4,
          lineStyle: { width: 2, color: '#1677ff' },
          areaStyle: { opacity: 0.08, color: '#1677ff' },
          itemStyle: { color: '#1677ff' },
        },
      ],
    }
  }, [klineData])

  // === hooks 结束，下面可以有条件 return ===

  if (loading && !data) {
    return (
      <Card className="stat-card" size="small" style={{ marginBottom: 16 }}>
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <Spin size="small" tip="加载指数数据..." />
        </div>
      </Card>
    )
  }

  if (!data?.indices) {
    return null
  }

  const { indices } = data

  // 格式化成交量（手 -> 亿手）
  const formatVolume = (vol) => {
    if (!vol) return '0'
    const yi = vol / 100000000
    if (yi >= 1) return `${yi.toFixed(2)}亿手`
    const wan = vol / 10000
    return `${wan.toFixed(2)}万手`
  }

  // 格式化涨跌额
  const formatChange = (change) => {
    if (!change) return '0.00'
    const sign = change > 0 ? '+' : ''
    return `${sign}${change.toFixed(2)}`
  }

  // 格式化涨跌幅
  const formatPctChg = (pctChg) => {
    if (!pctChg) return '0.00%'
    const sign = pctChg > 0 ? '+' : ''
    return `${sign}${pctChg.toFixed(2)}%`
  }

  // 获取涨跌图标
  const getIcon = (value) => {
    if (value > 0) return <ArrowUpOutlined />
    if (value < 0) return <ArrowDownOutlined />
    return <MinusOutlined />
  }

  // 指数显示顺序（2x2 网格）
  const indexOrder = ['000001.SH', '399001.SZ', '399006.SZ', '000688.SH']

  // 点击卡片打开 Drawer
  const handleCardClick = async (tsCode) => {
    setSelectedIndex(tsCode)
    setDrawerOpen(true)
    setKlineLoading(true)
    setKlineData(null)
    try {
      const json = await api.get('/market/index-kline', { params: { ts_code: tsCode, days: 30 } })
      setKlineData(json.data || [])
    } catch (err) {
      console.error('Failed to fetch index kline:', err)
    } finally {
      setKlineLoading(false)
    }
  }

  // 当前选中指数的信息
  const selectedInfo = selectedIndex ? INDEX_INFO[selectedIndex] : null
  const selectedData = selectedIndex ? indices[selectedIndex] : null

  return (
    <>
      <Card
        className="stat-card"
        size="small"
        title={
          <Space>
            <StockOutlined />
            <span>大盘指数</span>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <Row gutter={[12, 12]}>
          {indexOrder.map((tsCode) => {
            const indexData = indices[tsCode]
            if (!indexData) return null

            const color = getColor(indexData.pct_chg)
            const changeColor = getColor(indexData.change)

            return (
              <Col xs={24} sm={12} key={tsCode}>
                <div
                  onClick={() => handleCardClick(tsCode)}
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    background: '#fafafa',
                    border: '1px solid #f0f0f0',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#1677ff'
                    e.currentTarget.style.boxShadow = '0 2px 8px rgba(22,119,255,0.15)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#f0f0f0'
                    e.currentTarget.style.boxShadow = 'none'
                  }}
                >
                  <div style={{
                    fontSize: 14,
                    fontWeight: 600,
                    marginBottom: 8,
                    color: '#262626',
                  }}>
                    {indexData.name}
                  </div>
                  <div style={{
                    fontSize: 24,
                    fontWeight: 700,
                    color: color,
                    marginBottom: 4,
                  }}>
                    {indexData.close?.toFixed(2) || '--'}
                  </div>
                  <div style={{
                    fontSize: 13,
                    color: changeColor,
                    marginBottom: 8,
                  }}>
                    <span style={{ marginRight: 8 }}>
                      {getIcon(indexData.change)} {formatChange(indexData.change)}
                    </span>
                    <span style={{ fontWeight: 600 }}>
                      {formatPctChg(indexData.pct_chg)}
                    </span>
                  </div>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: 12,
                    color: '#8c8c8c',
                  }}>
                    <span>成交量: {formatVolume(indexData.vol)}</span>
                    <span>成交额: {formatAmount(indexData.amount)}</span>
                  </div>
                </div>
              </Col>
            )
          })}
        </Row>
      </Card>

      {/* 指数详情 Drawer */}
      <Drawer
        title={selectedInfo?.name || selectedIndex}
        placement="right"
        width={520}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedIndex(null)
          setKlineData(null)
        }}
      >
        {selectedData && (
          <>
            {/* 最新价 + 涨跌幅 */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 32, fontWeight: 700, color: getColor(selectedData.pct_chg) }}>
                {selectedData.close?.toFixed(2) || '--'}
              </div>
              <div style={{ fontSize: 16, color: getColor(selectedData.change), marginTop: 4 }}>
                <span style={{ marginRight: 12 }}>
                  {getIcon(selectedData.change)} {formatChange(selectedData.change)}
                </span>
                <span style={{ fontWeight: 600 }}>
                  {formatPctChg(selectedData.pct_chg)}
                </span>
              </div>
            </div>

            {/* 30日K线趋势图 */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>📈 近30日走势</div>
              {klineLoading ? (
                <div style={{ textAlign: 'center', padding: '40px 0' }}><Spin size="small" /></div>
              ) : klineOption ? (
                <div style={{ height: 280 }}>
                  <ReactECharts option={klineOption} style={{ height: '100%' }} />
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '40px 0', color: '#bfbfbf' }}>暂无K线数据</div>
              )}
            </div>

            {/* 指数简介 */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>📋 指数简介</div>
              <div style={{
                padding: '12px',
                background: '#f5f5f5',
                borderRadius: '6px',
                fontSize: 13,
                lineHeight: 1.8,
                color: '#595959',
              }}>
                {selectedInfo?.desc || '暂无简介'}
              </div>
            </div>

            {/* 详细数据 */}
            <Descriptions size="small" bordered column={2}>
              <Descriptions.Item label="最新价">{selectedData.close?.toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="涨跌幅">{formatPctChg(selectedData.pct_chg)}</Descriptions.Item>
              <Descriptions.Item label="成交量">{formatVolume(selectedData.vol)}</Descriptions.Item>
              <Descriptions.Item label="成交额">{formatAmount(selectedData.amount)}</Descriptions.Item>
            </Descriptions>
          </>
        )}
      </Drawer>
    </>
  )
}
