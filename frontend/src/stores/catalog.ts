import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/lib/client'
import type { ModuleId } from '@/lib/navigation'
import type { Stats } from '@/types/api'

export const useCatalogStore = defineStore('catalog', () => {
  const stats = ref<Stats | null>(null)

  async function refresh() {
    try {
      stats.value = await api<Stats>('/stats')
    } catch {
      return
    }
  }

  function count(moduleId: ModuleId): number {
    const current = stats.value
    if (!current) return 0
    if (moduleId === 'pages') return current.page_change
    if (moduleId === 'checks') return current.api_check
    if (moduleId === 'load') return current.load_test
    if (moduleId === 'alerts') return current.unread_notifications
    if (moduleId === 'runs') return current.runs_today
    if (moduleId === 'overview') return current.tasks
    return 0
  }

  return { stats, refresh, count }
})
