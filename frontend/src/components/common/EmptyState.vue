<script setup lang="ts">
import type { Component } from 'vue'
import type { Accent } from '@/lib/navigation'

defineProps<{
  title: string
  description: string
  icon: Component
  accent: Accent
}>()
</script>

<template>
  <div class="card empty" :data-accent="accent">
    <div>
      <div class="empty-icon"><component :is="icon" :size="32" /></div>
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
      <slot />
    </div>
  </div>
</template>
