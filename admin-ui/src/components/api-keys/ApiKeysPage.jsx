import { useState, useEffect, useCallback } from 'react'
import { apiKeys } from '@/api/client'
import { toast } from 'sonner'
import { extractErrorMessage, formatDateTime } from '@/lib/utils'
import { Plus, RefreshCw } from 'lucide-react'
import { CreateApiKeyDialog } from './CreateApiKeyDialog'

export function ApiKeysPage() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [editingQuota, setEditingQuota] = useState(null)
  const [quotaVal, setQuotaVal] = useState('')
  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiKeys.list()
      setList(data)
    } catch (err) {
      toast.error(`加载 API Key 失败: ${extractErrorMessage(err)}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchList() }, [fetchList])

  const handleToggleEnabled = async (key) => {
    try {
      if (key.is_enabled) {
        await apiKeys.disable(key.id)
        toast.success('已禁用')
      } else {
        await apiKeys.enable(key.id)
        toast.success('已启用')
      }
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  const handleDelete = async (id) => {
    if (!confirm('确定要吊销此 API Key？此操作无法撤销。')) return
    try {
      await apiKeys.delete(id)
      toast.success('已吊销')
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  const handleResetUsage = async (id) => {
    try {
      await apiKeys.resetUsage(id)
      toast.success('已用量已重置')
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  const handleSetQuota = async (id) => {
    const q = parseInt(quotaVal, 10)
    if (isNaN(q) || q < 0) { toast.error('请输入有效的额度值'); return }
    try {
      await apiKeys.setQuota(id, q)
      toast.success(`额度已设置为 ${q === 0 ? '无限制' : q}`)
      setEditingQuota(null)
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  return (
    <>
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-foreground">API Key 管理</h1>
            <div className="flex gap-2">
              <button onClick={fetchList} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent transition-colors text-foreground">
                <RefreshCw className="h-3.5 w-3.5" /> 刷新
              </button>
              <button onClick={() => setCreateOpen(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity">
                <Plus className="h-3.5 w-3.5" /> 创建 Key
              </button>
            </div>
          </div>

          {list.length === 0 ? (
            <div className="bg-card border border-border rounded-lg p-12 text-center text-muted-foreground">
              暂无 API Key
            </div>
          ) : (
            <div className="bg-card border border-border rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">ID</th>
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">名称</th>
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">分组</th>
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">状态</th>
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground min-w-[200px]">用量</th>
                      <th className="text-right px-4 py-3 font-medium text-muted-foreground">请求</th>
                      <th className="text-left px-4 py-3 font-medium text-muted-foreground">最后使用</th>
                      <th className="text-right px-4 py-3 font-medium text-muted-foreground">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map(key => (
                      <tr key={key.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3 font-mono text-muted-foreground">#{key.id}</td>
                        <td className="px-4 py-3 text-foreground">{key.name}</td>
                        <td className="px-4 py-3 text-foreground">{key.group_id != null ? `#${key.group_id}` : '全局'}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                            key.is_enabled
                              ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                              : 'bg-destructive/10 text-destructive'
                          }`}>
                            {key.is_enabled ? '启用' : '禁用'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {(() => {
                            const used = key.tokens_used || 0
                            const quota = key.token_quota || 0
                            const isUnlimited = quota === 0
                            const percent = isUnlimited ? 0 : Math.min(100, used / quota * 100)
                            const barColor = percent > 80 ? 'bg-red-500' : percent > 50 ? 'bg-yellow-500' : 'bg-blue-500'
                            return (
                              <div>
                                <div className="flex items-center justify-between text-xs mb-1">
                                  <span className="text-foreground">{used.toLocaleString()}</span>
                                  {editingQuota === key.id ? (
                                    <div className="flex items-center gap-1">
                                      <input
                                        type="number"
                                        value={quotaVal}
                                        onChange={e => setQuotaVal(e.target.value)}
                                        onKeyDown={e => {
                                          if (e.key === 'Enter') handleSetQuota(key.id)
                                          if (e.key === 'Escape') setEditingQuota(null)
                                        }}
                                        className="w-20 px-1.5 py-0.5 text-xs bg-background border border-border rounded text-right text-foreground"
                                        autoFocus
                                      />
                                      <button onClick={() => handleSetQuota(key.id)} className="text-xs text-primary hover:underline">确定</button>
                                    </div>
                                  ) : (
                                    <button
                                      onClick={() => { setEditingQuota(key.id); setQuotaVal(String(quota)) }}
                                      className="text-muted-foreground hover:text-primary transition-colors"
                                    >
                                      / {isUnlimited ? '∞' : quota.toLocaleString()}
                                    </button>
                                  )}
                                </div>
                                <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full transition-all ${isUnlimited ? 'bg-blue-500/30' : barColor}`}
                                    style={{ width: isUnlimited ? '100%' : `${percent}%` }}
                                  />
                                </div>
                              </div>
                            )
                          })()}
                        </td>
                        <td className="px-4 py-3 text-right text-foreground">{key.request_count}</td>
                        <td className="px-4 py-3 text-muted-foreground text-xs">{formatDateTime(key.last_used_at)}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1 justify-end">
                            <button
                              onClick={() => handleToggleEnabled(key)}
                              className={`px-2 py-1 text-xs rounded transition-colors ${
                                key.is_enabled
                                  ? 'bg-destructive/10 text-destructive hover:opacity-80'
                                  : 'bg-green-500/10 text-green-600 dark:text-green-400 hover:opacity-80'
                              }`}
                            >
                              {key.is_enabled ? '禁用' : '启用'}
                            </button>
                            <button onClick={() => handleResetUsage(key.id)} className="px-2 py-1 text-xs bg-accent text-accent-foreground rounded hover:opacity-80 transition-opacity">
                              重置
                            </button>
                            <button onClick={() => handleDelete(key.id)} className="px-2 py-1 text-xs bg-destructive/10 text-destructive rounded hover:opacity-80 transition-opacity">
                              吊销
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      <CreateApiKeyDialog open={createOpen} onClose={() => setCreateOpen(false)} onSuccess={fetchList} />
    </>
  )
}
