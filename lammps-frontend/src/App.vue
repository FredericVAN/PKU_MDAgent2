<template>
    <el-container class="content" style="min-height: 100vh; background: #f5f7fa;">
      <el-header style="background: linear-gradient(90deg, #409EFF 0%, #66b1ff 100%); color: white; font-size: 28px; letter-spacing: 2px; text-align: center; box-shadow: 0 2px 8px #e0e0e0;">
        AI4Materials 新材料自主仿真计算系统
      </el-header>
      <el-main style="padding: 40px 0 0 0;">
        <el-row style="width: 100%;">
          <!-- 主对话区 3/4 -->
          <el-col>
            <el-card style="min-height: 600px; width: 100%; box-shadow: 0 4px 24px #d0d7de;">
              <el-divider />
              <el-timeline style="margin: 0 10%;">
                <el-timeline-item
                  v-for="(msg, idx) in filteredMessages"
                  :key="idx"
                  :color="getColor(msg.node)"
                  :icon="getIcon(msg.node)"
                  :timestamp="msg.timestamp"
                  placement="top"
                >
                  <!-- 节点名标题 -->
                  <div style="font-size: 18px; font-weight: bold; margin-bottom: 8px; display: flex; align-items: center;">
                    <el-icon v-if="getIcon(msg.node)" style="margin-right: 6px;">
                      <component :is="getIcon(msg.node)" />
                    </el-icon>
                    <span :style="{ color: getColor(msg.node) }">{{ msg.node.toUpperCase() }}</span>
                  </div>
                  <!-- INIT 阶段：展示用户输入 -->
                  <template v-if="msg.node === 'init' && msg.state.user_input">
                    <el-card shadow="hover" style="background: #f0f9eb;">
                      <div style="font-weight: bold; color: #67c23a; margin-bottom: 8px;">
                        用户输入
                      </div>
                      <el-tag type="info" size="large">{{ msg.state.user_input }}</el-tag>
                    </el-card>
                  </template>
                  <!-- GENERATE 阶段：展示代码和文件名列表 -->
                  <template v-else-if="msg.node === 'generate' && (msg.state.lammps_code || msg.state.checkout_filename_list)">
                    <el-card shadow="hover" style="background: #f0f9eb; margin-bottom: 10px;">
                      <div style="font-weight: bold; color: #67c23a; margin-bottom: 8px;">
                        生成的 LAMMPS 代码
                      </div>
                      <pre v-if="msg.state.lammps_code" style="background: #f6f8fa; padding: 16px; border-radius: 6px; font-size: 16px; color: #333; overflow-x: auto;">{{ msg.state.lammps_code }}</pre>
                    </el-card>
                    <el-card v-if="msg.node === 'generate' && msg.state.checkout_filename_list && msg.state.checkout_filename_list.length" shadow="hover" style="background: #e0f7fa; margin-top: 10px;">
                        <div style="font-weight: bold; color: #1e88e5; margin-bottom: 8px; margin-top: 10px">
                          文件下载
                        </div>
                        <el-list v-if="fileList.length" style="display: flex; flex-wrap: wrap; flex-direction: row; gap: 10px; padding: 10px;">
                          <el-list-item v-for="(file, idx) in fileList" :key="idx" style="display: flex; align-items: center;" >
                            <div v-if="!isImage(file) && getFileName(file).includes('in.')">
                              <el-icon  style="color: #409EFF; margin-right: 6px;"><Document /></el-icon>
                              <span style="flex: 1; word-break: break-all; margin-left: 5px; margin-right: 10px;">{{ getFileName(file) }}</span>
                              <el-button
                                type="success"
                                size="small"
                                style="margin-right: 20px;"
                                @click="downloadFile(file)"
                              >下载</el-button>
                            </div>
                          </el-list-item>
                        </el-list>
                    </el-card>
                  </template>
                  <!-- RUN 阶段：展示运行结果和按钮 -->
                  <template v-else-if="msg.node === 'run' && msg.state.run_result">
                    <el-card shadow="hover" style="background: #ecf5ff;">
                      <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div style="font-weight: bold; color: #409EFF; margin-bottom: 8px;">
                          运行结果
                        </div>
                        <el-button
                          v-if="msg.state.generate_dir"
                          type="primary"
                          size="small"
                          @click="runShowModel()"
                        >{{ !runResultShowModel ? "原始结果" : "处理结果" }}</el-button>
                      </div>
                      <pre v-if="runResultShowModel" style="background: #f6f8fa; padding: 16px; border-radius: 6px; font-size: 16px; color: #333; overflow-x: auto;">{{ msg.state.run_result.extra_info }}</pre>
                      <div v-else style="background: #f6f8fa; margin-top: 16px; border-radius: 6px; font-size: 16px; color: #333;">
                        <div class="grid-container">
                          <div 
                            v-for="(item, key) in msg.state.run_result.extra_info['log.lammps']" 
                            :key="key" 
                            class="grid-item"
                          >
                            <div v-if="key!='performance_info' && key!='warnings' && key!='summary'" style="display: flex; flex-direction: row; place-items: center; height: 30px;">
                              <div style="color: gray; font-size: larger; margin-right: 10px;">{{ translateKey(key) }}:</div>
                              <div style="font-size: larger; margin-right: 10px;">{{ translateKey(item) }}</div>
                            </div>
                          </div>
                        </div>
                        <div class="grid-item" style="display: flex; flex-direction: row; place-items: center; height: 30px;">
                          <div style="color: chocolate; font-size: x-large; margin-right: 10px;">{{ translateKey('performance_info') }}:</div>
                          <div style="font-size: larger; margin-right: 10px;">{{ msg.state.run_result.extra_info['log.lammps']['performance_info'] }}</div>
                        </div>
                        <div class="grid-item" style="display: flex; flex-direction: row; place-items: center; height: 30px;">
                          <div style="color: red; font-size: x-large; margin-right: 10px;">{{ translateKey('warnings') }}:</div>
                          <div style="font-size: larger; margin-right: 10px;">{{ msg.state.run_result.extra_info['log.lammps']['warnings'] }}</div>
                        </div>
                        <div class="grid-item" style="display: flex; flex-direction: row; place-items: center; height: 30px;">
                          <div style="color: green; font-size: x-large; margin-right: 10px;">{{ translateKey('summary') }}</div>
                          <div style="font-size: larger; margin-right: 10px;">{{ msg.state.run_result.extra_info['log.lammps']['summary'] }}</div>
                        </div>
                      </div>
                      
                    </el-card>
                    <el-card v-if="msg.node === 'run' && msg.state.checkout_filename_list && msg.state.checkout_filename_list.length" shadow="hover" style="background: #e0f7fa; margin-top: 10px;">
                        <div style="font-weight: bold; color: #1e88e5; margin-bottom: 8px;">
                          图片预览
                        </div>
                        <el-list v-if="fileList.length" style="display: flex; flex-wrap: wrap; flex-direction: row; gap: 10px; padding: 10px;">
                          <el-list-item v-for="(file, idx) in fileList" :key="idx" style="display: flex; align-items: center;">
                            <div v-if="isImage(file)">
                              <img :src="`http://localhost:8000/file?path=${encodeURIComponent(file)}`" style="width: 600px; height: auto;" :alt="getFileName(file)">
                              <div style="display: flex; justify-content: center; margin-top: 10px;">
                                <el-button
                                  type="success"
                                  size="small"
                                  style="margin-right: 20px;"
                                  @click="downloadFile(file)"
                                >下载</el-button>
                              </div>

                            </div>
                          </el-list-item>
                        </el-list>
                        <div style="font-weight: bold; color: #1e88e5; margin-bottom: 8px; margin-top: 50px">
                          文件下载
                        </div>
                        <el-list v-if="fileList.length" style="display: flex; flex-wrap: wrap; flex-direction: row; gap: 10px; padding: 10px;">
                          <el-list-item v-for="(file, idx) in fileList" :key="idx" style="display: flex; align-items: center;" >
                            <div v-if="!isImage(file) && !getFileName(file).includes('in.')">
                              <el-icon  style="color: #409EFF; margin-right: 6px;"><Document /></el-icon>
                              <span style="flex: 1; word-break: break-all; margin-left: 5px; margin-right: 10px;">{{ getFileName(file) }}</span>
                              <el-button
                                type="success"
                                size="small"
                                style="margin-right: 20px;"
                                @click="downloadFile(file)"
                              >下载</el-button>
                            </div>
                          </el-list-item>
                        </el-list>
                    </el-card>
                  </template>
                  <!-- EVAL 阶段：展示评估结果 -->
                  <template v-else-if="msg.node === 'eval' && msg.state.eval_result">
                    <el-card shadow="hover" style="background: #fdf6ec;">
                      <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div style="font-weight: bold; color: #409EFF; margin-bottom: 8px;">
                          评估结果
                        </div>
                        <el-button
                          v-if="msg.state.generate_dir"
                          type="primary"
                          size="small"
                          @click="evalShowModel()"
                        >{{ !evalResultShowModel ? "原始结果" : "处理结果" }}</el-button>
                      </div>
                      <pre v-if="evalResultShowModel" style="background: #f6f8fa; padding: 16px; border-radius: 6px; font-size: 16px; color: #333; overflow-x: auto;">{{ msg.state.eval_result }}</pre>
                      <div v-else style="background: #f6f8fa; margin-top: 16px; border-radius: 6px; font-size: 16px; color: #333;">
                        <div class="grid-container">
                          <div 
                            v-for="item in stringToJson(msg.state.eval_result).module_detail" :key="item.id"
                            class="grid-item"
                          >
                            <div v-if="key!='performance_info' && key!='warnings' && key!='summary'" style="display: flex; flex-direction: row; place-items: center; height: 30px;">
                              <div style="color: gray; font-size: larger; margin-right: 10px;">{{ item.name }}:</div>
                              <div style="font-size: larger; margin-right: 10px;">{{ item.score }}</div>
                            </div>
                          </div>
                          <div 
                            v-for="item in stringToJson(msg.state.eval_result).penalty_detail" :key="item.id"
                            class="grid-item"
                          >
                            <div v-if="key!='performance_info' && key!='warnings' && key!='summary'" style="display: flex; flex-direction: row; place-items: center; height: 30px;">
                              <div style="color: gray; font-size: larger; margin-right: 10px;">{{ item.name }}:</div>
                              <div style="font-size: larger; margin-right: 10px;">{{ item.score }}</div>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div v-if="msg.state.final_score" style="margin-top: 10px;">
                        <div class="grid-item" style="display: flex; flex-direction: row; place-items: center; height: 30px;">
                          <div style="color: gray; font-size: x-large; margin-right: 10px;">最终分数: </div>
                          <div style="color: red; font-size: xxx-large">{{ msg.state.final_score }}</div>
                        </div>
                      </div>
                    </el-card>
                  </template>
                </el-timeline-item>
                
              </el-timeline>
            </el-card>
          </el-col>
        </el-row>
      </el-main>
      <!-- 图片预览弹窗 -->
      <el-dialog v-model="imgDialogVisible" width="auto" :show-close="true" center>
        <img :src="imgPreviewUrl" style="max-width: 600px; max-height: 600px;" />
      </el-dialog>
    </el-container>
    <div class="fixed-bottom">
        <div class="overlay" style="display: flex; flex-direction: row; align-items: center;">
          <el-input
            v-model="input"
            style="width: 75%; font-size: 18px;"
            :disabled="loading"
            :rows="3"
            type="textarea"
            placeholder="请输入LAMMPS任务描述"
            @keyup.enter="send"
            clearable
          />
          <el-button
            type="primary"
            style="margin-left: 20px; width: 200px; height: 90px; font-size: 18px;"
            @click="send"
            :loading="loading"
          >提交</el-button>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Cpu, Star, User, Picture, Document } from '@element-plus/icons-vue'

// 对话区相关
const input = ref('')
const messages = ref([])
const loading = ref(false)

function send() {
  if (!input.value.trim()) return
  messages.value = []
  loading.value = true
  fetch('http://localhost:8000/run_lammps_agents_stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_input: input.value })
  }).then(response => {
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
      })
    }
    read()
  }).catch(() => {
    loading.value = false
  })
}

// 只展示有内容的节点
const filteredMessages = computed(() =>
  messages.value.filter(msg =>
    (msg.node === 'init' && msg.state.user_input) ||
    (msg.node === 'generate' && (msg.state.lammps_code || (msg.state.checkout_filename_list && msg.state.checkout_filename_list.length))) ||
    (msg.node === 'run' && msg.state.run_result) ||
    (msg.node === 'eval' && msg.state.eval_result)
  )
)

// 节点颜色
function getColor(node) {
  if (node === 'init') return '#909399'
  if (node === 'generate') return '#67c23a'
  if (node === 'run') return '#409EFF'
  if (node === 'eval') return '#e6a23c'
  return '#909399'
}

// 节点图标
function getIcon(node) {
  if (node === 'init') return User
  if (node === 'generate') return Edit
  if (node === 'run') return Cpu
  if (node === 'eval') return Star
  return ''
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
  fetch('http://localhost:8000/list_files_in_dir', {
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
  imgPreviewUrl.value = `http://localhost:8000/file?path=${encodeURIComponent(file)}`
  imgDialogVisible.value = true
}
function downloadFile(file) {
  window.open(`http://localhost:8000/file?path=${encodeURIComponent(file)}`)
}

// 复制 generate_dir 路径
function copyDir(dir) {
  navigator.clipboard.writeText(dir)
    .then(() => {
      ElMessage.success('已复制临时文件夹路径到剪贴板！')
    })
    .catch(() => {
      ElMessage.error('复制失败，请手动复制：' + dir)
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

function getType(value) {
  return Object.prototype.toString.call(value).slice(8, -1).toLowerCase();
}

function stringToJson(value) {
  return JSON.parse(value)
}

function translateKey(key) {
  const translations = {
    'finished': '代码是否运行正常结束',
    'energy_stable': '能量稳定',
    'temperature_stable': '温度稳定',
    'pressure_reasonable': '压力合理',
    'thermal_equilibrium': '热平衡',
    'temperature_converged': '温度收敛',
    'dangerous_builds': '危险邻居构建次数',
    'neighs_per_atom': '平均邻居数',
    'timesteps': '时间步数量',
    'has_nan': '是否包含 NaN',
    'has_warning_lines': '是否有警告',
    'performance_info':'性能信息',
    'warnings':'警告列表',
    'summary':'总结信息',
    'True': '是',
    "False": '否',
  };
  return translations[key] || key; // 如果没有对应的翻译，返回原键名
}
</script>

<style>
body {
  background: #f5f7fa;
}
.el-header {
  line-height: 60px;
}
.grid-container {
  display: grid;
  grid-template-columns: repeat(4, 1fr); /* 4列 */
  gap: 16px;
}

@media (max-width: 900px) {
  .grid-container {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 600px) {
  .grid-container {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 400px) {
  .grid-container {
    grid-template-columns: 1fr;
  }
}

.grid-item {
  padding: 20px;
  border-radius: 4px;
}

.fixed-bottom {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #333;
  color: white;
  padding: 10px;
  z-index: 100;
}

.content {
  padding-bottom: 100px; /* 与底部固定元素高度相同 */
  height: 100%;
}

.overlay {
  position: absolute;
  bottom: 100%;
  left: 0;
  width: 100%;
  padding: 15px;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 100px;
  background: #fff;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>