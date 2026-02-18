import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'
import {
  Server, LogOut, Moon, Sun, Menu, X,
  LayoutDashboard, KeyRound, Shield, FolderOpen, ScrollText,
} from 'lucide-react'
import { DashboardPage } from '@/components/DashboardPage'
import { CredentialsPage } from '@/components/credentials/CredentialsPage'
import { ApiKeysPage } from '@/components/api-keys/ApiKeysPage'
import { GroupsPage } from '@/components/groups/GroupsPage'
import { UsageLogsPage } from '@/components/logs/UsageLogsPage'

const NAV_ITEMS = [
  { id: 'dashboard', label: '总览', icon: LayoutDashboard },
  { id: 'credentials', label: '凭据管理', icon: Shield },
  { id: 'api-keys', label: 'API Key', icon: KeyRound },
  { id: 'groups', label: '分组管理', icon: FolderOpen },
  { id: 'logs', label: '消费日志', icon: ScrollText },
]

export function Layout() {
  const { logout } = useAuth()
  const [activePage, setActivePage] = useState('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [darkMode, setDarkMode] = useState(() =>
    document.documentElement.classList.contains('dark')
  )

  const toggleDark = () => {
    setDarkMode(!darkMode)
    document.documentElement.classList.toggle('dark')
  }

  const navigate = (id) => {
    setActivePage(id)
    setSidebarOpen(false)
  }

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <DashboardPage />
      case 'credentials': return <CredentialsPage />
      case 'api-keys': return <ApiKeysPage />
      case 'groups': return <GroupsPage />
      case 'logs': return <UsageLogsPage />
      default: return <DashboardPage />
    }
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* 移动端遮罩 */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 侧边栏 */}
      <aside className={cn(
        'fixed inset-y-0 left-0 z-50 w-56 bg-card border-r border-border flex flex-col transition-transform lg:translate-x-0 lg:static lg:z-auto',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <div className="flex items-center gap-2 px-4 h-14 border-b border-border shrink-0">
          <Server className="h-5 w-5 text-primary" />
          <span className="font-semibold text-foreground">kiro2api</span>
        </div>

        <nav className="flex-1 py-2 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => navigate(item.id)}
              className={cn(
                'w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                activePage === item.id
                  ? 'bg-accent text-accent-foreground font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {item.label}
            </button>
          ))}
        </nav>

        <div className="border-t border-border p-2 shrink-0 flex gap-1">
          <button
            onClick={toggleDark}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/50 rounded-md transition-colors"
          >
            {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <button
            onClick={logout}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-destructive hover:bg-accent/50 rounded-md transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </aside>

      {/* 主内容 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部栏（移动端） */}
        <header className="sticky top-0 z-30 h-14 bg-background/95 backdrop-blur border-b border-border flex items-center px-4 lg:hidden">
          <button onClick={() => setSidebarOpen(true)} className="text-foreground">
            <Menu className="h-5 w-5" />
          </button>
          <span className="ml-3 font-semibold text-foreground">
            {NAV_ITEMS.find(i => i.id === activePage)?.label}
          </span>
        </header>

        <main className="flex-1 p-4 md:p-6 overflow-auto">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}
