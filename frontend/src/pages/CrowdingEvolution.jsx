import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Table, Tag, Button, Spin, Statistic, Space, Tabs, Tooltip, Badge,
} from 'antd';
import {
  WarningOutlined, ReloadOutlined, AlertOutlined, CheckCircleOutlined,
  ArrowUpOutlined, ArrowDownOutlined, MinusOutlined,
} from '@ant-design/icons';
import { apiCall } from '../services/api';

const API_BASE = '/api/strategies';

export default function CrowdingEvolution() {
  const [loading, setLoading] = useState(false);
  const [evolution, setEvolution] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [diversity, setDiversity] = useState(null);
  const [crossCrowding, setCrossCrowding] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  const loadData = async (signal) => {
    setLoading(true);
    try {
      const [evoRes, alertRes, divRes, crossRes] = await Promise.all([
        apiCall(`${API_BASE}/crowding-evolution?lookback_days=30`),
        apiCall(`${API_BASE}/crowding-alerts`),
        apiCall(`${API_BASE}/crowding-diversity?lookback_days=30`),
        apiCall(`${API_BASE}/crowding-cross`),
      ]);
      setEvolution(evoRes?.data || evoRes);
      setAlerts(alertRes?.data || alertRes);
      setDiversity(divRes?.data || divRes);
      setCrossCrowding(crossRes?.data || crossRes);
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return;
      console.error('Failed to load crowding evolution data:', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, []);

  // ---- 统计卡片 ----
  const summary = evolution?.summary || {};
  const totalStrategies = summary.total || 0;
  const overcrowdedCount = summary.overcrowded || 0;
  const warningCount = summary.warning || 0;
  const diversityIndex = diversity?.current_index ?? 0;
  const crossScore = crossCrowding?.cross_crowding_score ?? 0;

  const renderOverviewCards = () => (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={6}>
        <Card>
          <Statistic
            title="策略总数"
            value={totalStrategies}
            prefix={<AlertOutlined />}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="拥挤策略"
            value={overcrowdedCount}
            valueStyle={{ color: overcrowdedCount > 0 ? '#cf1322' : '#3f8600' }}
            prefix={<WarningOutlined />}
          />
          {warningCount > 0 && (
            <div style={{ marginTop: 4 }}>
              <Tag color="orange">预警 {warningCount}</Tag>
            </div>
          )}
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="多样性指数"
            value={(diversityIndex * 100).toFixed(1)}
            suffix="%"
            valueStyle={{ color: diversityIndex >= 0.7 ? '#3f8600' : diversityIndex >= 0.5 ? '#faad14' : '#cf1322' }}
          />
          <div style={{ marginTop: 4, fontSize: 12, color: '#999' }}>
            活跃 {diversity?.active_strategies || 0}/{diversity?.total_strategies || 0}
          </div>
        </Card>
      </Col>
      <Col span={6}>
        <Card>
          <Statistic
            title="跨策略拥挤"
            value={crossScore}
            suffix="分"
            valueStyle={{ color: crossScore >= 30 ? '#cf1322' : crossScore >= 15 ? '#faad14' : '#3f8600' }}
          />
          <div style={{ marginTop: 4, fontSize: 12, color: '#999' }}>
            重叠 {crossCrowding?.overlapping_count || 0} 只
          </div>
        </Card>
      </Col>
    </Row>
  );

  // ---- 策略拥挤度时间线表格 ----
  const crowdingColumns = [
    {
      title: '策略',
      dataIndex: 'strategy_name',
      key: 'name',
      fixed: 'left',
      width: 160,
      render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
    },
    {
      title: '当前选股',
      dataIndex: 'current_picks',
      key: 'current',
      width: 90,
      sorter: (a, b) => a.current_picks - b.current_picks,
      defaultSortOrder: 'descend',
    },
    {
      title: '滚动均值',
      dataIndex: 'rolling_avg',
      key: 'avg',
      width: 90,
    },
    {
      title: '标准差',
      dataIndex: 'rolling_std',
      key: 'std',
      width: 80,
    },
    {
      title: '拥挤比率',
      dataIndex: 'crowding_ratio',
      key: 'ratio',
      width: 100,
      render: (v) => {
        const color = v > 1.5 ? '#cf1322' : v > 1.2 ? '#faad14' : '#3f8600';
        return <span style={{ color, fontWeight: 'bold' }}>{v?.toFixed(2)}</span>;
      },
      sorter: (a, b) => (a.crowding_ratio || 0) - (b.crowding_ratio || 0),
      defaultSortOrder: 'descend',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (v) => {
        const map = {
          overcrowded: { color: 'red', text: '过拥挤' },
          warning: { color: 'orange', text: '预警' },
          normal: { color: 'green', text: '正常' },
        };
        const s = map[v] || { color: 'default', text: v };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '趋势',
      dataIndex: 'trend',
      key: 'trend',
      width: 90,
      render: (v) => {
        const map = {
          rising: { icon: <ArrowUpOutlined style={{ color: '#cf1322' }} />, text: '上升' },
          falling: { icon: <ArrowDownOutlined style={{ color: '#3f8600' }} />, text: '下降' },
          stable: { icon: <MinusOutlined style={{ color: '#999' }} />, text: '稳定' },
        };
        const t = map[v] || map.stable;
        return <Space size={4}>{t.icon}<span>{t.text}</span></Space>;
      },
    },
    {
      title: '选股趋势',
      dataIndex: 'history',
      key: 'sparkline',
      width: 160,
      render: (history) => {
        if (!history || history.length === 0) return null;
        const maxVal = Math.max(...history.map((h) => h.picks), 1);
        const barWidth = Math.floor(140 / history.length);
        return (
          <div style={{ display: 'flex', alignItems: 'flex-end', height: 32, gap: 1 }}>
            {history.map((h, i) => {
              const height = Math.max(2, (h.picks / maxVal) * 28);
              const isLast = i === history.length - 1;
              return (
                <Tooltip key={i} title={`${h.date}: ${h.picks}只`}>
                  <div
                    style={{
                      width: barWidth,
                      height,
                      background: isLast ? '#1677ff' : '#91caff',
                      borderRadius: 1,
                    }}
                  />
                </Tooltip>
              );
            })}
          </div>
        );
      },
    },
  ];

  // ---- 多样性指数图表 ----
  const renderDiversityChart = () => {
    const history = diversity?.diversity_history || [];
    if (history.length === 0) {
      return <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>暂无数据</div>;
    }

    const maxActive = Math.max(...history.map((h) => h.active_count), 1);
    const barWidth = Math.max(12, Math.floor(600 / history.length));

    return (
      <div style={{ padding: '16px 0' }}>
        <div style={{ marginBottom: 8, fontSize: 13, color: '#666' }}>
          多样性趋势：活跃策略数 / 总策略数 ({diversity?.total_strategies || 0})
          <Tag
            color={
              diversity?.trend === 'expanding'
                ? 'green'
                : diversity?.trend === 'contracting'
                ? 'red'
                : 'blue'
            }
            style={{ marginLeft: 8 }}
          >
            {diversity?.trend === 'expanding'
              ? '扩张中'
              : diversity?.trend === 'contracting'
              ? '收缩中'
              : diversity?.trend === 'stable'
              ? '稳定'
              : '数据不足'}
          </Tag>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            height: 160,
            gap: 2,
            borderBottom: '1px solid #f0f0f0',
            paddingBottom: 4,
            overflowX: 'auto',
          }}
        >
          {history.map((h, i) => {
            const height = Math.max(4, (h.diversity_index || 0) * 150);
            const color =
              h.diversity_index >= 0.7
                ? '#52c41a'
                : h.diversity_index >= 0.5
                ? '#faad14'
                : '#ff4d4f';
            return (
              <Tooltip
                key={i}
                title={`${h.trade_date}: ${h.active_count}/${h.total_strategies} (${(h.diversity_index * 100).toFixed(1)}%)`}
              >
                <div
                  style={{
                    width: barWidth,
                    height,
                    background: color,
                    borderRadius: '2px 2px 0 0',
                    minWidth: 4,
                    cursor: 'pointer',
                    transition: 'opacity 0.2s',
                  }}
                  onMouseEnter={(e) => (e.target.style.opacity = '0.8')}
                  onMouseLeave={(e) => (e.target.style.opacity = '1')}
                />
              </Tooltip>
            );
          })}
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 11,
            color: '#999',
            marginTop: 4,
          }}
        >
          <span>{history[0]?.trade_date}</span>
          <span>{history[history.length - 1]?.trade_date}</span>
        </div>
      </div>
    );
  };

  // ---- 跨策略拥挤热力图 ----
  const renderCrossCrowdingMatrix = () => {
    const pairs = crossCrowding?.top_pairs || [];
    const stocks = crossCrowding?.overlapping_stocks || [];

    if (stocks.length === 0 && pairs.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          暂无跨策略拥挤数据
        </div>
      );
    }

    return (
      <div>
        <Row gutter={16}>
          <Col span={12}>
            <Card title="🔗 重叠股票" size="small">
              <Table
                dataSource={stocks.slice(0, 15)}
                rowKey="ts_code"
                size="small"
                pagination={false}
                columns={[
                  {
                    title: '股票代码',
                    dataIndex: 'ts_code',
                    key: 'code',
                    width: 120,
                  },
                  {
                    title: '策略数',
                    dataIndex: 'strategy_count',
                    key: 'count',
                    width: 70,
                    render: (v) => (
                      <Badge
                        count={v}
                        style={{
                          backgroundColor: v >= 3 ? '#ff4d4f' : '#1677ff',
                        }}
                      />
                    ),
                    sorter: (a, b) => a.strategy_count - b.strategy_count,
                    defaultSortOrder: 'descend',
                  },
                  {
                    title: '策略列表',
                    dataIndex: 'strategies',
                    key: 'strategies',
                    render: (v) =>
                      v?.map((s) => (
                        <Tag key={s} color="blue" style={{ marginBottom: 2 }}>
                          {s}
                        </Tag>
                      )),
                  },
                ]}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card title="📊 策略对重叠度 (Jaccard)" size="small">
              <Table
                dataSource={pairs.slice(0, 15)}
                rowKey={(r) => `${r.strategy_a}-${r.strategy_b}`}
                size="small"
                pagination={false}
                columns={[
                  {
                    title: '策略 A',
                    dataIndex: 'strategy_a',
                    key: 'a',
                    width: 130,
                    render: (v) => <span style={{ fontSize: 12 }}>{v}</span>,
                  },
                  {
                    title: '策略 B',
                    dataIndex: 'strategy_b',
                    key: 'b',
                    width: 130,
                    render: (v) => <span style={{ fontSize: 12 }}>{v}</span>,
                  },
                  {
                    title: '重叠数',
                    dataIndex: 'overlap_count',
                    key: 'overlap',
                    width: 70,
                  },
                  {
                    title: 'Jaccard',
                    dataIndex: 'jaccard',
                    key: 'jaccard',
                    width: 90,
                    render: (v) => {
                      const pct = (v * 100).toFixed(1);
                      const color = v >= 0.3 ? '#ff4d4f' : v >= 0.15 ? '#faad14' : '#3f8600';
                      return <span style={{ color, fontWeight: 'bold' }}>{pct}%</span>;
                    },
                    sorter: (a, b) => a.jaccard - b.jaccard,
                    defaultSortOrder: 'descend',
                  },
                ]}
              />
            </Card>
          </Col>
        </Row>
      </div>
    );
  };

  // ---- 告警面板 ----
  const renderAlerts = () => {
    const alertList = alerts?.alerts || [];
    if (alertList.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: 40, color: '#52c41a' }}>
          <CheckCircleOutlined style={{ fontSize: 32, marginBottom: 8 }} />
          <div>当前无拥挤度告警</div>
        </div>
      );
    }

    return (
      <div>
        <Row gutter={16} style={{ marginBottom: 12 }}>
          <Col span={8}>
            <Card size="small">
              <Statistic
                title="高严重度"
                value={alerts.high_count || 0}
                valueStyle={{ color: '#cf1322' }}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card size="small">
              <Statistic
                title="中严重度"
                value={alerts.medium_count || 0}
                valueStyle={{ color: '#faad14' }}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card size="small">
              <Statistic
                title="低严重度"
                value={alerts.low_count || 0}
                valueStyle={{ color: '#1677ff' }}
              />
            </Card>
          </Col>
        </Row>
        <Table
          dataSource={alertList}
          rowKey={(r, i) => `${r.strategy_name}-${r.alert_type}-${i}`}
          size="small"
          pagination={{ pageSize: 10 }}
          columns={[
            {
              title: '严重度',
              dataIndex: 'severity',
              key: 'severity',
              width: 80,
              render: (v) => {
                const map = {
                  high: <Tag color="red">高</Tag>,
                  medium: <Tag color="orange">中</Tag>,
                  low: <Tag color="blue">低</Tag>,
                };
                return map[v] || v;
              },
              filters: [
                { text: '高', value: 'high' },
                { text: '中', value: 'medium' },
                { text: '低', value: 'low' },
              ],
              onFilter: (value, record) => record.severity === value,
            },
            {
              title: '类型',
              dataIndex: 'alert_type',
              key: 'type',
              width: 100,
              render: (v) => {
                const map = {
                  overcrowded: <Tag color="red">过拥挤</Tag>,
                  surging: <Tag color="volcano">急升</Tag>,
                  cooling_off: <Tag color="cyan">退潮</Tag>,
                  warning: <Tag color="orange">预警</Tag>,
                };
                return map[v] || v;
              },
            },
            {
              title: '策略',
              dataIndex: 'strategy_name',
              key: 'name',
              width: 160,
            },
            {
              title: '拥挤比率',
              dataIndex: 'crowding_ratio',
              key: 'ratio',
              width: 100,
              render: (v) => (
                <span style={{ fontWeight: 'bold', color: v > 1.5 ? '#cf1322' : '#faad14' }}>
                  {v?.toFixed(2)}
                </span>
              ),
            },
            {
              title: '选股数',
              dataIndex: 'current_picks',
              key: 'picks',
              width: 80,
            },
            {
              title: '滚动均值',
              dataIndex: 'rolling_avg',
              key: 'avg',
              width: 80,
            },
            {
              title: '告警信息',
              dataIndex: 'message',
              key: 'message',
              ellipsis: true,
            },
          ]}
        />
      </div>
    );
  };

  return (
    <div style={{ padding: 16 }}>
      <Card
        title="⚠️ 策略拥挤度演进"
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => loadData()} loading={loading}>
            刷新
          </Button>
        }
      >
        {renderOverviewCards()}

        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'overview',
              label: '📊 拥挤度时间线',
              children: (
                <Table
                  dataSource={evolution?.strategies || []}
                  columns={crowdingColumns}
                  rowKey="strategy_name"
                  size="small"
                  pagination={{ pageSize: 15 }}
                  loading={loading}
                  scroll={{ x: 1000 }}
                />
              ),
            },
            {
              key: 'diversity',
              label: '🌐 多样性指数',
              children: (
                <div style={{ padding: '0 16px' }}>
                  <Row gutter={16} style={{ marginBottom: 16 }}>
                    <Col span={8}>
                      <Card size="small">
                        <Statistic
                          title="当前多样性"
                          value={(diversityIndex * 100).toFixed(1)}
                          suffix="%"
                          valueStyle={{
                            color: diversityIndex >= 0.7 ? '#3f8600' : diversityIndex >= 0.5 ? '#faad14' : '#cf1322',
                          }}
                        />
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small">
                        <Statistic
                          title="活跃策略"
                          value={diversity?.active_strategies || 0}
                          suffix={`/ ${diversity?.total_strategies || 0}`}
                        />
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small">
                        <Statistic
                          title="趋势"
                          value={
                            diversity?.trend === 'expanding'
                              ? '扩张'
                              : diversity?.trend === 'contracting'
                              ? '收缩'
                              : '稳定'
                          }
                          valueStyle={{
                            color: diversity?.trend === 'expanding' ? '#3f8600' : diversity?.trend === 'contracting' ? '#cf1322' : '#1677ff',
                          }}
                        />
                      </Card>
                    </Col>
                  </Row>
                  <Card title="多样性指数趋势" size="small">
                    {renderDiversityChart()}
                  </Card>
                  <div style={{ marginTop: 12, padding: 12, background: '#fafafa', borderRadius: 6, fontSize: 12, color: '#666' }}>
                    <strong>解读：</strong>
                    多样性指数 ≥ 70% 表示市场由多种因子驱动，策略分散度高；
                    50%-70% 表示中等分散度；&lt; 50% 表示市场由少数因子主导，需警惕拥挤风险。
                    多样性收缩通常预示着市场即将出现风格切换。
                  </div>
                </div>
              ),
            },
            {
              key: 'cross',
              label: '🔗 跨策略拥挤',
              children: (
                <div style={{ padding: '0 8px' }}>
                  <Row gutter={16} style={{ marginBottom: 12 }}>
                    <Col span={8}>
                      <Card size="small">
                        <Statistic title="重叠股票数" value={crossCrowding?.overlapping_count || 0} />
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small">
                        <Statistic
                          title="高重叠(≥3策略)"
                          value={crossCrowding?.high_overlap_count || 0}
                          valueStyle={{ color: crossCrowding?.high_overlap_count > 0 ? '#cf1322' : '#3f8600' }}
                        />
                      </Card>
                    </Col>
                    <Col span={8}>
                      <Card size="small">
                        <Statistic
                          title="拥挤分数"
                          value={crossCrowding?.cross_crowding_score || 0}
                          suffix="分"
                          valueStyle={{
                            color: crossScore >= 30 ? '#cf1322' : crossScore >= 15 ? '#faad14' : '#3f8600',
                          }}
                        />
                      </Card>
                    </Col>
                  </Row>
                  {renderCrossCrowdingMatrix()}
                </div>
              ),
            },
            {
              key: 'alerts',
              label: (
                <span>
                  🚨 告警
                  {(alerts?.count || 0) > 0 && (
                    <Badge count={alerts.count} style={{ marginLeft: 4 }} />
                  )}
                </span>
              ),
              children: renderAlerts(),
            },
          ]}
        />
      </Card>
    </div>
  );
}
