import { createApp } from 'vue'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import i18n from './i18n'

const app = createApp(App)
app.use(ElementPlus)
app.use(i18n)
app.mount('#app')