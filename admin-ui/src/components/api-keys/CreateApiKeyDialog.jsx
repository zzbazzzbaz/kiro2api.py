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
    if (createdKey && !copied) {
      if (!confirm('你还没有复制 API Key，确定要关闭吗？关闭后无法再获取。')) return
    }
    setCreatedKey(null)
    setCopied(false)
    setForm({ name: '', group_id: '', token_quota: '0' })
    onClose()
  }

  // 创建成功后的保存界面 — 全屏遮罩，醒目展示
  if (createdKey) {
    return (
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70">
        <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-lg m-4 overflow-hidden">
          {/* 头部 */}
          <div className="bg-green-500/10 px-6 py-5 border-b border-green-500/20">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
                <Check className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-foreground">API Key 创建成功</h2>
                <p className="text-xs text-muted-foreground">请立即复制并妥善保存，此密钥仅显示一次</p>
              </div>
            </div>
          </div>

          <div className="px-6 py-5 space-y-5">
            {/* Key 展示区 */}
            <div>
              <label className="block text-xs font-medium text-muted-foreground mb-1.5">API Key</label>
              <div className="flex items-stretch gap-2">
                <code className="flex-1 bg-muted border border-border rounded-lg px-4 py-3 text-sm font-mono text-foreground break-all select-all leading-relaxed">
                  {createdKey.raw_key}
                </code>
                <button
                  onClick={handleCopy}
                  className={`shrink-0 px-4 rounded-lg font-medium text-sm transition-all ${
                    copied
                      ? 'bg-green-500 text-white'
                      : 'bg-primary text-primary-foreground hover:opacity-90'
                  }`}
                >
                  {copied ? (
                    <div className="flex items-center gap-1.5"><Check className="h-4 w-4" /> 已复制</div>
                  ) : (
                    <div className="flex items-center gap-1.5"><Copy className="h-4 w-4" /> 复制</div>
                  )}
                </button>
              </div>
            </div>

            {/* 详情 */}
            <div className="bg-muted/50 rounded-lg px-4 py-3 space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">ID</span>
                <span className="text-foreground font-mono">#{createdKey.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">名称</span>
                <span className="text-foreground">{createdKey.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">分组</span>
                <span className="text-foreground">{createdKey.group_id != null ? `#${createdKey.group_id}` : '全局'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Token 额度</span>
                <span className="text-foreground">{createdKey.token_quota === 0 ? '无限制' : createdKey.token_quota?.toLocaleString()}</span>
              </div>
            </div>

            {/* 警告 */}
            <div className="flex items-start gap-2 text-xs text-orange-600 dark:text-orange-400 bg-orange-500/5 border border-orange-500/20 rounded-lg px-3 py-2">
              <span className="shrink-0 mt-0.5">⚠️</span>
              <span>数据库中仅存储此 Key 的 SHA-256 哈希值，关闭此窗口后将无法再次获取原始密钥。</span>
            </div>

            <button
              onClick={handleClose}
              className="w-full py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
            >
              {copied ? '已保存，关闭' : '我已保存，关闭'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!open) return null

  const inputCls = 'w-full px-3 py-1.5 bg-background border border-border rounded-md text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/50'
  const labelCls = 'block text-sm font-medium text-foreground mb-1'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={handleClose}>
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-md m-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">创建 API Key</h2>
          <button onClick={handleClose} className="text-muted-foreground hover:text-foreground">
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
              placeholder="如: 测试 Key"
              autoFocus
            />
          </div>
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
            <div className="flex flex-wrap gap-1.5 mb-2">
              {[
                { label: '无限制', value: '0' },
                { label: '10K', value: '10000' },
                { label: '50K', value: '50000' },
                { label: '100K', value: '100000' },
                { label: '500K', value: '500000' },
                { label: '1M', value: '1000000' },
                { label: '5M', value: '5000000' },
                { label: '10M', value: '10000000' },
              ].map(preset => (
                <button
                  key={preset.value}
                  type="button"
                  onClick={() => setForm(prev => ({ ...prev, token_quota: preset.value }))}
                  className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                    form.token_quota === preset.value
                      ? 'border-primary bg-primary/10 text-primary font-medium'
                      : 'border-border text-muted-foreground hover:text-foreground hover:border-foreground/30'
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <input
              type="number"
              value={form.token_quota}
              onChange={e => setForm(prev => ({ ...prev, token_quota: e.target.value }))}
              className={inputCls}
              placeholder="0 = 无限制，或输入自定义值"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {submitting ? '创建中...' : '创建'}
          </button>
        </form>
      </div>
    </div>
  )
}
