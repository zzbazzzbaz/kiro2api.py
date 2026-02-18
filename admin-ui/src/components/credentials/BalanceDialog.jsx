import { useState, useEffect } from 'react'
import { credentials } from '@/api/client'
import { toast } from 'sonner'
import { extractErrorMessage, formatNumber, formatTimestamp } from '@/lib/utils'
import { X, RefreshCw } from 'lucide-react'

export function BalanceDialog({ credentialId, open, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchBalance = async (force = false) => {
    if (!credentialId) return
    setLoading(true)
    try {
      const result = await credentials.getBalance(credentialId, force)
      setData(result)
    } catch (err) {
      toast.error(`查询余额失败: ${extractErrorMessage(err)}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open && credentialId) fetchBalance()
  }, [open, credentialId])

  if (!open) return null

  const usagePercent = data?.usage_percentage ?? 0
  const barColor = usagePercent > 80 ? 'bg-red-500' : usagePercent > 50 ? 'bg-yellow-500' : 'bg-green-500'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-card border border-border rounded-lg shadow-xl w-full max-w-md m-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">
            凭据 #{credentialId} 余额
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchBalance(true)}
              disabled={loading}
              className="text-muted-foreground hover:text-foreground"
              title="强制刷新"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="p-4">
          {loading && !data ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : data ? (
            <div className="space-y-4">
              {/* 订阅类型 */}
              <div className="text-center">
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                  data.subscription_title?.includes('PRO')
                    ? 'bg-purple-500/10 text-purple-600 dark:text-purple-400'
                    : 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
                }`}>
                  {data.subscription_title || '未知'}
                </span>
                {data.cached && (
                  <span className="ml-2 text-xs text-muted-foreground">(缓存)</span>
                )}
              </div>

              {/* 使用量进度条 */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-muted-foreground">使用量</span>
                  <span className="text-foreground font-medium">{formatNumber(usagePercent)}%</span>
                </div>
                <div className="w-full h-3 bg-muted rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${barColor}`}
                    style={{ width: `${Math.min(100, usagePercent)}%` }}
                  />
                </div>
              </div>

              {/* 数值详情 */}
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-muted/50 rounded-lg p-3">
                  <div className="text-xl font-bold text-foreground">{formatNumber(data.current_usage)}</div>
                  <div className="text-xs text-muted-foreground">已使用</div>
                </div>
                <div className="bg-muted/50 rounded-lg p-3">
                  <div className="text-xl font-bold text-foreground">{formatNumber(data.usage_limit)}</div>
                  <div className="text-xs text-muted-foreground">总额度</div>
                </div>
                <div className="bg-muted/50 rounded-lg p-3">
                  <div className="text-xl font-bold text-green-600 dark:text-green-400">{formatNumber(data.remaining)}</div>
                  <div className="text-xs text-muted-foreground">剩余</div>
                </div>
              </div>

              {/* 重置时间 */}
              {data.next_reset_at && (
                <div className="text-center text-sm text-muted-foreground">
                  下次重置: {formatTimestamp(data.next_reset_at)}
                </div>
              )}

              {/* Free Trial 信息 */}
              {data.free_trial_info && data.free_trial_info.freeTrialStatus === 'ACTIVE' && (
                <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3 text-sm">
                  <div className="font-medium text-blue-600 dark:text-blue-400 mb-1">免费试用中</div>
                  <div className="text-muted-foreground">
                    额度: {formatNumber(data.free_trial_info.usageLimitWithPrecision || data.free_trial_info.usageLimit)} |
                    已用: {formatNumber(data.free_trial_info.currentUsageWithPrecision || data.free_trial_info.currentUsage)}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-8">无数据</div>
          )}
        </div>
      </div>
    </div>
  )
}
