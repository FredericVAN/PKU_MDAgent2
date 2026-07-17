import { createI18n } from 'vue-i18n'
import en from './locales/en'
import zh from './locales/zh'

const STORAGE_KEY = 'lammps-frontend-locale'
const SUPPORTED = ['en', 'zh']

function detectLocale() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved && SUPPORTED.includes(saved)) return saved
  return 'en'
}

const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages: { en, zh },
})

export function setLocale(locale) {
  if (!SUPPORTED.includes(locale)) return
  i18n.global.locale.value = locale
  localStorage.setItem(STORAGE_KEY, locale)
}

export default i18n
