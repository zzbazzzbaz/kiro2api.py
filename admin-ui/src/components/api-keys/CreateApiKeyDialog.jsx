import { useState } from 'react'
import { apiKeys } from '@/api/client'
import { toast } from 'sonner'
import { extractErrorMessage } from '@/lib/utils'
import { X, Copy, Check } from 'lucide-react'

export function CreateApiKeyDialog({ open, onClose, onSuccess }) {
  const [form, setForm] = useState({ name: '', group_id: '', token_quota: '0' })
  const [submitting, setSubmitting] = useState(false)
  const [createdKey, setCreatedKey] = useState(null)
  const [copied, setCopied] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.name.trim()) { toast.error('请输入 Key 名称'); return }

    setSubmitting(true)
    try {
      const payload = {
        name: form.name.trim(),
        token_quota: parseInt(form.token_quota, 10) || 0,
      }
      if (form.group_id) payload.group_id = parseInt(form.group_id, 10)

      const result = await apiKeys.create(payload)
      setCreatedKey(result)
      onSuccess()
    } catch (err) {
      toast.error(`创建失败: ${extractErrorMessage(err)}`)
    } finally {
      setSubmitting(false)
    }
  }

  const handleCopy = async () => {
    if (!createdKey?.raw_key) return
    try {
      await navigator.clipboard.writeText(createdKey.raw_key)
      setCopied(true)
      toast.success('已复制到剪贴板')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('复制失败')
    }
  }

  const handleClose = () => {
    setCreatedKey(null)
    setCopied(false)
    setForm({ name: '', group_id: '', token_quota: '0' })
    onClose()
  }

  if (!open) return null

  const inputCls = 'w-full px-3 py-1.5 bg-background border border-border rounded-md text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/50'
  const labelCls = 'block text-sm font-medium text-foreground mb-1'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={handleClose}>
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-md m-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">
            {createdKey ? '创建成功' : '创建 API Key'}
          </h2>
          <button onClick={handleClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-4">
          {createdKey ? (
            <div className="space-y-4">
              <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4">
                <div className="text-sm font-medium text-green-600 dark:text-green-400 mb-2">
                  API Key 已创建，请立即保存！
                </div>
                <div className="text-xs text-muted-foreground mb-3">
                  此密钥仅显示一次，关闭后无法再次获取。
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 bg-background border border-border rounded px-3 py-2 text-sm font-mono text-foreground break-all select-all">
                    {createdKey.raw_key}
                  </code>
                  <button
                    onClick={handleCopy}
                    className="shrink-0 p-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity"
                  >
                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="text-sm space-y-1">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">名称</span>
                  <span className="text-foreground">{createdKey.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">ID</span>
                  <span className="text-foreground">#{createdKey.id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">分组</span>
                  <span className="text-foreground">{createdKey.group_id != null ? `#${createdKey.group_id}` : '全局'}</span>
                </div>
              </div>

              <button
                onClick={handleClose}
                className="w-full py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 transition-opacity"
              >
                已保存，关闭
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className={labelCls}>名称 *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
                  className={inputCls}
                  placeholder="如: 测试 Key"
                  autoFocus
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>分组 ID</label>
                  <input
                    type="number"
                    value={form.group_id}
                    onChange={e => setForm(prev => ({ ...prev, group_id: e.target.value }))}
                    className={inputCls}
                    placeholder="留空为全局"
                  />
                </div>
                <div>
                  <label className={labelCls}>Token 额度</label>
                  <input
                    type="number"
                    value={form.token_quota}
                    onChange={e => setForm(prev => ({ ...prev, token_quota: e.target.value }))}
                    className={inputCls}
                    placeholder="0 = 无限制"
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                {submitting ? '创建中...' : '创建'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
