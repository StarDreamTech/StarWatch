<script setup lang="ts">
import { Play } from '@lucide/vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ModulePageShell from '@/components/common/ModulePageShell.vue'
import PairEditor from '@/components/common/PairEditor.vue'
import { ApiError, api } from '@/lib/client'
import { ASSERTION_KINDS, EXTRACTOR_KINDS, HTTP_METHODS, taskListPath } from '@/lib/constants'
import { moduleById } from '@/lib/navigation'
import { draftFromTask, emptyDraft, payloadFromDraft, type TaskDraft } from '@/lib/taskDraft'
import { useUiStore } from '@/stores/ui'
import type { PluginInfo, Run, Task, TaskType } from '@/types/api'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()
const plugins = ref<PluginInfo[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const taskType = computed(() => route.meta.taskType as TaskType)
const editingId = computed(() => (typeof route.params.id === 'string' ? route.params.id : ''))
const current = computed(() => moduleById(route.meta.module))
const draft = reactive<TaskDraft>(emptyDraft('page_change'))

const requesters = computed(() => plugins.value.filter((item) => item.slot === 'requester'))
const proxies = computed(() => plugins.value.filter((item) => item.slot === 'proxy'))
const notifiers = computed(() => plugins.value.filter((item) => item.slot === 'notifier'))
const requesterInfo = computed(() => requesters.value.find((item) => item.name === draft.requester))
const proxyInfo = computed(() => proxies.value.find((item) => item.name === draft.proxyProvider))
const notifierInfo = computed(() =>
  notifiers.value.find((item) => item.name === draft.notifyProvider),
)

function replaceDraft(next: TaskDraft) {
  Object.assign(draft, next)
}

async function load() {
  error.value = ''
  if (!editingId.value) {
    replaceDraft(emptyDraft(taskType.value))
    return
  }
  loading.value = true
  try {
    const task = await api<Task>(`/tasks/${editingId.value}`)
    if (task.task_type !== taskType.value) {
      error.value = '这条任务属于另一个模块'
      return
    }
    replaceDraft(draftFromTask(task))
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '任务读取失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => route.fullPath,
  () => void load(),
  { immediate: true },
)

onMounted(async () => {
  try {
    plugins.value = await api<PluginInfo[]>('/plugins')
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '插件目录读取失败'
  }
})

async function save() {
  const payload = payloadFromDraft(taskType.value, draft)
  if (!payload.ok) {
    error.value = payload.message
    return
  }
  if (taskType.value === 'load_test' && draft.enabled) {
    const accepted = await ui.confirm({
      title: '保存压力测试',
      message: '任务启用后，调度器会按计划向目标发送压测流量。确认保存？',
      confirmLabel: '保存并启用',
      tone: 'primary',
    })
    if (!accepted) return
  }
  saving.value = true
  error.value = ''
  try {
    const saved = editingId.value
      ? await api<Task>(`/tasks/${editingId.value}`, {
          method: 'PUT',
          body: JSON.stringify(payload.body),
        })
      : await api<Task>('/tasks', { method: 'POST', body: JSON.stringify(payload.body) })
    ui.flash(editingId.value ? '任务已保存' : '任务已创建')
    if (!editingId.value) await router.replace(`${taskListPath(taskType.value)}/${saved.id}`)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function runNow() {
  if (!editingId.value) return
  if (taskType.value === 'load_test') {
    const accepted = await ui.confirm({
      title: '开始压力测试',
      message: '立即运行会向目标发送多批请求。确认开始？',
      confirmLabel: '开始压测',
      tone: 'primary',
    })
    if (!accepted) return
  }
  saving.value = true
  try {
    const result = await api<Run>(`/tasks/${editingId.value}/run`, { method: 'POST' })
    await router.push(`/runs/${result.id}`)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '运行失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <ModulePageShell
    :title="route.meta.title"
    :description="route.meta.description"
    :icon="current.icon"
    :accent="current.accent"
  >
    <template #actions>
      <button v-if="editingId" class="btn-ghost" type="button" :disabled="saving" @click="runNow">
        <Play :size="16" />
        立即运行
      </button>
      <button class="btn-primary" type="button" :disabled="saving || loading" @click="save">
        {{ saving ? '保存中…' : '保存' }}
      </button>
    </template>
    <p v-if="error" class="banner banner-danger" role="alert">{{ error }}</p>
    <form class="stack" @submit.prevent="save">
      <section class="card form-card">
        <h2>基本信息</h2>
        <div class="grid-2">
          <label class="field">名称<input v-model="draft.name" maxlength="80" required /></label>
          <label class="field"
            >调度<input
              v-model="draft.schedule"
              placeholder="every 5 minutes 或 */5 * * * *"
              required
          /></label>
        </div>
        <p class="hint">
          支持五段 cron，也支持 every 30s、every 1 minute、每 2 分钟。最短间隔 5 秒。
        </p>
        <label class="field">说明<textarea v-model="draft.description" maxlength="500" /></label>
        <label class="check"
          ><input v-model="draft.enabled" type="checkbox" /><span
            >启用后由调度器按计划触发</span
          ></label
        >
      </section>

      <section class="card form-card">
        <h2>请求</h2>
        <div class="grid-2">
          <label class="field">
            方法
            <select v-model="draft.method">
              <option v-for="method in HTTP_METHODS" :key="method" :value="method">
                {{ method }}
              </option>
            </select>
          </label>
          <label class="field"
            >超时（秒）<input v-model="draft.timeoutSeconds" inputmode="decimal"
          /></label>
        </div>
        <label class="field"
          >地址<input v-model="draft.url" type="url" placeholder="https://example.com" required
        /></label>
        <label class="check"
          ><input v-model="draft.followRedirects" type="checkbox" /><span>跟随重定向</span></label
        >
        <label class="check"
          ><input v-model="draft.verifyTls" type="checkbox" /><span>校验 TLS 证书</span></label
        >
        <details class="details">
          <summary>请求头、查询参数和 Cookie</summary>
          <div class="stack" style="margin-top: 12px">
            <PairEditor
              v-model="draft.headers"
              key-placeholder="Header"
              value-placeholder="值"
              add-label="添加请求头"
            />
            <PairEditor
              v-model="draft.query"
              key-placeholder="参数"
              value-placeholder="值"
              add-label="添加查询参数"
            />
            <PairEditor
              v-model="draft.cookies"
              key-placeholder="Cookie"
              value-placeholder="值"
              add-label="添加 Cookie"
            />
          </div>
        </details>
        <label class="field">
          正文
          <select v-model="draft.bodyMode">
            <option value="none">无</option>
            <option value="json">JSON</option>
            <option value="form">表单</option>
            <option value="raw">原文</option>
          </select>
        </label>
        <label v-if="draft.bodyMode === 'json'" class="field"
          >JSON<textarea v-model="draft.jsonText" />
        </label>
        <PairEditor
          v-else-if="draft.bodyMode === 'form'"
          v-model="draft.formPairs"
          key-placeholder="字段"
          value-placeholder="值"
          add-label="添加字段"
        />
        <label v-else-if="draft.bodyMode === 'raw'" class="field"
          >原文<textarea v-model="draft.rawBody" />
        </label>
      </section>

      <section class="card form-card">
        <h2>请求器与代理</h2>
        <div class="grid-2">
          <label class="field">
            请求器
            <select v-model="draft.requester">
              <option v-for="item in requesters" :key="item.name" :value="item.name">
                {{ item.name }}{{ item.implemented ? '' : '（未实现）' }}
              </option>
            </select>
          </label>
          <label class="field">
            代理
            <select v-model="draft.proxyProvider">
              <option v-for="item in proxies" :key="item.name" :value="item.name">
                {{ item.name }}{{ item.implemented ? '' : '（未实现）' }}
              </option>
            </select>
          </label>
        </div>
        <p v-if="requesterInfo" class="hint">{{ requesterInfo.description }}</p>
        <p v-if="proxyInfo" class="hint">{{ proxyInfo.description }}</p>
        <label v-if="draft.proxyProvider === 'static'" class="field"
          >代理 URL<input v-model="draft.proxyUrl" placeholder="http://127.0.0.1:8088"
        /></label>
        <label v-else-if="draft.proxyProvider === 'rotating'" class="field"
          >代理列表，每行一个<textarea v-model="draft.proxyUrls" />
        </label>
        <label v-else-if="draft.proxyProvider === 'pool_api'" class="field"
          >代理池地址<input v-model="draft.proxyEndpoint" placeholder="http://pool.internal/lease"
        /></label>
      </section>

      <section v-if="taskType === 'page_change'" class="card form-card">
        <h2>提取字段</h2>
        <p class="hint">只比较这些字段。空提取会记为「内容为空」，不会覆盖上一份快照。</p>
        <div v-for="(rule, index) in draft.rules" :key="index" class="rule-grid">
          <input v-model="rule.name" placeholder="字段名" aria-label="字段名" />
          <select v-model="rule.kind" aria-label="提取方式">
            <option v-for="kind in EXTRACTOR_KINDS" :key="kind" :value="kind">{{ kind }}</option>
          </select>
          <input v-model="rule.expression" placeholder="表达式" aria-label="表达式" />
          <input v-model="rule.attribute" placeholder="属性，可空" aria-label="属性" />
          <button class="btn-ghost" type="button" @click="draft.rules.splice(index, 1)">
            删除
          </button>
        </div>
        <button
          class="btn-ghost"
          type="button"
          @click="draft.rules.push({ name: '', kind: 'css', expression: '', attribute: '' })"
        >
          添加字段
        </button>
      </section>

      <section v-if="taskType === 'api_check'" class="card form-card">
        <h2>断言</h2>
        <p class="hint">
          期望状态码可以让 404 这类响应通过。没有断言时，空的成功响应会记为内容为空。
        </p>
        <div v-for="(item, index) in draft.assertions" :key="index" class="rule-grid">
          <select v-model="item.kind" aria-label="断言类型">
            <option v-for="kind in ASSERTION_KINDS" :key="kind" :value="kind">{{ kind }}</option>
          </select>
          <input v-model="item.expected" placeholder="期望值" aria-label="期望值" />
          <input v-model="item.path" placeholder="path，状态码可空" aria-label="path" />
          <button class="btn-ghost" type="button" @click="draft.assertions.splice(index, 1)">
            删除
          </button>
        </div>
        <button
          class="btn-ghost"
          type="button"
          @click="draft.assertions.push({ kind: 'status', expected: '200', path: '' })"
        >
          添加断言
        </button>
      </section>

      <section v-if="taskType === 'load_test'" class="card form-card">
        <h2>压测参数</h2>
        <div class="grid-2">
          <label class="field"
            >并发（1–50）<input v-model="draft.concurrency" inputmode="numeric"
          /></label>
          <label class="field"
            >QPS，可空（≤100）<input v-model="draft.qps" inputmode="decimal"
          /></label>
          <label class="field"
            >持续秒数，可空（≤60）<input v-model="draft.durationSeconds" inputmode="decimal"
          /></label>
          <label class="field"
            >请求次数，可空（≤200）<input v-model="draft.requestCount" inputmode="numeric"
          /></label>
        </div>
        <p class="hint">
          持续时间和请求次数都留空时，抓取器使用默认的 10 次。单次压测最多 200 个请求。
        </p>
      </section>

      <section class="card form-card">
        <h2>通知</h2>
        <label class="field">
          外部通道
          <select v-model="draft.notifyProvider">
            <option v-for="item in notifiers" :key="item.name" :value="item.name">
              {{ item.name }}{{ item.implemented ? '' : '（未实现）' }}
            </option>
          </select>
        </label>
        <p v-if="notifierInfo" class="hint">{{ notifierInfo.description }} 站内通知仍会写入。</p>
        <label v-if="draft.notifyProvider === 'webhook'" class="field"
          >Webhook URL<input v-model="draft.webhookUrl" type="url"
        /></label>
        <div class="toolbar">
          <label class="check"
            ><input v-model="draft.notifyOn.change" type="checkbox" /><span>变化</span></label
          >
          <label class="check"
            ><input v-model="draft.notifyOn.failure" type="checkbox" /><span>失败</span></label
          >
          <label class="check"
            ><input v-model="draft.notifyOn.block" type="checkbox" /><span>拦截</span></label
          >
        </div>
      </section>
    </form>
  </ModulePageShell>
</template>
