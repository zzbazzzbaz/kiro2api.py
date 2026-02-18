import { useState } from 'react'
import { cn, formatDateTime, formatNumber } from '@/lib/utils'
import {
  Ban, Check, RotateCcw, Trash2, RefreshCw, ChevronDown, ChevronUp,
} from 'lucide-react'

export function CredentialCard({
  credential: c,
  selected,
  onToggleSelect,
  onDisable,
  onEnable,
  onReset,
  onDelete,
  onSetPriority,
  balance,
  loadingBalance,
  onRefreshBalance,
}) {
  const [editingPriority, setEditingPriority] = useState(false)
  const [priorityVal, setPriorityVal] = useState(c.priority)
  const [expanded, setExpanded] = useState(false)

  const handlePrioritySubmit = () => {
    const p = parseInt(priorityVal, 10)
    if (!isNaN(p) && p !== c.priority) onSetPriority(p)
    setEditingPriority(false)
  }

  const usagePercent = balance?.usage_percentage ?? 0
  const barColor = usagePercent > 80 ? 'bg-red-500' : usagePercent > 50 ? 'bg-yellow-500' : 'bg-green-500'

  return (
    <div className={cn(
      'bg-card border rounded-lg p-4 transition-all',
      selected ? 'border-primary ring-1 ring-primary/30' : 'border-border',
      c.is_disabled && 'opacity-60'
    )}>
      {/* 顶部行 */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="rounded border-border"
          />
          <span className="text-sm font-mono text-muted-foreground">#{c.id}</span>
          <span className={cn(
            'text-xs px-1.5 py-0.5 rounded font-medium',
            c.is_disabled
              ? 'bg-destructive/10 text-destructive'
              : 'bg-green-500/10 text-green-600 dark:text-green-400'
          )}>
            {c.is_disabled ? '已禁用' : '正常'}
          </span>
          {c.subscription_title && (
            <span className={cn(
              'text-xs px-1.5 py-0.5 rounded font-medium',
              c.subscription_title?.includes('PRO')
                ? 'bg-purple-500/10 text-purple-600 dark:text-purple-400'
                : 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
            )}>
              {c.subscription_title}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onRefreshBalance}
            disabled={loadingBalance}
            className="text-muted-foreground hover:text-foreground p-0.5"
            title="刷新额度"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', loadingBalance && 'animate-spin')} />
          </button>
          <button onClick={() => setExpanded(!expanded)} className="text-muted-foreground hover:text-foreground p-0.5">
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* 额度信息（内联） */}
      {balance && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-muted-foreground">
              {formatNumber(balance.current_usage)} / {formatNumber(balance.usage_limit)}
            </span>
            <span className={cn(
              'font-medium',
              usagePercent > 80 ? 'text-red-500' : usagePercent > 50 ? 'text-yellow-500' : 'text-green-500'
            )}>
              剩余 {formatNumber(balance.remaining)}
            </span>
          </div>
          <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className={cn('h-full rounded-full transition-all', barColor)}
              style={{ width: `${Math.min(100, usagePercent)}%` }}
            />
          </div>
        </div>
      )}
      {loadingBalance && !balance && (
        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          <div className="animate-spin rounded-full h-3 w-3 border-b border-primary" />
          查询中...
        </div>
      )}

      {/* 核心信息 */}
      <div className="mt-2.5 space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">邮箱</span>
          <span className="text-foreground truncate ml-2 max-w-[200px]">{c.email || '-'}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-muted-foreground">优先级</span>
          {editingPriority ? (
            <input
              type="number"
              value={priorityVal}
              onChange={(e) => setPriorityVal(e.target.value)}
              onBlur={handlePrioritySubmit}
              onKeyDown={(e) => e.key === 'Enter' && handlePrioritySubmit()}
              className="w-16 px-1.5 py-0.5 text-sm bg-background border border-border rounded text-foreground text-right"
              autoFocus
            />
          ) : (
            <button
              onClick={() => { setPriorityVal(c.priority); setEditingPriority(true) }}
              className="text-foreground hover:text-primary transition-colors"
            >
              {c.priority}
            </button>
          )}
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">认证</span>
          <span className="text-foreground">{c.auth_method || '-'}</span>
        </div>
        {c.fail_count > 0 && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">失败</span>
            <span className="text-destructive font-medium">{c.fail_count}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-muted-foreground">最后使用</span>
          <span className="text-foreground text-xs">{formatDateTime(c.last_used_at)}</span>
        </div>
      </div>

      {/* 展开详情 */}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-border space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">分组</span>
            <span className="text-foreground">{c.group_id != null ? `#${c.group_id}` : '默认'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Region</span>
            <span className="text-foreground">{c.region || '-'}</span>
          </div>
          {c.auth_region && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Auth Region</span>
              <span className="text-foreground">{c.auth_region}</span>
            </div>
          )}
          {c.api_region && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">API Region</span>
              <span className="text-foreground">{c.api_region}</span>
            </div>
          )}
          {c.proxy_url && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">代理</span>
              <span className="text-foreground truncate ml-2 max-w-[180px]">{c.proxy_url}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-muted-foreground">Token 过期</span>
            <span className="text-foreground text-xs">{formatDateTime(c.expires_at)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">创建时间</span>
            <span className="text-foreground text-xs">{formatDateTime(c.created_at)}</span>
          </div>
          {balance?.free_trial_info?.freeTrialStatus === 'ACTIVE' && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Free Trial</span>
              <span className="text-blue-500 text-xs">
                {formatNumber(balance.free_trial_info.currentUsageWithPrecision || 0)} / {formatNumber(balance.free_trial_info.usageLimitWithPrecision || 0)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* 操作按钮 */}
      <div className="mt-2.5 pt-2.5 border-t border-border flex gap-1.5 flex-wrap">
        {c.is_disabled ? (
          <button
            onClick={onEnable}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-green-500/10 text-green-600 dark:text-green-400 rounded hover:opacity-80 transition-opacity"
          >
            <Check className="h-3 w-3" /> 启用
          </button>
        ) : (
          <button
            onClick={onDisable}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-destructive/10 text-destructive rounded hover:opacity-80 transition-opacity"
          >
            <Ban className="h-3 w-3" /> 禁用
          </button>
        )}
        {c.fail_count > 0 && (
          <button
            onClick={onReset}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-orange-500/10 text-orange-600 dark:text-orange-400 rounded hover:opacity-80 transition-opacity"
          >
            <RotateCcw className="h-3 w-3" /> 重置
          </button>
        )}
        {c.is_disabled && (
          <button
            onClick={onDelete}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-destructive/10 text-destructive rounded hover:opacity-80 transition-opacity"
          >
            <Trash2 className="h-3 w-3" /> 删除
          </button>
        )}
      </div>
    </div>
  )
}
