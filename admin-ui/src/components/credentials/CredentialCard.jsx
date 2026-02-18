import { useState } from 'react'
import { cn, formatDateTime } from '@/lib/utils'
import {
  Ban, Check, RotateCcw, Trash2, BarChart3, ChevronDown, ChevronUp,
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
  onViewBalance,
}) {
  const [editingPriority, setEditingPriority] = useState(false)
  const [priorityVal, setPriorityVal] = useState(c.priority)
  const [expanded, setExpanded] = useState(false)

  const handlePrioritySubmit = () => {
    const p = parseInt(priorityVal, 10)
    if (!isNaN(p) && p !== c.priority) onSetPriority(p)
    setEditingPriority(false)
  }

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
        </div>
        <button onClick={() => setExpanded(!expanded)} className="text-muted-foreground hover:text-foreground shrink-0">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {/* 核心信息 */}
      <div className="mt-3 space-y-1.5 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">邮箱</span>
          <span className="text-foreground truncate ml-2 max-w-[200px]">{c.email || '-'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">订阅</span>
          <span className={cn(
            'font-medium',
            c.subscription_title?.includes('PRO') ? 'text-purple-500' : 'text-foreground'
          )}>
            {c.subscription_title || '-'}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-muted-foreground">优先级</span>
          {editingPriority ? (
            <div className="flex items-center gap-1">
              <input
                type="number"
                value={priorityVal}
                onChange={(e) => setPriorityVal(e.target.value)}
                onBlur={handlePrioritySubmit}
                onKeyDown={(e) => e.key === 'Enter' && handlePrioritySubmit()}
                className="w-16 px-1.5 py-0.5 text-sm bg-background border border-border rounded text-foreground text-right"
                autoFocus
              />
            </div>
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
          <span className="text-muted-foreground">认证方式</span>
          <span className="text-foreground">{c.auth_method || '-'}</span>
        </div>
        {c.fail_count > 0 && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">失败次数</span>
            <span className="text-destructive font-medium">{c.fail_count}</span>
          </div>
        )}
      </div>

      {/* 展开详情 */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-border space-y-1.5 text-sm">
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
            <span className="text-muted-foreground">最后使用</span>
            <span className="text-foreground">{formatDateTime(c.last_used_at)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Token 过期</span>
            <span className="text-foreground">{formatDateTime(c.expires_at)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">创建时间</span>
            <span className="text-foreground">{formatDateTime(c.created_at)}</span>
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="mt-3 pt-3 border-t border-border flex gap-1.5 flex-wrap">
        <button
          onClick={onViewBalance}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-accent text-accent-foreground rounded hover:opacity-80 transition-opacity"
        >
          <BarChart3 className="h-3 w-3" /> 余额
        </button>
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
