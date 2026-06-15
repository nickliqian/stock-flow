import React, { useState, useEffect, useMemo } from 'react';
import {
  Card, Row, Col, Table, Tag, Spin, Statistic, Segmented, Empty, Tooltip, Space,
} from 'antd';
import {
  ExperimentOutlined, ReloadOutlined, ThunderboltOutlined,
  RiseOutlined, FallOutlined, StockOutlined, SwapOutlined,
} from '@ant-design/icons';
import api from '../services/api';

const CATEGORY_LABELS = {
  value: '价值',
  momentum: '动量',
  flow: '资金',
  event: '事件',
  combo: '组合',
  other: '其他',
};

const CATEGORY_COLORS = {
  value: '#52c41a',
  momentum: '#1677ff',
  flow: '#faad14',
  event: '#ff4d4f',
  combo: '#722ed1',
  other: '#8c8c8c',
};

const REGIME_LABELS = {
  bull: { text: '牛市', color: 'green' },
  bear: { text: '熊市', color: 'red' },
  sideways: { text: '震荡', color: 'orange' },
  extreme: { text: '极端', color: 'volcano' },
  unknown: { text: '未知', color: 'default' },
};

function WeightBar({ value, maxValue = 0.3 }) {
  const pct = Math.min((value / maxValue) * 100, 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div
        style={{
          flex: 1,
          height: 14,
          background: '#f0f0f0',
          borderRadius: 7,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: `linear-gradient(90deg, #1677ff, #4096ff)`,
            borderRadius: 7,
            transition: 'width 0.5s ease',
          }}
        />
      </div>
      <span style={{ fontSize: 12, color: '#666', minWidth: 40, textAlign: 'right' }}>
        {(value * 100).toFixed(1)}%
      </span>
    </div>
  );
}

function PieChart({ data, size = 200 }) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  if (total === 0) return <Empty description="暂无数据" />;

  let accumulated = 0;
  const slices = data.map((d) => {
    const pct = (d.value / total) * 100;
    const start = accumulated;
    accumulated += pct;
    return { ...d, start, pct };
  });

  // Build conic gradient stops
  let stops = [];
  let acc = 0;
  for (const s of slices) {
    stops.push(`${s.color} ${acc}% ${acc + s.pct}%`);
    acc += s.pct;
  }
  const gradient = `conic-gradient(${stops.join(', ')})`;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
      <div
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          background: gradient,
          flexShrink: 0,
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        }}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {slices.map((s) => (
          <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: s.color, flexShrink: 0 }} />
            <span style={{ color: '#333' }}>{s.label}</span>
            <span style={{ color: '#999' }}>{(s.pct).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MiniLineChart({ data, width = 280, height = 60, color = '#1677ff' }) {
  if (!data || data.length < 2) {
    return <div style={{ width, height, background: '#fafafa', borderRadius: 4 }} />;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 8) - 4;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {data.map((v, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((v - min) / range) * (height - 8) - 4;
        return i === data.length - 1 ? (
          <circle key={i} cx={x} cy={y} r="3" fill={color} />
        ) : null;
      })}
    </svg>
  );
}

export default function AdaptiveWeight() {
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [executeResult, setExecuteResult] = useState(null);
  const [historyData, setHistoryData] = useState(null);
  const [activeTab, setActiveTab] = useState('weights');

  const loadData = async (signal) => {
    setLoading(true);
    try {
      const [summaryRes, historyRes] = await Promise.all([
        api.get('/strategies/adaptive/summary', { signal }),
        api.get('/strategies/adaptive/history', { params: { days: 30 }, signal }),
      ]);
      setSummary(summaryRes?.data || summaryRes);
      setHistoryData(historyRes?.data || historyRes);
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return;
      console.error('Failed to load adaptive weight data:', e);
    }
    setLoading(false);
  };

  const loadExecute = async (signal) => {
    setLoading(true);
    try {
      const res = await api.get('/strategies/adaptive/execute', {
        params: { limit: 50 },
        signal,
      });
      setExecuteResult(res?.data || res);
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return;
      console.error('Failed to execute adaptive strategy:', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, []);

  // --- Strategy weight table columns ---
  const weightColumns = [
    {
      title: '策略',
      key: 'name',
      width: 200,
      render: (_, r) => (
        <span>{r.icon || ''} {r.description || r.strategy_name}</span>
      ),
      sorter: (a, b) => (a.description || a.strategy_name).localeCompare(b.description || b.strategy_name),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 80,
      render: (v) => (
        <Tag color={CATEGORY_COLORS[v] || 'default'}>
          {CATEGORY_LABELS[v] || v}
        </Tag>
      ),
      filters: Object.entries(CATEGORY_LABELS).map(([k, v]) => ({ text: v, value: k })),
      onFilter: (value, record) => record.category === value,
    },
    {
      title: '权重',
      dataIndex: 'weight',
      key: 'weight',
      width: 200,
      sorter: (a, b) => a.weight - b.weight,
      defaultSortOrder: 'descend',
      render: (v) => <WeightBar value={v} maxValue={Math.min(0.3, (summary?.max_weight || 0.3) * 1.1)} />,
    },
    {
      title: '表现分数',
      dataIndex: 'perf_norm',
      key: 'perf_norm',
      width: 90,
      render: (v) => <span style={{ color: v > 0.6 ? '#52c41a' : v < 0.4 ? '#ff4d4f' : '#666' }}>{(v * 100).toFixed(0)}</span>,
    },
    {
      title: '一致性',
      dataIndex: 'cons_norm',
      key: 'cons_norm',
      width: 90,
      render: (v) => <span style={{ color: v > 0.6 ? '#52c41a' : v < 0.4 ? '#ff4d4f' : '#666' }}>{(v * 100).toFixed(0)}</span>,
    },
    {
      title: '体制匹配',
      dataIndex: 'regime_norm',
      key: 'regime_norm',
      width: 90,
      render: (v) => <span style={{ color: v > 0.6 ? '#52c41a' : v < 0.4 ? '#ff4d4f' : '#666' }}>{(v * 100).toFixed(0)}</span>,
    },
    {
      title: '相关性惩罚',
      dataIndex: 'corr_norm',
      key: 'corr_norm',
      width: 100,
      render: (v) => (
        <span style={{ color: v > 0.5 ? '#ff4d4f' : v > 0.2 ? '#faad14' : '#52c41a' }}>
          {v > 0 ? `-${(v * 100).toFixed(0)}` : '0'}
        </span>
      ),
    },
  ];

  // --- Execution result table columns ---
  const execColumns = [
    {
      title: '排名',
      key: 'rank',
      width: 60,
      render: (_, __, i) => i + 1,
    },
    {
      title: '股票代码',
      dataIndex: 'ts_code',
      key: 'ts_code',
      width: 120,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 100,
    },
    {
      title: '加权得分',
      dataIndex: 'weighted_score',
      key: 'weighted_score',
      width: 100,
      sorter: (a, b) => a.weighted_score - b.weighted_score,
      defaultSortOrder: 'descend',
      render: (v) => (
        <span style={{ fontWeight: 'bold', color: '#1677ff' }}>{v?.toFixed(3)}</span>
      ),
    },
    {
      title: '命中策略数',
      dataIndex: 'strategy_count',
      key: 'strategy_count',
      width: 100,
    },
    {
      title: '命中策略',
      dataIndex: 'strategies',
      key: 'strategies',
      render: (v) => (
        <Space size={2} wrap>
          {(v || []).map((s) => (
            <Tag key={s} style={{ fontSize: 11 }}>
              {s}
            </Tag>
          ))}
        </Space>
      ),
    },
  ];

  // Weight data for pie chart
  const pieData = useMemo(() => {
    if (!summary?.weights) return [];
    return Object.entries(summary.weights)
      .map(([name, w]) => ({
        label: w.description || name,
        value: w.weight,
        color: CATEGORY_COLORS[w.category] || '#8c8c8c',
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
  }, [summary]);

  // Category weights data
  const categoryPieData = useMemo(() => {
    if (!summary?.category_weights) return [];
    return Object.entries(summary.category_weights).map(([cat, data]) => ({
      label: CATEGORY_LABELS[cat] || cat,
      value: data.total_weight,
      color: CATEGORY_COLORS[cat] || '#8c8c8c',
    }));
  }, [summary]);

  // History timeline for top strategies
  const historyCharts = useMemo(() => {
    if (!historyData?.timeline || !historyData?.strategies) return [];
    const timeline = historyData.timeline;
    const strategies = historyData.strategies;

    // Pick top 5 strategies by latest weight
    const latest = timeline[timeline.length - 1] || {};
    const topStrategies = strategies
      .map((s) => ({ name: s, weight: latest[s] || 0 }))
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 5);

    const colors = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1'];
    return topStrategies.map((s, i) => ({
      name: s.name,
      data: timeline.map((t) => t[s.name] || 0),
      color: colors[i % colors.length],
    }));
  }, [historyData]);

  if (!summary && !loading) {
    return (
      <div style={{ padding: 24 }}>
        <Empty description="暂无数据，请先执行策略获取历史表现数据" />
      </div>
    );
  }

  const regimeInfo = REGIME_LABELS[summary?.regime] || REGIME_LABELS.unknown;

  return (
    <Spin spinning={loading}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>
          <ExperimentOutlined /> 自适应策略权重
        </h2>
        <Space>
          <Segmented
            value={activeTab}
            onChange={setActiveTab}
            options={[
              { label: '权重分布', value: 'weights' },
              { label: '组合选股', value: 'execute' },
              { label: '权重趋势', value: 'history' },
            ]}
          />
          <Tooltip title="刷新数据">
            <Segmented
              icon={<ReloadOutlined />}
              onClick={() => {
                const controller = new AbortController();
                if (activeTab === 'execute') {
                  loadExecute(controller.signal);
                } else {
                  loadData(controller.signal);
                }
              }}
            />
          </Tooltip>
        </Space>
      </div>

      {/* Summary Stats Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="策略总数"
              value={summary?.total_strategies || 0}
              prefix={<StockOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="最高权重"
              value={summary?.max_weight ? (summary.max_weight * 100).toFixed(1) : '--'}
              suffix="%"
              valueStyle={{ color: '#52c41a' }}
              prefix={<RiseOutlined />}
            />
            {summary?.max_weight_strategy && (
              <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                {summary.weights?.[summary.max_weight_strategy]?.icon || ''}{' '}
                {summary.weights?.[summary.max_weight_strategy]?.description || summary.max_weight_strategy}
              </div>
            )}
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="最低权重"
              value={summary?.min_weight ? (summary.min_weight * 100).toFixed(1) : '--'}
              suffix="%"
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<FallOutlined />}
            />
            {summary?.min_weight_strategy && (
              <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                {summary.weights?.[summary.min_weight_strategy]?.icon || ''}{' '}
                {summary.weights?.[summary.min_weight_strategy]?.description || summary.min_weight_strategy}
              </div>
            )}
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="市场状态"
              value={regimeInfo.text}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: regimeInfo.color === 'green' ? '#52c41a' : regimeInfo.color === 'red' ? '#ff4d4f' : '#faad14' }}
            />
            <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
              交易日: {summary?.trade_date || '--'}
            </div>
          </Card>
        </Col>
      </Row>

      {/* Factor Weights Info */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 13 }}>
          <span style={{ color: '#999' }}>权重因子配比：</span>
          <span>表现 <b>{(summary?.factor_weights?.performance || 0.4) * 100}%</b></span>
          <span>一致性 <b>{(summary?.factor_weights?.consistency || 0.25) * 100}%</b></span>
          <span>体制匹配 <b>{(summary?.factor_weights?.regime_fit || 0.2) * 100}%</b></span>
          <span>相关性惩罚 <b>{(summary?.factor_weights?.correlation || 0.15) * 100}%</b></span>
        </div>
      </Card>

      {activeTab === 'weights' && (
        <Row gutter={[16, 16]}>
          {/* Weight Pie Chart */}
          <Col xs={24} lg={10}>
            <Card title="策略权重分布" size="small">
              {pieData.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
                  <PieChart data={pieData} size={180} />
                </div>
              ) : (
                <Empty description="暂无权重数据" />
              )}
            </Card>
          </Col>

          {/* Category Weights */}
          <Col xs={24} lg={14}>
            <Card title="分类权重汇总" size="small">
              {categoryPieData.length > 0 ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
                  <PieChart data={categoryPieData} size={140} />
                  <div style={{ flex: 1 }}>
                    <Table
                      dataSource={Object.entries(summary?.category_weights || {}).map(([cat, d]) => ({
                        key: cat,
                        category: cat,
                        total_weight: d.total_weight,
                        count: d.count,
                        avg_weight: d.avg_weight,
                      }))}
                      columns={[
                        {
                          title: '分类',
                          dataIndex: 'category',
                          render: (v) => <Tag color={CATEGORY_COLORS[v]}>{CATEGORY_LABELS[v] || v}</Tag>,
                        },
                        { title: '策略数', dataIndex: 'count' },
                        { title: '总权重', dataIndex: 'total_weight', render: (v) => `${(v * 100).toFixed(1)}%` },
                        { title: '平均权重', dataIndex: 'avg_weight', render: (v) => `${(v * 100).toFixed(1)}%` },
                      ]}
                      pagination={false}
                      size="small"
                    />
                  </div>
                </div>
              ) : (
                <Empty description="暂无分类数据" />
              )}
            </Card>
          </Col>

          {/* Full Weight Table */}
          <Col span={24}>
            <Card title="策略权重详情" size="small">
              <Table
                dataSource={Object.entries(summary?.weights || {}).map(([name, w]) => ({
                  key: name,
                  ...w,
                }))}
                columns={weightColumns}
                pagination={{ pageSize: 15, size: 'small' }}
                size="small"
                scroll={{ x: 800 }}
              />
            </Card>
          </Col>
        </Row>
      )}

      {activeTab === 'execute' && (
        <Card title="自适应加权选股结果" size="small">
          {executeResult?.picks ? (
            <Table
              dataSource={executeResult.picks.map((p) => ({ key: p.ts_code, ...p }))}
              columns={execColumns}
              pagination={{ pageSize: 20, size: 'small' }}
              size="small"
              scroll={{ x: 800 }}
            />
          ) : (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin spinning={loading} />
              {!loading && (
                <div style={{ marginTop: 16 }}>
                  <a
                    onClick={() => {
                      const controller = new AbortController();
                      loadExecute(controller.signal);
                    }}
                    style={{ fontSize: 14 }}
                  >
                    点击执行自适应选股
                  </a>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {activeTab === 'history' && (
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Card title="策略权重历史趋势 (近5策略)" size="small">
              {historyCharts.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {historyCharts.map((chart) => (
                    <div key={chart.name} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 120, fontSize: 12, color: '#666', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: 4, background: chart.color, marginRight: 4 }} />
                        {chart.name}
                      </div>
                      <MiniLineChart data={chart.data} width={600} height={40} color={chart.color} />
                      <span style={{ fontSize: 12, color: '#999', minWidth: 40 }}>
                        {((chart.data[chart.data.length - 1] || 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty description="暂无历史数据" />
              )}
            </Card>
          </Col>

          <Col span={24}>
            <Card title="权重变化历史记录" size="small">
              <Table
                dataSource={(historyData?.history || []).map((r, i) => ({ key: `${r.trade_date}-${r.strategy_name}-${i}`, ...r }))}
                columns={[
                  { title: '交易日', dataIndex: 'trade_date', width: 100 },
                  { title: '策略', dataIndex: 'strategy_name', width: 160 },
                  {
                    title: '权重',
                    dataIndex: 'weight',
                    render: (v) => `${(v * 100).toFixed(2)}%`,
                    sorter: (a, b) => a.weight - b.weight,
                  },
                  { title: '表现分数', dataIndex: 'performance_score', render: (v) => (v * 100).toFixed(1) },
                  { title: '一致性', dataIndex: 'consistency_score', render: (v) => (v * 100).toFixed(1) },
                  { title: '体制匹配', dataIndex: 'regime_fit_score', render: (v) => (v * 100).toFixed(1) },
                  {
                    title: '相关性惩罚',
                    dataIndex: 'correlation_penalty',
                    render: (v) => (
                      <span style={{ color: v > 0 ? '#ff4d4f' : '#52c41a' }}>
                        {v > 0 ? `-${(v * 100).toFixed(1)}` : '0'}
                      </span>
                    ),
                  },
                ]}
                pagination={{ pageSize: 20, size: 'small' }}
                size="small"
                scroll={{ x: 700 }}
              />
            </Card>
          </Col>
        </Row>
      )}
    </Spin>
  );
}
