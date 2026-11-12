<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'
import { MODULES } from '@/lib/navigation'
import { useCatalogStore } from '@/stores/catalog'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const ui = useUiStore()
const catalog = useCatalogStore()

function select(id: string) {
  if (route.meta.module === id) ui.submenuCollapsed = false
  ui.openModule()
}
</script>

<template>
  <nav class="rail" aria-label="模块">
    <RouterLink
      v-for="item in MODULES"
      :key="item.id"
      :to="item.to"
      class="rail-link"
      :class="{ active: route.meta.module === item.id }"
      :data-accent="item.accent"
      :title="item.name"
      @click="select(item.id)"
    >
      <component :is="item.icon" :size="18" />
      <span class="rail-copy">
        <span class="rail-name">{{ item.name }}</span>
        <span class="rail-en">{{ item.en }}</span>
      </span>
      <span v-if="catalog.count(item.id) > 0" class="count">{{ catalog.count(item.id) }}</span>
    </RouterLink>
  </nav>
</template>
