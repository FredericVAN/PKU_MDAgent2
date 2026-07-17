<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-inner">
        <div class="brand">
          <span class="brand-badge"><el-icon><Cpu /></el-icon></span>
          <div class="brand-text">
            <h1>{{ t('app.title') }}</h1>
            <p>{{ t('app.subtitle') }}</p>
          </div>
        </div>

        <div class="header-tools">
          <button class="icon-btn" :title="t('header.newChat')" @click="newChat">
            <el-icon><EditPen /></el-icon>
          </button>
          <button class="icon-btn" :title="t('header.history')" @click="openHistory">
            <el-icon><Clock /></el-icon>
          </button>
          <div class="lang-toggle">
            <button :class="{ active: locale === 'en' }" @click="changeLocale('en')">EN</button>
            <button :class="{ active: locale === 'zh' }" @click="changeLocale('zh')">中文</button>
          </div>
        </div>
      </div>
    </header>

    <main class="app-main">
      <div class="chat-panel" ref="scrollContainer">
        <div v-if="viewingHistoryId" class="history-banner">
          <el-icon><Clock /></el-icon>
          <span>{{ t('history.viewing') }}</span>
          <el-button text type="primary" size="small" @click="newChat">{{ t('history.backToLive') }}</el-button>
        </div>

        <div v-if="filteredMessages.length === 0 && !loading" class="empty-state">
          <el-icon class="empty-icon"><Edit /></el-icon>
          <p class="empty-title">{{ t('empty.title') }}</p>
          <p class="empty-desc">{{ t('empty.desc') }}</p>
          <div class="example-block">
            <span class="example-label">{{ t('empty.tryLabel') }}</span>
            <div class="example-chips">
              <div v-for="(ex, i) in exampleList" :key="i" class="example-chip" @click="input = ex">{{ ex }}</div>
            </div>
          </div>
        </div>

        <div class="message-list">
          <div
            v-for="(msg, idx) in filteredMessages"
            :key="idx"
            class="message-item"
            :style="{ '--accent': getColor(msg.node) }"
          >
            <div class="message-rail">
              <span class="marker-dot">
                <el-icon v-if="getIcon(msg.node)"><component :is="getIcon(msg.node)" /></el-icon>
              </span>
              <span class="rail-line" />
            </div>

            <div class="message-body">
              <div class="message-head">
                <span class="message-title">{{ nodeLabel(msg.node) }}</span>
                <span class="message-time">{{ msg.timestamp }}</span>
              </div>

              <!-- INIT 阶段：展示用户输入 -->
              <template v-if="msg.node === 'init' && msg.state.user_input">
                <div class="panel">
                  <el-tag type="info" size="large" round>{{ msg.state.user_input }}</el-tag>
                </div>
              </template>

              <!-- GENERATE 阶段：展示代码和文件名列表 -->
              <template v-else-if="msg.node === 'generate' && (msg.state.lammps_code || msg.state.checkout_filename_list)">
                <div v-if="msg.state.lammps_code" class="panel code-panel">
                  <div class="code-toolbar">
                    <span class="code-lang">LAMMPS Script</span>
                    <el-button text size="small" class="copy-btn" @click="copyCode(msg.state.lammps_code)">
                      <el-icon><CopyDocument /></el-icon>&nbsp;{{ t('generate.copy') }}
                    </el-button>
                  </div>
                  <pre class="code-block">{{ msg.state.lammps_code }}</pre>
                </div>
                <div v-if="msg.state.checkout_filename_list && msg.state.checkout_filename_list.length" class="panel">
                  <div class="panel-subtitle"><el-icon><Document /></el-icon>&nbsp;{{ t('generate.filesToGenerate') }}</div>
                  <div class="chip-grid">
                    <div v-for="(file, i) in fileList" :key="i">
                      <div v-if="!isImage(file) && getFileName(file).includes('in.')" class="file-chip">
                        <el-icon class="file-chip-icon"><Document /></el-icon>
                        <span class="file-chip-name">{{ getFileName(file) }}</span>
                        <el-button type="primary" link size="small" @click="downloadFile(file)">{{ t('run.download') }}</el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </template>

              <!-- RUN 阶段：展示运行结果和按钮 -->
              <template v-else-if="msg.node === 'run' && msg.state.run_result">
                <div class="panel">
                  <div class="panel-toolbar">
                    <div class="panel-subtitle-row">
                      <span class="panel-subtitle-plain">{{ nodeLabel('run') }}</span>
                      <el-tag v-if="msg.state.generate_dir" size="small" class="dir-tag" @click="copyDir(msg.state.abs_generate_dir || msg.state.generate_dir)">
                        <el-icon><FolderOpened /></el-icon>&nbsp;{{ msg.state.generate_dir }}
                      </el-tag>
                    </div>
                    <el-button
                      v-if="msg.state.generate_dir"
                      type="primary"
                      size="small"
                      plain
                      @click="runShowModel()"
                    >{{ !runResultShowModel ? t('run.raw') : t('run.processed') }}</el-button>
                  </div>

                  <pre v-if="runResultShowModel" class="code-block">{{ msg.state.run_result.extra_info }}</pre>
                  <div v-else class="stat-grid">
                    <div
                      v-for="(item, key) in msg.state.run_result.extra_info['log.lammps']"
                      :key="key"
                      class="stat-item"
                    >
                      <template v-if="key!='performance_info' && key!='warnings' && key!='summary'">
                        <div class="stat-label">{{ statLabel(key) }}</div>
                        <div
                          class="stat-value"
                          :class="{ 'stat-good': item === true, 'stat-bad': item === false }"
                        >{{ formatStatValue(item) }}</div>
                      </template>
                    </div>
                  </div>
                  <div class="summary-rows">
                    <div class="summary-row">
                      <span class="summary-label perf">{{ t('stats.performance_info') }}</span>
                      <span class="summary-value">{{ msg.state.run_result.extra_info['log.lammps']['performance_info'] }}</span>
                    </div>
                    <div class="summary-row">
                      <span class="summary-label warn">{{ t('stats.warnings') }}</span>
                      <span class="summary-value">{{ msg.state.run_result.extra_info['log.lammps']['warnings'] }}</span>
                    </div>
                    <div class="summary-row">
                      <span class="summary-label ok">{{ t('stats.summary') }}</span>
                      <span class="summary-value">{{ msg.state.run_result.extra_info['log.lammps']['summary'] }}</span>
                    </div>
                  </div>
                </div>

                <div v-if="msg.state.checkout_filename_list && msg.state.checkout_filename_list.length && fileList.length" class="panel">
                  <template v-if="fileList.some(isImage)">
                    <div class="panel-subtitle"><el-icon><Picture /></el-icon>&nbsp;{{ t('run.images') }}</div>
                    <div class="image-grid">
                      <div v-for="(file, i) in fileList" :key="i">
                        <div v-if="isImage(file)" class="image-card">
                          <img
                            :src="`${API_BASE}/file?path=${encodeURIComponent(file)}`"
                            :alt="getFileName(file)"
                            @click="previewImage(file)"
                          >
                          <div class="image-card-footer">
                            <span class="image-card-name">{{ getFileName(file) }}</span>
                            <el-button type="primary" link size="small" @click="downloadFile(file)">{{ t('run.download') }}</el-button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </template>

                  <template v-if="fileList.some(f => !isImage(f) && !getFileName(f).includes('in.'))">
                    <div class="panel-subtitle" style="margin-top: 20px;"><el-icon><Document /></el-icon>&nbsp;{{ t('run.files') }}</div>
                    <div class="chip-grid">
                      <div v-for="(file, i) in fileList" :key="i">
                        <div v-if="!isImage(file) && !getFileName(file).includes('in.')" class="file-chip">
                          <el-icon class="file-chip-icon"><Document /></el-icon>
                          <span class="file-chip-name">{{ getFileName(file) }}</span>
                          <el-button type="primary" link size="small" @click="downloadFile(file)">{{ t('run.download') }}</el-button>
                        </div>
                      </div>
                    </div>
                  </template>
                </div>
              </template>

              <!-- ERROR 阶段：展示后端报错 -->
              <template v-else-if="msg.node === 'error'">
                <div class="panel error-panel">
                  <pre class="code-block error-block">{{ msg.message }}</pre>
                </div>
              </template>

              <!-- EVAL 阶段：展示评估结果 -->
              <template v-else-if="msg.node === 'eval' && msg.state.eval_result">
                <div class="panel">
                  <div class="panel-toolbar">
                    <span class="panel-subtitle-plain">{{ nodeLabel('eval') }}</span>
                    <el-button
                      v-if="msg.state.generate_dir"
                      type="primary"
                      size="small"
                      plain
                      @click="evalShowModel()"
                    >{{ !evalResultShowModel ? t('run.raw') : t('run.processed') }}</el-button>
                  </div>
                  <pre v-if="evalResultShowModel" class="code-block">{{ msg.state.eval_result }}</pre>
                  <div v-else class="stat-grid">
                    <div
                      v-for="item in stringToJson(msg.state.eval_result).module_detail"
                      :key="item.id"
                      class="stat-item"
                    >
                      <div class="stat-label">{{ item.name }}</div>
                      <div class="stat-value">{{ item.score }}</div>
                    </div>
                    <div
                      v-for="item in stringToJson(msg.state.eval_result).penalty_detail"
                      :key="item.id"
                      class="stat-item stat-item-penalty"
                    >
                      <div class="stat-label">{{ item.name }}</div>
                      <div class="stat-value">{{ item.score }}</div>
                    </div>
                  </div>
                  <div v-if="msg.state.final_score" class="final-score">
                    <span>{{ t('eval.finalScore') }}</span>
                    <strong>{{ msg.state.final_score }}</strong>
                  </div>
                </div>
              </template>
            </div>
          </div>

          <div v-if="loading" class="message-item thinking-item">
            <div class="message-rail">
              <span class="marker-dot marker-dot-loading"><el-icon class="spin-icon"><Loading /></el-icon></span>
            </div>
            <div class="message-body">
              <div class="thinking-text">
                <span class="thinking-dots"><i /><i /><i /></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 图片预览弹窗 -->
    <el-dialog v-model="imgDialogVisible" width="auto" :show-close="true" center class="preview-dialog">
      <img :src="imgPreviewUrl" class="preview-dialog-img" />
    </el-dialog>

    <!-- 历史记录抽屉 -->
    <el-drawer v-model="historyDrawerVisible" :title="t('history.title')" direction="rtl" size="380px" @open="fetchHistoryList">
      <div v-if="historyLoading" class="history-loading"><el-icon class="spin-icon"><Loading /></el-icon></div>
      <div v-else-if="historyList.length === 0" class="history-empty">{{ t('history.empty') }}</div>
      <div v-else class="history-list">
        <div
          v-for="item in historyList"
          :key="item.id"
          class="history-item"
          :class="{ active: item.id === viewingHistoryId }"
          @click="loadHistoryItem(item.id)"
        >
          <div class="history-item-top">
            <el-tag :type="item.status === 'error' ? 'danger' : 'success'" size="small" effect="plain">
              {{ item.status === 'error' ? t('history.statusError') : t('history.statusSuccess') }}
            </el-tag>
            <span class="history-item-time">{{ formatTime(item.created_at) }}</span>
          </div>
          <div class="history-item-text">{{ item.user_input }}</div>
          <div class="history-item-bottom">
            <span v-if="item.final_score" class="history-item-score">{{ t('history.score') }}: {{ item.final_score }}</span>
            <el-button text type="danger" size="small" @click.stop="deleteHistoryItem(item.id)">{{ t('history.delete') }}</el-button>
          </div>
        </div>
      </div>
    </el-drawer>

    <footer class="input-bar">
      <div class="input-inner-wrap">
        <div class="input-inner">
          <el-input
            v-model="input"
            class="task-input"
            :disabled="loading"
            :rows="2"
            type="textarea"
            :placeholder="t('input.placeholder')"
            @keydown.enter.exact.prevent="send"
            resize="none"
          />
          <el-button
            type="primary"
            class="send-btn"
            circle
            size="large"
            @click="send"
            :loading="loading"
          >
            <el-icon v-if="!loading"><Promotion /></el-icon>
          </el-button>
        </div>
        <div class="input-hint">{{ t('input.hint') }}</div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { setLocale } from './i18n'
import {
  Edit, Cpu, Star, User, Picture, Document, WarningFilled,
  Promotion, Loading, CopyDocument, FolderOpened, Clock, EditPen,
} from '@element-plus/icons-vue'

const { t, tm, te, locale } = useI18n()

function changeLocale(l) {
  setLocale(l)
}

// 后端地址：优先使用 VITE_API_BASE 环境变量，未设置时回退到本机开发地址
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// 对话区相关
const input = ref('')
const messages = ref([])
const loading = ref(false)
const scrollContainer = ref(null)
const viewingHistoryId = ref(null)
let activeAbortController = null

const exampleList = computed(() => tm('empty.examples'))

function scrollToBottom() {
  nextTick(() => {
    const el = scrollContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function showStreamError(text) {
  messages.value.push({
    node: 'error',
    message: text,
    timestamp: new Date().toLocaleString()
  })
  ElMessage.error(text)
  loading.value = false
}

function newChat() {
  if (activeAbortController) activeAbortController.abort()
  loading.value = false
  messages.value = []
  input.value = ''
  viewingHistoryId.value = null
}

function send() {
  if (!input.value.trim()) return
  if (activeAbortController) activeAbortController.abort()
  const controller = new AbortController()
  activeAbortController = controller
  viewingHistoryId.value = null
  messages.value = []
  loading.value = true
  fetch(`${API_BASE}/run_lammps_agents_stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_input: input.value }),
    signal: controller.signal,
  }).then(response => {
    if (!response.ok) {
      return response.text().then(text => {
        throw new Error(text || `${t('error.statusCode')}${response.status}`)
      })
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    function read() {
      reader.read().then(({ done, value }) => {
        if (done) {
          loading.value = false
          return
        }
        buffer += decoder.decode(value, { stream: true })
        let lines = buffer.split('\n\n')
        buffer = lines.pop()
        for (let line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            // 增加时间戳
            data.timestamp = new Date().toLocaleString()
            messages.value.push(data)

            // 如果是 run 节点且有 abs_generate_dir，立即刷新文件列表
            if (data.node === 'run' && data.state && data.state.abs_generate_dir) {
              lastGenerateDir.value = data.state.abs_generate_dir
              loadFileList(data.state.abs_generate_dir)
            }
          }
        }
        read()
      }).catch(err => {
        if (err.name === 'AbortError') return
        showStreamError(`${t('error.connectionLost')}${err.message || err}`)
      })
    }
    read()
  }).catch(err => {
    if (err.name === 'AbortError') return
    showStreamError(`${t('error.requestFailed')}${err.message || err}`)
  })
}

// 只展示有内容的节点
const filteredMessages = computed(() =>
  messages.value.filter(msg =>
    (msg.node === 'init' && msg.state.user_input) ||
    (msg.node === 'generate' && (msg.state.lammps_code || (msg.state.checkout_filename_list && msg.state.checkout_filename_list.length))) ||
    (msg.node === 'run' && msg.state.run_result) ||
    (msg.node === 'eval' && msg.state.eval_result) ||
    msg.node === 'error'
  )
)

watch([filteredMessages, loading], scrollToBottom)

// 节点颜色
function getColor(node) {
  if (node === 'init') return '#64748b'
  if (node === 'generate') return '#10b981'
  if (node === 'run') return '#3b82f6'
  if (node === 'eval') return '#f59e0b'
  if (node === 'error') return '#ef4444'
  return '#64748b'
}

// 节点图标
function getIcon(node) {
  if (node === 'init') return User
  if (node === 'generate') return Edit
  if (node === 'run') return Cpu
  if (node === 'eval') return Star
  if (node === 'error') return WarningFilled
  return ''
}

// 节点中文/英文名
function nodeLabel(node) {
  const path = `node.${node}`
  return te(path) ? t(path) : node
}

// 统计字段名/布尔值展示
function statLabel(key) {
  const path = `stats.${key}`
  return te(path) ? t(path) : key
}
function formatStatValue(item) {
  if (item === true) return t('common.yes')
  if (item === false) return t('common.no')
  return item
}

// 文件区相关
const fileList = ref([])
const fileLoading = ref(false)
const imgDialogVisible = ref(false)
const imgPreviewUrl = ref('')


const runResultShowModel = ref(false)
const evalResultShowModel = ref(false)

// 监听 generate_dir 自动加载文件列表
const lastGenerateDir = ref('')
watch(
  () => {
    // 找到最新的 abs_generate_dir
    const last = messages.value.slice().reverse().find(msg => msg.state && msg.state.abs_generate_dir && msg.node === 'run')
    return last ? last.state.abs_generate_dir : ''
  },
  (dir) => {
    if (dir && dir !== lastGenerateDir.value) {
      lastGenerateDir.value = dir
      loadFileList(dir)
    }
  },
  { immediate: true }
)

function loadFileList(dir) {
  fileLoading.value = true
  fileList.value = []
  fetch(`${API_BASE}/list_files_in_dir`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dir_path: dir })
  })
    .then(res => res.json())
    .then(data => {
      fileList.value = data.files || []
      fileLoading.value = false
    })
    .catch(() => {
      fileLoading.value = false
    })
}

function getFileName(path) {
  return path.split(/[\\/]/).pop()
}
function isImage(file) {
  return /\.(png|gif)$/i.test(file)
}
function previewImage(file) {
  imgPreviewUrl.value = `${API_BASE}/file?path=${encodeURIComponent(file)}`
  imgDialogVisible.value = true
}
function downloadFile(file) {
  window.open(`${API_BASE}/file?path=${encodeURIComponent(file)}`)
}

// 复制 generate_dir 路径
function copyDir(dir) {
  navigator.clipboard.writeText(dir)
    .then(() => {
      ElMessage.success(t('common.copySuccess'))
    })
    .catch(() => {
      ElMessage.error(t('common.copyFailPrefix') + dir)
    })
}

// 复制代码
function copyCode(code) {
  navigator.clipboard.writeText(code)
    .then(() => {
      ElMessage.success(t('common.codeCopySuccess'))
    })
    .catch(() => {
      ElMessage.error(t('common.codeCopyFail'))
    })
}

// 运行结果显示模式
function runShowModel() {
  runResultShowModel.value = !runResultShowModel.value;
}

// 评价结果显示模式
function evalShowModel() {
  evalResultShowModel.value = !evalResultShowModel.value;
}

function stringToJson(value) {
  return JSON.parse(value)
}

// 历史记录相关
const historyDrawerVisible = ref(false)
const historyList = ref([])
const historyLoading = ref(false)

function openHistory() {
  historyDrawerVisible.value = true
}

function fetchHistoryList() {
  historyLoading.value = true
  fetch(`${API_BASE}/history`)
    .then(res => res.json())
    .then(data => {
      historyList.value = data.items || []
    })
    .catch(() => {
      ElMessage.error(t('history.loadFailed'))
    })
    .finally(() => {
      historyLoading.value = false
    })
}

function loadHistoryItem(id) {
  fetch(`${API_BASE}/history/${encodeURIComponent(id)}`)
    .then(res => {
      if (!res.ok) throw new Error()
      return res.json()
    })
    .then(data => {
      if (activeAbortController) activeAbortController.abort()
      loading.value = false
      messages.value = data.messages || []
      viewingHistoryId.value = id
      historyDrawerVisible.value = false
    })
    .catch(() => {
      ElMessage.error(t('history.loadFailed'))
    })
}

function deleteHistoryItem(id) {
  ElMessageBox.confirm(t('history.confirmDeleteMsg'), t('history.confirmDeleteTitle'), {
    confirmButtonText: t('history.confirmOk'),
    cancelButtonText: t('history.confirmCancel'),
    type: 'warning',
  }).then(() => {
    fetch(`${API_BASE}/history/${encodeURIComponent(id)}`, { method: 'DELETE' })
      .then(res => {
        if (!res.ok) throw new Error()
        ElMessage.success(t('history.deleteSuccess'))
        historyList.value = historyList.value.filter(it => it.id !== id)
        if (viewingHistoryId.value === id) newChat()
      })
      .catch(() => {
        ElMessage.error(t('history.deleteFail'))
      })
  }).catch(() => {})
}

function formatTime(unixSeconds) {
  if (!unixSeconds) return ''
  return new Date(unixSeconds * 1000).toLocaleString()
}
</script>

<style>
body {
  margin: 0;
  background: #f4f6fb;
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    'PingFang SC', 'Microsoft YaHei', sans-serif;
}
</style>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding-bottom: 140px;
}

/* Header */
.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  background: linear-gradient(135deg, #4f46e5 0%, #4338ca 45%, #3b82f6 100%);
  box-shadow: 0 4px 20px rgba(67, 56, 202, 0.25);
}
.header-inner {
  max-width: 960px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}
.brand-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
  font-size: 22px;
  flex-shrink: 0;
}
.brand-text h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.5px;
}
.brand-text p {
  margin: 2px 0 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.78);
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.15s;
}
.icon-btn:hover {
  background: rgba(255, 255, 255, 0.26);
}
.lang-toggle {
  display: flex;
  background: rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  padding: 3px;
  margin-left: 4px;
}
.lang-toggle button {
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.75);
  font-size: 12px;
  font-weight: 600;
  padding: 6px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.lang-toggle button.active {
  background: #fff;
  color: #4338ca;
}

/* Main chat area */
.app-main {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 28px 20px 0;
}
.chat-panel {
  width: 100%;
  max-width: 960px;
}

.history-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 12px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 13px;
  margin-bottom: 20px;
}
.history-banner .el-button {
  margin-left: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;
}
.empty-icon {
  font-size: 40px;
  margin-bottom: 14px;
  color: #c7d2fe;
}
.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #64748b;
  margin: 0 0 6px;
}
.empty-desc {
  font-size: 13px;
  max-width: 400px;
  line-height: 1.6;
  margin: 0;
}
.example-block {
  margin-top: 28px;
  width: 100%;
  max-width: 560px;
}
.example-label {
  font-size: 12px;
  color: #a3aebc;
  display: block;
  margin-bottom: 10px;
}
.example-chips {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.example-chip {
  padding: 10px 14px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e5e9f2;
  font-size: 13px;
  color: #475569;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.example-chip:hover {
  border-color: #c7d2fe;
  box-shadow: 0 2px 10px rgba(79, 70, 229, 0.08);
}

.message-list {
  display: flex;
  flex-direction: column;
}

.message-item {
  display: flex;
  gap: 16px;
  padding-bottom: 28px;
}

.message-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}
.marker-dot {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent, #64748b);
  color: #fff;
  font-size: 16px;
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent, #64748b) 16%, transparent);
  flex-shrink: 0;
}
.rail-line {
  flex: 1;
  width: 2px;
  margin-top: 4px;
  background: linear-gradient(#e2e8f0, transparent);
}
.message-item:last-child .rail-line {
  display: none;
}

.message-body {
  flex: 1;
  min-width: 0;
  padding-top: 4px;
}
.message-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}
.message-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--accent, #334155);
}
.message-time {
  font-size: 12px;
  color: #a3aebc;
}

.panel {
  background: #fff;
  border: 1px solid #edf0f6;
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
  margin-bottom: 10px;
}
.panel:last-child {
  margin-bottom: 0;
}
.panel-subtitle {
  display: flex;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 12px;
}
.panel-subtitle-plain {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.panel-subtitle-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.dir-tag {
  cursor: pointer;
  max-width: 320px;
}
.dir-tag :deep(.el-tag__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Code block */
.code-panel {
  padding: 0;
  overflow: hidden;
  background: #1e2530;
  border: 1px solid #1e2530;
}
.code-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  background: #262f3d;
  border-bottom: 1px solid #323d4d;
}
.code-lang {
  font-size: 12px;
  color: #94a3b8;
  font-family: 'JetBrains Mono', Consolas, monospace;
}
.copy-btn {
  color: #cbd5e1;
}
.code-block {
  margin: 0;
  padding: 16px;
  color: #e2e8f0;
  font-size: 13.5px;
  font-family: 'JetBrains Mono', Consolas, 'Courier New', monospace;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
}

/* Error */
.error-panel {
  background: #fef2f2;
  border-color: #fecaca;
}
.error-block {
  background: transparent;
  color: #b91c1c;
  padding: 0;
}

/* Chips / files */
.chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.file-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #eef1f6;
  transition: box-shadow 0.15s, border-color 0.15s;
}
.file-chip:hover {
  border-color: #dbe4f3;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}
.file-chip-icon {
  color: #3b82f6;
}
.file-chip-name {
  font-size: 13px;
  color: #334155;
  word-break: break-all;
}

/* Image gallery */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 14px;
}
.image-card {
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #eef1f6;
  background: #f8fafc;
}
.image-card img {
  width: 100%;
  height: 160px;
  object-fit: cover;
  display: block;
  cursor: zoom-in;
  transition: transform 0.2s;
}
.image-card img:hover {
  transform: scale(1.03);
}
.image-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  font-size: 12px;
  color: #64748b;
}
.image-card-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 8px;
}

/* Stat grid */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
@media (max-width: 900px) {
  .stat-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 640px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
}
.stat-item {
  padding: 12px 14px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #eef1f6;
}
.stat-item-penalty {
  background: #fff7ed;
  border-color: #fed7aa;
}
.stat-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}
.stat-good {
  color: #16a34a;
}
.stat-bad {
  color: #dc2626;
}

.summary-rows {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.summary-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
}
.summary-label {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.summary-label.perf { color: #ea580c; }
.summary-label.warn { color: #dc2626; }
.summary-label.ok { color: #16a34a; }
.summary-value {
  font-size: 13px;
  color: #475569;
  word-break: break-all;
}

.final-score {
  margin-top: 14px;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 12px;
  padding: 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, #fff7ed, #fef3c7);
}
.final-score span {
  font-size: 14px;
  color: #92400e;
}
.final-score strong {
  font-size: 28px;
  color: #d97706;
}

/* Thinking indicator */
.thinking-item .message-body {
  display: flex;
  align-items: center;
}
.marker-dot-loading {
  background: #94a3b8;
}
.spin-icon {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.thinking-text {
  font-size: 13px;
  color: #94a3b8;
  display: flex;
  align-items: center;
}
.thinking-dots {
  display: inline-flex;
  gap: 3px;
}
.thinking-dots i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #94a3b8;
  animation: bounce 1.2s infinite ease-in-out;
}
.thinking-dots i:nth-child(2) { animation-delay: 0.15s; }
.thinking-dots i:nth-child(3) { animation-delay: 0.3s; }
@keyframes bounce {
  0%, 80%, 100% { opacity: 0.3; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

/* Image preview dialog */
.preview-dialog :deep(.el-dialog) {
  border-radius: 16px;
}
.preview-dialog-img {
  max-width: 78vw;
  max-height: 78vh;
  border-radius: 8px;
  display: block;
}

/* History drawer */
.history-loading, .history-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: #94a3b8;
  font-size: 13px;
}
.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.history-item {
  border: 1px solid #edf0f6;
  border-radius: 12px;
  padding: 12px 14px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.history-item:hover {
  border-color: #c7d2fe;
  box-shadow: 0 2px 10px rgba(79, 70, 229, 0.08);
}
.history-item.active {
  border-color: #4f46e5;
  background: #eef2ff;
}
.history-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.history-item-time {
  font-size: 11px;
  color: #a3aebc;
}
.history-item-text {
  font-size: 13px;
  color: #334155;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.history-item-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.history-item-score {
  font-size: 12px;
  color: #d97706;
  font-weight: 600;
}

/* Bottom input bar */
.input-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  padding: 16px 20px calc(16px + env(safe-area-inset-bottom));
  background: linear-gradient(180deg, rgba(244, 246, 251, 0) 0%, #f4f6fb 40%);
  z-index: 20;
}
.input-inner-wrap {
  width: 100%;
  max-width: 960px;
}
.input-inner {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: #fff;
  border-radius: 20px;
  padding: 10px 10px 10px 18px;
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.1);
  border: 1px solid #edf0f6;
}
.task-input :deep(.el-textarea__inner) {
  box-shadow: none;
  border: none;
  padding: 8px 0;
  font-size: 15px;
  resize: none;
}
.send-btn {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
}
.input-hint {
  text-align: center;
  font-size: 11px;
  color: #a3aebc;
  margin-top: 8px;
}
</style>
