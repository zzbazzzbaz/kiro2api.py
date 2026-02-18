/**
 * API 客户端 — 封装 fetch 并注入 Admin Key
 */

const STORAGE_KEY_BASE_URL = 'kiro2api_base_url'
const STORAGE_KEY_ADMIN_KEY = 'kiro2api_admin_key'

export function getBaseUrl() {
  return localStorage.getItem(STORAGE_KEY_BASE_URL) || ''
}

export function getAdminKey() {
  return localStorage.getItem(STORAGE_KEY_ADMIN_KEY) || ''
}

export function setAuth(baseUrl, adminKey) {
  localStorage.setItem(STORAGE_KEY_BASE_URL, baseUrl)
  localStorage.setItem(STORAGE_KEY_ADMIN_KEY, adminKey)
}

export function clearAuth() {
  localStorage.removeItem(STORAGE_KEY_BASE_URL)
  localStorage.removeItem(STORAGE_KEY_ADMIN_KEY)
}

export function isLoggedIn() {
  return !!getAdminKey()
}

/**
 * 通用 API 请求
 */
async function request(path, options = {}) {
  const baseUrl = getBaseUrl()
  const adminKey = getAdminKey()
  const url = `${baseUrl}${path}`

  const headers = {
    'Content-Type': 'application/json',
    ...(adminKey ? { 'x-admin-key': adminKey } : {}),
    ...options.headers,
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let errorData
    try {
      errorData = await response.json()
    } catch {
      errorData = { detail: `HTTP ${response.status}: ${response.statusText}` }
    }
    throw errorData
  }

  if (response.status === 204) return null
  return response.json()
}

// ===== 凭据 =====

export const credentials = {
  list: () => request('/api/admin/credentials'),
  add: (data) => request('/api/admin/credentials', { method: 'POST', body: JSON.stringify(data) }),
  delete: (id) => request(`/api/admin/credentials/${id}`, { method: 'DELETE' }),
  disable: (id) => request(`/api/admin/credentials/${id}/disable`, { method: 'POST' }),
  enable: (id) => request(`/api/admin/credentials/${id}/enable`, { method: 'POST' }),
  reset: (id) => request(`/api/admin/credentials/${id}/reset`, { method: 'POST' }),
  setPriority: (id, priority) => request(`/api/admin/credentials/${id}/priority?priority=${priority}`, { method: 'PUT' }),
  getBalance: (id, force = false) => request(`/api/admin/credentials/${id}/balance${force ? '?force=true' : ''}`),
}

// ===== API Keys =====

export const apiKeys = {
  list: () => request('/api/admin/api-keys'),
  create: (data) => request('/api/admin/api-keys', { method: 'POST', body: JSON.stringify(data) }),
  delete: (id) => request(`/api/admin/api-keys/${id}`, { method: 'DELETE' }),
  enable: (id) => request(`/api/admin/api-keys/${id}/enable`, { method: 'POST' }),
  disable: (id) => request(`/api/admin/api-keys/${id}/disable`, { method: 'POST' }),
  setQuota: (id, tokenQuota) => request(`/api/admin/api-keys/${id}/quota?token_quota=${tokenQuota}`, { method: 'PUT' }),
  resetUsage: (id) => request(`/api/admin/api-keys/${id}/reset-usage`, { method: 'POST' }),
  getUsageLogs: (params = {}) => {
    const query = new URLSearchParams()
    if (params.api_key_id) query.set('api_key_id', params.api_key_id)
    if (params.limit) query.set('limit', params.limit)
    if (params.offset != null) query.set('offset', params.offset)
    return request(`/api/admin/api-keys/usage-logs?${query}`)
  },
}

// ===== 分组 =====

export const groups = {
  list: () => request('/api/admin/groups'),
  create: (data) => request('/api/admin/groups', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => request(`/api/admin/groups/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/api/admin/groups/${id}`, { method: 'DELETE' }),
}

// ===== 配置 =====

export const config = {
  getLoadBalancingMode: () => request('/api/admin/config/load-balancing-mode'),
  setLoadBalancingMode: (mode) => request(`/api/admin/config/load-balancing-mode?mode=${mode}`, { method: 'PUT' }),
}
