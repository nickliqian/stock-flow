import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { Card, Input, Table, Tag, Button, Space, Spin, Empty, Typography, Tooltip, Pagination, Tabs } from 'antd'
import { SearchOutlined, StarOutlined, StarFilled, ArrowUpOutlined, ArrowDownOutlined, SwapOutlined, AppstoreOutlined, FundOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { formatAmount, getColorClass, getColor, getSign, debounce } from '../utils/format'
import { getSectors, getSectorMembers, searchSectors } from '../services/api'
import SectorDetail from '../components/SectorDetail'
import SectorRotation from './SectorRotation'
import ConceptBoard from './ConceptBoard'

const { Text } = Typography

const PINNED_KEY = 'stock_flow_pinned_sectors'

/**
 * 板块资金流向页面（含子 Tab：板块流向 / 板块轮动 / 概念板块）
 */
export default function SectorFlow({ tradeDate, onSelectStock }) {
  const [activeTab, setActiveTab] = useState('flow')

  const tradeDateLabel = (() => {
    if (!tradeDate) return null
    const s = String(tradeDate).replace(/-/g, '')
    const today = new Date()
    const todayStr = `${today.getFullYear()}${String(today.getMonth()+1).padStart(2,'0')}${String(today.getDate()).padStart(2,'0')}`
    if (s === todayStr) return '今日'
    return `${s.slice(4,6)}-${s.slice(6,8)}`
  })()

  return (
    <>
      {tradeDateLabel && (
        <div style={{ marginBottom: 8, textAlign: 'right' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            <ClockCircleOutlined style={{ marginRight: 4 }} />
            数据日期: {tradeDateLabel}
          </Text>
        </div>
      )}
      <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      type="card"
      items={[
        {
          key: 'flow',
          label: <span><FundOutlined /> 板块流向</span>,
          children: <SectorFlowContent tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
        {
          key: 'rotation',
          label: <span><SwapOutlined /> 板块轮动</span>,
          children: <SectorRotation tradeDate={tradeDate} onSelectStock={onSelectStock} />,
        },
        {
          key: 'concept',
          label: <span><AppstoreOutlined /> 概念板块</span>,
          children: <ConceptBoard onSelectStock={onSelectStock} />,
        },
      ]}
    />
    </>
  )
}

/** 板块流向子组件 */
function SectorFlowContent({ tradeDate, onSelectStock }) {
  const [sectors, setSectors] = useState([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sortBy, setSortBy] = useState('net_inflow')
  const [sortDir, setSortDir] = useState('desc')
  const [pinnedCodes, setPinnedCodes] = useState(() => {
    try {
      const saved = localStorage.getItem(PINNED_KEY)
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [isSearching, setIsSearching] = useState(false)

  // Detail view state
  const [selectedSector, setSelectedSector] = useState(null)
  const [detailMembers, setDetailMembers] = useState([])
  const [detailLoading, setDetailLoading] = useState(false)

  const size = 20

  useEffect(() => {
    localStorage.setItem(PINNED_KEY, JSON.stringify(pinnedCodes))
  }, [pinnedCodes])

  const fetchData = useCallback(async (pageNum, signal) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getSectors(pageNum, size, tradeDate, sortDir, sortBy, { signal })
      setSectors(data.data || [])
      setTotal(data.total || 0)
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('加载板块数据失败:', err)
      setError('数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [tradeDate, sortDir, sortBy])

  useEffect(() => {
    const controller = new AbortController()
    fetchData(page, controller.signal)
    return () => controller.abort()
  }, [page, fetchData])

  // 用 ref 持有最新的 tradeDate，确保 debounce 实例内始终读取最新值
  const tradeDateRef = useRef(tradeDate)
  tradeDateRef.current = tradeDate

  // debounce 只创建一次，避免 tradeDate 变化时创建新实例导致旧 timer 竞态
  const debouncedSearch = useMemo(
    () =>
      debounce(async (query) => {
        if (!query || query.trim().length === 0) {
          setSearchResults([])
          setIsSearching(false)
          setSearchLoading(false)
          return
        }
        setSearchLoading(true)
        try {
          const results = await searchSectors(query.trim(), tradeDateRef.current)
          setSearchResults(Array.isArray(results) ? results : [])
          setIsSearching(true)
        } catch (err) {
          if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
          console.error('搜索失败:', err)
          setSearchResults([])
        } finally {
          setSearchLoading(false)
        }
      }, 300),
    [], // 稳定引用，不随 tradeDate 变化
  )

  // 组件卸载时取消 pending 的 debounce timer
  useEffect(() => {
    return () => {
      debouncedSearch.cancel()
    }
  }, [debouncedSearch])

  const handleSearchChange = (e) => {
    const value = e.target.value
    setSearchQuery(value)
    if (value.trim().length > 0) {
      debouncedSearch(value)
    } else {
      setSearchResults([])
      setIsSearching(false)
    }
  }

  const handleClearSearch = () => {
    setSearchQuery('')
    setSearchResults([])
    setIsSearching(false)
  }

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(field)
      setSortDir('desc')
    }
    setPage(1)
  }

  const handleTogglePin = (code, e) => {
    e.stopPropagation()
    setPinnedCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [code, ...prev]
    )
  }

  const handleSectorClick = async (sector) => {
    setSelectedSector(sector)
    setDetailLoading(true)
    setDetailMembers([])
    window.scrollTo({ top: 0, behavior: 'smooth' })
    try {
      const data = await getSectorMembers(sector.sector_code)
      setDetailMembers(data.members || [])
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return
      console.error('加载成分股失败:', err)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleCloseDetail = () => {
    setSelectedSector(null)
    setDetailMembers([])
  }

  // 后端已排序，前端不再重复排序，直接使用 sectors 数据
  const pinnedSectors = sectors.filter((s) => pinnedCodes.includes(s.sector_code))
  const unpinnedSectors = sectors.filter((s) => !pinnedCodes.includes(s.sector_code))
  const displaySectors = [...pinnedSectors, ...unpinnedSectors]

  const showSearchResults = isSearching && searchQuery.trim().length > 0
  const displayData = showSearchResults ? searchResults : displaySectors

  // Detail view
  if (selectedSector) {
    return (
      <div className="page-content">
        <SectorDetail
          sector={selectedSector}
          members={detailMembers}
          loading={detailLoading}
          onClose={handleCloseDetail}
          onSelectStock={onSelectStock}
        />
      </div>
    )
  }

  // List view columns
  const columns = [
    ...(!showSearchResults ? [{
      title: '',
      key: 'pin',
      width: 40,
      render: (_, record) => {
        const isPinned = pinnedCodes.includes(record.sector_code)
        return (
          <span
            onClick={(e) => handleTogglePin(record.sector_code, e)}
            style={{ cursor: 'pointer', fontSize: 16, color: isPinned ? '#faad14' : '#d9d9d9' }}
          >
            {isPinned ? <StarFilled /> : <StarOutlined />}
          </span>
        )
      },
    }] : []),
    {
      title: '板块名称',
      key: 'sector_name',
      sorter: !showSearchResults,
      render: (_, record) => (
        <Text strong style={{ fontSize: 13 }}>{record.sector_name}</Text>
      ),
    },
    {
      title: (
        <span
          style={{ cursor: 'pointer' }}
          onClick={() => handleSort('net_inflow')}
        >
          主力净流入 {sortBy === 'net_inflow' && (sortDir === 'asc' ? '↑' : '↓')}
        </span>
      ),
      key: 'net_inflow',
      align: 'right',
      render: (_, record) => (
        <Text style={{ color: getColor(record.net_inflow), fontWeight: 500, fontSize: 13 }}>
          {getSign(record.net_inflow)}{formatAmount(record.net_inflow)}
        </Text>
      ),
    },
    {
      title: (
        <span
          style={{ cursor: 'pointer' }}
          onClick={() => handleSort('large_net')}
        >
          大单净流入 {sortBy === 'large_net' && (sortDir === 'asc' ? '↑' : '↓')}
        </span>
      ),
      key: 'large_net',
      align: 'right',
      render: (_, record) => (
        <Text style={{ color: getColor(record.large_net), fontSize: 13 }}>
          {getSign(record.large_net)}{formatAmount(record.large_net)}
        </Text>
      ),
    },
    {
      title: '领涨股',
      key: 'lead_stock',
      render: (_, record) => (
        <div>
          <Text style={{ fontSize: 12 }}>{record.lead_stock_name || record.lead_stock || '--'}</Text>
          <Text style={{ marginLeft: 4, fontSize: 11, color: getColor(record.lead_chg) }}>
            {record.lead_chg != null ? `${getSign(record.lead_chg)}${record.lead_chg.toFixed(2)}%` : ''}
          </Text>
        </div>
      ),
    },
  ]

  if (loading && sectors.length === 0 && !isSearching) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <Spin size="large" tip="加载中..." />
      </div>
    )
  }

  if (error) {
    return (
      <Card>
        <Empty description={error}>
          <Button type="primary" danger onClick={() => fetchData(page)}>
            重新加载
          </Button>
        </Empty>
      </Card>
    )
  }

  return (
    <div>
      {/* Search bar */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Input
          prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
          placeholder="搜索板块名称或代码..."
          value={searchQuery}
          onChange={handleSearchChange}
          allowClear
          onClear={handleClearSearch}
          size="large"
        />
        {showSearchResults && (
          <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
            找到 {searchResults.length} 个结果
          </Text>
        )}
      </Card>

      {/* Info bar */}
      {!showSearchResults && (
        <Card size="small" style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            点击 ★ 置顶关注板块 · 点击行查看趋势 · 共 {total} 个板块
            · 排序: {sortBy === 'net_inflow' ? '主力净流入' : sortBy === 'large_net' ? '大单净流入' : '板块名称'}
            {sortDir === 'asc' ? ' ↑' : ' ↓'}
          </Text>
          {pinnedCodes.length > 0 && (
            <Text style={{ fontSize: 12, color: '#faad14', marginLeft: 12 }}>
              ★ 已置顶 {pinnedCodes.length} 个板块
            </Text>
          )}
        </Card>
      )}

      {/* Data table */}
      <Card size="small" bodyStyle={{ padding: 0 }}>
        <Spin spinning={searchLoading}>
          <Table
            dataSource={displayData}
            columns={columns}
            rowKey={(record) => record.sector_code}
            pagination={false}
            size="small"
            locale={{ emptyText: showSearchResults ? `未找到"${searchQuery}"相关的板块` : '暂无板块数据' }}
            onRow={(record) => ({
              onClick: () => handleSectorClick(record),
              style: { cursor: 'pointer' },
            })}
            scroll={{ x: 600 }}
          />
        </Spin>
      </Card>

      {/* Pagination */}
      {!showSearchResults && total > size && (
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 12 }}>
          <Pagination
            current={page}
            total={total}
            pageSize={size}
            onChange={(p) => {
              setPage(p)
              window.scrollTo({ top: 0, behavior: 'smooth' })
            }}
            showSizeChanger={false}
            showTotal={(total) => `共 ${total} 条`}
            size="small"
          />
        </div>
      )}
    </div>
  )
}
