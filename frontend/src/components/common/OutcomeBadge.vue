<script setup lang="ts">
import { computed } from 'vue'
import { OUTCOME_LABEL, OUTCOME_TONE } from '@/lib/constants'
import type { Outcome } from '@/types/api'

const props = defineProps<{ outcome: Outcome | null }>()
const label = computed(() => (props.outcome ? OUTCOME_LABEL[props.outcome] : '尚未运行'))
const tone = computed(() => (props.outcome ? OUTCOME_TONE[props.outcome] : 'muted'))
</script>

<template>
  <span class="badge" :data-tone="tone">{{ label }}</span>
</template>
