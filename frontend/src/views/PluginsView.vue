<script setup lang="ts">
import { Blocks } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'
import ModulePageShell from '@/components/common/ModulePageShell.vue'
import { ApiError, api } from '@/lib/client'
import { SLOT_LABEL } from '@/lib/constants'
import { moduleById } from '@/lib/navigation'
import type { PluginInfo } from '@/types/api'

const plugins = ref<PluginInfo[]>([])
const loading = ref(true)
const error = ref('')
const current = moduleById('plugins')

const groups = computed(() => {
  const order = ['requester', 'proxy', 'extractor', 'notifier', 'task']
  return order
    .map((slot) => ({
      slot,
      label: SLOT_LABEL[slot] ?? slot,
      items: plugins.value.filter((item) => item.slot === slot),
    }))
    .filter((group) => group.items.length > 0)
})

onMounted(async () => {
  try {
    plugins.value = await api<PluginInfo[]>('/plugins')
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : '插件目录加载失败'
  } finally {
    loading.value = false
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
    <p v-if="error" class="banner banner-danger" role="alert">{{ error }}</p>
    <LoadingSkeleton v-if="loading" />
    <EmptyState
      v-else-if="groups.length === 0"
      title="没有注册插件"
      description="调度器启动时会装入内置插件。如果这里是空的，请检查服务日志。"
      :icon="Blocks"
      accent="violet"
    />
    <section v-for="group in groups" :key="group.slot" class="stack">
      <h2>{{ group.label }}</h2>
      <div class="card-grid">
        <article v-for="item in group.items" :key="group.slot + item.name" class="card form-card">
          <div class="toolbar">
            <strong>{{ item.name }}</strong>
            <span class="badge" :data-tone="item.implemented ? 'emerald' : 'amber'">
              {{ item.implemented ? '可用' : '存根' }}
            </span>
          </div>
          <p class="hint">{{ item.description }}</p>
        </article>
      </div>
    </section>
  </ModulePageShell>
</template>
