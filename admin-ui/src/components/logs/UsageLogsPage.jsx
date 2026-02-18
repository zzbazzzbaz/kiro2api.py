import { useState, useEffect, useCallback } from 'react'
import { apiKeys } from '@/api/client'
import { toast } from 'sonner'
import { extractErrorMessage, formatDateTime } from '@/lib/utils'
import { RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'

const PAGE_SIZE = 50

export function UsageLogsPage() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const [filterKeyId, setFilterKeyId] = useState('')
  const [keyList, setKeyList] = useState([])

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    try {
      const params = { limit: PAGE_SIZE, offset }
      if (filterKeyId) params.api_key_id = filterKeyId
      const data = await apiKeys.getUsageLogs(params)
      setLogs(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      toast.error(`加载日志失败: ${extractErrorMessage(err)}`)
    } finally {
      setLoading(false)
    }
  }, [offset, filterKeyId])

  const fetchKeys = useCallback(async () => {
    try {
      const data = await apiKeys.list()
      setKeyList(data)
    } catch {}
  }, [])

  useEffect(() => { fetchKeys() }, [fetchKeys])
  useEffect(() => { fetchLogs() }, [fetchLogs])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const statusColor = (code) => {
    if (code >= 200 && code < 300) return 'text-green-600 dark:text-green-400'
    if (code >= 400 && code < 500) return 'text-yellow-600 dark:text-yellow-400'
    return 'text-red-600 dark:text-red-400'
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold text-foreground">消费日志</h1>
        <div className="flex items-center gap-2">
          <select
            value={filterKeyId}
            onChange={e => { setFilterKeyId(e.target.value); setOffset(0) }}
            className="px-3 py-1.5 text-sm bg-background border border-border rounded-md text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            <option value="">全部 Key</option>
            {keyList.map(k => (
              <option key={k.id} value={k.id}>#{k.id} {k.name}</option>
            ))}
          </select>
          <button onClick={fetchLogs} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent transition-colors text-foreground">
            <RefreshCw className="h-3.5 w-3.5" /> 刷新
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      ) : logs.length === 0 ? (
        <div className="bg-card border border-border rounded-lg p-12 text-center text-muted-foreground">
          暂无日志
        </div>
      ) : (
        <>
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">ID</th>
                    <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">Key</th>
                    <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">凭据</th>
                    <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">模型</th>
                    <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">端点</th>
                    <th className="text-right px-3 py-2.5 font-medium text-muted-foreground">输入</th>
                    <th className="text-right px-3 py-2.5 font-medium text-muted-foreground">输出</th>
                    <th className="text-right px-3 py-2.5 font-medium text-muted-foreground">总计</th>
                    <th className="text-center px-3 py-2.5 font-medium text-muted-foreground">状态</th>
                    <th className="text-right px-3 py-2.5 font-medium text-muted-foreground">耗时</th>
                    <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <tr key={log.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                      <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{log.id}</td>
                      <td className="px-3 py-2 text-foreground">{log.api_key_id != null ? `#${log.api_key_id}` : '-'}</td>
                      <td className="px-3 py-2 text-foreground">{log.credential_id != null ? `#${log.credential_id}` : '-'}</td>
                      <td className="px-3 py-2 font-mono text-xs text-foreground">{log.model}</td>
                      <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{log.endpoint}</td>
                      <td className="px-3 py-2 text-right text-foreground">{log.input_tokens.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right text-foreground">{log.output_tokens.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right font-medium text-foreground">{log.total_tokens.toLocaleString()}</td>
                      <td className="px-3 py-2 text-center">
                        <span className={`font-mono text-xs font-medium ${statusColor(log.status_code)}`}>
                          {log.status_code}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right text-muted-foreground">{log.duration_ms}ms</td>
                      <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">{formatDateTime(log.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 分页 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                className="flex items-center gap-1 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent disabled:opacity-50 transition-colors text-foreground"
              >
                <ChevronLeft className="h-4 w-4" /> 上一页
              </button>
              <span className="text-sm text-muted-foreground">
                第 {currentPage} / {totalPages} 页（共 {total} 条）
              </span>
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={currentPage >= totalPages}
                className="flex items-center gap-1 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent disabled:opacity-50 transition-colors text-foreground"
              >
                下一页 <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
