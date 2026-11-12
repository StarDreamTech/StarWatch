<script setup lang="ts">
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
</script>

<template>
  <div v-if="ui.pendingConfirm" class="dialog-backdrop" role="presentation">
    <div class="dialog" role="dialog" aria-modal="true" :aria-label="ui.pendingConfirm.title">
      <h2>{{ ui.pendingConfirm.title }}</h2>
      <p>{{ ui.pendingConfirm.message }}</p>
      <div class="dialog-actions">
        <button class="btn-ghost" type="button" @click="ui.settleConfirm(false)">取消</button>
        <button
          :class="ui.pendingConfirm.tone === 'danger' ? 'btn-danger' : 'btn-primary'"
          type="button"
          @click="ui.settleConfirm(true)"
        >
          {{ ui.pendingConfirm.confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
