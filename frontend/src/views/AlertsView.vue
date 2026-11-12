<script setup lang="ts">
import { Bell } from '@lucide/vue'
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ModulePageShell from '@/components/common/ModulePageShell.vue'
import OutcomeBadge from '@/components/common/OutcomeBadge.vue'
import { ApiError, api, withQuery } from '@/lib/client'
import { CATEGORY_LABEL, DELIVERY_LABEL, PAGE_SIZE } from '@/lib/constants'
import { formatDateTime } from '@/lib/format'
import { moduleById } from '@/lib/navigation'
import { useCatalogStore } from '@/stores/catalog'
import { useUiStore } from '@/stores/ui'
import type { Notification, Page } from '@/types/api'

const catalog = useCatalogStore()
const ui = useUiStore()
const items = ref<Notification[]>([])
const total = ref(0)
const page = ref(1)
const unreadOnly = ref(false)
const loading = ref(true)
const error = ref('')
const current = moduleById('alerts')

async function load() {
  error.value = ''
  try {
    const result = await api<Page<Notification>>(
      withQuery('/notifications', {
        unread_only: unreadOnly.value || undefined,
        limit: PAGE_SIZE,
        offset: (page.value - 1) * PAGE_SIZE,
      }),
    )
    items.value = result.items
    total.value = result.total
    await catalog.refresh()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '通知加载失败'
  } finally {
    loading.value = false
  }
}

function showUnreadOnly() {
  page.value = 1
  void load()
}

function previousPage() {
  page.value -= 1
  void load()
}

function nextPage() {
  page.value += 1
  void load()
}

async function mark(ids: string[] | null) {
  try {
    await api('/notifications/read', { method: 'POST', body: JSON.stringify({ ids }) })
    ui.flash(ids ? '已标为已读' : '全部未读已处理')
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '标记已读失败'
  }
}

onMounted(() => void load())
</script>

<template>
  <ModulePageShell
    :title="current.name"
    :description="$route.meta.description"
    :icon="current.icon"
    :accent="current.accent"
  >
    <template #actions>
      <button class="btn-ghost" type="button" @click="mark(null)">全部标为已读</button>
    </template>
    <div class="toolbar">
      <label class="check">
        <input v-model="unreadOnly" type="checkbox" @change="showUnreadOnly" />
        <span>只看未读</span>
      </label>
    </div>
    <p v-if="error" class="banner banner-danger" role="alert">{{ error }}</p>
    <LoadingSkeleton v-if="loading" />
    <EmptyState
      v-else-if="items.length === 0"
      title="没有通知"
      description="变化、失败和拦截产生后会出现在这里。"
      :icon="Bell"
      accent="rose"
    />
    <div v-else class="stack">
      <article
        v-for="item in items"
        :key="item.id"
        class="card form-card"
        :style="item.read ? undefined : { borderColor: 'var(--sw-rose)' }"
      >
        <div class="toolbar">
          <strong>{{ item.title }}</strong>
          <OutcomeBadge :outcome="item.outcome" />
          <span class="badge" data-tone="rose">{{ CATEGORY_LABEL[item.category] }}</span>
          <span class="badge" data-tone="muted">{{ DELIVERY_LABEL[item.delivery] }}</span>
        </div>
        <p>{{ item.message }}</p>
        <p class="hint">
          {{ item.task_name }} · {{ formatDateTime(item.created_at) }} · {{ item.provider
          }}<span v-if="item.delivery_detail"> · {{ item.delivery_detail }}</span>
        </p>
        <div class="row-actions">
          <RouterLink class="btn-ghost" :to="`/runs/${item.run_id}`">查看运行</RouterLink>
          <button v-if="!item.read" class="btn-ghost" type="button" @click="mark([item.id])">
            标为已读
          </button>
        </div>
      </article>
      <div v-if="total > PAGE_SIZE" class="pager">
        <button class="btn-ghost" type="button" :disabled="page <= 1" @click="previousPage">
          上一页
        </button>
        <span>第 {{ page }} 页，共 {{ total }} 条</span>
        <button
          class="btn-ghost"
          type="button"
          :disabled="page * PAGE_SIZE >= total"
          @click="nextPage"
        >
          下一页
        </button>
      </div>
    </div>
  </ModulePageShell>
</template>
