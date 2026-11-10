<script setup lang="ts">
import { Play, Plus, Trash2 } from '@lucide/vue'
import { computed, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import DataTable, { type TableColumn, type TableRow } from '@/components/common/DataTable.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ModulePageShell from '@/components/common/ModulePageShell.vue'
import OutcomeBadge from '@/components/common/OutcomeBadge.vue'
import { ApiError, api, withQuery } from '@/lib/client'
import { LIST_POLL_MS, PAGE_SIZE, taskEditorPath } from '@/lib/constants'
import { formatDateTime } from '@/lib/format'
import { moduleById } from '@/lib/navigation'
import { useCatalogStore } from '@/stores/catalog'
import { useUiStore } from '@/stores/ui'
import type { Page, Run, Task, TaskType } from '@/types/api'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const catalog = useCatalogStore()
const tasks = ref<Task[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const loading = ref(true)
const error = ref('')
const busyId = ref('')
let timer = 0
let searchTimer = 0

const taskType = computed(() => route.meta.taskType as TaskType)
const current = computed(() => moduleById(route.meta.module))
const columns: TableColumn[] = [
  { key: 'name', label: '名称', sortable: true },
  { key: 'schedule', label: '调度', sortable: true },
  { key: 'target', label: '目标' },
  { key: 'requester', label: '请求器' },
  { key: 'proxy', label: '代理' },
  { key: 'state', label: '状态' },
  { key: 'outcome', label: '上次结果' },
  { key: 'next', label: '下次运行', sortable: true },
  { key: 'actions', label: '操作' },
]

const rows = computed<TableRow[]>(() =>
  tasks.value.map((task) => ({
    id: task.id,
    cells: {
      name: task.name,
      schedule: task.schedule.expression,
      target: task.request.url,
      requester: task.requester.name,
      proxy: task.proxy.provider,
      state: task.running ? '运行中' : task.enabled ? '启用' : '停用',
      outcome: '',
      next: formatDateTime(task.next_run_at),
      actions: '',
    },
  })),
)

function taskById(id: string): Task | undefined {
  return tasks.value.find((item) => item.id === id)
}

async function load() {
  error.value = ''
  try {
    const result = await api<Page<Task>>(
      withQuery('/tasks', {
        task_type: taskType.value,
        q: keyword.value.trim() || undefined,
        limit: PAGE_SIZE,
        offset: (page.value - 1) * PAGE_SIZE,
      }),
    )
    tasks.value = result.items
    total.value = result.total
    await catalog.refresh()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '任务列表加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => route.name,
  () => {
    page.value = 1
    keyword.value = ''
    loading.value = true
    void load()
  },
  { immediate: true },
)

watch(keyword, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    page.value = 1
    void load()
  }, 300)
})

timer = window.setInterval(() => void load(), LIST_POLL_MS)
onUnmounted(() => {
  window.clearInterval(timer)
  window.clearTimeout(searchTimer)
})

async function toggle(task: Task) {
  busyId.value = task.id
  try {
    await api<Task>(`/tasks/${task.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled: !task.enabled }),
    })
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '无法切换启用状态'
  } finally {
    busyId.value = ''
  }
}

async function run(task: Task) {
  if (task.task_type === 'load_test') {
    const accepted = await ui.confirm({
      title: '开始压力测试',
      message: `「${task.name}」会立即向目标发送多批请求。确认开始？`,
      confirmLabel: '开始压测',
      tone: 'primary',
    })
    if (!accepted) return
  }
  busyId.value = task.id
  try {
    const result = await api<Run>(`/tasks/${task.id}/run`, { method: 'POST' })
    ui.flash('运行已完成')
    await router.push(`/runs/${result.id}`)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '运行失败'
  } finally {
    busyId.value = ''
  }
}

function goToPage(next: number) {
  page.value = next
  void load()
}

async function remove(task: Task) {
  const accepted = await ui.confirm({
    title: '删除任务',
    message: `删除「${task.name}」后，历史运行记录仍会保留。确认删除？`,
    confirmLabel: '删除',
    tone: 'danger',
  })
  if (!accepted) return
  busyId.value = task.id
  try {
    await api<void>(`/tasks/${task.id}`, { method: 'DELETE' })
    ui.flash('任务已删除')
    await load()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '删除失败'
  } finally {
    busyId.value = ''
  }
}
</script>

<template>
  <ModulePageShell
    :title="current.name"
    :description="route.meta.description"
    :icon="current.icon"
    :accent="current.accent"
  >
    <template #actions>
      <RouterLink class="btn-primary" :to="taskEditorPath(taskType)">
        <Plus :size="16" />
        新建
      </RouterLink>
    </template>
    <div class="toolbar">
      <input
        v-model="keyword"
        class="control"
        type="search"
        placeholder="按名称或地址搜索"
        aria-label="搜索当前列表"
      />
    </div>
    <p v-if="error" class="banner banner-danger" role="alert">{{ error }}</p>
    <LoadingSkeleton v-if="loading" />
    <EmptyState
      v-else-if="total === 0"
      :title="keyword.trim() ? '没有匹配的任务' : '这里还是空的'"
      :description="
        keyword.trim()
          ? '换一个关键字，或清空搜索。'
          : '创建第一个任务后，调度器会按计划调用抓取器。'
      "
      :icon="current.icon"
      :accent="current.accent"
    >
      <RouterLink v-if="!keyword.trim()" class="btn-primary" :to="taskEditorPath(taskType)"
        >新建任务</RouterLink
      >
    </EmptyState>
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
        <template v-if="column.key === 'name'">
          <RouterLink :to="taskEditorPath(taskType, row.id)">{{ row.cells.name }}</RouterLink>
          <p v-if="taskById(row.id)?.description" class="hint">
            {{ taskById(row.id)?.description }}
          </p>
        </template>
        <OutcomeBadge
          v-else-if="column.key === 'outcome'"
          :outcome="taskById(row.id)?.last_outcome ?? null"
        />
        <button
          v-else-if="column.key === 'state' && taskById(row.id)"
          class="btn-ghost"
          type="button"
          :disabled="busyId === row.id"
          @click="toggle(taskById(row.id)!)"
        >
          {{ row.cells.state }}
        </button>
        <div v-else-if="column.key === 'actions' && taskById(row.id)" class="row-actions">
          <button
            class="btn-ghost"
            type="button"
            :disabled="busyId === row.id"
            @click="run(taskById(row.id)!)"
          >
            <Play :size="14" />
            运行
          </button>
          <button
            class="btn-ghost"
            type="button"
            :disabled="busyId === row.id"
            @click="remove(taskById(row.id)!)"
          >
            <Trash2 :size="14" />
            删除
          </button>
        </div>
        <span v-else>{{ row.cells[column.key] }}</span>
      </template>
    </DataTable>
  </ModulePageShell>
</template>
