<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ModulePageShell from '@/components/common/ModulePageShell.vue'
import OutcomeBadge from '@/components/common/OutcomeBadge.vue'
import SnapshotDiff from '@/components/common/SnapshotDiff.vue'
import { ApiError, api, withQuery } from '@/lib/client'
import { OUTCOME_LABEL, TASK_TYPE_LABEL, taskEditorPath } from '@/lib/constants'
import { formatDateTime, formatLatency, formatNumber } from '@/lib/format'
import { moduleById } from '@/lib/navigation'
import type { DiffResult, Page, Run, RunSummary } from '@/types/api'

const route = useRoute()
const run = ref<Run | null>(null)
const loading = ref(true)
const error = ref('')
const current = moduleById('runs')
const versions = ref<RunSummary[]>([])
const versionsOffset = ref(0)
const versionsTotal = ref(0)
const versionsLoading = ref(false)
const comparisonLoading = ref(false)
const comparisonError = ref('')
const beforeId = ref('')
const afterId = ref('')
const comparison = ref<DiffResult | null>(null)
const comparisonApplied = ref(false)
const displayedDiff = computed(() => (comparisonApplied.value ? comparison.value : run.value?.diff))

function comparable(version: RunSummary): boolean {
  return (
    version.task_type === 'page_change' &&
    ['baseline', 'changed', 'unchanged', 'success'].includes(version.outcome)
  )
}

function clearComparison() {
  comparison.value = null
  comparisonApplied.value = true
  comparisonError.value = ''
}

async function loadVersions() {
  const detailId = route.params.id
  const taskId = run.value?.task_id
  if (!taskId) return
  versionsLoading.value = true
  try {
    const result = await api<Page<RunSummary>>(
      withQuery('/runs', {
        task_id: taskId,
        limit: 50,
        offset: versionsOffset.value,
      }),
    )
    if (route.params.id !== detailId || run.value?.task_id !== taskId) return
    const byId = new Map(versions.value.map((version) => [version.id, version]))
    for (const version of result.items) byId.set(version.id, version)
    versions.value = [...byId.values()].sort((a, b) => b.started_at.localeCompare(a.started_at))
    versionsOffset.value += result.items.length
    versionsTotal.value = result.total
  } catch (caught) {
    if (route.params.id !== detailId) return
    comparisonError.value = caught instanceof ApiError ? caught.message : '历史版本读取失败'
  } finally {
    if (route.params.id === detailId) versionsLoading.value = false
  }
}

async function compareVersions() {
  const detailId = route.params.id
  const selectedAfter = afterId.value
  const selectedBefore = beforeId.value
  comparisonLoading.value = true
  comparisonError.value = ''
  comparisonApplied.value = true
  comparison.value = null
  try {
    const result = selectedBefore
      ? await api<DiffResult>(
          withQuery(`/runs/${selectedAfter}/compare`, { before_id: selectedBefore }),
        )
      : (await api<Run>(`/runs/${selectedAfter}`)).diff
    if (
      route.params.id === detailId &&
      afterId.value === selectedAfter &&
      beforeId.value === selectedBefore
    ) {
      comparison.value = result
      if (!result)
        comparisonError.value = '此版本没有自动对比结果，请选择一个历史版本作为对比前版本。'
    }
  } catch (caught) {
    if (route.params.id !== detailId) return
    comparisonError.value = caught instanceof ApiError ? caught.message : '版本对比失败'
  } finally {
    if (route.params.id === detailId) comparisonLoading.value = false
  }
}

const histogram = computed(() => {
  const counts = run.value?.load?.status_histogram ?? {}
  const max = Math.max(1, ...Object.values(counts))
  return Object.entries(counts).map(([code, count]) => ({
    code,
    count,
    width: `${(count / max) * 100}%`,
  }))
})

async function load() {
  loading.value = true
  error.value = ''
  run.value = null
  versions.value = []
  versionsOffset.value = 0
  versionsTotal.value = 0
  comparison.value = null
  comparisonApplied.value = false
  comparisonError.value = ''
  comparisonLoading.value = false
  versionsLoading.value = false
  beforeId.value = ''
  const id = route.params.id
  if (typeof id !== 'string') return
  try {
    const result = await api<Run>(`/runs/${id}`)
    if (route.params.id !== id) return
    run.value = result
    afterId.value = result.id
    versions.value = [result]
    if (result.task_type === 'page_change') await loadVersions()
  } catch (caught) {
    if (route.params.id !== id) return
    error.value = caught instanceof ApiError ? caught.message : '运行详情加载失败'
  } finally {
    if (route.params.id === id) loading.value = false
  }
}

watch(
  () => route.params.id,
  () => void load(),
  { immediate: true },
)
</script>

<template>
  <ModulePageShell
    :title="run?.task_name ?? current.name"
    :description="route.meta.description"
    :icon="current.icon"
    :accent="current.accent"
  >
    <template #actions>
      <RouterLink class="btn-ghost" to="/runs">返回列表</RouterLink>
      <RouterLink v-if="run" class="btn-primary" :to="taskEditorPath(run.task_type, run.task_id)"
        >打开任务</RouterLink
      >
    </template>
    <p v-if="error" class="banner banner-danger" role="alert">{{ error }}</p>
    <LoadingSkeleton v-if="loading" />
    <template v-else-if="run">
      <section class="card form-card">
        <div class="toolbar">
          <OutcomeBadge :outcome="run.outcome" />
          <span>{{ TASK_TYPE_LABEL[run.task_type] }}</span>
          <span v-if="run.error_type" class="badge" data-tone="rose">{{ run.error_type }}</span>
        </div>
        <p>{{ run.summary }}</p>
        <p v-if="run.error_message" class="banner banner-danger">{{ run.error_message }}</p>
        <dl class="meta">
          <div>
            <dt>开始</dt>
            <dd>{{ formatDateTime(run.started_at) }}</dd>
          </div>
          <div>
            <dt>结束</dt>
            <dd>{{ formatDateTime(run.finished_at) }}</dd>
          </div>
          <div>
            <dt>耗时</dt>
            <dd>{{ formatLatency(run.latency_ms) }}</dd>
          </div>
          <div>
            <dt>状态码</dt>
            <dd>{{ run.status_code ?? '—' }}</dd>
          </div>
          <div>
            <dt>请求器</dt>
            <dd>{{ run.requester }}</dd>
          </div>
          <div>
            <dt>代理</dt>
            <dd>{{ run.proxy_label || '直连' }}</dd>
          </div>
          <div>
            <dt>最终地址</dt>
            <dd>{{ run.final_url || '—' }}</dd>
          </div>
        </dl>
      </section>

      <section v-if="run.task_type === 'page_change'" class="card form-card">
        <h2>历史版本与差异</h2>
        <div class="grid-2">
          <label class="field"
            >对比前版本
            <select v-model="beforeId" :disabled="comparisonLoading" @change="clearComparison">
              <option value="">对比后版本的上次成功快照</option>
              <option
                v-for="version in versions"
                :key="version.id"
                :value="version.id"
                :disabled="!comparable(version)"
              >
                {{ formatDateTime(version.started_at) }} · {{ OUTCOME_LABEL[version.outcome] }} ·
                {{ version.id.slice(0, 8) }}
              </option>
            </select>
          </label>
          <label class="field"
            >对比后版本
            <select v-model="afterId" :disabled="comparisonLoading" @change="clearComparison">
              <option
                v-for="version in versions"
                :key="version.id"
                :value="version.id"
                :disabled="!comparable(version)"
              >
                {{ formatDateTime(version.started_at) }} · {{ OUTCOME_LABEL[version.outcome] }} ·
                {{ version.id.slice(0, 8) }}
              </option>
            </select>
          </label>
        </div>
        <div class="toolbar">
          <button
            class="btn-primary"
            type="button"
            :disabled="
              comparisonLoading ||
              !versions.some((version) => version.id === afterId && comparable(version))
            "
            @click="compareVersions"
          >
            {{ comparisonLoading ? '对比中…' : '对比版本' }}
          </button>
          <button
            v-if="versionsOffset < versionsTotal"
            class="btn-ghost"
            type="button"
            :disabled="versionsLoading"
            @click="loadVersions"
          >
            {{ versionsLoading ? '加载中…' : '加载更早版本' }}
          </button>
        </div>
        <p v-if="comparisonError" class="banner banner-danger" role="alert">
          {{ comparisonError }}
        </p>
        <SnapshotDiff v-if="displayedDiff" :diff="displayedDiff" />
        <p v-else-if="!comparisonError" class="hint">
          选择两个成功版本后点击对比，可查看逐行增删改。
        </p>
      </section>

      <section v-if="Object.keys(run.extracted).length" class="card form-card">
        <h2>本次提取</h2>
        <div v-for="(values, name) in run.extracted" :key="name">
          <strong>{{ name }}</strong>
          <pre class="pre">{{ values.join('\n') || '（空）' }}</pre>
        </div>
      </section>

      <section v-if="run.load" class="card form-card">
        <h2>压测汇总</h2>
        <dl class="meta">
          <div>
            <dt>总请求</dt>
            <dd>{{ formatNumber(run.load.total) }}</dd>
          </div>
          <div>
            <dt>成功</dt>
            <dd>{{ formatNumber(run.load.succeeded) }}</dd>
          </div>
          <div>
            <dt>失败</dt>
            <dd>{{ formatNumber(run.load.failed) }}</dd>
          </div>
          <div>
            <dt>拦截</dt>
            <dd>{{ formatNumber(run.load.blocked) }}</dd>
          </div>
          <div>
            <dt>超时</dt>
            <dd>{{ formatNumber(run.load.timeouts) }}</dd>
          </div>
          <div>
            <dt>P50 / P95</dt>
            <dd>
              {{ formatLatency(run.load.latency_ms_p50) }} /
              {{ formatLatency(run.load.latency_ms_p95) }}
            </dd>
          </div>
        </dl>
        <div v-for="bar in histogram" :key="bar.code" class="bar-row">
          <span>{{ bar.code }}</span>
          <span class="bar" :style="{ width: bar.width }" />
          <span>{{ bar.count }}</span>
        </div>
      </section>

      <section class="card form-card">
        <h2>响应头</h2>
        <pre class="pre">{{
          Object.entries(run.headers)
            .map(([key, value]) => `${key}: ${value}`)
            .join('\n') || '（无）'
        }}</pre>
      </section>
      <section class="card form-card">
        <h2>响应正文</h2>
        <p v-if="run.body_truncated" class="hint">正文已按存储上限截断。</p>
        <pre class="pre">{{ run.body || '（空）' }}</pre>
      </section>
    </template>
  </ModulePageShell>
</template>
