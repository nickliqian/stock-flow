import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Table, Tag, Button, Spin, Tabs, Statistic, Space, Tooltip, Progress, Empty,
} from 'antd';
import {
  ReloadOutlined, TrophyOutlined, RiseOutlined, FallOutlined, MinusOutlined,
  ArrowUpOutlined, ArrowDownOutlined, SwapOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import api from '../services/api';

const TRUST_GRADE_COLORS = {
  'A+': '#52c41a',
  A: '#1890ff',
  'B+': '#faad14',
  B: '#fa8c16',
  'C+': '#ff4d4f',
  C: '#a61d24',
  D: '#8c8c8c',
};

const RECOMMENDATION_MAP = {
  increase_exposure: { color: '#52c41a', text: '增加暴露' },
  increase: { color: '#52c41a', text: '增加' },
  maintain: { color: '#1890ff', text: '维持' },
  standard: { color: '#1890ff', text: '标准' },
  decrease_exposure: { color: '#faad14', text: '减少暴露' },
  decrease: { color: '#faad14', text: '减少' },
  avoid: { color: '#ff4d4f', text: '回避' },
};

const CATEGORY_COLORS = {
  value: { color: '#faad14', bg: '#fffbe6' },
  momentum: { color: '#1890ff', bg: '#e6f7ff' },
  flow: { color: '#13c2c2', bg: '#e6fffb' },
  event: { color: '#ff4d4f', bg: '#fff2f0' },
  combo: { color: '#722ed1', bg: '#f9f0ff' },
};

const CATEGORY_LABELS = {
  value: '价值',
  momentum: '动量',
  flow: '资金',
  event: '事件',
  combo: '组合',
  unknown: '未知',
};

const QUALITY_MAP = {
  excellent: { color: '#52c41a', text: '优秀' },
  good: { color: '#1890ff', text: '良好' },
  fair: { color: '#faad14', text: '一般' },
  poor: { color: '#ff4d4f', text: '较差' },
  insufficient_data: { color: '#8c8c8c', text: '数据不足' },
};

const TREND_MAP = {
  improving: { icon: <RiseOutlined style={{ color: '#52c41a' }} />, text: '改善中', color: '#52c41a' },
  declining: { icon: <FallOutlined style={{ color: '#ff4d4f' }} />, text: '下降中', color: '#ff4d4f' },
  stable: { icon: <MinusOutlined style={{ color: '#1890ff' }} />, text: '稳定', color: '#1890ff' },
  insufficient_data: { icon: null, text: '数据不足', color: '#8c8c8c' },
};

const CONFIDENCE_MAP = {
  high: { color: '#52c41a', text: '高' },
  medium: { color: '#faad14', text: '中' },
  low: { color: '#ff4d4f', text: '低' },
};

// ========== 辅助组件 ==========

/** 组件评分进度条 */
function ScoreBar({ score, max = 100, color }) {
  const resolved = color || (score >= 60 ? '#52c41a' : score >= 40 ? '#faad14' : '#ff4d4f');
  return (
    <Progress
      percent={Math.min(100, Math.max(0, score))}
      size="small"
      strokeColor={resolved}
      format={(v) => `${v}`}
    />
  );
}

/** 趋势指示器 */
function TrendIndicator({ value }) {
  if (value == null) return <span style={{ color: '#8c8c8c' }}>N/A</span>;
  if (value > 0.005) return <Space size={2}><RiseOutlined style={{ color: '#52c41a' }} /><span style={{ color: '#52c41a', fontWeight: 500 }}>↑</span></Space>;
  if (value < -0.005) return <Space size={2}><FallOutlined style={{ color: '#ff4d4f' }} /><span style={{ color: '#ff4d4f', fontWeight: 500 }}>↓</span></Space>;
  return <Space size={2}><MinusOutlined style={{ color: '#1890ff' }} /><span style={{ color: '#1890ff', fontWeight: 500 }}>→</span></Space>;
}

/** 分类标签 */
function CategoryTag({ category }) {
  const cfg = CATEGORY_COLORS[category] || CATEGORY_COLORS.unknown;
  return (
    <Tag
      color={cfg.color}
      style={{ borderRadius: 4, fontWeight: 500, background: 'transparent' }}
    >
      {CATEGORY_LABELS[category] || category}
    </Tag>
  );
}

/** 信任等级徽章 */
function TrustGradeBadge({ grade }) {
  const color = TRUST_GRADE_COLORS[grade] || '#8c8c8c';
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 36,
        height: 24,
        borderRadius: 12,
        background: `${color}20`,
        color,
        fontWeight: 700,
        fontSize: 13,
        padding: '0 8px',
      }}
    >
      {grade}
    </span>
  );
}

// ========== Tab 1: 策略信任度 ==========

function TrustTab({ data, loading }) {
  if (loading) return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  if (!data) return <Empty description="暂无信任度数据" />;

  const { strategies = [], summary = {} } = data;
  const avgTrust = summary.avg_trust || 0;
  const grades = summary.strategies_by_grade || {};
  const aGradeCount = (grades['A+'] || 0) + (grades['A'] || 0);
  const total = summary.total || strategies.length;

  // 推荐分布
  const recCounts = { increase: 0, maintain: 0, decrease: 0, avoid: 0 };
  strategies.forEach((s) => {
    if (s.recommendation?.includes('increase')) recCounts.increase++;
    else if (s.recommendation === 'maintain') recCounts.maintain++;
    else if (s.recommendation?.includes('decrease')) recCounts.decrease++;
    else if (s.recommendation === 'avoid') recCounts.avoid++;
  });

  const trustColor = avgTrust >= 60 ? '#52c41a' : avgTrust >= 40 ? '#faad14' : '#ff4d4f';

  const columns = [
    {
      title: '策略',
      dataIndex: 'icon',
      key: 'name',
      fixed: 'left',
      width: 180,
      render: (_, r) => (
        <div>
          <span style={{ fontWeight: 600 }}>{r.icon} {r.name}</span>
          {r.description && (
            <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>{r.description}</div>
          )}
        </div>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 80,
      render: (v) => <CategoryTag category={v} />,
    },
    {
      title: '信任分数',
      dataIndex: 'trust_score',
      key: 'trust_score',
      width: 100,
      sorter: (a, b) => (a.trust_score || 0) - (b.trust_score || 0),
      defaultSortOrder: 'descend',
      render: (v) => {
        const color = v >= 60 ? '#52c41a' : v >= 40 ? '#faad14' : '#ff4d4f';
        return <span style={{ color, fontWeight: 700, fontSize: 15 }}>{v}</span>;
      },
    },
    {
      title: '等级',
      dataIndex: 'trust_grade',
      key: 'trust_grade',
      width: 70,
      render: (v) => <TrustGradeBadge grade={v} />,
    },
    {
      title: '信号质量',
      key: 'signal_quality',
      width: 120,
      render: (_, r) => <ScoreBar score={r.components?.signal_quality || 0} />,
    },
    {
      title: '一致性',
      key: 'consistency',
      width: 120,
      render: (_, r) => <ScoreBar score={r.components?.consistency || 0} />,
    },
    {
      title: '趋势',
      key: 'trend',
      width: 120,
      render: (_, r) => <ScoreBar score={r.components?.trend || 0} color={r.components?.trend >= 55 ? '#52c41a' : r.components?.trend >= 40 ? '#faad14' : '#ff4d4f'} />,
    },
    {
      title: '建议',
      dataIndex: 'recommendation',
      key: 'recommendation',
      width: 90,
      render: (v) => {
        const cfg = RECOMMENDATION_MAP[v] || { color: '#8c8c8c', text: v };
        return (
          <Tag
            style={{
              color: cfg.color,
              borderColor: `${cfg.color}60`,
              background: 'transparent',
              fontWeight: 500,
            }}
          >
            {cfg.text}
          </Tag>
        );
      },
    },
    {
      title: '理由',
      dataIndex: 'rationale',
      key: 'rationale',
      ellipsis: true,
      width: 260,
      render: (v) => (
        <Tooltip title={v} placement="topLeft">
          <span style={{ fontSize: 12, color: '#666' }}>{v}</span>
        </Tooltip>
      ),
    },
  ];

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="平均信任度"
              value={avgTrust}
              valueStyle={{ color: trustColor }}
              suffix="分"
              prefix={<TrophyOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="A+/A 策略数"
              value={aGradeCount}
              valueStyle={{ color: '#1890ff' }}
              suffix={`/ ${total}`}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="策略总数" value={total} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" title="推荐分布" style={{ height: '100%' }}>
            <Space size={12} wrap>
              <Tooltip title="增加暴露">
                <Tag color="green" style={{ fontSize: 12 }}>↑ {recCounts.increase}</Tag>
              </Tooltip>
              <Tooltip title="维持">
                <Tag color="blue" style={{ fontSize: 12 }}>→ {recCounts.maintain}</Tag>
              </Tooltip>
              <Tooltip title="减少暴露">
                <Tag color="orange" style={{ fontSize: 12 }}>↓ {recCounts.decrease}</Tag>
              </Tooltip>
              <Tooltip title="回避">
                <Tag color="red" style={{ fontSize: 12 }}>✕ {recCounts.avoid}</Tag>
              </Tooltip>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 信任度表格 */}
      <Table
        dataSource={strategies}
        columns={columns}
        rowKey="name"
        size="small"
        pagination={{ pageSize: 20 }}
        scroll={{ x: 1300 }}
      />
    </div>
  );
}

// ========== Tab 2: 信号质量分布 ==========

function DistributionTab({ data, loading }) {
  if (loading) return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  if (!data) return <Empty description="暂无信号质量数据" />;

  const { strategies = [], summary = {} } = data;

  const columns = [
    {
      title: '策略',
      key: 'name',
      fixed: 'left',
      width: 180,
      render: (_, r) => (
        <div>
          <span style={{ fontWeight: 600 }}>{r.icon} {r.name}</span>
          {r.description && (
            <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>{r.description}</div>
          )}
        </div>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 80,
      render: (v) => <CategoryTag category={v} />,
    },
    {
      title: '评分-收益相关性',
      dataIndex: 'score_return_correlation',
      key: 'correlation',
      width: 150,
      sorter: (a, b) => (a.score_return_correlation || 0) - (b.score_return_correlation || 0),
      defaultSortOrder: 'descend',
      render: (v) => {
        const color = v > 0.3 ? '#52c41a' : v > 0.1 ? '#1890ff' : v > -0.1 ? '#faad14' : '#ff4d4f';
        return (
          <div>
            <Progress
              percent={Math.min(100, Math.max(0, Math.round((v + 1) * 50)))}
              size="small"
              strokeColor={color}
              showInfo={true}
            />
            <span style={{ fontSize: 11, color }}>{v?.toFixed(3)}</span>
          </div>
        );
      },
    },
    {
      title: '一致性评分',
      dataIndex: 'consistency_score',
      key: 'consistency',
      width: 120,
      sorter: (a, b) => (a.consistency_score || 0) - (b.consistency_score || 0),
      render: (v) => {
        const color = v >= 60 ? '#52c41a' : v >= 45 ? '#1890ff' : v >= 35 ? '#faad14' : '#ff4d4f';
        return <span style={{ color, fontWeight: 600 }}>{v != null ? `${v}%` : 'N/A'}</span>;
      },
    },
    {
      title: '综合质量',
      dataIndex: 'overall_quality',
      key: 'quality',
      width: 100,
      render: (v) => {
        const cfg = QUALITY_MAP[v] || QUALITY_MAP.poor;
        return (
          <Tag
            style={{
              color: cfg.color,
              borderColor: `${cfg.color}60`,
              background: 'transparent',
              fontWeight: 500,
            }}
          >
            {cfg.text}
          </Tag>
        );
      },
    },
    {
      title: '分位数分析',
      key: 'tiers',
      width: 320,
      render: (_, r) => {
        const tiers = r.score_tiers || [];
        if (tiers.length === 0) return <span style={{ color: '#999' }}>数据不足</span>;
        return (
          <div style={{ display: 'flex', gap: 8 }}>
            {tiers.map((t, i) => (
              <Tooltip
                key={i}
                title={`${t.tier}: 均分${t.avg_score}, 1日${t.avg_ret_1d != null ? t.avg_ret_1d + '%' : '-'}, 3日${t.avg_ret_3d != null ? t.avg_ret_3d + '%' : '-'}, 5日${t.avg_ret_5d != null ? t.avg_ret_5d + '%' : '-'} (${t.count}只)`}
              >
                <div
                  style={{
                    flex: 1,
                    padding: '4px 6px',
                    borderRadius: 4,
                    background: i === 0 ? '#f6ffed' : i === 3 ? '#fff2f0' : '#fafafa',
                    border: `1px solid ${i === 0 ? '#b7eb8f' : i === 3 ? '#ffa39e' : '#f0f0f0'}`,
                    textAlign: 'center',
                    fontSize: 11,
                    cursor: 'default',
                    minWidth: 60,
                  }}
                >
                  <div style={{ color: '#999', marginBottom: 2 }}>{t.tier}</div>
                  <div style={{ fontWeight: 600, color: t.avg_ret_1d > 0 ? '#52c41a' : t.avg_ret_1d < 0 ? '#ff4d4f' : '#666' }}>
                    {t.avg_ret_1d != null ? `${t.avg_ret_1d}%` : '-'}
                  </div>
                </div>
              </Tooltip>
            ))}
          </div>
        );
      },
    },
  ];

  return (
    <div>
      {/* 汇总卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic title="策略总数" value={summary.total || 0} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic
              title="优秀"
              value={summary.excellent || 0}
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="良好" value={summary.good || 0} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="一般" value={summary.fair || 0} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="较差" value={summary.poor || 0} valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
      </Row>

      {summary.date_range && (
        <div style={{ marginBottom: 12, fontSize: 12, color: '#999' }}>
          数据区间: {summary.date_range.start} ~ {summary.date_range.end}
        </div>
      )}

      <Table
        dataSource={strategies}
        columns={columns}
        rowKey="name"
        size="small"
        pagination={{ pageSize: 20 }}
        scroll={{ x: 1100 }}
      />
    </div>
  );
}

// ========== Tab 3: 有效性趋势 ==========

function TrendTab({ data, loading }) {
  if (loading) return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  if (!data) return <Empty description="暂无趋势数据" />;

  const {
    strategy_name = 'all',
    trend_data = [],
    trend_direction = 'insufficient_data',
    trend_slope = 0,
    best_period,
    worst_period,
  } = data;

  const trendCfg = TREND_MAP[trend_direction] || TREND_MAP.insufficient_data;

  const columns = [
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date',
      width: 110,
      render: (v) => <span style={{ fontWeight: 500 }}>{v}</span>,
    },
    {
      title: '平均评分',
      dataIndex: 'avg_score',
      key: 'avg_score',
      width: 100,
      render: (v) => <span style={{ fontWeight: 600 }}>{v?.toFixed(2)}</span>,
    },
    {
      title: '平均收益',
      dataIndex: 'avg_ret_1d',
      key: 'avg_ret',
      width: 100,
      sorter: (a, b) => (a.avg_ret_1d ?? -999) - (b.avg_ret_1d ?? -999),
      render: (v) => {
        if (v == null) return <span style={{ color: '#999' }}>N/A</span>;
        const color = v > 0 ? '#52c41a' : v < 0 ? '#ff4d4f' : '#666';
        return <span style={{ color, fontWeight: 600 }}>{v > 0 ? '+' : ''}{v}%</span>;
      },
    },
    {
      title: '胜率',
      dataIndex: 'win_rate',
      key: 'win_rate',
      width: 100,
      sorter: (a, b) => (a.win_rate || 0) - (b.win_rate || 0),
      render: (v) => {
        const color = v >= 55 ? '#52c41a' : v >= 45 ? '#faad14' : '#ff4d4f';
        return <span style={{ color, fontWeight: 600 }}>{v}%</span>;
      },
    },
    {
      title: '相关性',
      dataIndex: 'correlation',
      key: 'correlation',
      width: 100,
      render: (v) => {
        const color = v > 0.1 ? '#52c41a' : v > -0.1 ? '#faad14' : '#ff4d4f';
        return <span style={{ color, fontWeight: 600 }}>{v?.toFixed(3)}</span>;
      },
    },
    {
      title: '选股数',
      dataIndex: 'pick_count',
      key: 'pick_count',
      width: 80,
      sorter: (a, b) => (a.pick_count || 0) - (b.pick_count || 0),
      defaultSortOrder: 'descend',
    },
  ];

  return (
    <div>
      {/* 趋势概览 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="策略"
              value={strategy_name === 'all' ? '全策略' : strategy_name}
              valueStyle={{ fontSize: 16 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="趋势方向"
              value={trendCfg.text}
              valueStyle={{ color: trendCfg.color }}
              prefix={trendCfg.icon}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="最佳交易日"
              value={best_period?.date || 'N/A'}
              valueStyle={{ fontSize: 14, color: '#52c41a' }}
              suffix={best_period?.avg_ret_1d != null ? `+${best_period.avg_ret_1d}%` : ''}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="最差交易日"
              value={worst_period?.date || 'N/A'}
              valueStyle={{ fontSize: 14, color: '#ff4d4f' }}
              suffix={worst_period?.avg_ret_1d != null ? `${worst_period.avg_ret_1d}%` : ''}
            />
          </Card>
        </Col>
      </Row>

      {/* 趋势斜率 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Space>
              <span style={{ fontSize: 12, color: '#999' }}>趋势斜率:</span>
              <TrendIndicator value={trend_slope} />
              <span style={{ fontSize: 12 }}>{trend_slope?.toFixed(4)}</span>
            </Space>
          </Card>
        </Col>
      </Row>

      <Table
        dataSource={trend_data}
        columns={columns}
        rowKey="date"
        size="small"
        pagination={{ pageSize: 15 }}
        scroll={{ x: 600 }}
      />
    </div>
  );
}

// ========== Tab 4: 暴露调整 ==========

function RebalanceTab({ data, loading }) {
  if (loading) return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  if (!data) return <Empty description="暂无暴露调整数据" />;

  const { recommendations = [], category_summary = {}, summary = {}, regime_alignment } = data;
  const avgTrust = summary.avg_trust || 0;

  const columns = [
    {
      title: '策略',
      key: 'name',
      fixed: 'left',
      width: 180,
      render: (_, r) => (
        <div>
          <span style={{ fontWeight: 600 }}>{r.icon} {r.strategy_name}</span>
        </div>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 80,
      render: (v) => <CategoryTag category={v} />,
    },
    {
      title: '当前 → 推荐',
      key: 'exposure',
      width: 180,
      render: (_, r) => {
        const currCfg = RECOMMENDATION_MAP[r.current_exposure] || { color: '#1890ff', text: '标准' };
        const recCfg = RECOMMENDATION_MAP[r.recommended_exposure] || { color: '#8c8c8c', text: r.recommended_exposure };
        return (
          <Space size={8}>
            <Tag style={{ color: currCfg.color, borderColor: `${currCfg.color}60`, background: 'transparent' }}>
              {currCfg.text}
            </Tag>
            <ArrowRightOutlined style={{ color: '#999' }} />
            <Tag
              style={{
                color: recCfg.color,
                borderColor: `${recCfg.color}60`,
                background: 'transparent',
                fontWeight: 600,
              }}
            >
              {recCfg.text}
            </Tag>
          </Space>
        );
      },
    },
    {
      title: '调整幅度',
      dataIndex: 'exposure_change_pct',
      key: 'change',
      width: 140,
      sorter: (a, b) => (a.exposure_change_pct || 0) - (b.exposure_change_pct || 0),
      defaultSortOrder: 'descend',
      render: (v) => {
        const color = v > 0 ? '#52c41a' : v < 0 ? '#ff4d4f' : '#8c8c8c';
        const pct = Math.abs(v);
        return (
          <div>
            <Progress
              percent={Math.min(100, pct * 2)}
              size="small"
              strokeColor={color}
              showInfo={false}
            />
            <span style={{ fontSize: 11, color, fontWeight: 600 }}>
              {v > 0 ? '+' : ''}{v}%
            </span>
          </div>
        );
      },
    },
    {
      title: '信心',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 70,
      render: (v) => {
        const cfg = CONFIDENCE_MAP[v] || CONFIDENCE_MAP.low;
        return (
          <Tag
            style={{
              color: cfg.color,
              borderColor: `${cfg.color}60`,
              background: 'transparent',
            }}
          >
            {cfg.text}
          </Tag>
        );
      },
    },
    {
      title: '理由',
      dataIndex: 'rationale',
      key: 'rationale',
      ellipsis: true,
      width: 300,
      render: (v) => (
        <Tooltip title={v} placement="topLeft">
          <span style={{ fontSize: 12, color: '#666' }}>{v}</span>
        </Tooltip>
      ),
    },
  ];

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="平均信任度"
              value={avgTrust}
              valueStyle={{ color: avgTrust >= 60 ? '#52c41a' : avgTrust >= 40 ? '#faad14' : '#ff4d4f' }}
              suffix="分"
            />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="增加" value={summary.increase_count || 0} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic
              title="标准"
              value={(summary.total_strategies || 0) - (summary.increase_count || 0) - (summary.decrease_count || 0) - (summary.avoid_count || 0)}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="减少" value={summary.decrease_count || 0} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="回避" value={summary.avoid_count || 0} valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
      </Row>

      {/* 分类汇总 */}
      {Object.keys(category_summary).length > 0 && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          {Object.entries(category_summary).map(([cat, info]) => (
            <Col key={cat} span={4}>
              <Card size="small" title={<CategoryTag category={cat} />}>
                <Statistic
                  title="平均信任度"
                  value={info.avg_trust}
                  suffix={`/ ${info.total}`}
                  valueStyle={{
                    fontSize: 14,
                    color: info.avg_trust >= 60 ? '#52c41a' : info.avg_trust >= 40 ? '#faad14' : '#ff4d4f',
                  }}
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* 暴露调整表 */}
      <Table
        dataSource={recommendations}
        columns={columns}
        rowKey="strategy_name"
        size="small"
        pagination={{ pageSize: 20 }}
        scroll={{ x: 1100 }}
      />
    </div>
  );
}

// ========== 简单箭头 (内联) ==========

function ArrowRightOutlined({ style }) {
  return (
    <span style={{ ...style, fontSize: 14 }}>→</span>
  );
}

// ========== 主组件 ==========

export default function SignalEffectiveness() {
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('trust');

  const [trustData, setTrustData] = useState(null);
  const [distributionData, setDistributionData] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [rebalanceData, setRebalanceData] = useState(null);

  const loadData = async (signal) => {
    setLoading(true);
    try {
      const [trustRes, distRes, trendRes, rebalRes] = await Promise.all([
        api.get('/strategies/signal-effectiveness/trust', { params: { lookback_days: 20 }, signal }),
        api.get('/strategies/signal-effectiveness/distribution', { params: { lookback_days: 20 }, signal }),
        api.get('/strategies/signal-effectiveness/trend', { params: { days: 30 }, signal }),
        api.get('/strategies/signal-effectiveness/rebalance', { params: { lookback_days: 20 }, signal }),
      ]);
      setTrustData(trustRes?.data || trustRes);
      setDistributionData(distRes?.data || distRes);
      setTrendData(trendRes?.data || trendRes);
      setRebalanceData(rebalRes?.data || rebalRes);
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return;
      console.error('Failed to load signal effectiveness data:', e);
    }
    setLoading(false);
  };

  useEffect(() => {
    const controller = new AbortController();
    loadData(controller.signal);
    return () => controller.abort();
  }, []);

  return (
    <div style={{ padding: 16 }}>
      <Card
        title="🎯 策略信号有效性"
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => loadData()} loading={loading}>
            刷新
          </Button>
        }
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: 'trust',
              label: '🏆 策略信任度',
              children: <TrustTab data={trustData} loading={loading && !trustData} />,
            },
            {
              key: 'distribution',
              label: '📊 信号质量分布',
              children: <DistributionTab data={distributionData} loading={loading && !distributionData} />,
            },
            {
              key: 'trend',
              label: '📈 有效性趋势',
              children: <TrendTab data={trendData} loading={loading && !trendData} />,
            },
            {
              key: 'rebalance',
              label: '🎯 暴露调整',
              children: <RebalanceTab data={rebalanceData} loading={loading && !rebalanceData} />,
            },
          ]}
        />
      </Card>
    </div>
  );
}