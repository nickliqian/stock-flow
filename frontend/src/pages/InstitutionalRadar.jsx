import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, Tag, Button, Tabs, Select, Space, Statistic, Tooltip, Empty } from 'antd';
import { BankOutlined, ReloadOutlined } from '@ant-design/icons';
import { apiCall } from '../services/api';

const API_BASE = '/api/strategies';

export default function InstitutionalRadar() {
  const [loading, setLoading] = useState(false);
  const [instFlow, setInstFlow] = useState(null);
  const [crowding, setCrowding] = useState(null);
  const [activeTab, setActiveTab] = useState('inst');
  const [minStrategies, setMinStrategies] = useState(3);
  const [selectedStock, setSelectedStock] = useState(null);
  const [conviction, setConviction] = useState(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [instData, crowdData] = await Promise.all([
        apiCall(`${API_BASE}/institutional/flow`),
        apiCall(`${API_BASE}/institutional/crowding?min_strategies=${minStrategies}`),
      ]);
      setInstFlow(instData?.data || instData);
      setCrowding(crowdData?.data || crowdData);
    } catch (e) {
      console.error('Failed to load radar data:', e);
    }
    setLoading(false);
  };

  const loadConviction = async (tsCode) => {
    setSelectedStock(tsCode);
    try {
      const data = await apiCall(`${API_BASE}/institutional/conviction/${tsCode}`);
      setConviction(data);
    } catch (e) {
      console.error('Failed to load conviction:', e);
    }
  };

  useEffect(() => { loadData(); }, [minStrategies]);

  const instColumns = [
    { title: '股票代码', dataIndex: 'ts_code', key: 'ts_code', width: 120 },
    { title: '信号', dataIndex: 'signal', key: 'signal',
      render: v => ({
        bullish: <Tag color='red'>看多</Tag>,
        bearish: <Tag color='green'>看空</Tag>,
        neutral: <Tag>中性</Tag>,
      }[v] || v)
    },
    { title: '机构净买入(万)', dataIndex: 'net_buy', key: 'net_buy',
      render: v => <span style={{ color: v > 0 ? '#ff4d4f' : '#52c41a', fontWeight: 'bold' }}>{v?.toLocaleString()}</span>,
      sorter: (a, b) => a.net_buy - b.net_buy, defaultSortOrder: 'descend'
    },
    { title: '买入(万)', dataIndex: 'total_buy', key: 'total_buy', render: v => v?.toLocaleString() },
    { title: '卖出(万)', dataIndex: 'total_sell', key: 'total_sell', render: v => v?.toLocaleString() },
    { title: '机构数', dataIndex: 'inst_count', key: 'inst_count' },
    { title: '上榜原因', dataIndex: 'reasons', key: 'reasons', ellipsis: true },
    { title: '操作', key: 'action',
      render: (_, r) => <Button size='small' type='link' onClick={() => loadConviction(r.ts_code)}>置信度</Button>
    },
  ];

  const crowdColumns = [
    { title: '股票代码', dataIndex: 'ts_code', key: 'ts_code', width: 120 },
    { title: '策略数', dataIndex: 'strategy_count', key: 'count',
      sorter: (a, b) => a.strategy_count - b.strategy_count, defaultSortOrder: 'descend'
    },
    { title: '拥挤风险', dataIndex: 'crowding_risk', key: 'risk',
      render: v => ({
        high: <Tag color='red'>高风险</Tag>,
        medium: <Tag color='orange'>中风险</Tag>,
        low: <Tag color='blue'>低风险</Tag>,
      }[v] || v)
    },
    { title: '总分', dataIndex: 'total_score', key: 'total_score',
      sorter: (a, b) => a.total_score - b.total_score
    },
    { title: '平均分', dataIndex: 'avg_score', key: 'avg_score' },
    { title: '分类覆盖', dataIndex: 'categories', key: 'cats',
      render: v => v?.map(c => <Tag key={c}>{c}</Tag>)
    },
    { title: '策略详情', dataIndex: 'strategies', key: 'strats',
      render: v => v?.map(s => (
        <Tooltip key={s.name} title={s.description}>
          <Tag color={s.category === 'value' ? 'blue' : s.category === 'momentum' ? 'orange' : s.category === 'flow' ? 'purple' : 'green'}>
            {s.icon} {s.name.split('_').slice(0,2).join('_')}
          </Tag>
        </Tooltip>
      ))
    },
    { title: '操作', key: 'action',
      render: (_, r) => <Button size='small' type='link' onClick={() => loadConviction(r.ts_code)}>置信度</Button>
    },
  ];

  const renderConviction = () => {
    if (!conviction) return <Empty description='点击股票查看置信度评分' />;
    const { components, conviction_score, grade, ts_code } = conviction;
    return (
      <Card title={`🎯 ${ts_code} 综合置信度`} size='small' style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title='综合置信度' value={conviction_score} suffix='/100'
              valueStyle={{ color: conviction_score >= 70 ? '#3f8600' : conviction_score >= 50 ? '#1890ff' : '#cf1322' }} />
            <Tag color={conviction_score >= 70 ? 'green' : conviction_score >= 50 ? 'blue' : 'red'} style={{ marginTop: 8 }}>{grade}</Tag>
          </Col>
          <Col span={6}>
            <Statistic title='策略信号' value={components.strategy.score} suffix='/100'
              valueStyle={{ fontSize: 20 }} />
            <div style={{ fontSize: 12, color: '#999' }}>命中 {components.strategy.hits} 个策略</div>
          </Col>
          <Col span={6}>
            <Statistic title='机构动向' value={components.institutional.score} suffix='/100'
              valueStyle={{ fontSize: 20 }} />
            <div style={{ fontSize: 12, color: '#999' }}>{components.institutional.detail ? '有龙虎榜数据' : '无龙虎榜数据'}</div>
          </Col>
          <Col span={6}>
            <Statistic title='拥挤度调整' value={components.crowding.score} suffix='/100'
              valueStyle={{ fontSize: 20 }} />
            <div style={{ fontSize: 12, color: '#999' }}>{components.crowding.detail ? `${components.crowding.detail.strategy_count} 策略命中` : '未达门槛'}</div>
          </Col>
        </Row>
        {components.strategy.details?.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <strong>命中策略：</strong>
            {components.strategy.details.map((s, i) => (
              <Tag key={i} color={s.category === 'value' ? 'blue' : s.category === 'momentum' ? 'orange' : 'purple'} style={{ marginTop: 4 }}>
                {s.icon} {s.name} ({s.score.toFixed(0)}分)
              </Tag>
            ))}
          </div>
        )}
      </Card>
    );
  };

  return (
    <div style={{ padding: 16 }}>
      <Card title='🏛️ 机构动向雷达 + 策略拥挤度' extra={
        <Space>
          <span>最低策略数:
            <Select value={minStrategies} onChange={setMinStrategies} size='small' style={{ width: 80, marginLeft: 8 }}>
              {[2,3,4,5,6].map(n => <Select.Option key={n} value={n}>{n}</Select.Option>)}
            </Select>
          </span>
          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>刷新</Button>
        </Space>
      }>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          { key: 'inst', label: '🏦 机构动向', children: (
            <>
              {instFlow?.summary && (
                <Row gutter={16} style={{ marginBottom: 16 }}>
                  <Col span={6}><Card size='small'><Statistic title='上榜股票' value={instFlow.summary.total_stocks} /></Card></Col>
                  <Col span={6}><Card size='small'><Statistic title='机构交易数' value={instFlow.summary.total_inst_trades} /></Card></Col>
                  <Col span={6}><Card size='small'><Statistic title='看多' value={instFlow.summary.bullish_count} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
                  <Col span={6}><Card size='small'><Statistic title='看空' value={instFlow.summary.bearish_count} valueStyle={{ color: '#52c41a' }} /></Card></Col>
                </Row>
              )}
              <Table dataSource={instFlow?.stocks || []} columns={instColumns} rowKey='ts_code' size='small'
                pagination={{ pageSize: 20 }} loading={loading} />
            </>
          )},
          { key: 'crowd', label: '⚠️ 策略拥挤度', children: (
            <>
              {crowding?.summary && (
                <Row gutter={16} style={{ marginBottom: 16 }}>
                  <Col span={6}><Card size='small'><Statistic title='分析股票数' value={crowding.summary.total_analyzed} /></Card></Col>
                  <Col span={6}><Card size='small'><Statistic title='拥挤股票' value={crowding.summary.crowded_count} valueStyle={{ color: '#faad14' }} /></Card></Col>
                  <Col span={6}><Card size='small'><Statistic title='高风险' value={crowding.summary.high_risk} valueStyle={{ color: '#ff4d4f' }} /></Card></Col>
                  <Col span={6}><Card size='small'><Statistic title='中风险' value={crowding.summary.medium_risk} valueStyle={{ color: '#faad14' }} /></Card></Col>
                </Row>
              )}
              <Table dataSource={crowding?.crowded_stocks || []} columns={crowdColumns} rowKey='ts_code' size='small'
                pagination={{ pageSize: 20 }} loading={loading} scroll={{ x: 1200 }} />
            </>
          )},
          { key: 'conviction', label: '🎯 置信度评分', children: (
            <div>
              {renderConviction()}
              <div style={{ marginTop: 16, padding: 16, background: '#1a1a2e', borderRadius: 8 }}>
                <h4 style={{ color: '#e0e0e0' }}>💡 置信度评分说明</h4>
                <p style={{ color: '#999', margin: '8px 0' }}>
                  <strong>策略信号 (40%)</strong>：评估该股票被多少个策略选中及策略得分。<br/>
                  <strong>机构动向 (30%)</strong>：龙虎榜机构席位净买入数据。机构净买入越多，分数越高。<br/>
                  <strong>拥挤度调整 (30%)</strong>：被3-4个策略选中为最佳(70分)，太少(40分)或太多(40-60分)都会降低分数。<br/>
                  <strong>等级</strong>：A+(80+) / A(70+) / B+(60+) / B(50+) / C+(40+) / C(&lt;40)
                </p>
              </div>
            </div>
          )},
        ]} />
      </Card>
    </div>
  );
}
