import { useState, useEffect, useCallback } from 'react'
import { credentials } from '@/api/client'
import { toast } from 'sonner'
import { extractErrorMessage } from '@/lib/utils'
import { Plus, RefreshCw, Trash2, RotateCcw, BarChart3, CheckSquare, Square, Ban, Check } from 'lucide-react'
import { CredentialCard } from './CredentialCard'
import { AddCredentialDialog } from './AddCredentialDialog'

export function CredentialsPage() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [balanceMap, setBalanceMap] = useState(new Map())
  const [loadingBalanceIds, setLoadingBalanceIds] = useState(new Set())
  const [queryingAll, setQueryingAll] = useState(false)
  const [queryProgress, setQueryProgress] = useState({ current: 0, total: 0 })
  const [filter, setFilter] = useState('all') // all | enabled | disabled | failed

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await credentials.list()
      setList(data)
    } catch (err) {
      toast.error(`加载凭据失败: ${extractErrorMessage(err)}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchList() }, [fetchList])

  // 统计
  const totalCount = list.length
  const enabledCount = list.filter(c => !c.is_disabled).length
  const disabledCount = list.filter(c => c.is_disabled).length
  const failedCount = list.filter(c => c.fail_count > 0).length

  // 过滤
  const filteredList = list.filter(c => {
    if (filter === 'enabled') return !c.is_disabled
    if (filter === 'disabled') return c.is_disabled
    if (filter === 'failed') return c.fail_count > 0
    return true
  })

  // ===== 操作 =====
  const handleDisable = async (id) => {
    try { await credentials.disable(id); toast.success('已禁用'); fetchList() }
    catch (err) { toast.error(extractErrorMessage(err)) }
  }
  const handleEnable = async (id) => {
    try { await credentials.enable(id); toast.success('已启用'); fetchList() }
    catch (err) { toast.error(extractErrorMessage(err)) }
  }
  const handleReset = async (id) => {
    try { await credentials.reset(id); toast.success('已重置并启用'); fetchList() }
    catch (err) { toast.error(extractErrorMessage(err)) }
  }
  const handleDelete = async (id) => {
    if (!confirm('确定要删除此凭据？需先禁用，此操作无法撤销。')) return
    try { await credentials.delete(id); toast.success('已删除'); fetchList() }
    catch (err) { toast.error(extractErrorMessage(err)) }
  }
  const handleSetPriority = async (id, priority) => {
    try { await credentials.setPriority(id, priority); toast.success(`优先级 → ${priority}`); fetchList() }
    catch (err) { toast.error(extractErrorMessage(err)) }
  }

  // ===== 余额 =====
  const handleFetchBalance = async (id, force = false) => {
    setLoadingBalanceIds(prev => { const s = new Set(prev); s.add(id); return s })
    try {
      const data = await credentials.getBalance(id, force)
      setBalanceMap(prev => { const m = new Map(prev); m.set(id, data); return m })
    } catch (err) {
      toast.error(`#${id} 余额查询失败: ${extractErrorMessage(err)}`)
    } finally {
      setLoadingBalanceIds(prev => { const s = new Set(prev); s.delete(id); return s })
    }
  }

  const handleQueryAllBalances = async () => {
    const targets = filteredList.filter(c => !c.is_disabled)
    if (targets.length === 0) { toast.error('没有可查询的启用凭据'); return }
    setQueryingAll(true)
    setQueryProgress({ current: 0, total: targets.length })
    let ok = 0, fail = 0
    for (let i = 0; i < targets.length; i++) {
      const id = targets[i].id
      setLoadingBalanceIds(prev => { const s = new Set(prev); s.add(id); return s })
      try {
        const data = await credentials.getBalance(id)
        setBalanceMap(prev => { const m = new Map(prev); m.set(id, data); return m })
        ok++
      } catch { fail++ }
      finally { setLoadingBalanceIds(prev => { const s = new Set(prev); s.delete(id); return s }) }
      setQueryProgress({ current: i + 1, total: targets.length })
    }
    setQueryingAll(false)
    toast.success(`查询完成: 成功 ${ok}${fail > 0 ? `, 失败 ${fail}` : ''}`)
  }

  // ===== 选择 =====
  const toggleSelect = (id) => {
    setSelectedIds(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s })
  }
  const selectAll = () => {
    setSelectedIds(new Set(filteredList.map(c => c.id)))
  }
  const deselectAll = () => setSelectedIds(new Set())

  // ===== 批量 =====
  const handleBatchDisable = async () => {
    const targets = [...selectedIds].filter(id => { const c = list.find(x => x.id === id); return c && !c.is_disabled })
    if (targets.length === 0) { toast.error('选中项中没有可禁用凭据'); return }
    let ok = 0, fail = 0
    for (const id of targets) { try { await credentials.disable(id); ok++ } catch { fail++ } }
    toast.success(`禁用完成: 成功 ${ok}${fail ? `, 失败 ${fail}` : ''}`)
    deselectAll(); fetchList()
  }
  const handleBatchEnable = async () => {
    const targets = [...selectedIds].filter(id => { const c = list.find(x => x.id === id); return c && c.is_disabled })
    if (targets.length === 0) { toast.error('选中项中没有可启用凭据'); return }
    let ok = 0, fail = 0
    for (const id of targets) { try { await credentials.enable(id); ok++ } catch { fail++ } }
    toast.success(`启用完成: 成功 ${ok}${fail ? `, 失败 ${fail}` : ''}`)
    deselectAll(); fetchList()
  }
  const handleBatchReset = async () => {
    const targets = [...selectedIds].filter(id => { const c = list.find(x => x.id === id); return c && c.fail_count > 0 })
    if (targets.length === 0) { toast.error('选中项中没有失败凭据'); return }
    let ok = 0, fail = 0
    for (const id of targets) { try { await credentials.reset(id); ok++ } catch { fail++ } }
    toast.success(`重置完成: 成功 ${ok}${fail ? `, 失败 ${fail}` : ''}`)
    deselectAll(); fetchList()
  }
  const handleBatchDelete = async () => {
    const targets = [...selectedIds].filter(id => { const c = list.find(x => x.id === id); return c && c.is_disabled })
    if (targets.length === 0) { toast.error('只能删除已禁用凭据'); return }
    if (!confirm(`确定要删除 ${targets.length} 个已禁用凭据？无法撤销。`)) return
    let ok = 0, fail = 0
    for (const id of targets) { try { await credentials.delete(id); ok++ } catch { fail++ } }
    toast.success(`删除完成: 成功 ${ok}${fail ? `, 失败 ${fail}` : ''}`)
    deselectAll(); fetchList()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  const filterTabs = [
    { id: 'all', label: `全部 (${totalCount})` },
    { id: 'enabled', label: `启用 (${enabledCount})` },
    { id: 'disabled', label: `禁用 (${disabledCount})` },
    { id: 'failed', label: `异常 (${failedCount})` },
  ]

  return (
    <div className="space-y-4">
      {/* 标题 + 操作栏 */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold text-foreground">凭据管理</h1>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={handleQueryAllBalances}
            disabled={queryingAll}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent transition-colors text-foreground disabled:opacity-50"
          >
            <BarChart3 className={`h-3.5 w-3.5 ${queryingAll ? 'animate-pulse' : ''}`} />
            {queryingAll ? `${queryProgress.current}/${queryProgress.total}` : '查询余额'}
          </button>
          <button onClick={fetchList} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent transition-colors text-foreground">
            <RefreshCw className="h-3.5 w-3.5" /> 刷新
          </button>
          <button onClick={() => setAddOpen(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity">
            <Plus className="h-3.5 w-3.5" /> 添加凭据
          </button>
        </div>
      </div>

      {/* 过滤标签 + 选择操作 */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1">
          {filterTabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => { setFilter(tab.id); deselectAll() }}
              className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                filter === tab.id
                  ? 'bg-primary text-primary-foreground font-medium'
                  : 'bg-muted text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {selectedIds.size > 0 ? (
            <>
              <span className="text-xs text-muted-foreground">已选 {selectedIds.size}</span>
              <button onClick={handleBatchEnable} className="flex items-center gap-1 px-2 py-1 text-xs bg-green-500/10 text-green-600 dark:text-green-400 rounded hover:opacity-80">
                <Check className="h-3 w-3" /> 批量启用
              </button>
              <button onClick={handleBatchDisable} className="flex items-center gap-1 px-2 py-1 text-xs bg-orange-500/10 text-orange-600 rounded hover:opacity-80">
                <Ban className="h-3 w-3" /> 批量禁用
              </button>
              <button onClick={handleBatchReset} className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-500/10 text-blue-600 dark:text-blue-400 rounded hover:opacity-80">
                <RotateCcw className="h-3 w-3" /> 批量重置
              </button>
              <button onClick={handleBatchDelete} className="flex items-center gap-1 px-2 py-1 text-xs bg-destructive/10 text-destructive rounded hover:opacity-80">
                <Trash2 className="h-3 w-3" /> 批量删除
              </button>
              <button onClick={deselectAll} className="text-xs text-muted-foreground hover:text-foreground ml-1">取消</button>
            </>
          ) : (
            <button onClick={selectAll} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              <CheckSquare className="h-3 w-3" /> 全选
            </button>
          )}
        </div>
      </div>

      {/* 列表 */}
      {filteredList.length === 0 ? (
        <div className="bg-card border border-border rounded-lg p-12 text-center text-muted-foreground">
          {totalCount === 0 ? '暂无凭据，点击上方「添加凭据」开始' : '当前过滤条件下无凭据'}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filteredList.map(cred => (
            <CredentialCard
              key={cred.id}
              credential={cred}
              selected={selectedIds.has(cred.id)}
              onToggleSelect={() => toggleSelect(cred.id)}
              onDisable={() => handleDisable(cred.id)}
              onEnable={() => handleEnable(cred.id)}
              onReset={() => handleReset(cred.id)}
              onDelete={() => handleDelete(cred.id)}
              onSetPriority={(p) => handleSetPriority(cred.id, p)}
              balance={balanceMap.get(cred.id) || null}
              loadingBalance={loadingBalanceIds.has(cred.id)}
              onRefreshBalance={() => handleFetchBalance(cred.id, true)}
            />
          ))}
        </div>
      )}

      <AddCredentialDialog open={addOpen} onClose={() => setAddOpen(false)} onSuccess={fetchList} />
    </div>
  )
}
