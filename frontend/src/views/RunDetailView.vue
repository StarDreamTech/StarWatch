<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ModulePageShell from '@/components/common/ModulePageShell.vue'
import OutcomeBadge from '@/components/common/OutcomeBadge.vue'
import { ApiError, api } from '@/lib/client'
import { DIFF_LABEL, TASK_TYPE_LABEL, taskEditorPath } from '@/lib/constants'
import { formatDateTime, formatLatency, formatNumber } from '@/lib/format'
import { moduleById } from '@/lib/navigation'
import type { Run } from '@/types/api'

const route = useRoute()
const run = ref<Run | null>(null)
const loading = ref(true)
const error = ref('')
const current = moduleById('runs')

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
  const id = route.params.id
  if (typeof id !== 'string') return
  try {
    run.value = await api<Run>(`/runs/${id}`)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '运行详情加载失败'
  } finally {
    loading.value = false
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

      <section v-if="run.diff" class="card form-card">
        <h2>字段差异</h2>
        <p class="hint">
          {{ run.diff.changed ? '和上一份成功快照相比有变化。' : '提取字段与上一份快照一致。' }}
        </p>
        <article v-for="field in run.diff.fields" :key="field.name" class="stack">
          <div class="toolbar">
            <strong>{{ field.name }}</strong>
            <span class="badge" :data-tone="field.status === 'unchanged' ? 'muted' : 'cyan'">{{
              DIFF_LABEL[field.status]
            }}</span>
          </div>
          <div class="diff-grid">
            <pre class="diff-box before">{{ field.before.join('\n') || '（空）' }}</pre>
            <pre class="diff-box after">{{ field.after.join('\n') || '（空）' }}</pre>
          </div>
        </article>
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
