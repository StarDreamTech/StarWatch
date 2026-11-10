<script setup lang="ts">
import type { Component } from 'vue'
import type { Accent } from '@/lib/navigation'

defineProps<{
  label: string
  value: string | number
  hint?: string
  icon: Component
  accent: Accent
}>()
</script>

<template>
  <article class="stat-card" :data-accent="accent">
    <span class="stat-icon"><component :is="icon" :size="18" /></span>
    <div>
      <p class="stat-label">{{ label }}</p>
      <p class="stat-value">{{ value }}</p>
      <p v-if="hint" class="stat-hint">{{ hint }}</p>
    </div>
  </article>
</template>
