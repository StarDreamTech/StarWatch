<script setup lang="ts">
import { Bell, Menu, Moon, Search, Star, Sun, UserRound } from '@lucide/vue'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { api, withQuery } from '@/lib/client'
import { BELL_LIMIT, SEARCH_DEBOUNCE_MS, SEARCH_LIMIT, taskEditorPath } from '@/lib/constants'
import { formatDateTime } from '@/lib/format'
import { useCatalogStore } from '@/stores/catalog'
import { useUiStore } from '@/stores/ui'
import type { Notification, Page, Task } from '@/types/api'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const catalog = useCatalogStore()
const query = ref('')
const results = ref<Task[]>([])
const notices = ref<Notification[]>([])
const searching = ref(false)
const root = ref<HTMLElement | null>(null)
let timer = 0

watch(query, (value) => {
  window.clearTimeout(timer)
  const text = value.trim()
  if (!text) {
    results.value = []
    ui.searchOpen = false
    return
  }
  timer = window.setTimeout(() => void search(text), SEARCH_DEBOUNCE_MS)
})

async function search(text: string) {
  searching.value = true
  ui.searchOpen = true
  try {
    const page = await api<Page<Task>>(withQuery('/tasks', { q: text, limit: SEARCH_LIMIT }))
    results.value = page.items
  } catch {
    results.value = []
  } finally {
    searching.value = false
  }
}

async function loadNotices() {
  ui.bellOpen = !ui.bellOpen
  ui.menuOpen = false
  ui.searchOpen = false
  if (!ui.bellOpen) return
  try {
    const page = await api<Page<Notification>>(
      withQuery('/notifications', { unread_only: true, limit: BELL_LIMIT }),
    )
    notices.value = page.items
  } catch {
    notices.value = []
  }
}

async function openNotice(item: Notification) {
  try {
    await api('/notifications/read', {
      method: 'POST',
      body: JSON.stringify({ ids: [item.id] }),
    })
    await catalog.refresh()
  } catch {
    /* 已读失败不阻断跳转。 */
  }
  ui.bellOpen = false
  await router.push(`/runs/${item.run_id}`)
}

function openTask(task: Task) {
  ui.searchOpen = false
  query.value = ''
  void router.push(taskEditorPath(task.task_type, task.id))
}

function toggleMenu() {
  ui.menuOpen = !ui.menuOpen
  ui.bellOpen = false
  ui.searchOpen = false
}

function onDocumentClick(event: MouseEvent) {
  if (!root.value?.contains(event.target as Node)) ui.closePopovers()
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
  window.clearTimeout(timer)
})
</script>

<template>
  <header ref="root" class="topbar">
    <button
      class="icon-btn mobile-only"
      type="button"
      aria-label="打开导航"
      @click="ui.drawerOpen = true"
    >
      <Menu :size="18" />
    </button>
    <RouterLink class="brand" to="/" @click="ui.openModule()">
      <span class="brand-mark" aria-hidden="true"><Star :size="16" /></span>
      <span class="brand-copy">
        <span class="brand-name">星哨</span>
        <span class="brand-en">StarWatch</span>
      </span>
    </RouterLink>
    <nav class="crumbs desktop-only" aria-label="当前位置">
      <span v-for="(crumb, index) in route.meta.crumbs" :key="crumb">
        <span v-if="index"> / </span>
        <strong v-if="index === route.meta.crumbs.length - 1">{{ crumb }}</strong>
        <span v-else>{{ crumb }}</span>
      </span>
    </nav>
    <div class="search">
      <Search class="search-icon" :size="16" />
      <input
        v-model="query"
        type="search"
        placeholder="搜索任务名称或地址"
        aria-label="搜索任务"
        @focus="ui.menuOpen = false"
      />
      <div v-if="ui.searchOpen" class="popover" style="left: 0; right: auto; width: 100%">
        <p v-if="searching" class="hint" style="padding: 12px">正在搜索…</p>
        <p v-else-if="results.length === 0" class="hint" style="padding: 12px">没有匹配的任务</p>
        <button v-for="task in results" :key="task.id" type="button" @click="openTask(task)">
          {{ task.name }}
          <small>{{ task.request.url }}</small>
        </button>
      </div>
    </div>
    <div class="bell">
      <button class="icon-btn" type="button" aria-label="通知" @click.stop="loadNotices">
        <Bell :size="18" />
        <span v-if="catalog.stats && catalog.stats.unread_notifications > 0" class="badge-dot">
          {{ catalog.stats.unread_notifications > 99 ? '99+' : catalog.stats.unread_notifications }}
        </span>
      </button>
      <div v-if="ui.bellOpen" class="popover">
        <p v-if="notices.length === 0" class="hint" style="padding: 12px">没有未读通知</p>
        <button v-for="item in notices" :key="item.id" type="button" @click="openNotice(item)">
          {{ item.title }}
          <small>{{ formatDateTime(item.created_at) }} · {{ item.message }}</small>
        </button>
        <RouterLink to="/alerts" @click="ui.bellOpen = false">查看全部通知</RouterLink>
      </div>
    </div>
    <div style="position: relative">
      <button class="user-btn" type="button" aria-label="操作员菜单" @click.stop="toggleMenu">
        <span class="avatar"><UserRound :size="16" /></span>
        <span class="user-label">本地操作员</span>
      </button>
      <div v-if="ui.menuOpen" class="popover" style="width: 220px">
        <p style="margin: 0; padding: 12px 12px 0">本地操作员</p>
        <p class="hint" style="padding: 0 12px 8px">自托管部署，不需要登录</p>
        <button type="button" @click="ui.toggleTheme()">
          <Sun v-if="ui.theme === 'dark'" :size="16" />
          <Moon v-else :size="16" />
          {{ ui.theme === 'dark' ? '切换为浅色' : '切换为深色' }}
        </button>
        <RouterLink to="/settings" @click="ui.menuOpen = false">打开设置</RouterLink>
      </div>
    </div>
  </header>
</template>
