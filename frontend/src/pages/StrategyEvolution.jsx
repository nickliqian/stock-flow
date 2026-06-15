import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Table, Tag, Button, Spin, Tabs, Statistic, Space, Slider, Empty } from 'antd';
import { ExperimentOutlined, ReloadOutlined } from '@ant-design/icons';
import api from '../services/api';

export default function StrategyEvolution() {
  const [loadingReport, setLoadingReport] = useState(false);
  const [loadingDecay, setLoadingDecay] = useState(false);
  const [loadingOptimize, setLoadingOptimize] = useState(false);
  const [report, setReport] = useState(null);
  const [optimizeResult, setOptimizeResult] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [decayData, setDecayData] = useState([]);
  const [holdDays, setHoldDays] = useState(5);
  const [topN, setTopN] = useState(30);

  // 兼容旧代码中引用 loading 的地方（如 decay table loading、optimize button loading）
  const loading = loadingReport || loadingDecay || loadingOptimize;

  const loadReport = async (signal) => {
    setLoadingReport(true);
    try {
      const res = await api.get('/strategies/evolution/report', { signal });
      setReport(res?.data || res);
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return;
      console.error('Failed to load evolution report:', e);
    }
    setLoadingReport(false);
  };

  const loadDecay = async (signal) => {
    setLoadingDecay(true);
    try {
      const res = await api.get('/strategies/evolution/decay', { params: { lookback_days: 20 }, signal });
      setDecayData(res?.data || res || []);
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return;
      console.error('Failed to load decay data:', e);
    }
    setLoadingDecay(false);
  };

  const optimizeStrategy = async (name, signal) => {
    setLoadingOptimize(true);
    setSelectedStrategy(name);
    try {
      const res = await api.get(`/strategies/evolution/optimize/${name}`, {
        params: { hold_days: holdDays, top_n: topN }, signal
      });
      setOptimizeResult(res?.data || res);
      setActiveTab('optimize');
    } catch (e) {
      console.error('Failed to optimize strategy:', e);
    }
    setLoadingOptimize(false);
  };

  useEffect(() => {
    const controller = new AbortController();
    loadReport(controller.signal);
    loadDecay(controller.signal);
    return () => controller.abort();
  }, []);

  const decayColumns = [
    { title: '策略', dataIndex: 'name', key: 'name', render: (v, r) => `${r.icon || ''} ${r.description || v}` },
    { title: '分类', dataIndex: 'category', key: 'category',
      render: v => ({ value: '价值', momentum: '动量', flow: '资金', event: '事件', combo: '组合' }[v] || v) },
    { title: '衰减分数', dataIndex: 'decay_score', key: 'decay_score',
      render: v => {
        const color = v > 20 ? '#ff4d4f' : v > 10 ? '#faad14' : '#52c41a';
        return <span style={{ color, fontWeight: 'bold' }}>{v != null ? v.toFixed(1) : 'N/A'}</span>;
      },
      sorter: (a, b) => (a.decay_score || 0) - (b.decay_score || 0),
      defaultSortOrder: 'descend',
    },
    { title: '状态', dataIndex: 'status', key: 'status',
      render: v => {
        const map = { growing: { color: 'green', text: '成长期' }, mature: { color: 'blue', text: '成熟期' },
          declining: { color: 'red', text: '衰退期' }, dormant: { color: 'default', text: '休眠期' } };
        const s = map[v] || { color: 'default', text: v };
        return <Tag color={s.color}>{s.text}</Tag>;
      }
    },
    { title: '近期胜率', dataIndex: 'recent_win_rate', key: 'rw',
      render: v => v != null ? `${v}%` : 'N/A' },
    { title: '历史胜率', dataIndex: 'historical_win_rate', key: 'hw',
      render: v => v != null ? `${v}%` : 'N/A' },
    { title: '操作', key: 'action',
      render: (_, r) => <Button type='primary' size='small' onClick={() => optimizeStrategy(r.name)}
        loading={loading && selectedStrategy === r.name}>优化</Button>
    },
  ];

  const renderOptimization = () => {
    if (!optimizeResult) return <Empty description='请先选择策略进行优化' />;
    const { original, best_variant, all_variants, strategy_name, date_range } = optimizeResult;

    return (
      <div style={{ padding: '0 16px' }}>
        <h3>🧪 {strategy_name} 参数优化结果</h3>
        {date_range && <p style={{ color: '#999' }}>回测区间: {date_range.start} ~ {date_range.end}</p>}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Card title='原始参数' size='small'>
              <Statistic title='胜率' value={original?.win_rate || 0} suffix='%' />
              <Statistic title='平均收益' value={original?.avg_return || 0} suffix='%' />
              <Statistic title='夏普比率' value={original?.sharpe || 0} />
            </Card>
          </Col>
          <Col span={8}>
            <Card title='最优变体' size='small' style={{ border: '2px solid #1890ff' }}>
              <Statistic title='胜率' value={best_variant?.win_rate || 0} suffix='%'
                valueStyle={{ color: (best_variant?.win_rate || 0) > (original?.win_rate || 0) ? '#3f8600' : '#cf1322' }} />
              <Statistic title='平均收益' value={best_variant?.avg_return || 0} suffix='%'
                valueStyle={{ color: (best_variant?.avg_return || 0) > (original?.avg_return || 0) ? '#3f8600' : '#cf1322' }} />
              <Statistic title='夏普比率' value={best_variant?.sharpe || 0} />
            </Card>
          </Col>
          <Col span={8}>
            <Card title='改进幅度' size='small'>
              <Statistic title='胜率提升'
                value={((best_variant?.win_rate || 0) - (original?.win_rate || 0)).toFixed(1)} suffix='%'
                valueStyle={{ color: ((best_variant?.win_rate || 0) - (original?.win_rate || 0)) > 0 ? '#3f8600' : '#cf1322' }} />
              <Statistic title='收益提升'
                value={((best_variant?.avg_return || 0) - (original?.avg_return || 0)).toFixed(2)} suffix='%'
                valueStyle={{ color: ((best_variant?.avg_return || 0) - (original?.avg_return || 0)) > 0 ? '#3f8600' : '#cf1322' }} />
              <Statistic title='夏普提升'
                value={((best_variant?.sharpe || 0) - (original?.sharpe || 0)).toFixed(2)} />
            </Card>
          </Col>
        </Row>

        <Card title='参数变体排行' size='small'>
          <Table
            dataSource={all_variants || []}
            rowKey='id'
            size='small'
            pagination={{ pageSize: 10 }}
            columns={[
              { title: '排名', dataIndex: 'rank', key: 'rank', width: 60 },
              { title: '参数', dataIndex: 'params_desc', key: 'params', render: v => <code>{v}</code> },
              { title: '胜率', dataIndex: 'win_rate', key: 'wr', render: v => `${v}%`,
                sorter: (a, b) => a.win_rate - b.win_rate },
              { title: '平均收益', dataIndex: 'avg_return', key: 'ar', render: v => `${v}%`,
                sorter: (a, b) => a.avg_return - b.avg_return },
              { title: '夏普比率', dataIndex: 'sharpe', key: 'sh',
                sorter: (a, b) => a.sharpe - b.sharpe },
              { title: '最大回撤', dataIndex: 'max_drawdown', key: 'md', render: v => `${v}%` },
              { title: '总收益', dataIndex: 'total_return', key: 'tr', render: v => `${v}%` },
              { title: '选股数', dataIndex: 'avg_picks', key: 'ap' },
              { title: '状态', dataIndex: 'is_best', key: 'best',
                render: v => v ? <Tag color='blue'>最优</Tag> : null },
            ]}
          />
        </Card>
      </div>
    );
  };

  const renderOverview = () => {
    if (!report) return <Spin spinning={loading} />;
    return (
      <div style={{ padding: '0 16px' }}>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card><Statistic title='总策略数' value={report.total_strategies || 0} prefix={<ExperimentOutlined />} /></Card>
          </Col>
          <Col span={6}>
            <Card><Statistic title='成长期' value={report.growing || 0} valueStyle={{ color: '#3f8600' }} /></Card>
          </Col>
          <Col span={6}>
            <Card><Statistic title='成熟期' value={report.mature || 0} valueStyle={{ color: '#1890ff' }} /></Card>
          </Col>
          <Col span={6}>
            <Card><Statistic title='衰退期' value={report.declining || 0} valueStyle={{ color: '#cf1322' }} /></Card>
          </Col>
        </Row>

        {report.recommendations && report.recommendations.length > 0 && (
          <Card title='💡 优化建议' size='small' style={{ marginBottom: 16 }}>
            {report.recommendations.map((rec, i) => (
              <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
                <Tag color={rec.priority === 'high' ? 'red' : rec.priority === 'medium' ? 'orange' : 'blue'}>
                  {rec.priority === 'high' ? '高优先' : rec.priority === 'medium' ? '中优先' : '低优先'}
                </Tag>
                <strong>{rec.icon} {rec.strategy_name}</strong>: {rec.message}
                <Button size='small' style={{ marginLeft: 8 }} onClick={() => optimizeStrategy(rec.strategy_name)}>
                  立即优化
                </Button>
              </div>
            ))}
          </Card>
        )}
      </div>
    );
  };

  return (
    <div style={{ padding: '16px' }}>
      <Card title='🧪 策略自进化引擎' extra={
        <Space>
          <span>持有天数: <Slider value={holdDays} onChange={setHoldDays} min={1} max={20} style={{ width: 100 }} /></span>
          <span>选股数: <Slider value={topN} onChange={setTopN} min={5} max={50} style={{ width: 100 }} /></span>
          <Button icon={<ReloadOutlined />} onClick={() => { loadReport(); loadDecay(); }}>刷新</Button>
        </Space>
      }>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          { key: 'overview', label: '📊 概览', children: renderOverview() },
          { key: 'decay', label: '📉 衰减检测', children: (
            <Table dataSource={decayData} columns={decayColumns} rowKey='name' size='small'
              pagination={{ pageSize: 15 }} loading={loading} />
          )},
          { key: 'optimize', label: '⚡ 参数优化', children: renderOptimization() },
        ]} />
      </Card>
    </div>
  );
}
