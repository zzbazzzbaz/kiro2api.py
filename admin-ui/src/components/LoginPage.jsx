import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { setAuth, clearAuth } from '@/api/client'
import { Server } from 'lucide-react'
import { toast } from 'sonner'
import { extractErrorMessage } from '@/lib/utils'

export function LoginPage() {
  const { login } = useAuth()
  const [baseUrl, setBaseUrl] = useState(window.location.origin)
  const [adminKey, setAdminKey] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!adminKey.trim()) {
      toast.error('请输入 Admin API Key')
      return
    }

    setLoading(true)
    const url = baseUrl.replace(/\/$/, '')
    const key = adminKey.trim()

    // 先临时写入 localStorage 供 fetch 使用，但不触发登录状态
    setAuth(url, key)
    try {
      // 用一次实际请求验证连接
      const resp = await fetch(`${url}/api/admin/credentials`, {
        headers: { 'x-api-key': key },
      })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw data
      }
      toast.success('登录成功')
      login(url, key) // 验证通过后再切换到 Dashboard
    } catch (err) {
      clearAuth()
      setLoading(false)
      toast.error(`连接失败: ${extractErrorMessage(err)}`)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <div className="w-full max-w-md">
        <div className="bg-card border border-border rounded-lg shadow-lg p-8">
          <div className="flex items-center justify-center gap-3 mb-8">
            <Server className="h-8 w-8 text-primary" />
            <h1 className="text-2xl font-bold text-foreground">kiro2api Admin</h1>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                后端地址
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="http://127.0.0.1:8000"
                className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                Admin API Key
              </label>
              <input
                type="password"
                value={adminKey}
                onChange={(e) => setAdminKey(e.target.value)}
                placeholder="输入 Admin API Key"
                className="w-full px-3 py-2 bg-background border border-border rounded-md text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                autoFocus
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 px-4 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {loading ? '连接中...' : '登录'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
