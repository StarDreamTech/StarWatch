<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'
import { MODULES } from '@/lib/navigation'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const ui = useUiStore()
</script>

<template>
  <div v-if="ui.drawerOpen" class="mobile-only">
    <button
      class="drawer-backdrop"
      type="button"
      aria-label="关闭导航"
      @click="ui.drawerOpen = false"
    />
    <nav class="drawer" aria-label="移动导航">
      <section v-for="item in MODULES" :key="item.id" :data-accent="item.accent">
        <h2>{{ item.name }}</h2>
        <RouterLink
          v-for="child in item.children"
          :key="child.to + item.id"
          :to="child.to"
          class="sub-link"
          :class="{ active: route.path === child.to }"
          @click="ui.drawerOpen = false"
        >
          <component :is="child.icon" :size="16" />
          <span>
            {{ child.name }}
            <small>{{ child.description }}</small>
          </span>
        </RouterLink>
      </section>
    </nav>
  </div>
</template>
