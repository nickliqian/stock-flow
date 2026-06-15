import React, { useState, useEffect, useCallback } from 'react'
import { Card, Tree, Spin, Typography, Breadcrumb, Empty, Space, Tag } from 'antd'
import {
  FolderOutlined,
  FileTextOutlined,
  FileOutlined,
  BookOutlined,
  HomeOutlined,
} from '@ant-design/icons'

const { Text } = Typography

/** 后端 API 基础路径 */
const API_BASE = '/api/research-browser'

/**
 * 将后端返回的目录树转换为 antd Tree 组件需要的 treeData 格式
 */
function convertToTreeData(nodes) {
  if (!nodes || !Array.isArray(nodes.children)) return []
  return nodes.children.map((node) => {
    const isDir = node.type === 'dir'
    const isMd = node.name.endsWith('.md')
    const isTxt = node.name.endsWith('.txt')
    return {
      title: (
        <span style={{ fontSize: 13 }}>
          {isDir ? (
            <FolderOutlined style={{ color: '#faad14', marginRight: 4 }} />
          ) : isMd ? (
            <FileTextOutlined style={{ color: '#1677ff', marginRight: 4 }} />
          ) : isTxt ? (
            <FileOutlined style={{ color: '#8c8c8c', marginRight: 4 }} />
          ) : (
            <FileOutlined style={{ color: '#bfbfbf', marginRight: 4 }} />
          )}
          {node.name}
        </span>
      ),
      key: node.path,
      isLeaf: !isDir,
      children: isDir ? convertToTreeData(node) : undefined,
      _raw: node, // 保留原始数据，方便后续使用
    }
  })
}

/**
 * 格式化文件大小
 */
function formatSize(bytes) {
  if (bytes == null) return '--'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * 简易 Markdown 渲染 — 将 Markdown 转为简单 HTML
 * 不引入额外依赖，覆盖常用语法即可
 */
function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    // 代码块（先处理，避免内部被干扰）
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>')
    // 行内代码
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // 标题
    .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // 粗体 / 斜体
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // 链接
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // 无序列表
    .replace(/^[ \t]*[-*] (.+)$/gm, '<li>$1</li>')
    // 引用块
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    // 水平分割线
    .replace(/^---+$/gm, '<hr />')
    // 行内图片（简化处理）
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2" style="max-width:100%" />')
    // 段落（连续非空行包 <p>）
    .replace(/\n\n/g, '</p><p>')
    // 单换行 → <br>
    .replace(/\n/g, '<br />')

  return `<p>${html}</p>`
}

/**
 * 研究资料浏览器主组件
 *
 * 左侧 30%：目录树（antd Tree）
 * 右侧 70%：Markdown 文件内容渲染
 * 顶部：当前路径面包屑
 */
export default function ResearchBrowser() {
  // 目录树数据（原始格式）
  const [treeData, setTreeData] = useState(null)
  const [treeLoading, setTreeLoading] = useState(true)

  // 选中的文件路径
  const [selectedFile, setSelectedFile] = useState(null)

  // 文件内容
  const [fileContent, setFileContent] = useState(null)
  const [fileLoading, setFileLoading] = useState(false)

  /** 加载目录树 */
  useEffect(() => {
    const controller = new AbortController()
    const fetchTree = async () => {
      setTreeLoading(true)
      try {
        const resp = await fetch(`${API_BASE}/tree`, { signal: controller.signal })
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
        const data = await resp.json()
        setTreeData(data)
      } catch (err) {
        if (err.name === 'AbortError') return
        console.error('加载目录树失败:', err)
      } finally {
        setTreeLoading(false)
      }
    }
    fetchTree()
    return () => controller.abort()
  }, [])

  /** 点击文件 → 加载内容 */
  const handleFileSelect = useCallback(async (selectedKeys) => {
    const filePath = selectedKeys[0]
    if (!filePath) return
    setSelectedFile(filePath)
    setFileContent(null)
    setFileLoading(true)
    try {
      const resp = await fetch(`${API_BASE}/file?path=${encodeURIComponent(filePath)}`)
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${resp.status}`)
      }
      const data = await resp.json()
      setFileContent(data)
    } catch (err) {
      console.error('加载文件失败:', err)
      setFileContent({ error: err.message })
    } finally {
      setFileLoading(false)
    }
  }, [])

  /** 面包屑路径分段 */
  const breadcrumbItems = selectedFile
    ? [
        { title: <HomeOutlined /> },
        ...selectedFile.split('/').map((seg) => ({ title: seg })),
      ]
    : [{ title: <HomeOutlined /> }, { title: '研究资料' }]

  return (
    <div style={{ height: 'calc(100vh - 100px)', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部标题 + 面包屑 */}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Space>
          <BookOutlined style={{ fontSize: 18 }} />
          <Text strong style={{ fontSize: 16 }}>研究资料</Text>
        </Space>
        <Breadcrumb items={breadcrumbItems} />
      </div>

      {/* 主体：左右分栏 */}
      <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 0 }}>
        {/* 左侧：目录树 */}
        <Card
          size="small"
          style={{ width: '30%', minWidth: 240, overflow: 'auto' }}
          bodyStyle={{ padding: 8 }}
          title={
            <Space size={4}>
              <FolderOutlined />
              <Text strong style={{ fontSize: 13 }}>目录</Text>
            </Space>
          }
        >
          <Spin spinning={treeLoading}>
            {treeData ? (
              <Tree
                showIcon={false}
                defaultExpandAll={false}
                defaultExpandedKeys={['raw', 'insights', 'logs']}
                onSelect={(keys) => {
                  // 只在选中文件时加载内容（目录不处理）
                  if (keys.length > 0) {
                    const key = keys[0]
                    const node = findNode(treeData, key)
                    if (node && node.type === 'file') {
                      handleFileSelect(keys)
                    }
                  }
                }}
                treeData={convertToTreeData(treeData)}
                style={{ fontSize: 13 }}
              />
            ) : !treeLoading ? (
              <Empty description="暂无数据" />
            ) : null}
          </Spin>
        </Card>

        {/* 右侧：文件内容 */}
        <Card
          size="small"
          style={{ flex: 1, overflow: 'auto' }}
          bodyStyle={{ padding: fileContent && !fileContent.error ? 20 : 16 }}
          title={
            <Space size={4}>
              <FileTextOutlined />
              <Text strong style={{ fontSize: 13 }}>
                {selectedFile ? selectedFile.split('/').pop() : '文件内容'}
              </Text>
              {fileContent && !fileContent.error && (
                <Tag style={{ marginLeft: 8 }}>{formatSize(fileContent.size)}</Tag>
              )}
            </Space>
          }
        >
          <Spin spinning={fileLoading}>
            {!selectedFile ? (
              <Empty description="点击左侧文件查看内容" />
            ) : fileContent?.error ? (
              <Empty description={`加载失败: ${fileContent.error}`} />
            ) : fileContent ? (
              <div>
                {/* 文件元信息 */}
                <div style={{ marginBottom: 12, color: '#8c8c8c', fontSize: 12 }}>
                  修改时间: {fileContent.modified || '--'}
                </div>
                {/* Markdown 内容 */}
                <div
                  style={{
                    lineHeight: 1.8,
                    fontSize: 14,
                    color: '#333',
                    whiteSpace: 'pre-wrap',
                  }}
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(fileContent.content) }}
                />
              </div>
            ) : (
              <Empty description="点击左侧文件查看内容" />
            )}
          </Spin>
        </Card>
      </div>
    </div>
  )
}

/**
 * 在 treeData 中递归查找指定 path 的节点
 */
function findNode(node, targetPath) {
  if (!node) return null
  if (node.path === targetPath) return node
  if (Array.isArray(node.children)) {
    for (const child of node.children) {
      const found = findNode(child, targetPath)
      if (found) return found
    }
  }
  return null
}
