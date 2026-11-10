<script setup lang="ts">
import { PanelLeftClose } from '@lucide/vue'
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { moduleById } from '@/lib/navigation'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const ui = useUiStore()
const current = computed(() => moduleById(route.meta.module))
</script>

<template>
  <aside class="submenu" :class="{ collapsed: ui.submenuCollapsed }" :data-accent="current.accent">
    <div class="submenu-inner">
      <button class="collapse-btn" type="button" @click="ui.submenuCollapsed = true">
        <PanelLeftClose :size="16" />
        收起
      </button>
      <RouterLink
        v-for="child in current.children"
        :key="child.to"
        :to="child.to"
        class="sub-link"
        :class="{ active: route.path === child.to }"
      >
        <component :is="child.icon" :size="16" />
        <span>
          {{ child.name }}
          <small>{{ child.description }}</small>
        </span>
      </RouterLink>
    </div>
  </aside>
</template>
