<script setup lang="ts">
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { computed, ref } from 'vue'

export interface TableColumn {
  key: string
  label: string
  sortable?: boolean
}

export interface TableRow {
  id: string
  cells: Record<string, string>
}

const props = defineProps<{
  columns: TableColumn[]
  rows: TableRow[]
  page: number
  pageSize: number
  total: number
}>()

const emit = defineEmits<{ page: [page: number] }>()
const sortKey = ref<string | null>(null)
const sortDir = ref<'asc' | 'desc'>('asc')

const sorted = computed(() => {
  const rows = [...props.rows]
  const key = sortKey.value
  if (!key) return rows
  const direction = sortDir.value === 'asc' ? 1 : -1
  rows.sort(
    (left, right) =>
      (left.cells[key] ?? '').localeCompare(right.cells[key] ?? '', 'zh') * direction,
  )
  return rows
})

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

function toggleSort(column: TableColumn) {
  if (!column.sortable) return
  if (sortKey.value === column.key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortKey.value = column.key
  sortDir.value = 'asc'
}
</script>

<template>
  <div class="card">
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column.key">
              <button v-if="column.sortable" type="button" @click="toggleSort(column)">
                {{ column.label }}
                <span v-if="sortKey === column.key">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </button>
              <span v-else>{{ column.label }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in sorted" :key="row.id">
            <td v-for="column in columns" :key="column.key">
              <slot name="cell" :row="row" :column="column">{{ row.cells[column.key] }}</slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="total > pageSize" class="pager">
      <button class="btn-ghost" type="button" :disabled="page <= 1" @click="emit('page', page - 1)">
        <ChevronLeft :size="16" />
        上一页
      </button>
      <span>第 {{ page }} / {{ pageCount }} 页，共 {{ total }} 条</span>
      <button
        class="btn-ghost"
        type="button"
        :disabled="page >= pageCount"
        @click="emit('page', page + 1)"
      >
        下一页
        <ChevronRight :size="16" />
      </button>
    </div>
  </div>
</template>
