<script setup lang="ts">
import { DIFF_LABEL } from '@/lib/constants'
import type { DiffResult } from '@/types/api'

defineProps<{ diff: DiffResult }>()

const tones = { added: 'emerald', removed: 'rose', modified: 'amber', unchanged: 'muted' }
</script>

<template>
  <div class="stack">
    <p class="hint">{{ diff.changed ? '所选版本之间有变化。' : '所选版本内容一致。' }}</p>
    <div class="toolbar" aria-label="差异颜色说明">
      <span class="badge" data-tone="emerald">+ 新增</span>
      <span class="badge" data-tone="rose">− 删除</span>
      <span class="badge" data-tone="amber">~ 修改</span>
    </div>
    <article v-for="field in diff.fields" :key="field.name" class="stack">
      <div class="toolbar">
        <strong>{{ field.name }}</strong>
        <span class="badge" :data-tone="tones[field.status]">{{ DIFF_LABEL[field.status] }}</span>
      </div>
      <div class="diff-scroll">
        <table class="diff-table" :aria-label="`${field.name} 逐行差异`">
          <colgroup>
            <col class="number-column" />
            <col />
            <col class="number-column" />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th colspan="2">对比前</th>
              <th colspan="2">对比后</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(line, index) in field.lines"
              :key="index"
              :aria-label="DIFF_LABEL[line.status]"
            >
              <td class="line-number">{{ line.before_number }}</td>
              <td>
                <div class="line">
                  <span v-if="line.before !== null" class="mark" :data-status="line.status">{{
                    line.before
                  }}</span>
                </div>
              </td>
              <td class="line-number">{{ line.after_number }}</td>
              <td>
                <div class="line">
                  <span v-if="line.after !== null" class="mark" :data-status="line.status">{{
                    line.after
                  }}</span>
                </div>
              </td>
            </tr>
            <tr v-if="!field.lines.length">
              <td colspan="4">（空）</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </div>
</template>

<style scoped>
.diff-scroll {
  overflow: auto;
  max-height: 640px;
  border: 1px solid var(--sw-border);
  border-radius: 10px;
}
.diff-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
}
th {
  text-align: left;
  padding: 10px;
  background: var(--sw-panel);
}
td {
  vertical-align: top;
  padding: 3px 8px;
}
.number-column {
  width: 44px;
}
.line-number {
  text-align: right;
  color: var(--sw-muted);
  font-size: 12px;
  user-select: none;
}
.line {
  min-height: 1.5em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
}
.mark {
  white-space: break-spaces;
  overflow-wrap: anywhere;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}
.mark[data-status='added'] {
  background: color-mix(in srgb, var(--sw-emerald) 34%, transparent);
}
.mark[data-status='removed'] {
  background: color-mix(in srgb, var(--sw-rose) 32%, transparent);
}
.mark[data-status='modified'] {
  background: color-mix(in srgb, var(--sw-amber) 38%, transparent);
}
td:nth-child(2) {
  border-right: 1px solid var(--sw-border);
}
</style>
