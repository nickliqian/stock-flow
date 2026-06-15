import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Card, Table, Segmented, Spin, Empty, Typography, Tag, Row, Col, Statistic, Divider, Alert } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import StockSearch from '../components/StockSearch'
import PriceTrendChart from '../components/PriceTrendChart'
import FlowTrendChart from '../components/FlowTrendChart'
import { getStockDetail, getDragonTiger, getStockDaily, getStockFlowTrend, getStockRanking, getStockBasic } from '../services/api'
import { formatAmount, formatPercent, getColorClass, getColor, getSign } from '../utils/format'

const { Text, Title } = Typography

/**
 * 个股流向页面
 * 使用 Ant Design 构建
 */
export default function StockFlow({ tradeDate, initialStock }) {
  const [selectedStock, setSelectedStock] = useState(null)
  const [stockDetail, setStockDetail] = useState(null)
  const [dragonData, setDragonData] = useState([])
  const [dailyPrices, setDailyPrices] = useState([])
  const [flowTrendData, setFlowTrendData] = useState({ labels: [], series: {} })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stockRanking, setStockRanking] = useState([])
  const [rankingLoading, setRankingLoading] = useState(false)
  const [rankingType, setRankingType] = useState('net_inflow')
  const [stockBasicData, setStockBasicData] = useState(null)

  const fetchStockDataRef = useRef(0)
  const fetchStockData = useCallback(async (tsCode) => {
    const callId = ++fetchStockDataRef.current
    setLoading(true)
    setError(null)
    setStockDetail(null)
    setDragonData([])
    setDailyPrices([])
    setFlowTrendData({ labels: [], series: {} })
    setStockBasicData(null)
    try {
      const [detail, dragon, daily, flowTrend, basic] = await Promise.all([
        getStockDetail(tsCode),
        getDragonTiger(tsCode).catch(() => []),
        getStockDaily(tsCode, 20).catch(() => []),
        getStockFlowTrend(tsCode, 10).catch(() => ({ series: {} })),
        getStockBasic(tsCode).catch(() => null),
      ])
      if (fetchStockDataRef.current !== callId) return
      setStockDetail(detail)
      setDragonData(Array.isArray(dragon) ? dragon : [])
      setDailyPrices(Array.isArray(daily) ? daily : [])
      setFlowTrendData(flowTrend)
      setStockBasicData(basic)
    } catch (err) {
      if (fetchStockDataRef.current !== callId) return
      console.error('加载个股数据失败:', err)
      setError('数据加载失败')
    } finally {
      if (fetchStockDataRef.current === callId) setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    if (initialStock && initialStock.ts_code) {
      setSelectedStock(initialStock)
      fetchStockData(initialStock.ts_code)
    }
    return () => { cancelled = true }
  }, [initialStock, fetchStockData])

  useEffect(() => {
    if (stockDetail) return
    const controller = new AbortController()
    const loadRanking = async () => {
      setRankingLoading(true)
      try {
        const data = await getStockRanking(tradeDate, rankingType, 20, { signal: controller.signal })
        setStockRanking(data.items || data || [])
      } catch (err) {
        if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
        console.error('加载排行数据失败:', err)
        setStockRanking([])
      } finally {
        setRankingLoading(false)
      }
    }
    loadRanking()
    return () => controller.abort()
  }, [rankingType, tradeDate])

  const handleSelectStock = (stock) => {
    setSelectedStock(stock)
    fetchStockData(stock.ts_code)
  }

  // 资金流向柱状图
  const renderFlowChart = () => {
    if (!stockDetail) return null
    const categories = ['小单', '中单', '大单', '超大单', '主力']
    const values = [
      stockDetail.small_net,
      stockDetail.medium_net,
      stockDetail.large_net,
      stockDetail.super_large_net,
      stockDetail.main_net_inflow,
    ]
    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255,255,255,0.96)',
        borderColor: '#e8e8e8',
        textStyle: { color: '#1f1f1f', fontSize: 12 },
        formatter: (params) => {
          const p = params[0]
          const color = getColor(p.value)
          return `<div><b>${p.name}</b><br/><span style="color:${color}">${formatAmount(p.value)}</span></div>`
        },
      },
      grid: { left: 10, right: 10, top: 10, bottom: 5, containLabel: true },
      xAxis: {
        type: 'category',
        data: categories,
        axisLine: { lineStyle: { color: '#e8e8e8' } },
        axisLabel: { fontSize: 11, color: '#595959' },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { fontSize: 10, color: '#8c8c8c', formatter: (v) => formatAmount(v) },
        splitLine: { lineStyle: { color: '#f0f0f0' } },
      },
      series: [{
        type: 'bar',
        data: values.map((v) => ({ value: v, itemStyle: { color: getColor(v) } })),
        barWidth: '40%',
        label: {
          show: true, position: 'top', fontSize: 10,
          formatter: (p) => formatAmount(p.value), color: '#595959',
        },
      }],
    }
    return (
      <Card className="chart-card" title="📊 资金流向分布" size="small">
        <div style={{ height: 200 }}>
          <ReactECharts option={option} style={{ height: '100%' }} />
        </div>
      </Card>
    )
  }

  // 资金流向明细列表
  const renderFlowDetail = () => {
    if (!stockDetail) return null
    const items = [
      { label: '主力净流入', value: stockDetail.main_net_inflow },
      { label: '超大单净流入', value: stockDetail.super_large_net },
      { label: '大单净流入', value: stockDetail.large_net },
      { label: '中单净流入', value: stockDetail.medium_net },
      { label: '小单净流入', value: stockDetail.small_net },
    ]

    return (
      <Card className="chart-card" title="💰 资金流向明细" size="small">
        <Row gutter={[8, 12]}>
          {items.map((item) => (
            <Col xs={8} sm={8} md={4} key={item.label}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: 15, fontWeight: 600, color: getColor(item.value) }}>
                  {getSign(item.value)}{formatAmount(item.value)}
                </div>
              </div>
            </Col>
          ))}
        </Row>
        {stockDetail.large_net_vol !== undefined && (
          <>
            <Divider style={{ margin: '10px 0' }} />
            <Row gutter={16} justify="center">
              <Col>
                <Text type="secondary" style={{ fontSize: 12 }}>大单净量: </Text>
                <Text style={{ fontSize: 13, color: getColor(stockDetail.large_net_vol) }}>
                  {formatAmount(stockDetail.large_net_vol)}
                </Text>
              </Col>
              <Col>
                <Text type="secondary" style={{ fontSize: 12 }}>大单占比: </Text>
                <Text style={{ fontSize: 13, color: getColor(stockDetail.large_pct) }}>
                  {formatPercent(stockDetail.large_pct)}
                </Text>
              </Col>
            </Row>
          </>
        )}
      </Card>
    )
  }

  // 龙虎榜
  const renderDragon = () => {
    if (!dragonData || dragonData.length === 0) return null
    return (
      <Card className="chart-card" title="🐉 龙虎榜" size="small">
        {dragonData.map((item, idx) => (
          <Card key={item.ts_code || idx} size="small" style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Text strong>{item.name}</Text>
                <Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>{item.ts_code}</Text>
              </div>
            </div>
            <Row gutter={16} style={{ marginTop: 8 }}>
              <Col>
                <Text style={{ fontSize: 12, color: getColor(item.pct_change) }}>
                  涨幅 {formatPercent(item.pct_change)}
                </Text>
              </Col>
              <Col>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  换手 {item.turnover_rate != null ? item.turnover_rate.toFixed(2) : '--'}%
                </Text>
              </Col>
              <Col>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  成交 {formatAmount(item.amount)}
                </Text>
              </Col>
            </Row>
            {item.net_buy != null && (
              <div style={{ marginTop: 4 }}>
                <Text style={{ fontSize: 12, color: getColor(item.net_buy) }}>
                  净买入 {formatAmount(item.net_buy)}
                </Text>
              </div>
            )}
            {item.reason && (
              <Tag color="red" style={{ marginTop: 4, fontSize: 11 }}>上榜原因: {item.reason}</Tag>
            )}
          </Card>
        ))}
      </Card>
    )
  }

  // Ranking columns
  const rankingColumns = [
    {
      title: '代码',
      key: 'ts_code',
      dataIndex: 'ts_code',
      width: 100,
    },
    {
      title: '名称',
      key: 'name',
      dataIndex: 'name',
    },
    {
      title: '涨跌幅',
      key: 'pct_change',
      align: 'right',
      render: (_, record) => (
        <Text style={{ color: getColor(record.pct_change), fontWeight: 500 }}>
          {getSign(record.pct_change)}{record.pct_change != null ? record.pct_change.toFixed(2) : '--'}%
        </Text>
      ),
    },
    {
      title: '净流入',
      key: 'net_amount',
      align: 'right',
      render: (_, record) => (
        <Text style={{ color: getColor(record.net_amount), fontWeight: 600 }}>
          {formatAmount(record.net_amount)}
        </Text>
      ),
    },
  ]

  return (
    <div>
      <StockSearch type="stock" onSelect={handleSelectStock} />

      {loading && (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" tip="加载中..." />
        </div>
      )}

      {error && (
        <Alert type="error" message={error} showIcon style={{ marginBottom: 12 }} />
      )}

      {/* 未选择股票 — 显示个股排行 */}
      {!loading && !error && !stockDetail && (
        <Card
          className="chart-card"
          title="📊 个股资金排行"
          size="small"
          extra={
            <Segmented
              className="day-segmented"
              size="small"
              value={rankingType}
              onChange={setRankingType}
              options={[
                { label: '净流入', value: 'net_inflow' },
                { label: '净流出', value: 'net_outflow' },
              ]}
            />
          }
        >
          <Table
            dataSource={stockRanking}
            columns={rankingColumns}
            rowKey="ts_code"
            loading={rankingLoading}
            pagination={false}
            size="small"
            locale={{ emptyText: <Empty description="暂无数据" /> }}
            onRow={(record) => ({
              onClick: () => handleSelectStock({ ts_code: record.ts_code, name: record.name }),
              style: { cursor: 'pointer' },
            })}
          />
        </Card>
      )}

      {/* 股票详情 */}
      {stockDetail && (
        <>
          {/* 个股头部信息 */}
          <Card className="chart-card" size="small">
            <Row align="middle" gutter={16}>
              <Col>
                <Title level={4} style={{ margin: 0 }}>{stockDetail.name}</Title>
                <Text type="secondary" style={{ fontSize: 12 }}>{stockDetail.ts_code}</Text>
              </Col>
              <Col>
                <Statistic
                  value={stockDetail.pct_change || 0}
                  precision={2}
                  suffix="%"
                  valueStyle={{
                    fontSize: 24,
                    fontWeight: 700,
                    color: getColor(stockDetail.pct_change),
                  }}
                  prefix={stockDetail.pct_change > 0 ? <ArrowUpOutlined /> : stockDetail.pct_change < 0 ? <ArrowDownOutlined /> : <MinusOutlined />}
                />
              </Col>
            </Row>
            <Row gutter={16} style={{ marginTop: 8 }}>
              <Col>
                <Text type="secondary" style={{ fontSize: 12 }}>净流入: </Text>
                <Text style={{ fontSize: 13, fontWeight: 500, color: getColor(stockDetail.main_net_inflow) }}>
                  {formatAmount(stockDetail.main_net_inflow)}
                </Text>
              </Col>
              <Col>
                <Text type="secondary" style={{ fontSize: 12 }}>换手率: </Text>
                <Text style={{ fontSize: 13 }}>
                  {stockDetail.turnover_rate != null ? stockDetail.turnover_rate.toFixed(2) : '--'}%
                </Text>
              </Col>
            </Row>
          </Card>

          {/* 基本面指标卡片 */}
          {stockBasicData && (
            <Card className="chart-card" title="📈 基本面指标" size="small">
              <Row gutter={[16, 12]}>
                <Col xs={8} sm={8} md={4}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>PE(TTM)</div>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>
                      {stockBasicData.pe_ttm ? stockBasicData.pe_ttm.toFixed(2) : '--'}
                    </div>
                  </div>
                </Col>
                <Col xs={8} sm={8} md={4}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>PB</div>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>
                      {stockBasicData.pb ? stockBasicData.pb.toFixed(2) : '--'}
                    </div>
                  </div>
                </Col>
                <Col xs={8} sm={8} md={4}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>总市值</div>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>
                      {stockBasicData.total_mv ? (stockBasicData.total_mv / 10000).toFixed(2) + '亿' : '--'}
                    </div>
                  </div>
                </Col>
                <Col xs={8} sm={8} md={4}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>流通市值</div>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>
                      {stockBasicData.circ_mv ? (stockBasicData.circ_mv / 10000).toFixed(2) + '亿' : '--'}
                    </div>
                  </div>
                </Col>
                <Col xs={8} sm={8} md={4}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>股息率</div>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>
                      {stockBasicData.dv_ratio ? stockBasicData.dv_ratio.toFixed(2) + '%' : '--'}
                    </div>
                  </div>
                </Col>
                <Col xs={8} sm={8} md={4}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 12, color: '#8c8c8c', marginBottom: 4 }}>换手率</div>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>
                      {stockBasicData.turnover_rate ? stockBasicData.turnover_rate.toFixed(2) + '%' : '--'}
                    </div>
                  </div>
                </Col>
              </Row>
            </Card>
          )}

          <PriceTrendChart data={dailyPrices} />
          <FlowTrendChart data={flowTrendData} />
          {renderFlowChart()}
          {renderFlowDetail()}
          {renderDragon()}
        </>
      )}
    </div>
  )
}
