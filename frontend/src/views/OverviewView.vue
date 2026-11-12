<script setup lang="ts">
import { Activity, Bell, ListChecks, TriangleAlert } from '@lucide/vue'
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ModulePageShell from '@/components/common/ModulePageShell.vue'
import OutcomeBadge from '@/components/common/OutcomeBadge.vue'
import StatCard from '@/components/common/StatCard.vue'
import { ApiError, api, withQuery } from '@/lib/client'
import { LIST_POLL_MS, TASK_TYPE_LABEL, taskEditorPath } from '@/lib/constants'
import { formatDateTime, formatLatency } from '@/lib/format'
import { moduleById } from '@/lib/navigation'
import { useCatalogStore } from '@/stores/catalog'
import type { Page, RunSummary, Stats } from '@/types/api'

const catalog = useCatalogStore()
const runs = ref<RunSummary[]>([])
const loading = ref(true)
const error = ref('')
const current = moduleById('overview')
let timer = 0

async function load() {
  error.value = ''
  try {
    await catalog.refresh()
    const page = await api<Page<RunSummary>>(withQuery('/runs', { limit: 8 }))
    runs.value = page.items
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '总览加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
  timer = window.setInterval(() => void load(), LIST_POLL_MS)
})

onUnmounted(() => window.clearInterval(timer))

function hint(stats: Stats | null, key: 'enabled' | 'problems' | 'changed' | 'unread'): string {
  if (!stats) return '等待调度器'
  if (key === 'enabled') return `${stats.enabled} 个启用中`
  if (key === 'problems') return '失败、拦截、空页面和超时'
  if (key === 'changed') return '含基线之后的字段变化'
  return '站内通知，不含已读'
}
</script>

<template>
  <ModulePageShell
    :title="current.name"
    :description="$route.meta.description"
    :icon="current.icon"
    :accent="current.accent"
  >
    <p v-if="error" class="banner banner-danger" role="alert">{{ error }}</p>
    <LoadingSkeleton v-if="loading" />
    <template v-else>
      <div class="stat-grid">
        <StatCard
          label="任务"
          :value="catalog.stats?.tasks ?? 0"
          :hint="hint(catalog.stats, 'enabled')"
          :icon="ListChecks"
          accent="cyan"
        />
        <StatCard
          label="今日运行"
          :value="catalog.stats?.runs_today ?? 0"
          hint="按调度器时区的自然日"
          :icon="Activity"
          accent="blue"
        />
        <StatCard
          label="今日变化"
          :value="catalog.stats?.changed_today ?? 0"
          :hint="hint(catalog.stats, 'changed')"
          :icon="Activity"
          accent="emerald"
        />
        <StatCard
          label="今日异常"
          :value="catalog.stats?.problems_today ?? 0"
          :hint="hint(catalog.stats, 'problems')"
          :icon="TriangleAlert"
          accent="rose"
        />
      </div>
      <div class="card-grid">
        <RouterLink
          class="card"
          style="padding: 16px; text-decoration: none; color: inherit"
          to="/alerts"
        >
          <Bell :size="18" />
          <strong> {{ catalog.stats?.unread_notifications ?? 0 }} 条未读通知</strong>
          <p class="hint">{{ hint(catalog.stats, 'unread') }}</p>
        </RouterLink>
      </div>
      <EmptyState
        v-if="runs.length === 0"
        title="还没有运行记录"
        description="创建一个任务并等到调度时间，或在列表里立即运行。"
        :icon="current.icon"
        accent="cyan"
      >
        <RouterLink class="btn-primary" to="/pages/new">新建网页监控</RouterLink>
      </EmptyState>
      <div v-else class="card table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>任务</th>
              <th>类型</th>
              <th>结果</th>
              <th>耗时</th>
              <th>摘要</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in runs" :key="run.id">
              <td>{{ formatDateTime(run.started_at) }}</td>
              <td>
                <RouterLink :to="taskEditorPath(run.task_type, run.task_id)">{{
                  run.task_name
                }}</RouterLink>
              </td>
              <td>{{ TASK_TYPE_LABEL[run.task_type] }}</td>
              <td>
                <RouterLink :to="`/runs/${run.id}`"
                  ><OutcomeBadge :outcome="run.outcome"
                /></RouterLink>
              </td>
              <td>{{ formatLatency(run.latency_ms) }}</td>
              <td>{{ run.summary }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </ModulePageShell>
</template>
