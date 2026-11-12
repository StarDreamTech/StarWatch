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
  <section class="page">
    <header class="page-head">
      <div class="page-title">
        <span class="page-icon" :data-accent="accent"><component :is="icon" :size="20" /></span>
        <div>
          <h1>{{ title }}</h1>
          <p>{{ description }}</p>
        </div>
      </div>
      <div class="page-actions">
        <slot name="actions" />
      </div>
    </header>
    <slot />
  </section>
</template>
