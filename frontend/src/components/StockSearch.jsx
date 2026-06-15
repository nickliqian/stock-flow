import React, { useState, useCallback, useRef, useEffect } from 'react'
import { Input, Card, List, Typography, Spin } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { searchStocks, searchSectors } from '../services/api'
import { debounce } from '../utils/format'

const { Text } = Typography

/**
 * 搜索框组件
 * 使用 antd Input + Dropdown
 */
export default function StockSearch({ type = 'stock', onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [loading, setLoading] = useState(false)
  const wrapperRef = useRef(null)

  useEffect(() => {
    function handleClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const doSearch = useCallback(
    debounce(async (value) => {
      if (!value || value.trim().length === 0) {
        setResults([])
        setShowDropdown(false)
        setLoading(false)
        return
      }
      setLoading(true)
      try {
        const apiFn = type === 'sector' ? searchSectors : searchStocks
        const res = await apiFn(value.trim())
        const data = res
        setResults(Array.isArray(data) ? data : [])
        setShowDropdown(true)
      } catch (err) {
        console.error('搜索失败:', err)
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300),
    [type]
  )

  const handleChange = (e) => {
    const value = e.target.value
    setQuery(value)
    setLoading(true)
    doSearch(value)
  }

  const handleClear = () => {
    setQuery('')
    setResults([])
    setShowDropdown(false)
  }

  const handleSelect = (item) => {
    setQuery(type === 'stock' ? `${item.name || item.symbol}` : item.sector_name)
    setShowDropdown(false)
    onSelect && onSelect(item)
  }

  const placeholder = type === 'stock' ? '搜索股票代码或名称...' : '搜索板块名称...'

  return (
    <div ref={wrapperRef} style={{ position: 'relative', marginBottom: 12 }}>
      <Input
        prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
        placeholder={placeholder}
        value={query}
        onChange={handleChange}
        allowClear
        onClear={handleClear}
        size="large"
      />

      {showDropdown && (
        <Card
          size="small"
          style={{
            position: 'absolute',
            top: 44,
            left: 0,
            right: 0,
            zIndex: 1000,
            maxHeight: 300,
            overflow: 'auto',
          }}
          bodyStyle={{ padding: 0 }}
        >
          {loading && (
            <div style={{ padding: 16, textAlign: 'center' }}>
              <Spin size="small" />
            </div>
          )}
          {!loading && results.length === 0 && (
            <div style={{ padding: 16, textAlign: 'center', color: '#8c8c8c', fontSize: 13 }}>
              未找到相关结果
            </div>
          )}
          {!loading && results.map((item, idx) => (
            <div
              key={item.ts_code || item.sector_code || idx}
              onClick={() => handleSelect(item)}
              style={{
                padding: '10px 16px',
                borderBottom: '1px solid #f0f0f0',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = '#f5f5f5' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = '#fff' }}
            >
              <Text strong style={{ fontSize: 13 }}>
                {type === 'stock' ? item.name : item.sector_name}
              </Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {type === 'stock' ? item.ts_code : item.sector_code}
                {item.industry ? ` · ${item.industry}` : ''}
              </Text>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
