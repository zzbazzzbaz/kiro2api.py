import { useState, useEffect, useCallback } from 'react'
import { credentials } from '@/api/client'
import { toast } from 'sonner'
import { extractErrorMessage } from '@/lib/utils'
import { Plus, RefreshCw, Trash2, RotateCcw } from 'lucide-react'
import { CredentialCard } from './CredentialCard'
import { AddCredentialDialog } from './AddCredentialDialog'
import { BalanceDialog } from './BalanceDialog'

export function CredentialsPage() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [balanceOpen, setBalanceOpen] = useState(false)
  const [balanceId, setBalanceId] = useState(null)
  const [selectedIds, setSelectedIds] = useState(new Set())

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

  const handleDisable = async (id) => {
    try {
      await credentials.disable(id)
      toast.success('已禁用')
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  const handleEnable = async (id) => {
    try {
      await credentials.enable(id)
      toast.success('已启用')
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  const handleReset = async (id) => {
    try {
      await credentials.reset(id)
      toast.success('已重置并启用')
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定要删除此凭据？此操作无法撤销。')) return
    try {
      await credentials.delete(id)
      toast.success('已删除')
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  const handleSetPriority = async (id, priority) => {
    try {
      await credentials.setPriority(id, priority)
      toast.success(`优先级已设置为 ${priority}`)
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  const handleViewBalance = (id) => {
    setBalanceId(id)
    setBalanceOpen(true)
  }

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleBatchDelete = async () => {
    const disabled = [...selectedIds].filter(id => list.find(c => c.id === id)?.is_disabled)
    if (disabled.length === 0) { toast.error('选中项中没有已禁用凭据'); return }
    if (!confirm(`确定要删除 ${disabled.length} 个已禁用凭据？`)) return

    let ok = 0, fail = 0
    for (const id of disabled) {
      try { await credentials.delete(id); ok++ } catch { fail++ }
    }
    toast.success(`删除完成: 成功 ${ok}, 失败 ${fail}`)
    setSelectedIds(new Set())
    fetchList()
  }

  const handleBatchReset = async () => {
    const failed = [...selectedIds].filter(id => list.find(c => c.id === id)?.fail_count > 0)
    if (failed.length === 0) { toast.error('选中项中没有失败凭据'); return }

    let ok = 0, fail = 0
    for (const id of failed) {
      try { await credentials.reset(id); ok++ } catch { fail++ }
    }
    toast.success(`重置完成: 成功 ${ok}, 失败 ${fail}`)
    setSelectedIds(new Set())
    fetchList()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-foreground">凭据管理</h1>
          {selectedIds.size > 0 && (
            <span className="text-sm bg-accent text-accent-foreground px-2 py-1 rounded">
              已选 {selectedIds.size}
            </span>
          )}
        </div>
        <div className="flex gap-2 flex-wrap">
          {selectedIds.size > 0 && (
            <>
              <button onClick={handleBatchReset} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent transition-colors text-foreground">
                <RotateCcw className="h-3.5 w-3.5" /> 批量恢复
              </button>
              <button onClick={handleBatchDelete} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-destructive/50 text-destructive rounded-md hover:bg-destructive/10 transition-colors">
                <Trash2 className="h-3.5 w-3.5" /> 批量删除
              </button>
              <button onClick={() => setSelectedIds(new Set())} className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
                取消选择
              </button>
            </>
          )}
          <button onClick={fetchList} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent transition-colors text-foreground">
            <RefreshCw className="h-3.5 w-3.5" /> 刷新
          </button>
          <button onClick={() => setAddOpen(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity">
            <Plus className="h-3.5 w-3.5" /> 添加凭据
          </button>
        </div>
      </div>

      {list.length === 0 ? (
        <div className="bg-card border border-border rounded-lg p-12 text-center text-muted-foreground">
          暂无凭据，点击上方「添加凭据」开始
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {list.map(cred => (
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
              onViewBalance={() => handleViewBalance(cred.id)}
            />
          ))}
        </div>
      )}

      <AddCredentialDialog open={addOpen} onClose={() => setAddOpen(false)} onSuccess={fetchList} />
      <BalanceDialog credentialId={balanceId} open={balanceOpen} onClose={() => setBalanceOpen(false)} />
    </div>
  )
}
