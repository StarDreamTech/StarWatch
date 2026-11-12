<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import ConfirmDialog from '@/components/shell/ConfirmDialog.vue'
import IconRail from '@/components/shell/IconRail.vue'
import MobileDrawer from '@/components/shell/MobileDrawer.vue'
import SubMenu from '@/components/shell/SubMenu.vue'
import TopBar from '@/components/shell/TopBar.vue'
import { LIST_POLL_MS } from '@/lib/constants'
import { useCatalogStore } from '@/stores/catalog'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const catalog = useCatalogStore()
let timer = 0

function onKey(event: KeyboardEvent) {
  if (event.key !== 'Escape') return
  ui.drawerOpen = false
  ui.closePopovers()
  if (ui.pendingConfirm) ui.settleConfirm(false)
}

onMounted(() => {
  void catalog.refresh()
  timer = window.setInterval(() => void catalog.refresh(), LIST_POLL_MS)
  window.addEventListener('keydown', onKey)
})

onUnmounted(() => {
  window.clearInterval(timer)
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div class="shell">
    <TopBar />
    <div class="shell-body">
      <IconRail class="desktop-only" />
      <SubMenu class="desktop-only" />
      <main class="content">
        <p v-if="ui.notice" class="flash" role="status">{{ ui.notice }}</p>
        <RouterView />
      </main>
    </div>
    <MobileDrawer />
    <ConfirmDialog />
  </div>
</template>
