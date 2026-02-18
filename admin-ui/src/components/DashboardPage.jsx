import { useState, useEffect } from 'react'
import { credentials, apiKeys, groups, config } from '@/api/client'
import { Shield, KeyRound, FolderOpen, Activity } from 'lucide-react'
import { toast } from 'sonner'
import { extractErrorMessage } from '@/lib/utils'

export function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [lbMode, setLbMode] = useState(null)
  const [loading, setLoading] = useState(true)
  const [switching, setSwitching] = useState(false)

  const fetchStats = async () => {
    setLoading(true)
    try {
      const [creds, keys, grps, cfg] = await Promise.all([
        credentials.list(),
        apiKeys.list(),
        groups.list(),
        config.getLoadBalancingMode(),
      ])

      setStats({
        totalCredentials: creds.length,
        availableCredentials: creds.filter(c => !c.is_disabled).length,
        disabledCredentials: creds.filter(c => c.is_disabled).length,
        totalApiKeys: keys.length,
        enabledApiKeys: keys.filter(k => k.is_enabled).length,
        totalGroups: grps.length,
      })
      setLbMode(cfg.mode)
    } catch (err) {
      toast.error(`加载失败: ${extractErrorMessage(err)}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchStats() }, [])

  const handleToggleLbMode = async () => {
    const newMode = lbMode === 'priority' ? 'balanced' : 'priority'
    setSwitching(true)
    try {
      await config.setLoadBalancingMode(newMode)
      setLbMode(newMode)
      toast.success(`已切换到${newMode === 'priority' ? '优先级模式' : '均衡负载模式'}`)
    } catch (err) {
      toast.error(`切换失败: ${extractErrorMessage(err)}`)
    } finally {
      setSwitching(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  const cards = [
    {
      icon: Shield,
      label: '凭据总数',
      value: stats?.totalCredentials ?? 0,
      sub: `${stats?.availableCredentials ?? 0} 可用 / ${stats?.disabledCredentials ?? 0} 已禁用`,
      color: 'text-blue-500',
    },
    {
      icon: KeyRound,
      label: 'API Key',
      value: stats?.totalApiKeys ?? 0,
      sub: `${stats?.enabledApiKeys ?? 0} 已启用`,
      color: 'text-green-500',
    },
    {
      icon: FolderOpen,
      label: '分组',
      value: stats?.totalGroups ?? 0,
      sub: '凭据分组',
      color: 'text-purple-500',
    },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-foreground">总览</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <div key={card.label} className="bg-card border border-border rounded-lg p-5">
            <div className="flex items-center gap-3 mb-3">
              <card.icon className={`h-5 w-5 ${card.color}`} />
              <span className="text-sm text-muted-foreground">{card.label}</span>
            </div>
            <div className="text-3xl font-bold text-foreground">{card.value}</div>
            <div className="text-sm text-muted-foreground mt-1">{card.sub}</div>
          </div>
        ))}
      </div>

      {/* 负载均衡模式 */}
      <div className="bg-card border border-border rounded-lg p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="h-5 w-5 text-orange-500" />
            <div>
              <div className="font-medium text-foreground">负载均衡模式</div>
              <div className="text-sm text-muted-foreground">
                {lbMode === 'priority'
                  ? '优先级模式 — 始终使用优先级最高的可用凭据'
                  : '均衡负载 — 选择使用次数最少的凭据，平均分配请求'
                }
              </div>
            </div>
          </div>
          <button
            onClick={handleToggleLbMode}
            disabled={switching}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {switching ? '切换中...' : (lbMode === 'priority' ? '切换到均衡' : '切换到优先级')}
          </button>
        </div>
      </div>
    </div>
  )
}
