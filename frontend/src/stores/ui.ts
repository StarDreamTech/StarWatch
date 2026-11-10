import { defineStore } from 'pinia'
import { ref } from 'vue'
import { NOTICE_MS, THEME_STORAGE_KEY } from '@/lib/constants'

export type ThemeName = 'light' | 'dark'

export interface ConfirmRequest {
  title: string
  message: string
  confirmLabel: string
  tone: 'danger' | 'primary'
}

interface PendingConfirm extends ConfirmRequest {
  resolve: (accepted: boolean) => void
}

export const useUiStore = defineStore('ui', () => {
  const theme = ref<ThemeName>('light')
  const drawerOpen = ref(false)
  const submenuCollapsed = ref(false)
  const notice = ref<string | null>(null)
  const searchOpen = ref(false)
  const bellOpen = ref(false)
  const menuOpen = ref(false)
  const pendingConfirm = ref<PendingConfirm | null>(null)

  function applyTheme(next: ThemeName) {
    theme.value = next
    document.documentElement.classList.toggle('dark', next === 'dark')
    localStorage.setItem(THEME_STORAGE_KEY, next)
  }

  function hydrateTheme() {
    applyTheme(localStorage.getItem(THEME_STORAGE_KEY) === 'dark' ? 'dark' : 'light')
  }

  function toggleTheme() {
    applyTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  function openModule() {
    submenuCollapsed.value = false
    drawerOpen.value = false
  }

  function closePopovers() {
    searchOpen.value = false
    bellOpen.value = false
    menuOpen.value = false
  }

  function flash(message: string) {
    notice.value = message
    window.setTimeout(() => {
      if (notice.value === message) notice.value = null
    }, NOTICE_MS)
  }

  function confirm(request: ConfirmRequest): Promise<boolean> {
    return new Promise((resolve) => {
      pendingConfirm.value = { ...request, resolve }
    })
  }

  function settleConfirm(accepted: boolean) {
    pendingConfirm.value?.resolve(accepted)
    pendingConfirm.value = null
  }

  return {
    theme,
    drawerOpen,
    submenuCollapsed,
    notice,
    searchOpen,
    bellOpen,
    menuOpen,
    pendingConfirm,
    applyTheme,
    hydrateTheme,
    toggleTheme,
    openModule,
    closePopovers,
    flash,
    confirm,
    settleConfirm,
  }
})
