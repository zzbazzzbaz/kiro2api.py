/**
 * 合并 class 名称
 */
export function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

/**
 * 格式化日期时间
 */
export function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return dateStr
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

/**
 * 格式化 Unix 时间戳
 */
export function formatTimestamp(ts) {
  if (!ts) return '-'
  return formatDateTime(new Date(ts * 1000).toISOString())
}

/**
 * 提取错误消息
 */
export function extractErrorMessage(error) {
  if (typeof error === 'string') return error
  if (error?.detail) return error.detail
  if (error?.error?.message) return error.error.message
  if (error?.message) return error.message
  return '未知错误'
}

/**
 * 格式化数字（保留小数）
 */
export function formatNumber(n, decimals = 1) {
  if (n == null) return '-'
  return Number(n).toFixed(decimals)
}
