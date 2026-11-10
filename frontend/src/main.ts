import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { useUiStore } from './stores/ui'
import './styles/theme.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
useUiStore(pinia).hydrateTheme()
app.use(router)
app.mount('#app')
