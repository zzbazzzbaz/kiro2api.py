import { useState } from 'react'
import { credentials } from '@/api/client'
import { toast } from 'sonner'
import { extractErrorMessage } from '@/lib/utils'
import { X } from 'lucide-react'

export function AddCredentialDialog({ open, onClose, onSuccess }) {
  const [authMethod, setAuthMethod] = useState('social')
  const [form, setForm] = useState({
    refresh_token: '',
    client_id: '',
    client_secret: '',
    profile_arn: '',
    group_id: '',
    priority: '0',
    region: '',
    auth_region: '',
    api_region: '',
    machine_id: '',
    proxy_url: '',
    proxy_username: '',
    proxy_password: '',
  })
  const [submitting, setSubmitting] = useState(false)

  const updateField = (field, value) => setForm(prev => ({ ...prev, [field]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.refresh_token.trim()) {
      toast.error('请输入 Refresh Token')
      return
    }

    setSubmitting(true)
    try {
      const payload = {
        refresh_token: form.refresh_token.trim(),
        auth_method: authMethod,
        priority: parseInt(form.priority, 10) || 0,
      }
      if (authMethod === 'idc') {
        if (!form.client_id.trim() || !form.client_secret.trim()) {
          toast.error('IdC 认证需要 Client ID 和 Client Secret')
          setSubmitting(false)
          return
        }
        payload.client_id = form.client_id.trim()
        payload.client_secret = form.client_secret.trim()
      }
      if (form.profile_arn.trim()) payload.profile_arn = form.profile_arn.trim()
      if (form.group_id) payload.group_id = parseInt(form.group_id, 10)
      if (form.region.trim()) payload.region = form.region.trim()
      if (form.auth_region.trim()) payload.auth_region = form.auth_region.trim()
      if (form.api_region.trim()) payload.api_region = form.api_region.trim()
      if (form.machine_id.trim()) payload.machine_id = form.machine_id.trim()
      if (form.proxy_url.trim()) payload.proxy_url = form.proxy_url.trim()
      if (form.proxy_username.trim()) payload.proxy_username = form.proxy_username.trim()
      if (form.proxy_password.trim()) payload.proxy_password = form.proxy_password.trim()

      const result = await credentials.add(payload)
      toast.success(`凭据已添加 (ID: ${result.id})`)
      onSuccess()
      onClose()
      // 重置表单
      setForm({
        refresh_token: '', client_id: '', client_secret: '', profile_arn: '',
        group_id: '', priority: '0', region: '', auth_region: '', api_region: '',
        machine_id: '', proxy_url: '', proxy_username: '', proxy_password: '',
      })
    } catch (err) {
      toast.error(`添加失败: ${extractErrorMessage(err)}`)
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  const inputCls = 'w-full px-3 py-1.5 bg-background border border-border rounded-md text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/50'
  const labelCls = 'block text-sm font-medium text-foreground mb-1'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-lg max-h-[85vh] overflow-y-auto m-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-border sticky top-0 bg-card z-10">
          <h2 className="text-lg font-semibold text-foreground">添加凭据</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* 认证方式 */}
          <div>
            <label className={labelCls}>认证方式</label>
            <div className="flex gap-2">
              {['social', 'idc'].map(m => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setAuthMethod(m)}
                  className={`px-4 py-1.5 text-sm rounded-md border transition-colors ${
                    authMethod === m
                      ? 'border-primary bg-primary/10 text-primary font-medium'
                      : 'border-border text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {m === 'social' ? 'Social' : 'IdC (BuilderId)'}
                </button>
              ))}
            </div>
          </div>

          {/* Refresh Token */}
          <div>
            <label className={labelCls}>Refresh Token *</label>
            <textarea
              value={form.refresh_token}
              onChange={e => updateField('refresh_token', e.target.value)}
              rows={3}
              className={inputCls + ' resize-none'}
              placeholder="粘贴 refresh_token..."
            />
          </div>

          {/* IdC 专用字段 */}
          {authMethod === 'idc' && (
            <>
              <div>
                <label className={labelCls}>Client ID *</label>
                <input type="text" value={form.client_id} onChange={e => updateField('client_id', e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Client Secret *</label>
                <textarea value={form.client_secret} onChange={e => updateField('client_secret', e.target.value)} rows={2} className={inputCls + ' resize-none'} />
              </div>
            </>
          )}

          {/* 可选字段 */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>优先级</label>
              <input type="number" value={form.priority} onChange={e => updateField('priority', e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>分组 ID</label>
              <input type="number" value={form.group_id} onChange={e => updateField('group_id', e.target.value)} className={inputCls} placeholder="留空为默认" />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className={labelCls}>Region</label>
              <input type="text" value={form.region} onChange={e => updateField('region', e.target.value)} className={inputCls} placeholder="us-east-1" />
            </div>
            <div>
              <label className={labelCls}>Auth Region</label>
              <input type="text" value={form.auth_region} onChange={e => updateField('auth_region', e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>API Region</label>
              <input type="text" value={form.api_region} onChange={e => updateField('api_region', e.target.value)} className={inputCls} />
            </div>
          </div>

          <div>
            <label className={labelCls}>代理 URL</label>
            <input type="text" value={form.proxy_url} onChange={e => updateField('proxy_url', e.target.value)} className={inputCls} placeholder="socks5://127.0.0.1:1080" />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {submitting ? '添加中...' : '添加凭据'}
          </button>
        </form>
      </div>
    </div>
  )
}
