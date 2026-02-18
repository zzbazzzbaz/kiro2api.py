import { useState, useEffect, useCallback } from 'react'
import { groups } from '@/api/client'
import { toast } from 'sonner'
import { extractErrorMessage, formatDateTime } from '@/lib/utils'
import { Plus, RefreshCw, Pencil, Trash2, X } from 'lucide-react'

export function GroupsPage() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editGroup, setEditGroup] = useState(null)

  const fetchList = useCallback(async () => {
    setLoading(true)
    try {
      const data = await groups.list()
      setList(data)
    } catch (err) {
      toast.error(`加载分组失败: ${extractErrorMessage(err)}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchList() }, [fetchList])

  const handleDelete = async (id) => {
    if (!confirm('确定要删除此分组？')) return
    try {
      await groups.delete(id)
      toast.success('已删除')
      fetchList()
    } catch (err) { toast.error(extractErrorMessage(err)) }
  }

  const openCreate = () => { setEditGroup(null); setDialogOpen(true) }
  const openEdit = (g) => { setEditGroup(g); setDialogOpen(true) }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">分组管理</h1>
        <div className="flex gap-2">
          <button onClick={fetchList} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent transition-colors text-foreground">
            <RefreshCw className="h-3.5 w-3.5" /> 刷新
          </button>
          <button onClick={openCreate} className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity">
            <Plus className="h-3.5 w-3.5" /> 创建分组
          </button>
        </div>
      </div>

      {list.length === 0 ? (
        <div className="bg-card border border-border rounded-lg p-12 text-center text-muted-foreground">
          暂无分组
        </div>
      ) : (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">ID</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">名称</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">描述</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">负载均衡</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">凭据</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">Key</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">创建时间</th>
                  <th className="text-right px-4 py-3 font-medium text-muted-foreground">操作</th>
                </tr>
              </thead>
              <tbody>
                {list.map(g => (
                  <tr key={g.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-mono text-muted-foreground">#{g.id}</td>
                    <td className="px-4 py-3 text-foreground font-medium">{g.name}</td>
                    <td className="px-4 py-3 text-muted-foreground">{g.description || '-'}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-1.5 py-0.5 rounded bg-accent text-accent-foreground">
                        {g.load_balancing_mode || '全局'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-foreground">{g.credential_count}</td>
                    <td className="px-4 py-3 text-right text-foreground">{g.api_key_count}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{formatDateTime(g.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1 justify-end">
                        <button onClick={() => openEdit(g)} className="px-2 py-1 text-xs bg-accent text-accent-foreground rounded hover:opacity-80 transition-opacity">
                          编辑
                        </button>
                        <button onClick={() => handleDelete(g.id)} className="px-2 py-1 text-xs bg-destructive/10 text-destructive rounded hover:opacity-80 transition-opacity">
                          删除
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

      <GroupDialog
        open={dialogOpen}
        editGroup={editGroup}
        onClose={() => setDialogOpen(false)}
        onSuccess={fetchList}
      />
    </div>
  )
}

function GroupDialog({ open, editGroup, onClose, onSuccess }) {
  const [form, setForm] = useState({ name: '', description: '', load_balancing_mode: '' })
  const [submitting, setSubmitting] = useState(false)
  const isEdit = !!editGroup

  useEffect(() => {
    if (editGroup) {
      setForm({
        name: editGroup.name || '',
        description: editGroup.description || '',
        load_balancing_mode: editGroup.load_balancing_mode || '',
      })
    } else {
      setForm({ name: '', description: '', load_balancing_mode: '' })
    }
  }, [editGroup, open])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) { toast.error('请输入分组名称'); return }

    setSubmitting(true)
    try {
      const payload = { name: form.name.trim() }
      if (form.description.trim()) payload.description = form.description.trim()
      if (form.load_balancing_mode) payload.load_balancing_mode = form.load_balancing_mode

      if (isEdit) {
        await groups.update(editGroup.id, payload)
        toast.success('分组已更新')
      } else {
        await groups.create(payload)
        toast.success('分组已创建')
      }
      onSuccess()
      onClose()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  const inputCls = 'w-full px-3 py-1.5 bg-background border border-border rounded-md text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/50'
  const labelCls = 'block text-sm font-medium text-foreground mb-1'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-md m-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">{isEdit ? '编辑分组' : '创建分组'}</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className={labelCls}>名称 *</label>
            <input
              type="text"
              value={form.name}
              onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
              className={inputCls}
              autoFocus
            />
          </div>
          <div>
            <label className={labelCls}>描述</label>
            <input
              type="text"
              value={form.description}
              onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>负载均衡模式</label>
            <select
              value={form.load_balancing_mode}
              onChange={e => setForm(prev => ({ ...prev, load_balancing_mode: e.target.value }))}
              className={inputCls}
            >
              <option value="">使用全局配置</option>
              <option value="priority">优先级模式</option>
              <option value="balanced">均衡负载</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {submitting ? '提交中...' : (isEdit ? '更新' : '创建')}
          </button>
        </form>
      </div>
    </div>
  )
}
