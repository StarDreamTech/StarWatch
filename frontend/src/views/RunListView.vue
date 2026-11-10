<script setup lang="ts">
import { ScrollText } from '@lucide/vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import DataTable, { type TableColumn, type TableRow } from '@/components/common/DataTable.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ModulePageShell from '@/components/common/ModulePageShell.vue'
import OutcomeBadge from '@/components/common/OutcomeBadge.vue'
import { ApiError, api, withQuery } from '@/lib/client'
import { LIST_POLL_MS, OUTCOME_LABEL, PAGE_SIZE, TASK_TYPE_LABEL } from '@/lib/constants'
import { formatDateTime, formatLatency } from '@/lib/format'
import { moduleById } from '@/lib/navigation'
import type { Outcome, Page, RunSummary } from '@/types/api'

const runs = ref<RunSummary[]>([])
const total = ref(0)
const page = ref(1)
const outcome = ref<Outcome | ''>('')
const loading = ref(true)
const error = ref('')
const current = moduleById('runs')
let timer = 0

const columns: TableColumn[] = [
  { key: 'time', label: '开始时间', sortable: true },
  { key: 'name', label: '任务', sortable: true },
  { key: 'type', label: '类型' },
  { key: 'outcome', label: '结果' },
  { key: 'status', label: '状态码' },
  { key: 'latency', label: '耗时' },
  { key: 'summary', label: '摘要' },
]

const rows = computed<TableRow[]>(() =>
  runs.value.map((run) => ({
    id: run.id,
    cells: {
      time: formatDateTime(run.started_at),
      name: run.task_name,
      type: TASK_TYPE_LABEL[run.task_type],
      outcome: '',
      status: run.status_code === null ? '—' : String(run.status_code),
      latency: formatLatency(run.latency_ms),
      summary: run.summary,
    },
  })),
)

async function load() {
  error.value = ''
  try {
    const result = await api<Page<RunSummary>>(
      withQuery('/runs', {
        outcome: outcome.value || undefined,
        limit: PAGE_SIZE,
        offset: (page.value - 1) * PAGE_SIZE,
      }),
    )
    runs.value = result.items
    total.value = result.total
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '运行记录加载失败'
  } finally {
    loading.value = false
  }
}

function goToPage(next: number) {
  page.value = next
  void load()
}

watch(outcome, () => {
  page.value = 1
  void load()
})

onMounted(() => {
  void load()
  timer = window.setInterval(() => void load(), LIST_POLL_MS)
})
onUnmounted(() => window.clearInterval(timer))

function runById(id: string): RunSummary | undefined {
  return runs.value.find((item) => item.id === id)
}
</script>

<template>
  <ModulePageShell
    :title="current.name"
    :description="$route.meta.description"
    :icon="current.icon"
    :accent="current.accent"
  >
    <div class="toolbar">
      <label class="field" style="width: 220px">
        结果
        <select v-model="outcome">
          <option value="">全部</option>
          <option v-for="(label, key) in OUTCOME_LABEL" :key="key" :value="key">{{ label }}</option>
        </select>
      </label>
    </div>
    <p v-if="error" class="banner banner-danger" role="alert">{{ error }}</p>
    <LoadingSkeleton v-if="loading" />
    <EmptyState
      v-else-if="total === 0"
      title="没有运行记录"
      description="任务被调度或手动运行后，结果会出现在这里。"
      :icon="ScrollText"
      accent="orange"
    />
    <DataTable
      v-else
      :columns="columns"
      :rows="rows"
      :page="page"
      :page-size="PAGE_SIZE"
      :total="total"
      @page="goToPage"
    >
      <template #cell="{ row, column }">
        <RouterLink v-if="column.key === 'name'" :to="`/runs/${row.id}`">{{
          row.cells.name
        }}</RouterLink>
        <OutcomeBadge
          v-else-if="column.key === 'outcome'"
          :outcome="runById(row.id)?.outcome ?? null"
        />
        <span v-else>{{ row.cells[column.key] }}</span>
      </template>
    </DataTable>
  </ModulePageShell>
</template>
