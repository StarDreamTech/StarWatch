<script setup lang="ts">
import { Plus, Trash2 } from '@lucide/vue'
import type { Pair } from '@/lib/taskDraft'

const props = defineProps<{
  modelValue: Pair[]
  keyPlaceholder: string
  valuePlaceholder: string
  addLabel: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: Pair[]] }>()

function update(index: number, field: keyof Pair, value: string) {
  emit(
    'update:modelValue',
    props.modelValue.map((item, itemIndex) =>
      itemIndex === index ? { ...item, [field]: value } : item,
    ),
  )
}

function add() {
  emit('update:modelValue', [...props.modelValue, { key: '', value: '' }])
}

function remove(index: number) {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, itemIndex) => itemIndex !== index),
  )
}
</script>

<template>
  <div class="stack">
    <div v-for="(pair, index) in modelValue" :key="index" class="pair-row">
      <input
        :value="pair.key"
        :placeholder="keyPlaceholder"
        :aria-label="keyPlaceholder"
        @input="update(index, 'key', ($event.target as HTMLInputElement).value)"
      />
      <input
        :value="pair.value"
        :placeholder="valuePlaceholder"
        :aria-label="valuePlaceholder"
        @input="update(index, 'value', ($event.target as HTMLInputElement).value)"
      />
      <button class="icon-btn" type="button" aria-label="删除一行" @click="remove(index)">
        <Trash2 :size="16" />
      </button>
    </div>
    <button class="btn-ghost" type="button" @click="add">
      <Plus :size="16" />
      {{ addLabel }}
    </button>
  </div>
</template>
