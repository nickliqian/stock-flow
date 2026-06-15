import React, { useState } from 'react'
import { Tabs } from 'antd'
import { BulbOutlined, LineChartOutlined, DashboardOutlined, HeartOutlined } from '@ant-design/icons'
import SmartMoney from './SmartMoney'
import FlowIntelligence from './FlowIntelligence'
import SignalMatrix from './SignalMatrix'
import StockHealth from './StockHealth'

/**
 * 智能分析页面
 * 包含 4 个子 Tab：健康度 / 聪明钱 / 资金背离 / 信号矩阵
 */
export default function SmartAnalysis({ tradeDate, onSelectStock }) {
  const [activeTab, setActiveTab] = useState('health')

  return (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      type="card"
      items={[
        {
          key: 'health',
          label: <span><HeartOutlined /> 健康度</span>,
          children: <StockHealth tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
        {
          key: 'smartmoney',
          label: <span><BulbOutlined /> 聪明钱</span>,
          children: <SmartMoney tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
        {
          key: 'flow-intelligence',
          label: <span><LineChartOutlined /> 资金背离</span>,
          children: <FlowIntelligence tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
        {
          key: 'signal-matrix',
          label: <span><DashboardOutlined /> 信号矩阵</span>,
          children: <SignalMatrix tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
      ]}
    />
  )
}
