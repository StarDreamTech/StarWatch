<script setup lang="ts">
import { Moon, Sun } from '@lucide/vue'
import { onMounted, ref } from 'vue'
import ModulePageShell from '@/components/common/ModulePageShell.vue'
import { ApiError, apiBase, fetchHealth } from '@/lib/client'
import { moduleById } from '@/lib/navigation'
import { useUiStore } from '@/stores/ui'
import type { Health } from '@/types/api'

const ui = useUiStore()
const health = ref<Health | null>(null)
const error = ref('')
const current = moduleById('settings')

function mongoLabel(value: Health['mongo'] | undefined): string {
  if (value === 'ok') return '可连接'
  if (value === 'down') return '不可用'
  if (value === 'skipped') return '未使用，当前是内存试验'
  return '检测中'
}

onMounted(async () => {
  try {
    health.value = await fetchHealth()
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '无法读取调度器状态'
  }
})
</script>

<template>
  <ModulePageShell
    :title="current.name"
    :description="$route.meta.description"
    :icon="current.icon"
    :accent="current.accent"
  >
    <section class="card form-card">
      <h2>外观</h2>
      <p class="hint">主题保存在这台浏览器的本地存储里，键名是 starwatch.theme。</p>
      <button class="btn-primary" type="button" @click="ui.toggleTheme()">
        <Sun v-if="ui.theme === 'dark'" :size="16" />
        <Moon v-else :size="16" />
        {{ ui.theme === 'dark' ? '切换为浅色' : '切换为深色' }}
      </button>
    </section>
    <section class="card form-card">
      <h2>调度器</h2>
      <p v-if="error" class="banner banner-danger" role="alert">{{ error }}</p>
      <dl v-else class="meta">
        <div>
          <dt>接口前缀</dt>
          <dd>{{ apiBase() }}</dd>
        </div>
        <div>
          <dt>服务</dt>
          <dd>{{ health?.service ?? '检测中' }}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>{{ health ? (health.status === 'ok' ? '正常' : '降级') : '检测中' }}</dd>
        </div>
        <div>
          <dt>MongoDB</dt>
          <dd>
            {{ mongoLabel(health?.mongo) }}
          </dd>
        </div>
      </dl>
      <p class="hint">数据库、时区、跨域来源和限流都由环境变量配置，不在页面里保存密钥。</p>
    </section>
    <section class="card form-card">
      <h2>关于</h2>
      <p>星哨 StarWatch 0.1.0。调度器只负责时间和存储，抓取由独立的 fetcher 完成。</p>
      <p class="hint">当前操作员是这台自托管实例的本地使用者，没有单独的登录账号。</p>
    </section>
  </ModulePageShell>
</template>
