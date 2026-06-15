# Stock Flow UI & 交互规范

> 版本: 1.0 | 更新: 2026-06-15
> 本规范定义了 stock-flow 项目的 UI 设计和交互模式，所有新功能开发必须遵守。

---

## 1. 设计原则

| 原则 | 说明 |
|------|------|
| **专业金融** | 参考同花顺、东方财富等专业终端风格 |
| **信息密度** | 在有限空间展示最多有效信息 |
| **操作效率** | 减少点击次数，常用操作一键可达 |
| **视觉一致** | 全局统一的色彩、间距、圆角、字体 |

---

## 2. 色彩系统

### 2.1 基础色板

| 用途 | 色值 | 说明 |
|------|------|------|
| **主色** | `#1677ff` | 品牌蓝，按钮、链接、选中态 |
| **成功/涨** | `#cf1322` | 中国股市红色=涨 |
| **下跌** | `#3f8600` | 中国股市绿色=跌 |
| **警告** | `#d48806` | 橙色警告 |
| **文字主色** | `#262626` | 标题、正文 |
| **文字次色** | `#8c8c8c` | 辅助说明 |
| **文字禁用** | `#bfbfbf` | 禁用状态文字 |

### 2.2 背景色

| 用途 | 色值 | 说明 |
|------|------|------|
| **页面背景** | `#f5f5f5` | 最外层背景 |
| **卡片背景** | `#ffffff` | 卡片、表格、弹窗 |
| **表格行交替** | `#fafafa` | 奇偶行区分 |
| **悬停态** | `#f0f0f0` | 鼠标悬停行 |
| **侧边栏** | `#001529` | 深色侧边导航 |
| **Header** | `#ffffff` | 顶部导航栏 |

### 2.3 边框色

| 用途 | 色值 |
|------|------|
| 默认边框 | `#e8e8e8` |
| 分割线 | `#f0f0f0` |
| 输入框聚焦 | `#1677ff` |

---

## 3. 字体规范

### 3.1 字体族

```css
font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
```

### 3.2 字号层级

| 用途 | 字号 | 字重 | 示例 |
|------|------|------|------|
| 页面标题 | 20px | 600 | 📊 策略选股 |
| 卡片标题 | 16px | 600 | 📈 资金趋势 |
| 正文 | 14px | 400 | 默认文本 |
| 辅助文字 | 12px | 400 | 时间戳、单位 |
| 数据展示 | 14-16px | 500 | 金额、涨跌幅 |

---

## 4. 间距与圆角

### 4.1 间距系统

| 场景 | 间距 |
|------|------|
| 页面内边距 | 16px |
| 卡片内边距 | 16-24px |
| 卡片间距 | 16px |
| 表格行高 | 48px |
| 表格单元格内边距 | 12px 8px |

### 4.2 圆角

| 组件 | 圆角 |
|------|------|
| 卡片 | 8px |
| 按钮 | 6px |
| 输入框 | 6px |
| 标签 Tag | 4px |
| 头像 | 50% (圆形) |

---

## 5. 组件规范

### 5.1 卡片 (Card)

```jsx
// 标准卡片
<Card 
  size="small"
  title={<><Icon /> 标题文字</>}
  extra={<Button type="link">更多</Button>}
>
  {/* 内容 */}
</Card>

// 无标题卡片
<Card size="small">
  {/* 内容 */}
</Card>
```

**样式要求：**
- 背景：`#ffffff`
- 边框：`1px solid #e8e8e8`
- 圆角：`8px`
- 阴影：无（或 `0 1px 2px rgba(0,0,0,0.03)`）

### 5.2 表格 (Table)

```jsx
<Table
  dataSource={data}
  columns={columns}
  size="small"
  pagination={{ pageSize: 20, showSizeChanger: false }}
  rowKey="id"
/>
```

**样式要求：**
- 表头背景：`#fafafa`
- 表头文字：`#262626`，字重 600
- 行悬停：`#f0f0f0`
- 分页：底部居中

### 5.3 按钮 (Button)

| 类型 | 场景 | 样式 |
|------|------|------|
| primary | 主要操作（提交、执行） | 蓝色实心 |
| default | 次要操作（刷新、重置） | 白色描边 |
| text | 链接式操作（详情、编辑） | 无边框蓝色文字 |
| danger | 危险操作（删除） | 红色 |

### 5.4 标签 (Tag)

| 类型 | 场景 | 颜色 |
|------|------|------|
| 涨/正向 | 涨停、资金流入 | `red` |
| 跌/负向 | 跌停、资金流出 | `green` |
| 信息 | 状态、类型 | `blue` |
| 警告 | 注意事项 | `orange` |

### 5.5 抽屉 (Drawer)

```jsx
<Drawer
  title="详情"
  placement="right"
  width={600}
  open={visible}
  onClose={() => setVisible(false)}
>
  {/* 内容 */}
</Drawer>
```

**样式要求：**
- 背景：`#ffffff`
- 标题栏背景：`#fafafa`
- 标题栏底部边框：`1px solid #e8e8e8`

### 5.6 弹窗 (Modal)

```jsx
<Modal
  title="标题"
  open={visible}
  onCancel={() => setVisible(false)}
  footer={null}
>
  {/* 内容 */}
</Modal>
```

---

## 6. 交互模式

### 6.1 数据加载

| 场景 | 处理方式 |
|------|----------|
| 初始加载 | `Skeleton` 骨架屏 |
| 刷新数据 | `Spin` 加载中 + 按钮 loading |
| 提交表单 | 按钮 `loading` 状态 |
| 无数据 | `Empty` 空状态组件 |

### 6.2 操作反馈

| 操作 | 反馈 |
|------|------|
| 成功 | `message.success('操作成功')` |
| 失败 | `message.error('错误信息')` |
| 警告 | `notification.warning({...})` |
| 删除确认 | `Modal.confirm({...})` |

### 6.3 表格交互

| 交互 | 实现 |
|------|------|
| 排序 | 点击表头切换升序/降序 |
| 筛选 | 顶部搜索框 / 下拉筛选 |
| 分页 | 底部分页器，默认 20 条/页 |
| 行点击 | 跳转详情 / 展开抽屉 |
| 固定列 | 首列（名称）固定左侧 |

### 6.4 策略执行

| 阶段 | UI 表现 |
|------|---------|
| 等待执行 | 策略卡片 + 「执行」按钮 |
| 执行中 | 按钮 loading + 进度提示 |
| 执行完成 | 显示结果数量 + 结果表格 |
| 执行失败 | 错误提示 + 重试按钮 |

---

## 7. 图表规范

### 7.1 配色方案

```javascript
const chartColors = {
  primary: '#1677ff',    // 主色
  success: '#cf1322',    // 涨（红）
  danger: '#3f8600',     // 跌（绿）
  warning: '#d48806',    // 警告
  info: '#8c8c8c',       // 灰色
  series: [              // 多系列配色
    '#1677ff', '#cf1322', '#3f8600', 
    '#d48806', '#722ed1', '#13c2c2',
  ],
}
```

### 7.2 图表类型选择

| 数据类型 | 推荐图表 |
|----------|----------|
| 趋势变化 | 折线图 (Line) |
| 数量对比 | 柱状图 (Bar) |
| 占比分布 | 饼图 (Pie) |
| 多维对比 | 雷达图 (Radar) |
| 热力分布 | 热力图 (Heatmap) |

### 7.3 图表样式

- 背景：透明或 `#ffffff`
- 网格线：`#f0f0f0`
- 坐标轴：`#e8e8e8`
- 标签文字：`#8c8c8c`，12px
- Tooltip：白色背景，带阴影

---

## 8. 响应式断点

| 断点 | 宽度 | 适配 |
|------|------|------|
| xs | < 576px | 手机 |
| sm | ≥ 576px | 平板 |
| md | ≥ 768px | 小屏桌面 |
| lg | ≥ 992px | 标准桌面 |
| xl | ≥ 1200px | 大屏桌面 |

**最小宽度要求：** 1200px（金融终端主要面向桌面用户）

---

## 9. 图标规范

### 9.1 图标库

使用 `@ant-design/icons`，保持一致。

### 9.2 常用图标映射

| 功能 | 图标 |
|------|------|
| 大盘/市场 | `BarChartOutlined` |
| 资金流 | `FundOutlined` |
| 个股 | `StockOutlined` |
| 策略 | `RocketOutlined` |
| 搜索/选股 | `SearchOutlined` |
| 智能/分析 | `BulbOutlined` |
| 自选/收藏 | `StarOutlined` |
| 日志/记录 | `RobotOutlined` |
| 刷新 | `ReloadOutlined` |
| 添加 | `PlusOutlined` |
| 详情 | `EyeOutlined` |
| 删除 | `DeleteOutlined` |

---

## 10. 代码规范

### 10.1 组件结构

```jsx
// 页面组件标准结构
export default function PageName() {
  // 1. 状态定义
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  
  // 2. 数据获取
  const fetchData = async () => { ... }
  useEffect(() => { fetchData() }, [])
  
  // 3. 事件处理
  const handleClick = () => { ... }
  
  // 4. 渲染
  return (
    <div style={{ padding: '0 4px' }}>
      {/* 顶部操作栏 */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space><Icon /> <Text strong>标题</Text></Space>
        <Space><Button>操作</Button></Space>
      </div>
      
      {/* 内容区 */}
      <Card size="small">
        {/* 内容 */}
      </Card>
    </div>
  )
}
```

### 10.2 样式写法

```jsx
// ✅ 推荐：行内样式（组件级别）
<div style={{ padding: 16, background: '#fff' }}>

// ✅ 推荐：常量定义（复用样式）
const cardStyle = { background: '#ffffff', border: '1px solid #e8e8e8' }

// ⚠️ 避免：内联复杂样式
<div style={{ 
  padding: 16, 
  background: '#fff',
  borderRadius: 8,
  boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
  border: '1px solid #e8e8e8',
}}>

// ✅ 复杂样式用 className
<div className="custom-card">
```

### 10.3 禁止事项

| ❌ 禁止 | ✅ 替代 |
|---------|---------|
| 深色背景 `#000`, `#1a1a2e` | 浅色背景 `#ffffff`, `#fafafa` |
| 硬编码魔法数字 | 使用常量或配置 |
| 全局 CSS 覆盖 | 组件级样式 |
| 内联 `!important` | 调整选择器优先级 |

---

## 11. 文件组织

```
frontend/src/
├── pages/           # 页面组件（每个主菜单一个文件）
│   ├── MarketOverview.jsx
│   ├── SectorFlow.jsx
│   ├── StockFlow.jsx
│   ├── StockScreener.jsx
│   ├── StrategyDashboard.jsx
│   ├── SmartAnalysis.jsx
│   ├── Watchlist.jsx
│   └── ActivityLog.jsx
├── components/      # 可复用组件
│   ├── MarketIndex.jsx
│   ├── LimitStats.jsx
│   └── ...
├── services/        # API 调用
│   └── api.js
├── App.jsx          # 主入口 + 路由
└── main.jsx         # 应用入口
```

---

## 12. 新功能检查清单

开发新功能前，确认以下事项：

- [ ] 背景色是否使用浅色系？
- [ ] 文字颜色与背景对比度是否足够？
- [ ] 是否使用了规范的圆角（8px 卡片、6px 按钮）？
- [ ] 表格是否配置了分页？
- [ ] 加载状态是否有 loading 提示？
- [ ] 操作成功/失败是否有反馈？
- [ ] 空数据是否有 Empty 组件？
- [ ] 图表配色是否符合规范？
- [ ] 是否复用了现有组件？

---

*本规范由 AI 助手生成，项目迭代过程中持续更新。*
