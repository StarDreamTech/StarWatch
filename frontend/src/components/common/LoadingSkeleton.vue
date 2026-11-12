<script setup lang="ts">
withDefaults(defineProps<{ rows?: number }>(), { rows: 4 })
</script>

<template>
  <div class="card skeleton" aria-hidden="true">
    <div
      v-for="index in rows"
      :key="index"
      class="pulse"
      :style="{ width: `${88 - (index % 3) * 12}%` }"
    />
  </div>
</template>
