import { useState } from 'react'
import { cn, formatDateTime, formatNumber, formatTimestamp } from '@/lib/utils'
import {
  Ban, Check, RotateCcw, Trash2, RefreshCw, ChevronDown, ChevronUp,
  Globe, Shield, Clock, AlertTriangle,
} from 'lucide-react'

function Row({ label, value, mono, danger, truncate }) {
  return (
    <div className="flex justify-between items-center gap-2">
      <span className="text-muted-foreground text-xs shrink-0">{label}</span>
      <span className={cn(
        'text-xs text-right',
        danger ? 'text-destructive font-medium' : 'text-foreground',
        mono && 'font-mono',
        truncate && 'truncate max-w-[180px]',
      )}>
        {value ?? '-'}
      </span>
    </div>
  )
}

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
      'bg-card border rounded-lg transition-all',
      selected ? 'border-primary ring-1 ring-primary/30' : 'border-border',
      c.is_disabled && 'opacity-60'
    )}>
      {/* === 头部：ID + 标签 + 操作 === */}
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          <input type="checkbox" checked={selected} onChange={onToggleSelect} className="rounded border-border shrink-0" />
          <span className="text-xs font-mono text-muted-foreground">#{c.id}</span>
          <span className={cn(
            'text-[10px] px-1.5 py-0.5 rounded font-medium leading-none',
            c.is_disabled ? 'bg-destructive/10 text-destructive' : 'bg-green-500/10 text-green-600 dark:text-green-400'
          )}>
            {c.is_disabled ? '禁用' : '正常'}
          </span>
          {c.subscription_title && (
            <span className={cn(
              'text-[10px] px-1.5 py-0.5 rounded font-medium leading-none',
              c.subscription_title?.includes('PRO') ? 'bg-purple-500/10 text-purple-600 dark:text-purple-400' : 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
            )}>
              {c.subscription_title}
            </span>
          )}
          {c.fail_count > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded font-medium leading-none bg-orange-500/10 text-orange-600 dark:text-orange-400">
              {c.fail_count} 失败
            </span>
          )}
        </div>
        <div className="flex items-center gap-0.5 shrink-0">
          <button onClick={onRefreshBalance} disabled={loadingBalance} className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-accent" title="查询余额">
            <RefreshCw className={cn('h-3 w-3', loadingBalance && 'animate-spin')} />
          </button>
          <button onClick={() => setExpanded(!expanded)} className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-accent">
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>
      </div>

      <div className="px-3 py-2 space-y-2">
        {/* === 额度进度条 === */}
        {balance ? (
          <div>
            <div className="flex items-center justify-between text-[11px] mb-0.5">
              <span className="text-muted-foreground">
                已用 {formatNumber(balance.current_usage)} / {formatNumber(balance.usage_limit)}
              </span>
              <span className={cn('font-medium', usagePercent > 80 ? 'text-red-500' : usagePercent > 50 ? 'text-yellow-500' : 'text-green-500')}>
                剩余 {formatNumber(balance.remaining)} ({formatNumber(100 - usagePercent)}%)
              </span>
            </div>
            <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
              <div className={cn('h-full rounded-full transition-all', barColor)} style={{ width: `${Math.min(100, usagePercent)}%` }} />
            </div>
            {balance.next_reset_at && (
              <div className="text-[10px] text-muted-foreground mt-0.5">
                重置: {formatTimestamp(balance.next_reset_at)}
              </div>
            )}
          </div>
        ) : loadingBalance ? (
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <div className="animate-spin rounded-full h-2.5 w-2.5 border-b border-primary" /> 查询余额中...
          </div>
        ) : null}

        {/* === 核心字段 === */}
        <div className="space-y-0.5">
          <Row label="邮箱" value={c.email} truncate />
          <Row label="认证" value={c.auth_method} />
          <div className="flex justify-between items-center gap-2">
            <span className="text-muted-foreground text-xs shrink-0">优先级</span>
            {editingPriority ? (
              <input
                type="number" value={priorityVal}
                onChange={(e) => setPriorityVal(e.target.value)}
                onBlur={handlePrioritySubmit}
                onKeyDown={(e) => e.key === 'Enter' && handlePrioritySubmit()}
                className="w-14 px-1 py-0 text-xs bg-background border border-border rounded text-foreground text-right"
                autoFocus
              />
            ) : (
              <button onClick={() => { setPriorityVal(c.priority); setEditingPriority(true) }}
                className="text-xs text-foreground hover:text-primary transition-colors">
                {c.priority}
              </button>
            )}
          </div>
          <Row label="分组" value={c.group_id != null ? `#${c.group_id}` : '默认'} />
          <Row label="最后使用" value={formatDateTime(c.last_used_at)} />
        </div>

        {/* === 展开：完整字段 === */}
        {expanded && (
          <div className="pt-1.5 border-t border-border space-y-0.5">
            <Row label="Region" value={c.region} mono />
            <Row label="Auth Region" value={c.auth_region || '← Region'} mono />
            <Row label="API Region" value={c.api_region || '← 全局'} mono />
            <Row label="Machine ID" value={c.machine_id} truncate mono />
            <Row label="代理" value={c.proxy_url} truncate mono />
            <Row label="Token 过期" value={formatDateTime(c.expires_at)} />
            <Row label="创建时间" value={formatDateTime(c.created_at)} />
            {c.fail_count > 0 && <Row label="失败次数" value={c.fail_count} danger />}
            {balance?.free_trial_info?.freeTrialStatus === 'ACTIVE' && (
              <Row label="Free Trial" value={`${formatNumber(balance.free_trial_info.currentUsageWithPrecision || 0)} / ${formatNumber(balance.free_trial_info.usageLimitWithPrecision || 0)}`} />
            )}
          </div>
        )}
      </div>

      {/* === 操作栏 === */}
      <div className="px-3 py-1.5 border-t border-border flex gap-1 flex-wrap">
        {c.is_disabled ? (
          <button onClick={onEnable} className="flex items-center gap-1 px-2 py-0.5 text-[11px] bg-green-500/10 text-green-600 dark:text-green-400 rounded hover:opacity-80">
            <Check className="h-2.5 w-2.5" /> 启用
          </button>
        ) : (
          <button onClick={onDisable} className="flex items-center gap-1 px-2 py-0.5 text-[11px] bg-destructive/10 text-destructive rounded hover:opacity-80">
            <Ban className="h-2.5 w-2.5" /> 禁用
          </button>
        )}
        {c.fail_count > 0 && (
          <button onClick={onReset} className="flex items-center gap-1 px-2 py-0.5 text-[11px] bg-orange-500/10 text-orange-600 dark:text-orange-400 rounded hover:opacity-80">
            <RotateCcw className="h-2.5 w-2.5" /> 重置
          </button>
        )}
        {c.is_disabled && (
          <button onClick={onDelete} className="flex items-center gap-1 px-2 py-0.5 text-[11px] bg-destructive/10 text-destructive rounded hover:opacity-80">
            <Trash2 className="h-2.5 w-2.5" /> 删除
          </button>
        )}
      </div>
    </div>
  )
}
