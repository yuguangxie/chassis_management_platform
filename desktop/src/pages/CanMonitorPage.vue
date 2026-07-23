<template>
  <div class="can-monitor-page">
    <section class="page-header">
      <div class="title-block">
        <div class="title-icon"><MonitorDot /></div>
        <div>
          <h1>CAN 报文监控</h1>
          <p>实时帧、历史帧、DBC 解码与统计分析</p>
        </div>
        <PageDataState :loading="store.loading" :error="store.error" :stale="store.offline || store.quality !== 'good' || Boolean(store.statistics.mock)" :empty="!store.latestFrames.length" />
      </div>
      <div class="header-actions">
        <IndustrialButton v-if="auth.can('operator')" size="compact" variant="danger" :disabled="store.offline" @click="clearDisplay"><template #icon><Trash2 :size="16" /></template>清空显示</IndustrialButton>
        <IndustrialButton v-if="auth.can('operator')" size="compact" :disabled="store.offline" @click="postAction('/logs/export/csv', '导出 CSV')"><template #icon><Download :size="16" /></template>导出 CSV</IndustrialButton>
        <IndustrialButton v-if="auth.can('operator')" size="compact" :disabled="store.offline" @click="postAction('/logs/export/raw-can', '导出原始日志')"><template #icon><FileDown :size="16" /></template>导出原始日志</IndustrialButton>
        <IndustrialButton v-if="auth.can('operator')" size="compact" :disabled="store.offline" @click="loadFirstHistory"><template #icon><FolderOpen :size="16" /></template>加载历史文件</IndustrialButton>
      </div>
    </section>

    <section class="filter-panel">
      <div class="filter-item compact">
        <span>通道</span>
        <div class="segmented">
          <button v-for="item in channelOptions" :key="item.value" :class="{ active: store.filters.channel === item.value }" @click="store.filters.channel = item.value">{{ item.label }}</button>
        </div>
      </div>
      <label class="filter-item">
        <span>CAN ID</span>
        <input v-model="store.filters.canId" placeholder="例如: 0x121 或 121" />
      </label>
      <label class="filter-item">
        <span>报文名</span>
        <input v-model="store.filters.messageName" placeholder="例如: SCU" />
      </label>
      <div class="filter-item compact">
        <span>方向</span>
        <div class="segmented">
          <button v-for="item in directionOptions" :key="item.value" :title="item.hint" :class="{ active: store.filters.direction === item.value }" @click="store.filters.direction = item.value">{{ item.label }}</button>
        </div>
      </div>
      <label class="filter-item narrow">
        <span>周期状态</span>
        <select v-model="store.filters.status">
          <option value="all">全部</option>
          <option value="normal">正常</option>
          <option value="timeout">超时</option>
          <option value="error">错误</option>
        </select>
      </label>
      <label class="filter-item narrow">
        <span>时间范围</span>
        <select v-model="store.filters.timeRange">
          <option value="realtime">实时</option>
          <option value="1m">最近1分钟</option>
          <option value="5m">最近5分钟</option>
          <option value="history">历史</option>
        </select>
      </label>
      <div class="filter-item compact">
        <span>显示进制</span>
        <div class="segmented">
          <button title="十六进制（Hex）" :class="{ active: store.filters.radix === 'Hex' }" @click="store.filters.radix = 'Hex'">十六进制</button>
          <button title="十进制（Dec）" :class="{ active: store.filters.radix === 'Dec' }" @click="store.filters.radix = 'Dec'">十进制</button>
        </div>
      </div>
      <label class="filter-item pause">
        <span>暂停刷新</span>
        <button class="toggle" :class="{ on: store.paused }" @click="store.setPaused(!store.paused)" aria-label="暂停刷新"><i /></button>
      </label>
    </section>

    <section class="main-grid">
      <article class="panel frame-panel">
        <div class="panel-head">
          <h2>实时帧列表</h2>
          <span>按 CAN ID 聚合：{{ store.latestFrames.length }} 条</span>
        </div>
        <div class="frame-table-wrap">
          <table class="frame-table">
            <thead>
              <tr>
                <th>时间戳</th>
                <th>通道</th>
                <th>方向</th>
                <th class="sortable" @click="store.cycleSortByCanId()">CAN ID <ArrowUpDown :size="13" />{{ sortLabel }}</th>
                <th>帧类型</th>
                <th>DLC</th>
                <th>Data Hex</th>
                <th>报文名</th>
                <th>周期ms</th>
                <th>状态</th>
                <th>来源会话</th>
                <th>次数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="frame in store.latestFrames" :key="frame.can_id_hex" :class="{ selected: selectedFrame?.can_id_hex === frame.can_id_hex }" @click="store.selectFrame(frame)">
                <td>{{ frame.timestamp }}</td>
                <td><span class="channel-pill">{{ frame.channel }}</span></td>
                <td>{{ directionLabel(frame.direction) }}</td>
                <td class="can-id">{{ canIdLabel(frame) }}</td>
                <td>{{ frame.frame_type }}</td>
                <td>{{ frame.dlc }}</td>
                <td class="hex">{{ dataLabel(frame.data_hex) }}</td>
                <td>{{ frame.message_name }}</td>
                <td>{{ frame.period_ms }}</td>
                <td><span class="status-pill" :class="statusClass(frame.status)">{{ localizeStatus(frame.status) }}</span></td>
                <td>{{ frame.source_session }}</td>
                <td>{{ frame.frame_count }}</td>
              </tr>
              <tr v-if="!store.latestFrames.length">
                <td class="empty" colspan="12">当前显示缓存为空，请等待实时帧；离线时页面会明确标记并启用显式 Mock 数据。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel detail-panel">
        <div class="panel-head detail-head">
          <h2>帧详情 - {{ selectedFrame?.can_id_hex || '-' }}（{{ selectedFrame?.message_name || '仅原始数据' }}）</h2>
          <div class="icon-actions"><button disabled title="尚未实现：帧详情独立全屏"><Maximize2 :size="16" /></button><button disabled title="尚未实现：关闭帧详情面板"><X :size="16" /></button></div>
        </div>
        <div v-if="selectedFrame" class="detail-content">
          <div class="frame-info">
            <div><span>通道</span><b>{{ selectedFrame.channel }}</b></div>
            <div><span>方向</span><b>{{ directionLabel(selectedFrame.direction) }}</b></div>
            <div><span>帧类型</span><b>{{ selectedFrame.frame_type }}</b></div>
            <div><span>时间戳</span><b>{{ selectedFrame.timestamp }}</b></div>
            <div><span>DLC</span><b>{{ selectedFrame.dlc }}</b></div>
            <div><span>周期</span><b>{{ selectedFrame.period_ms }} ms</b></div>
          </div>
          <div class="data-row">
            <span>Data Hex</span>
            <code>{{ selectedFrame.data_hex }}</code>
            <button class="copy-action" type="button" aria-label="复制帧数据" @click="copyFrameData"><Copy :size="14" /></button>
          </div>
          <div class="tabs">
            <button class="active">信号解码</button>
            <button disabled title="尚未实现：当前帧原始信息已在上方展示">原始数据（尚未实现）</button>
            <button disabled title="尚未实现：DBC 信息请在系统设置查看">DBC信息（尚未实现）</button>
            <button disabled title="尚未实现：发送历史需要独立审计视图">发送历史（尚未实现）</button>
          </div>
          <div class="signal-table-wrap">
            <table class="signal-table">
              <thead>
                <tr>
                  <th>信号名</th>
                  <th>起始位</th>
                  <th>长度</th>
                  <th>类型</th>
                  <th>raw</th>
                  <th>物理值</th>
                  <th>单位</th>
                  <th>枚举/故障</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="signal in selectedSignals" :key="signal.name">
                  <td>{{ signal.name }}</td>
                  <td>{{ signal.start_bit }}</td>
                  <td>{{ signal.length }}</td>
                  <td>{{ signal.type }}</td>
                  <td class="hex">{{ signal.raw }}</td>
                  <td>{{ signal.physical_value }}</td>
                  <td>{{ signal.unit }}</td>
                  <td>{{ signal.enum }}</td>
                  <td>{{ signal.remark }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </article>
    </section>

    <section class="stats-grid">
      <article class="panel chart-card distribution">
        <div class="panel-head"><h2>CAN ID 分布（前 6 项）</h2></div>
        <div class="chart-body"><BarChart :option="distributionOption" height="100%" /></div>
      </article>
      <article class="panel chart-card">
        <div class="panel-head"><h2>帧率趋势（fps）</h2></div>
        <div class="chart-body"><RealtimeLineChart :option="fpsOption" height="100%" /></div>
      </article>
      <article class="panel chart-card">
        <div class="panel-head"><h2>周期抖动（ms）</h2></div>
        <div class="chart-body"><RealtimeLineChart :option="jitterOption" height="100%" /></div>
      </article>
      <article class="panel error-card">
        <div class="panel-head"><h2>错误统计</h2></div>
        <div class="error-kpis">
          <div class="kpi warn"><span>超时计数</span><strong>{{ store.statistics.error_summary.timeout_count }}</strong></div>
          <div class="kpi bad"><span>错误帧计数</span><strong>{{ store.statistics.error_summary.error_frame_count }}</strong></div>
          <div class="kpi bad"><span>13字节协议错误计数</span><strong>{{ store.statistics.error_summary.protocol_error_count }}</strong></div>
        </div>
      </article>
      <article class="panel history-card">
        <div class="panel-head"><h2>历史文件（raw_can）</h2><button class="more" @click="showAllHistory = !showAllHistory">{{ showAllHistory ? '收起' : '更多' }} &gt;</button></div>
        <table class="history-table">
          <thead><tr><th>文件名</th><th>会话ID</th><th>开始时间</th><th>大小</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="file in visibleHistoryFiles" :key="file.file_id">
              <td>{{ file.file_name }}</td>
              <td>{{ file.session_id }}</td>
              <td>{{ file.started_at }}</td>
              <td>{{ file.size }}</td>
              <td class="file-actions">
                <Download :size="14" @click="downloadHistory(file.file_id, file.file_name)" />
                <FolderOpen :size="14" @click="postAction('/logs/load-history', '打开历史文件', { file_id: file.file_id })" />
                <Trash2 v-if="auth.isAdmin" :size="14" @click="deleteHistory(file.file_id)" />
              </td>
            </tr>
          </tbody>
        </table>
      </article>
    </section>

    <footer class="monitor-footer">
      <div>
        <span :class="store.offline ? 'stale-dot' : 'green-dot'" />
        {{ store.offline ? '离线，记录状态未知' : '数据记录中' }}
        <span>已运行：{{ store.statistics.footer_status.uptime }}</span>
        <span>缓冲使用：{{ store.statistics.footer_status.buffer_usage }}%</span>
      </div>
      <div>
        <span>接收帧率：{{ store.offline ? '—（数据陈旧）' : `${store.statistics.footer_status.rx_fps.toLocaleString()} fps` }}</span>
        <span>发送帧率：{{ store.offline ? '—（数据陈旧）' : `${store.statistics.footer_status.tx_fps.toLocaleString()} fps` }}</span>
      </div>
    </footer>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowUpDown, Copy, Download, FileDown, FolderOpen, Maximize2, MonitorDot, Trash2, X } from 'lucide-vue-next'
import { apiDelete, apiDownload, apiPost, formatApiError } from '../api/http'
import { wsClient } from '../api/websocket'
import type { CanLatestFrame, CanDecodedSignal } from '../api/types'
import { useCanStore } from '../stores/can'
import BarChart from '../components/charts/BarChart.vue'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import PageDataState from '../components/PageDataState.vue'
import { useAuthStore } from '../stores/auth'
import IndustrialButton from '../components/common/IndustrialButton.vue'
import { localizeStatus } from '../ui/uiStatusLabels'

const store = useCanStore()
const auth = useAuthStore()
const toast = ref('')
const showAllHistory = ref(false)
const channelOptions: Array<{ value: 'ALL' | 'CAN1' | 'CAN2'; label: string }> = [
  { value: 'ALL', label: '全部' }, { value: 'CAN1', label: 'CAN1' }, { value: 'CAN2', label: 'CAN2' },
]
const directionOptions: Array<{ value: 'ALL' | 'RX' | 'TX'; label: string; hint: string }> = [
  { value: 'ALL', label: '全部', hint: '全部方向' }, { value: 'RX', label: '接收', hint: '接收（RX）' }, { value: 'TX', label: '发送', hint: '发送（TX）' },
]

const selectedFrame = computed(() => store.selectedFrame)
const selectedSignals = computed<CanDecodedSignal[]>(() => store.selectedDecoded?.signals || rawSignals(selectedFrame.value))
const sortLabel = computed(() => (store.sortMode === 'can_id_asc' ? '升序' : store.sortMode === 'can_id_desc' ? '降序' : '最近'))
const visibleHistoryFiles = computed(() => showAllHistory.value ? store.statistics.history_files : store.statistics.history_files.slice(0, 4))

const chartText = { color: '#91A7C6', fontSize: 10 }
const axisLine = { lineStyle: { color: '#24486F' } }
const splitLine = { lineStyle: { color: 'rgba(72, 119, 170, .22)' } }

const distributionOption = computed<Record<string, unknown>>(() => ({
  backgroundColor: 'transparent',
  grid: { left: 48, right: 42, top: 10, bottom: 22, containLabel: true },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'value', splitNumber: 4, axisLabel: { ...chartText, hideOverlap: true, formatter: (value: number) => value >= 1000 ? `${Math.round(value / 1000)}k` : value }, axisLine, splitLine },
  yAxis: {
    type: 'category',
    inverse: true,
    axisLabel: { ...chartText, hideOverlap: true },
    axisLine,
    data: store.statistics.can_id_distribution.slice(0, 6).map((item) => item.can_id_hex),
  },
  series: [{
    type: 'bar',
    barWidth: 10,
    data: store.statistics.can_id_distribution.slice(0, 6).map((item) => item.count),
    label: { show: true, position: 'right', color: '#BCD4F2', formatter: ({ dataIndex }: { dataIndex: number }) => `${store.statistics.can_id_distribution[dataIndex]?.percent}%` },
    itemStyle: { color: '#2F80FF', borderRadius: [0, 5, 5, 0] },
  }],
}))

const fpsOption = computed<Record<string, unknown>>(() => ({
  backgroundColor: 'transparent',
  color: ['#21C55D', '#2F80FF'],
  grid: { left: 36, right: 12, top: 24, bottom: 20, containLabel: true },
  legend: { type: 'scroll', top: 0, right: 6, textStyle: chartText },
  xAxis: { type: 'category', data: store.statistics.fps_trend.map((item) => item.time.slice(0, 5)), axisLabel: { ...chartText, hideOverlap: true, interval: 'auto' }, axisLine },
  yAxis: { type: 'value', min: 0, max: 1200, splitNumber: 4, axisLabel: { ...chartText, hideOverlap: true }, axisLine, splitLine },
  series: [
    { name: 'CAN1', type: 'line', smooth: true, showSymbol: false, data: store.statistics.fps_trend.map((item) => item.can1) },
    { name: 'CAN2', type: 'line', smooth: true, showSymbol: false, data: store.statistics.fps_trend.map((item) => item.can2) },
  ],
}))

const jitterOption = computed<Record<string, unknown>>(() => ({
  backgroundColor: 'transparent',
  color: ['#2F80FF', '#21C55D', '#F6C343'],
  grid: { left: 36, right: 12, top: 24, bottom: 20, containLabel: true },
  legend: { type: 'scroll', top: 0, right: 2, textStyle: chartText },
  xAxis: { type: 'category', data: store.statistics.period_jitter.map((item) => item.time.slice(0, 5)), axisLabel: { ...chartText, hideOverlap: true, interval: 'auto' }, axisLine },
  yAxis: { type: 'value', min: -10, max: 10, splitNumber: 4, axisLabel: { ...chartText, hideOverlap: true }, axisLine, splitLine },
  series: [
    { name: '0x121', type: 'scatter', symbolSize: 7, data: store.statistics.period_jitter.map((item) => item.id_121) },
    { name: '0x51', type: 'scatter', symbolSize: 7, data: store.statistics.period_jitter.map((item) => item.id_51) },
    { name: '0x100', type: 'scatter', symbolSize: 7, data: store.statistics.period_jitter.map((item) => item.id_100) },
  ],
}))

onMounted(async () => {
  store.bindWebSocket()
  if (!wsClient.ws || wsClient.ws.readyState > WebSocket.OPEN) wsClient.connect()
  await Promise.all([store.loadLatest(), store.loadStatistics()])
  if (store.selectedFrame) await store.loadDecoded(store.selectedFrame.can_id_hex, store.selectedFrame.channel)
})

function canIdLabel(frame: CanLatestFrame): string {
  return store.filters.radix === 'Dec' ? String(frame.can_id) : frame.can_id_hex
}

function dataLabel(dataHex: string): string {
  if (store.filters.radix === 'Hex') return dataHex
  return dataHex.split(/\s+/).filter(Boolean).map((byte) => Number.parseInt(byte, 16)).join(' ')
}

function directionLabel(direction: string): string {
  return direction === 'RX' ? '接收' : direction === 'TX' ? '发送' : localizeStatus(direction)
}

function statusClass(status: string): string {
  if (status.includes('超时')) return 'warn'
  if (status.includes('错误') || status.toLowerCase().includes('fail')) return 'bad'
  return 'good'
}

function rawSignals(frame?: CanLatestFrame): CanDecodedSignal[] {
  const bytes = (frame?.data_hex || '').split(/\s+/).filter(Boolean)
  return bytes.map((byte, index) => ({
    name: `Data Byte${index}`,
    start_bit: index * 8,
    length: 8,
    type: 'uint8',
    raw: `0x${byte}`,
    raw_value: Number.parseInt(byte, 16),
    physical_value: Number.parseInt(byte, 16),
    unit: '-',
    enum: '-',
    remark: 'DBC 解析失败，raw-only',
  }))
}

async function postAction(path: string, label: string, body: unknown = {}) {
  try {
    const res = await apiPost<{ message?: string; details?: Record<string, unknown>; ok?: boolean }>(path, body)
    const downloadUrl = typeof res.details?.download_url === 'string' ? res.details.download_url : ''
    if (downloadUrl) await apiDownload(downloadUrl, typeof res.details?.file_name === 'string' ? res.details.file_name : undefined)
    showToast(`${label}：${res.message || '完成'}`)
    return true
  } catch (error) {
    showToast(`${label}：${formatApiError(error)}`)
    return false
  }
}

async function clearDisplay() {
  if (await postAction('/can/frames/clear-display', '清空显示')) store.clearDisplay()
}

async function loadFirstHistory() {
  const file = store.statistics.history_files[0]
  if (!file) { showToast('加载历史文件：当前没有可加载文件'); return }
  await postAction('/logs/load-history', '加载历史文件', { file_id: file.file_id })
}

async function downloadHistory(fileId: string, fileName: string) {
  try {
    const result = await apiDownload(`/logs/raw-can-files/${encodeURIComponent(fileId)}/download`, fileName)
    showToast(`下载历史文件：已下载 ${result.filename}`)
  } catch (error) {
    showToast(`下载历史文件：${formatApiError(error)}`)
  }
}

async function deleteHistory(fileId: string) {
  try {
    const res = await apiDelete<{ message?: string }>(`/logs/raw-can-files/${encodeURIComponent(fileId)}`)
    showToast(`删除历史文件：${res.message || '完成'}`)
    await store.loadStatistics()
  } catch (error) {
    showToast(`删除历史文件：${formatApiError(error)}`)
  }
}

async function copyFrameData() {
  if (!selectedFrame.value) return
  try {
    await navigator.clipboard.writeText(selectedFrame.value.data_hex)
    showToast('帧数据已复制')
  } catch (error) {
    showToast(`复制失败：${formatApiError(error)}`)
  }
}

function showToast(message: string) {
  toast.value = message
  window.setTimeout(() => {
    if (toast.value === message) toast.value = ''
  }, 2400)
}
</script>

<style scoped>
.can-monitor-page {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-rows: 42px 76px minmax(0, 1.48fr) minmax(0, .88fr) 34px;
  gap: 10px;
  color: #d7e7fb;
}

.page-header,
.filter-panel,
.panel,
.monitor-footer {
  border: 1px solid rgba(30, 58, 95, .98);
  background: linear-gradient(145deg, rgba(16, 36, 61, .96), rgba(10, 22, 40, .98));
  box-shadow: inset 0 1px 0 rgba(84, 138, 203, .12), 0 12px 28px rgba(0, 0, 0, .16);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 8px 14px;
  border-radius: 8px;
}

.title-block {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.title-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #8FC4FF;
  background: linear-gradient(145deg, rgba(47, 128, 255, .28), rgba(47, 128, 255, .08));
  border: 1px solid rgba(47, 128, 255, .45);
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  font-size: 19px;
  font-weight: 760;
  letter-spacing: 0;
}

.title-block p {
  margin-top: 3px;
  color: #8EA7C8;
  font-size: 12px;
}

.offline-badge {
  margin-left: 10px;
  padding: 4px 9px;
  border-radius: 999px;
  color: #F6C343;
  border: 1px solid rgba(246, 195, 67, .45);
  background: rgba(246, 195, 67, .08);
  font-size: 12px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

button {
  border: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
}

.action {
  height: 32px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 11px;
  border-radius: 6px;
  color: #CFE4FF;
  border: 1px solid rgba(47, 128, 255, .48);
  background: linear-gradient(180deg, rgba(47, 128, 255, .24), rgba(47, 128, 255, .10));
  font-size: 12px;
}

.action.danger {
  color: #FFD4D4;
  border-color: rgba(239, 68, 68, .5);
  background: linear-gradient(180deg, rgba(239, 68, 68, .22), rgba(239, 68, 68, .09));
}

.filter-panel {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  min-width: 0;
}

.filter-item {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.filter-item span {
  color: #8EA7C8;
  font-size: 11px;
}

.filter-item input,
.filter-item select {
  width: 100%;
  min-width: 0;
  height: 31px;
  padding: 0 9px;
  color: #D7E7FB;
  border: 1px solid rgba(45, 82, 130, .95);
  border-radius: 6px;
  outline: none;
  background: #081A2D;
}

.filter-item select {
  appearance: none;
}

.segmented {
  height: 31px;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 1fr;
  padding: 3px;
  border-radius: 7px;
  border: 1px solid rgba(45, 82, 130, .95);
  background: #081A2D;
}

.segmented button {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-radius: 5px;
  color: #8EA7C8;
  background: transparent;
  font-size: 12px;
}

.segmented button.active {
  color: #fff;
  background: linear-gradient(180deg, #2F80FF, #1C5FC4);
  box-shadow: 0 0 14px rgba(47, 128, 255, .24);
}

.pause {
  justify-items: start;
}

.toggle {
  width: 46px;
  height: 24px;
  position: relative;
  border-radius: 999px;
  border: 1px solid rgba(80, 104, 135, .8);
  background: #18263A;
}

.toggle i {
  position: absolute;
  top: 3px;
  left: 4px;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  background: #8190A5;
  transition: transform .16s ease, background .16s ease;
}

.toggle.on {
  border-color: rgba(246, 195, 67, .65);
  background: rgba(246, 195, 67, .18);
}

.toggle.on i {
  transform: translateX(21px);
  background: #F6C343;
}

.main-grid {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.58fr) minmax(430px, .72fr);
  gap: 10px;
}

.stats-grid {
  min-height: 0;
  display: grid;
  grid-template-columns: 1.2fr .95fr .95fr .72fr 1.08fr;
  gap: 10px;
}

.panel {
  min-height: 0;
  overflow: hidden;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
}

.panel-head {
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid rgba(30, 58, 95, .85);
}

.panel-head h2 {
  font-size: 14px;
  font-weight: 700;
}

.panel-head span,
.more {
  color: #8EA7C8;
  background: transparent;
  font-size: 12px;
}

.detail-head h2 {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 12px;
}

.icon-actions {
  display: flex;
  gap: 8px;
  color: #8EA7C8;
  flex: none;
}
.icon-actions button,.copy-action{display:grid;place-items:center;border:0;color:inherit;background:transparent}.icon-actions button:disabled{opacity:.45;cursor:not-allowed}.tabs button:disabled{opacity:.45;cursor:not-allowed}

.frame-table-wrap,
.signal-table-wrap {
  min-height: 0;
  overflow: auto;
  scrollbar-color: #28527D #081A2D;
}

.frame-table,
.signal-table,
.history-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

th {
  height: 31px;
  color: #94ACCA;
  background: #0A1A2D;
  border-bottom: 1px solid rgba(30, 58, 95, .9);
  font-size: 11px;
  font-weight: 650;
}

td {
  height: 31px;
  padding: 0 7px;
  color: #D7E7FB;
  border-bottom: 1px solid rgba(30, 58, 95, .48);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

thead th {
  position: sticky;
  top: 0;
  z-index: 1;
}

.frame-table th:nth-child(1) { width: 118px; }
.frame-table th:nth-child(2) { width: 68px; }
.frame-table th:nth-child(3) { width: 54px; }
.frame-table th:nth-child(4) { width: 96px; }
.frame-table th:nth-child(5) { width: 74px; }
.frame-table th:nth-child(6) { width: 44px; }
.frame-table th:nth-child(7) { width: 218px; }
.frame-table th:nth-child(8) { width: 176px; }
.frame-table th:nth-child(9) { width: 72px; }
.frame-table th:nth-child(10) { width: 68px; }
.frame-table th:nth-child(11) { width: 114px; }
.frame-table th:nth-child(12) { width: 68px; }

.sortable {
  color: #CFE4FF;
  cursor: pointer;
}

.sortable svg {
  vertical-align: -2px;
  margin: 0 4px;
}

.frame-table tbody tr {
  background: rgba(9, 26, 45, .24);
}

.frame-table tbody tr:hover,
.frame-table tbody tr.selected {
  background: rgba(47, 128, 255, .18);
  box-shadow: inset 3px 0 0 #2F80FF;
}

.can-id,
.hex {
  font-family: Consolas, Monaco, monospace;
  color: #B8D7FF;
}

.channel-pill,
.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 46px;
  height: 20px;
  padding: 0 7px;
  border-radius: 999px;
  border: 1px solid rgba(47, 128, 255, .48);
  background: rgba(47, 128, 255, .12);
  color: #9CCAFF;
  font-size: 11px;
}

.status-pill.good {
  color: #B8F7CD;
  border-color: rgba(33, 197, 93, .52);
  background: rgba(33, 197, 93, .12);
}

.status-pill.warn {
  color: #FFE4A3;
  border-color: rgba(246, 195, 67, .55);
  background: rgba(246, 195, 67, .12);
}

.status-pill.bad {
  color: #FFCACA;
  border-color: rgba(239, 68, 68, .55);
  background: rgba(239, 68, 68, .12);
}

.empty {
  text-align: center;
  color: #8EA7C8;
}

.detail-content {
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr);
  gap: 10px;
  padding: 10px;
}

.frame-info {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.frame-info div {
  min-width: 0;
  padding: 7px 8px;
  border: 1px solid rgba(30, 58, 95, .82);
  border-radius: 6px;
  background: rgba(7, 17, 31, .55);
}

.frame-info span,
.data-row span {
  display: block;
  color: #8EA7C8;
  font-size: 11px;
}

.frame-info b {
  display: block;
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.data-row {
  min-width: 0;
  display: grid;
  grid-template-columns: 60px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border: 1px solid rgba(30, 58, 95, .82);
  border-radius: 6px;
  background: rgba(7, 17, 31, .55);
}

.data-row code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #CFE4FF;
  font-family: Consolas, Monaco, monospace;
}

.tabs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}

.tabs button {
  height: 28px;
  border-radius: 6px;
  color: #8EA7C8;
  border: 1px solid rgba(45, 82, 130, .88);
  background: #081A2D;
  font-size: 12px;
}

.tabs button.active {
  color: #fff;
  border-color: rgba(47, 128, 255, .55);
  background: rgba(47, 128, 255, .22);
}

.signal-table th:nth-child(1) { width: 180px; }
.signal-table th:nth-child(2),
.signal-table th:nth-child(3) { width: 54px; }
.signal-table th:nth-child(4) { width: 78px; }
.signal-table th:nth-child(5) { width: 72px; }
.signal-table th:nth-child(6) { width: 78px; }
.signal-table th:nth-child(7) { width: 48px; }
.signal-table th:nth-child(8) { width: 160px; }
.signal-table th:nth-child(9) { width: 120px; }

.chart-body {
  flex: 1;
  min-height: 0;
  padding: 4px 6px 8px 2px;
}

.chart-body :deep(.chart) {
  min-height: 0;
}

.error-kpis {
  display: grid;
  grid-template-rows: repeat(3, 1fr);
  gap: 8px;
  padding: 10px;
  min-height: 0;
  flex: 1;
}

.kpi {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-radius: 7px;
  border: 1px solid rgba(30, 58, 95, .9);
  background: rgba(7, 17, 31, .58);
}

.kpi span {
  color: #9CB5D5;
  font-size: 12px;
}

.kpi strong {
  font-size: 25px;
}

.kpi.warn strong {
  color: #F6C343;
}

.kpi.bad strong {
  color: #EF4444;
}

.history-table th,
.history-table td {
  height: 27px;
  font-size: 11px;
}

.history-table th:nth-child(1) { width: 170px; }
.history-table th:nth-child(2) { width: 96px; }
.history-table th:nth-child(3) { width: 70px; }
.history-table th:nth-child(4) { width: 58px; }
.history-table th:nth-child(5) { width: 70px; }

.file-actions {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #8FC4FF;
}

.file-actions svg {
  cursor: pointer;
}

.monitor-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-radius: 7px;
  color: #9CB5D5;
  font-size: 12px;
}

.monitor-footer div {
  display: flex;
  align-items: center;
  gap: 18px;
}

.green-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #21C55D;
  box-shadow: 0 0 12px rgba(33, 197, 93, .8);
}

.toast {
  position: fixed;
  right: 28px;
  bottom: 42px;
  z-index: 20;
  max-width: 520px;
  padding: 10px 14px;
  color: #D7E7FB;
  border: 1px solid rgba(47, 128, 255, .55);
  border-radius: 8px;
  background: rgba(11, 29, 50, .96);
  box-shadow: 0 14px 34px rgba(0, 0, 0, .32);
  font-size: 13px;
}

@media (max-width: 1500px) {
  .can-monitor-page {
    grid-template-rows: 42px 108px minmax(0, 1.5fr) minmax(0, .86fr) 34px;
    gap:8px;
  }

  .filter-panel {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    grid-template-rows:repeat(2,minmax(0,1fr));
    gap: 5px 8px;
    padding:5px 9px;
  }
  .filter-item{gap:3px}.filter-item span{font-size:9px}.filter-item input,.filter-item select,.segmented{height:27px}.segmented button{font-size:10px;padding-inline:3px}

  .main-grid {
    grid-template-columns: minmax(0, 1.48fr) minmax(380px, .75fr);
  }

  .stats-grid {
    grid-template-columns: 1.1fr .9fr .9fr .68fr 1fr;
  }
  .panel-head{height:32px}.panel-head h2{font-size:11px}.chart-body{padding:2px 3px 4px}.error-kpis{gap:4px;padding:5px}.kpi{padding-inline:6px}.kpi span{font-size:9px}.kpi strong{font-size:18px}.history-table th,.history-table td{height:23px;font-size:9px}
}
</style>
