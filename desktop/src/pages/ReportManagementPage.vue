<template>
  <section :class="['report-page', previewFullscreen ? 'preview-fullscreen' : '']">
    <header class="page-title-row">
      <div class="title-left">
        <div class="title-icon"><FileChartColumn :size="22" /></div>
        <div><h1>报告管理</h1><p>报告目录扫描、预览、导出与关联数据管理</p></div>
      </div>
      <PageDataState :loading="reportsStore.loading" :error="reportsStore.error" :stale="reportsStore.offline || dashboard.mock || dashboard.quality !== 'good'" :empty="!dashboard.reports.length" />
    </header>

    <section class="top-row">
      <article class="panel directory-panel">
        <h2>报告目录</h2>
        <div class="directory-path">
          <Folder :size="20" /><div><span>默认设备目录</span><strong>{{ dashboard.directory.path }}</strong></div>
          <IndustrialButton v-if="auth.isAdmin" compact type="button" :disabled="reportsStore.offline" @click="runAction('change-directory', '更改目录')">更改目录</IndustrialButton>
        </div>
        <div class="directory-body">
          <div class="storage-block">
            <h3>存储空间统计</h3>
            <div class="storage-content">
              <div class="mini-chart"><RealtimeLineChart :option="storageDonutOption" height="100%" /></div>
              <div class="storage-values">
                <p><span>总容量</span><b>{{ dashboard.directory.total_gb }} GB</b></p>
                <p><span>已使用</span><b>{{ dashboard.directory.used_gb }} GB ({{ dashboard.directory.used_percent }}%)</b></p>
                <p><span>可用</span><b>{{ dashboard.directory.free_gb }} GB ({{ (100 - dashboard.directory.used_percent).toFixed(1) }}%)</b></p>
              </div>
            </div>
          </div>
          <div class="file-types">
            <h3>文件类型统计</h3>
            <p v-for="(item, index) in dashboard.directory.file_type_stats" :key="item.type">
              <i :style="{ background: fileTypeColors[index] }"></i><span>{{ item.type }}</span><b>{{ item.count.toLocaleString() }} ({{ item.percent }}%)</b>
            </p>
          </div>
        </div>
        <footer><span>最近扫描时间　{{ dashboard.directory.last_scan_time }}</span><b>{{ localizeStatus(dashboard.directory.scan_status) }}</b></footer>
      </article>

      <article class="panel filter-panel">
        <h2>搜索与筛选</h2>
        <div class="filter-content">
          <div class="filters-grid">
            <label><span>底盘编号</span><input v-model="filters.chassis" placeholder="请输入底盘编号" /></label>
            <label><span>VIN</span><input v-model="filters.vin" placeholder="请输入VIN" /></label>
            <label class="date-range"><span>检测时间</span><div><CalendarDays :size="15" /><input v-model="filters.startTime" placeholder="开始日期时间" /><em>→</em><input v-model="filters.endTime" placeholder="结束日期时间" /></div></label>
            <label><span>结果</span><select v-model="filters.result"><option value="全部">全部</option><option value="PASS">通过</option><option value="FAIL">失败</option></select></label>
            <label><span>操作员</span><select v-model="filters.operator"><option>全部</option><option v-for="operator in reportOperators" :key="operator">{{ operator }}</option></select></label>
            <label><span>文件类型</span><select v-model="filters.fileType"><option>全部</option><option v-for="type in reportTypes" :key="type">{{ type }}</option></select></label>
          </div>
          <div class="scan-actions">
            <button v-if="auth.can('operator')" type="button" :disabled="reportsStore.offline" @click="runAction('scan', '扫描目录')"><RefreshCw :size="19" /><span><strong>扫描目录</strong><small>刷新目录报告索引</small></span></button>
            <button v-if="auth.can('operator')" type="button" :disabled="reportsStore.offline" @click="runAction('open-directory', '打开报告目录')"><FolderOpen :size="19" /><span><strong>打开报告目录</strong><small>定位当前报告目录</small></span></button>
          </div>
        </div>
      </article>
    </section>

    <section class="middle-row">
      <article class="panel report-list-panel">
        <header class="panel-header"><h2>报告列表</h2><div class="table-tools"><button aria-label="刷新报告列表" @click="reportsStore.loadDashboard()"><RefreshCw :size="14" /></button><button aria-label="列设置（尚未实现）" disabled title="尚未实现"><Columns3 :size="14" /></button><button aria-label="列表密度（尚未实现）" disabled title="尚未实现"><List :size="14" /></button></div></header>
        <div class="table-scroll">
          <table class="dense-table report-table">
            <thead><tr><th>报告ID</th><th>底盘编号</th><th>VIN</th><th>检测时间</th><th>结果</th><th>操作员</th><th>类型</th><th>大小</th><th>路径</th><th>生成状态</th></tr></thead>
            <tbody>
              <tr v-for="item in filteredReports" :key="item.report_id" :class="{ selected: item.report_id === selected.report_id }" @click="selectReport(item)">
                <td>{{ item.report_id }}</td><td>{{ item.chassis_no }}</td><td>{{ item.vin }}</td><td>{{ item.test_time }}</td>
                <td><StatusPill :value="item.result" /></td><td>{{ item.operator }}</td><td>{{ item.type }}</td><td>{{ item.size }}</td><td :title="item.path">{{ item.path }}</td>
                <td><span class="complete-pill">{{ localizeStatus(item.generation_status) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel preview-panel">
        <h2>报告预览</h2>
        <div class="preview-tabs"><button v-for="tabName in previewTabs" :key="tabName" :class="{ active: activePreviewTab === tabName }" @click="activePreviewTab = tabName">{{ tabName }}</button></div>
        <div v-if="activePreviewTab === '预览'" class="document-viewer">
          <div class="viewer-toolbar">
            <button aria-label="预览菜单（尚未实现）" disabled title="尚未实现"><Menu :size="15" /></button><strong>{{ selected.filename }}</strong>
            <span>{{ selected.preview.page }} / {{ selected.preview.total_pages }}</span>
            <button aria-label="缩小预览" @click="zoom = Math.max(50, zoom - 10)"><Minus :size="14" /></button><b>{{ zoom }}%</b><button aria-label="放大预览" @click="zoom = Math.min(160, zoom + 10)"><Plus :size="14" /></button>
            <button aria-label="全屏预览" @click="previewFullscreen = !previewFullscreen"><Maximize2 :size="14" /></button>
            <button aria-label="下载报告" @click="downloadSelectedReport"><Download :size="14" /></button>
            <button v-if="auth.can('operator')" aria-label="打印报告" :disabled="!selected.report_id || !reportsStore.printers.available" @click="runAction('print', '打印')"><Printer :size="14" /></button>
          </div>
          <div class="paper-viewport">
            <img v-if="selected.preview_image_data_url" class="report-render" :src="selected.preview_image_data_url" :alt="selected.filename" :style="{ transform: `scale(${zoom / 100})` }" />
            <div v-else class="report-paper" :style="{ transform: `scale(${zoom / 100})` }">
              <div class="paper-brand"><div class="paper-logo">YL</div><span><strong>测试科技</strong><small>TEST TECHNOLOGY</small></span></div>
              <h3>{{ selected.preview.title }}</h3>
              <dl><div><dt>底盘编号：</dt><dd>{{ selected.preview.chassis_no }}</dd></div><div><dt>车辆识别码（VIN）：</dt><dd>{{ selected.preview.vin }}</dd></div><div><dt>检测时间：</dt><dd>{{ selected.preview.test_time }}</dd></div><div><dt>结果：</dt><dd :class="selected.preview.result.toLowerCase()">{{ localizeStatus(selected.preview.result) }}</dd></div><div><dt>操作员：</dt><dd>{{ selected.preview.operator }}</dd></div></dl>
              <div :class="['pass-stamp', selected.preview.result.toLowerCase()]">{{ localizeStatus(selected.preview.result) }}</div>
            </div>
          </div>
        </div>
        <pre v-else-if="activePreviewTab === 'JSON摘要'" class="code-preview">{{ JSON.stringify(selected.json_summary || {}, null, 2) }}</pre>
        <div v-else class="csv-preview"><table class="dense-table"><thead><tr><th>信号</th><th>值</th><th>单位</th><th>结果</th></tr></thead><tbody><tr v-for="row in selected.csv_rows || []" :key="String(row.signal)"><td>{{ row.signal }}</td><td>{{ row.value }}</td><td>{{ row.unit }}</td><td>{{ localizeStatus(String(row.result)) }}</td></tr></tbody></table></div>
      </article>
    </section>

    <section class="bottom-row">
      <article class="panel related-panel">
        <h2>关联数据</h2>
        <div class="data-tabs"><button v-for="(tabName, index) in relatedTabs" :key="tabName" :class="{ active: index === 0 }" :disabled="index !== 0" :title="index === 0 ? '' : '尚未实现：当前统一展示关联会话摘要'">{{ tabName }}{{ index === 0 ? '' : '（尚未实现）' }}</button></div>
        <div class="table-scroll"><table class="dense-table related-table"><thead><tr><th>会话编号</th><th>开始时间</th><th>结束时间</th><th>结果</th><th>报告数</th><th>操作</th></tr></thead><tbody><tr v-for="row in dashboard.related_data.sessions" :key="row.session_id"><td>{{ row.session_id }}</td><td>{{ row.started_at }}</td><td>{{ row.ended_at }}</td><td><StatusPill :value="row.result" /></td><td>{{ row.report_count }}</td><td><button class="eye-btn" aria-label="查看会话（尚未实现）" disabled title="尚未实现"><Eye :size="14" /></button></td></tr></tbody></table></div>
      </article>

      <article class="panel chart-panel"><header><h2>报告存储使用趋势</h2><select disabled title="当前仅支持近7天"><option>近7天</option></select></header><RealtimeLineChart :option="storageTrendOption" height="100%" /></article>
      <article class="panel chart-panel"><header><h2>结果分布统计</h2><select disabled title="当前仅支持全部时间"><option>全部时间</option></select></header><RealtimeLineChart :option="resultDistributionOption" height="100%" /></article>

      <article class="panel operations-panel">
        <h2>操作</h2>
        <div class="operation-grid">
          <IndustrialActionButton v-for="item in visibleOperationButtons" :key="item.action" :title="item.label" :subtitle="item.subtitle" :variant="item.action === 'delete' ? 'danger' : 'primary'" :disabled="reportsStore.offline || !selected.report_id" @click="handleOperation(item.action, item.label)">
            <template #icon><component :is="item.icon" :size="22" /></template>
          </IndustrialActionButton>
        </div>
        <div v-if="reportsStore.activePrintJob" class="print-job" data-testid="print-job-status">
          <span :class="['print-state', reportsStore.activePrintJob.status.toLowerCase()]">{{ printStatusLabel }}</span>
          <b>{{ reportsStore.activePrintJob.job_id }}</b>
          <small>spooler {{ reportsStore.activePrintJob.spooler_job_id || '待分配' }} · 尝试 {{ reportsStore.activePrintJob.attempts }}</small>
          <em v-if="reportsStore.activePrintJob.error_message">{{ reportsStore.activePrintJob.error_message }}</em>
          <button v-if="['QUEUED','PRINTING'].includes(reportsStore.activePrintJob.status) && auth.can('operator')" @click="cancelPrint">取消</button>
          <button v-if="reportsStore.activePrintJob.status === 'FAILED' && auth.can('operator')" @click="retryPrint">重试</button>
        </div>
      </article>
    </section>

    <div v-if="deleteConfirmOpen" class="dialog-overlay" role="dialog" aria-label="删除报告确认">
      <div class="confirm-dialog"><div class="confirm-icon"><Trash2 :size="28" /></div><h3>确认删除报告？</h3><p>{{ selected.report_id }} 删除后不可恢复，且需要管理员权限。</p><div><button @click="deleteConfirmOpen = false">取消删除</button><button class="danger" @click="confirmDelete">确认删除</button></div></div>
    </div>
    <div v-if="printConfirmOpen" class="dialog-overlay" role="dialog" aria-modal="true" aria-label="打印预览确认">
      <div class="confirm-dialog print-dialog">
        <div class="confirm-icon"><Printer :size="28" /></div><h3>确认打印已预览的 PDF</h3>
        <p>报告 {{ selected.report_id }} 将按当前文件 hash 提交到系统打印队列。</p>
        <label><span>打印机</span><select v-model="selectedPrinter"><option v-for="printer in reportsStore.printers.printers" :key="printer.name" :value="printer.name">{{ printer.name }}{{ printer.is_default ? '（默认）' : '' }}</option></select></label>
        <label class="preview-check"><input v-model="printPreviewConfirmed" type="checkbox" /> 我已核对 PDF 预览、车辆信息和检测结果</label>
        <div><button @click="printConfirmOpen = false">取消</button><button :disabled="!printPreviewConfirmed || !selectedPrinter" @click="confirmPrint">提交打印</button></div>
      </div>
    </div>
    <div v-if="toast" class="toast">{{ toast }}</div>
  </section>
</template>

<script setup lang="ts">
import {
  CalendarDays, Columns3, Download, Eye, FileChartColumn, FileOutput, FileText, Folder, FolderOpen,
  List, Maximize2, Menu, Minus, Plus, Printer, RefreshCw, RotateCcw, ScrollText, Trash2,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { wsClient } from '../api/websocket'
import { formatApiError } from '../api/http'
import type { ReportListItem, ReportPreviewData } from '../api/types'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import { useReportsStore } from '../stores/reports'
import { useAuthStore, type Role } from '../stores/auth'
import PageDataState from '../components/PageDataState.vue'
import IndustrialActionButton from '../components/common/IndustrialActionButton.vue'
import IndustrialButton from '../components/common/IndustrialButton.vue'
import { localizeStatus } from '../ui/uiStatusLabels'

type StoreAction = 'scan' | 'open-directory' | 'change-directory' | 'export-word' | 'export-pdf' | 'print' | 'regenerate'
type OperationAction = StoreAction | 'delete' | 'related-logs'

const reportsStore = useReportsStore()
const auth = useAuthStore()
const route = useRoute()
const dashboard = computed(() => reportsStore.dashboard)
const emptyReportPreview: ReportPreviewData = {
  report_id: '', filename: '未选择报告', file_type: '', file_sha256: '', file_size_bytes: 0,
  data_source: 'none', mock: false, quality: 'unavailable', updated_at: '', trace_id: '',
  preview: { title: '未选择报告', chassis_no: '-', vin: '-', test_time: '-', result: 'WAIT', operator: '-', page: 0, total_pages: 0, zoom: 100 },
  json_summary: {}, csv_rows: [], document_text: [], preview_image_data_url: null,
}
const selected = computed<ReportPreviewData>(() => dashboard.value.selected_report || emptyReportPreview)
const activePreviewTab = ref('预览')
const previewTabs = ['预览', 'JSON摘要', 'CSV前100行']
const relatedTabs = ['检测会话', '原始CAN', '解码信号', '操作日志', '报告文件']
const fileTypeColors = ['#2F80FF', '#EF4444', '#F6C343', '#21C55D', '#8B5CF6']
const zoom = ref(100)
const previewFullscreen = ref(false)
const deleteConfirmOpen = ref(false)
const printConfirmOpen = ref(false)
const printPreviewConfirmed = ref(false)
const selectedPrinter = ref('')
const toast = ref('')
let toastTimer: number | undefined
let pollTimer: number | undefined
let wsReady = false
let wsDisposers: Array<() => void> = []

const filters = reactive({ chassis: '', vin: '', startTime: '', endTime: '', result: '全部', operator: '全部', fileType: '全部' })

const StatusPill = defineComponent({
  props: { value: { type: String, required: true } },
  setup(props) { return () => h('span', { class: ['result-pill', props.value.toLowerCase()] }, localizeStatus(props.value)) },
})

const operationButtons: Array<{ label: string; subtitle: string; action: OperationAction; icon: Component; role: Role }> = [
  { label: '导出 Word', subtitle: '生成可编辑报告', action: 'export-word', icon: FileText, role: 'operator' }, { label: '导出 PDF', subtitle: '导出已核验版式', action: 'export-pdf', icon: FileOutput, role: 'operator' },
  { label: '打印', subtitle: '预览确认后提交', action: 'print', icon: Printer, role: 'operator' }, { label: '删除', subtitle: '管理员危险操作', action: 'delete', icon: Trash2, role: 'admin' },
  { label: '重新生成', subtitle: '按当前数据重建', action: 'regenerate', icon: RotateCcw, role: 'operator' }, { label: '关联日志', subtitle: '查看报告审计链', action: 'related-logs', icon: ScrollText, role: 'viewer' },
]
const visibleOperationButtons = computed(() => operationButtons.filter(item => auth.can(item.role)))
const reportOperators = computed(() => [...new Set(dashboard.value.reports.map(item=>item.operator).filter(Boolean))])
const reportTypes = computed(() => [...new Set(dashboard.value.reports.map(item=>item.type).filter(Boolean))])
const printStatusLabel = computed(() => ({QUEUED:'排队中',PRINTING:'打印中',COMPLETED:'已完成',FAILED:'失败',CANCELLED:'已取消'}[reportsStore.activePrintJob?.status || 'QUEUED']))

const filteredReports = computed(() => dashboard.value.reports.filter((item) =>
  (!filters.chassis || item.chassis_no.toLowerCase().includes(filters.chassis.toLowerCase()))
  && (!filters.vin || item.vin.toLowerCase().includes(filters.vin.toLowerCase()))
  && (!filters.startTime || item.test_time >= filters.startTime)
  && (!filters.endTime || item.test_time <= filters.endTime)
  && (filters.result === '全部' || item.result === filters.result)
  && (filters.operator === '全部' || item.operator === filters.operator)
  && (filters.fileType === '全部' || item.type.includes(filters.fileType)),
))

const storageDonutOption = computed(() => ({
  backgroundColor: 'transparent', tooltip: { trigger: 'item' },
  series: [{ type: 'pie', radius: ['57%', '80%'], center: ['50%', '50%'], label: { show: false }, data: [
    { name: '已使用', value: dashboard.value.directory.used_gb, itemStyle: { color: '#2F80FF' } },
    { name: '可用', value: dashboard.value.directory.free_gb, itemStyle: { color: '#21C55D' } },
  ] }],
}))

const storageTrendOption = computed(() => {
  const rows = dashboard.value.charts.storage_trend
  return { backgroundColor: 'transparent', color: ['#2F80FF', '#21C55D'], tooltip: { trigger: 'axis' }, legend: { type: 'scroll', bottom: 0, textStyle: { color: '#AFC2DA', fontSize: 10 }, itemWidth: 16 }, grid: { left: 32, right: 12, top: 18, bottom: 36, containLabel: true }, xAxis: { type: 'category', data: rows.map((row) => row.date), boundaryGap: false, axisLabel: { color: '#8CA6C5', fontSize: 10, hideOverlap: true }, axisLine: { lineStyle: { color: '#315A83' } } }, yAxis: { type: 'value', name: 'GB', nameTextStyle: { color: '#8CA6C5' }, axisLabel: { color: '#8CA6C5', fontSize: 10, hideOverlap: true }, splitLine: { lineStyle: { color: '#1A385C', type: 'dashed' } } }, series: [
    { name: '已使用', type: 'line', smooth: true, data: rows.map((row) => row.used), symbolSize: 5, areaStyle: { opacity: 0.12 } },
    { name: '可用', type: 'line', smooth: true, data: rows.map((row) => row.free), symbolSize: 5, areaStyle: { opacity: 0.08 } },
  ] }
})

const resultDistributionOption = computed(() => {
  const rows = dashboard.value.charts.result_distribution
  const total = rows.reduce((sum, row) => sum + row.value, 0)
  return { backgroundColor: 'transparent', tooltip: { trigger: 'item' }, legend: { type: 'scroll', orient: 'vertical', right: 4, top: 'center', textStyle: { color: '#CFE2FF', fontSize: 11 }, itemWidth: 9, itemHeight: 9, formatter: (name: string) => { const row = rows.find((item) => localizeStatus(item.name) === name); return `${name}  ${(row?.value || 0).toLocaleString()} (${(row?.percent || 0).toFixed(1)}%)` } }, graphic: [{ type: 'text', left: '26%', top: '43%', style: { text: `总计\n${total.toLocaleString()}`, fill: '#EAF2FF', fontSize: 16, fontWeight: 700, textAlign: 'center', lineHeight: 21 } }], series: [{ type: 'pie', radius: ['48%', '70%'], center: ['28%', '54%'], label: { show: false }, data: rows.map((row) => ({ name: localizeStatus(row.name), value: row.value, itemStyle: { color: row.name === 'PASS' ? '#21C55D' : '#EF4444' } })) }] }
})

watch(selected, (value) => { zoom.value = value.preview.zoom || 100 }, { immediate: true })

onMounted(async () => {
  await reportsStore.loadDashboard()
  try {
    const printers = await reportsStore.loadPrinters()
    selectedPrinter.value = printers.default_printer || printers.printers[0]?.name || ''
  } catch (error) { showToast(`打印机诊断：${formatActionError(error)}`) }
  const reportId = typeof route.query.report_id === 'string' ? route.query.report_id : ''
  const sessionId = typeof route.query.session_id === 'string' ? route.query.session_id : ''
  const target = dashboard.value.reports.find((item) => item.report_id === reportId)
    || dashboard.value.reports.find((item) => item.session_id === sessionId)
  if (target) {
    try { await reportsStore.selectReport(target) } catch (error) { showToast(formatActionError(error)) }
  }
  setupWebSocketRefresh()
  pollTimer = window.setInterval(() => { void reportsStore.loadDashboard(); void reportsStore.refreshPrintJob() }, 5000)
})

onBeforeUnmount(() => { if (pollTimer) window.clearInterval(pollTimer); if (toastTimer) window.clearTimeout(toastTimer); wsDisposers.forEach((dispose) => dispose()); wsDisposers = [] })

async function selectReport(item: ReportListItem) { activePreviewTab.value = '预览'; await reportsStore.selectReport(item) }

async function downloadSelectedReport() {
  try { const result = await reportsStore.downloadSelected(); showToast(`下载报告：已下载 ${result.filename}`) }
  catch (error) { showToast(`下载报告：${formatActionError(error)}`) }
}

function setupWebSocketRefresh() {
  try { if (!wsReady) { wsClient.connect(); wsReady = true }; ['reports.scan_progress', 'reports.generation_status'].forEach((topic) => wsDisposers.push(wsClient.on(topic, () => void reportsStore.loadDashboard()))) } catch { wsReady = false }
}

async function handleOperation(action: OperationAction, label: string) {
  if (action === 'delete') { deleteConfirmOpen.value = true; return }
  if (action === 'related-logs') {
    try { await reportsStore.relatedData(); showToast('查看关联日志：关联数据已刷新，当前保持在本页') }
    catch (error) { showToast(`查看关联日志：${formatActionError(error)}`) }
    return
  }
  await runAction(action, label)
}

async function runAction(action: StoreAction, label: string) {
  if (action === 'print') {
    printPreviewConfirmed.value = false
    printConfirmOpen.value = true
    return
  }
  try { const result = await reportsStore.runAction(action); showToast(`${label}：${result.message || '完成'}`) }
  catch (error) { showToast(`${label}：${formatActionError(error)}`) }
}

async function confirmPrint() {
  try {
    const result = await reportsStore.submitPrint(printPreviewConfirmed.value, selectedPrinter.value || null)
    printConfirmOpen.value = false
    showToast(`打印：${result.message || '已提交队列'}`)
  } catch (error) { showToast(`打印：${formatActionError(error)}`) }
}

async function cancelPrint() {
  try { const job = await reportsStore.cancelPrintJob(); showToast(`打印：${job?.status === 'CANCELLED' ? '已取消' : '状态已更新'}`) }
  catch (error) { showToast(`取消打印：${formatActionError(error)}`) }
}

async function retryPrint() {
  try { const job = await reportsStore.retryPrintJob(); showToast(`打印重试：${job?.status || '已提交'}`) }
  catch (error) { showToast(`打印重试：${formatActionError(error)}`) }
}

async function confirmDelete() {
  deleteConfirmOpen.value = false
  try { const result = await reportsStore.deleteSelected(); showToast(`删除：${result.message || '完成'}`); await reportsStore.loadDashboard() }
  catch (error) { showToast(`删除：${formatActionError(error)}`) }
}

function formatActionError(error: unknown) {
  return formatApiError(error)
}

function showToast(message: string) { toast.value = message; if (toastTimer) window.clearTimeout(toastTimer); toastTimer = window.setTimeout(() => { if (toast.value === message) toast.value = '' }, 2800) }
</script>

<style scoped>
.report-page { position:relative; height:100%; min-height:0; overflow:hidden; display:grid; grid-template-rows:42px 200px 340px minmax(0,1fr); gap:10px; color:#EAF2FF; }
.panel { min-height:0; overflow:hidden; border:1px solid #1E3A5F; border-radius:8px; background:linear-gradient(180deg,rgba(16,36,61,.98),rgba(8,23,41,.98)); box-shadow:0 9px 22px rgba(0,0,0,.2); }
.page-title-row { display:flex; align-items:center; justify-content:space-between; padding:0 4px; }
.title-left { display:flex; align-items:center; gap:10px; }.title-icon { width:34px;height:34px;display:grid;place-items:center;border-radius:6px;color:#B9D9FF;border:1px solid rgba(47,128,255,.5);background:linear-gradient(135deg,rgba(47,128,255,.42),rgba(34,211,238,.16)); }
.page-title-row h1 { margin:0;font-size:22px;line-height:24px;font-weight:800; }.page-title-row p { margin:4px 0 0;color:#8CA6C5;font-size:12px; }
.mock-badge { height:30px;display:inline-flex;align-items:center;padding:0 10px;border-radius:6px;border:1px solid rgba(246,195,67,.42);color:#F6C343;background:rgba(246,195,67,.1);font-size:12px; }
.top-row { display:grid;grid-template-columns:.78fr 1.82fr;gap:10px;min-height:0; }.middle-row { display:grid;grid-template-columns:1.55fr .85fr;gap:10px;min-height:0; }.bottom-row { display:grid;grid-template-columns:1.05fr .75fr .65fr .9fr;gap:10px;min-height:0; }
.panel h2 { margin:0;color:#EAF2FF;font-size:13px;line-height:20px;font-weight:800; }.directory-panel { display:grid;grid-template-rows:24px 42px minmax(0,1fr) 20px;padding:6px 10px 4px; }
.directory-path { display:grid;grid-template-columns:24px 1fr auto;align-items:center;gap:8px;border:1px solid #1E3A5F;border-radius:6px;padding:0 8px;background:#081A2F;color:#2F80FF; }.directory-path div { display:grid;min-width:0; }.directory-path span { color:#8CA6C5;font-size:9px; }.directory-path strong { color:#DDEBFF;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }.directory-path button,.table-tools button,.eye-btn { border:1px solid #315A83;border-radius:4px;color:#CFE2FF;background:#102A4A;font-size:10px; }
.directory-body { display:grid;grid-template-columns:1.08fr .92fr;min-height:0;padding-top:5px; }.storage-block { border-right:1px solid #1E3A5F;padding-right:8px; }.directory-body h3 { margin:0 0 3px;color:#AFC2DA;font-size:10px; }.storage-content { display:grid;grid-template-columns:88px 1fr;align-items:center; }.mini-chart { height:79px; }.storage-values { display:grid;gap:4px; }.storage-values p,.file-types p { margin:0;display:flex;align-items:center;justify-content:space-between;gap:7px;color:#8CA6C5;font-size:9px; }.storage-values b,.file-types b { color:#CFE2FF;font-weight:500; }.file-types { padding-left:10px;display:grid;align-content:start;gap:3px; }.file-types p i { width:7px;height:7px;flex:0 0 auto; }.file-types p span { margin-right:auto;color:#AFC2DA; }.directory-panel footer { display:flex;align-items:end;justify-content:space-between;color:#8CA6C5;font-size:9px;border-top:1px solid #1E3A5F; }.directory-panel footer b { color:#21C55D; }
.filter-panel { display:grid;grid-template-rows:28px minmax(0,1fr);padding:6px 12px; }.filter-content { display:grid;grid-template-columns:1fr 170px;gap:16px;min-height:0; }.filters-grid { display:grid;grid-template-columns:.8fr .8fr 1.45fr;grid-template-rows:repeat(2,58px);gap:12px 16px;align-content:center; }.filters-grid label { display:grid;align-content:start;gap:5px;min-width:0;color:#AFC2DA;font-size:10px; }.filters-grid input,.filters-grid select { width:100%;height:32px;border:1px solid #1E3A5F;border-radius:5px;outline:none;color:#DDEBFF;background:#081A2F;padding:0 10px;font-size:11px; }.filters-grid input::placeholder { color:#5F7899; }.date-range div { height:32px;display:grid;grid-template-columns:22px 1fr 16px 1fr;align-items:center;border:1px solid #1E3A5F;border-radius:5px;background:#081A2F;padding:0 7px;color:#6F88A8; }.date-range div input { height:28px;border:0;padding:0 3px; }.date-range em { text-align:center;font-style:normal; }.scan-actions { display:grid;grid-template-rows:1fr 1fr;gap:12px;padding:20px 0; }.scan-actions button { display:flex;align-items:center;justify-content:center;gap:10px;border:1px solid #2F80FF;border-radius:6px;color:#EAF2FF;background:linear-gradient(135deg,#176CD9,#0E4A98); }.scan-actions span { display:grid;text-align:left;gap:3px; }.scan-actions strong { font-size:13px; }.scan-actions small { color:#9FC6F6;font-size:9px; }
.report-list-panel { display:grid;grid-template-rows:30px minmax(0,1fr);padding:0 8px 8px; }.panel-header { display:flex;align-items:center;justify-content:space-between; }.table-tools { display:flex;gap:5px; }.table-tools button { width:24px;height:22px;display:grid;place-items:center;padding:0; }.table-scroll { min-height:0;overflow:auto;scrollbar-color:#2B5C90 #07172A; }.dense-table { width:100%;border-collapse:collapse;table-layout:fixed;font-size:9px; }.dense-table th,.dense-table td { height:25px;padding:0 6px;border:1px solid #1E3A5F;color:#CFE2FF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }.dense-table th { color:#AFC2DA;background:#0A2039;font-weight:700; }.report-table tbody tr { cursor:pointer; }.report-table tbody tr:hover,.report-table tbody tr.selected { background:rgba(47,128,255,.14); }.report-table tbody tr.selected { box-shadow:inset 3px 0 #2F80FF; }
.report-table th:nth-child(1){width:13%}.report-table th:nth-child(2){width:9%}.report-table th:nth-child(3){width:15%}.report-table th:nth-child(4){width:14%}.report-table th:nth-child(5){width:6%}.report-table th:nth-child(6){width:7%}.report-table th:nth-child(7){width:7%}.report-table th:nth-child(8){width:7%}.report-table th:nth-child(9){width:15%}.report-table th:nth-child(10){width:7%}
.result-pill,.complete-pill { display:inline-flex;align-items:center;justify-content:center;min-width:37px;height:18px;border-radius:3px;font-size:9px;font-weight:800; }.result-pill.pass,.complete-pill { color:#21C55D;border:1px solid rgba(33,197,93,.6);background:rgba(33,197,93,.08); }.result-pill.fail { color:#EF4444;border:1px solid rgba(239,68,68,.65);background:rgba(239,68,68,.08); }
.preview-panel { display:grid;grid-template-rows:28px 34px minmax(0,1fr);padding:0 8px 8px; }.preview-panel h2 { display:flex;align-items:center; }.preview-tabs,.data-tabs { display:flex;border-bottom:1px solid #1E3A5F; }.preview-tabs button,.data-tabs button { border:0;border-bottom:2px solid transparent;color:#94A9C5;background:transparent;padding:0 18px;font-size:11px; }.preview-tabs button.active,.data-tabs button.active { color:#EAF2FF;border-bottom-color:#2F80FF;background:rgba(47,128,255,.16); }.document-viewer { min-height:0;display:grid;grid-template-rows:36px minmax(0,1fr);border:1px solid #1E3A5F;border-top:0;background:#07111F; }.viewer-toolbar { display:flex;align-items:center;gap:7px;padding:0 7px;background:#26313E;color:#F2F5F8;font-size:9px; }.viewer-toolbar button { width:22px;height:22px;display:grid;place-items:center;padding:0;border:0;border-radius:3px;color:#E4EAF0;background:transparent; }.viewer-toolbar button:hover { background:#3D4A58; }.viewer-toolbar strong { min-width:0;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }.viewer-toolbar b { min-width:32px;text-align:center; }.paper-viewport { min-height:0;overflow:auto;display:grid;place-items:start center;padding:8px;background:#1F2935;scrollbar-color:#738292 #202A34; }.report-render { width:310px;height:auto;transform-origin:top center;box-shadow:0 5px 18px rgba(0,0,0,.45); }.report-paper { position:relative;width:310px;min-height:220px;transform-origin:top center;padding:20px 28px;background:#FFFFFF;color:#17202C;box-shadow:0 5px 18px rgba(0,0,0,.45); }.paper-brand { display:flex;align-items:center;gap:5px; }.paper-logo { width:22px;height:22px;display:grid;place-items:center;border-radius:50%;color:#FFFFFF;background:#147BD1;font-size:8px;font-weight:900; }.paper-brand span { display:grid; }.paper-brand strong { font-size:9px; }.paper-brand small { font-size:5px;color:#5A6775; }.report-paper h3 { margin:16px 0 13px;text-align:center;font-size:16px;letter-spacing:0;color:#131A23; }.report-paper dl { width:78%;margin:0 auto;display:grid;gap:6px;font-size:8px; }.report-paper dl div { display:grid;grid-template-columns:72px 1fr; }.report-paper dt { font-weight:700; }.report-paper dd { margin:0; }.report-paper dd.pass { color:#16A34A;font-weight:800; }.report-paper dd.fail { color:#DC2626;font-weight:800; }.pass-stamp { position:absolute;right:36px;bottom:18px;transform:rotate(-12deg);border:3px double currentColor;border-radius:50%;padding:8px 4px;font-size:17px;font-weight:900; }.pass-stamp.pass { color:#16A34A; }.pass-stamp.fail { color:#DC2626; }.code-preview,.csv-preview { min-height:0;overflow:auto;margin:0;padding:12px;border:1px solid #1E3A5F;background:#07111F;color:#9FD5FF;font:11px/1.5 Consolas,monospace; }.csv-preview { font-family:inherit; }
.related-panel { display:grid;grid-template-rows:28px 34px minmax(0,1fr);padding:0 8px 8px; }.related-panel h2 { display:flex;align-items:center; }.data-tabs button { flex:1;padding:0 4px;font-size:9px; }.related-table th:nth-child(1){width:29%}.related-table th:nth-child(2){width:20%}.related-table th:nth-child(3){width:20%}.related-table th:nth-child(4){width:11%}.related-table th:nth-child(5){width:10%}.related-table th:nth-child(6){width:10%}.related-table th,.related-table td { height:29px; }.eye-btn { color:#2F80FF;border:0;background:transparent; }
.chart-panel { display:grid;grid-template-rows:32px minmax(0,1fr);padding:0 8px 8px; }.chart-panel header { display:flex;align-items:center;justify-content:space-between; }.chart-panel select { height:23px;border:1px solid #315A83;border-radius:4px;color:#AFC2DA;background:#081A2F;font-size:9px;padding:0 5px; }.operations-panel { display:grid;grid-template-rows:28px minmax(0,1fr) auto;padding:0 10px 8px; }.operations-panel h2 { display:flex;align-items:center; }.operation-grid { min-height:0;overflow:auto;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-auto-rows:70px;align-content:start;gap:6px; }.operation-grid :deep(.industrial-action){padding:0 6px;gap:6px}.operation-grid :deep(.icon-block){width:30px;height:38px}.operation-grid :deep(.action-copy strong){font-size:11px}.operation-grid :deep(.action-copy small){font-size:8px}.print-job{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:4px 6px;margin-top:5px;padding-top:5px;border-top:1px solid #1E3A5F;font-size:8px}.print-job b,.print-job small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.print-job small{grid-column:1/4;color:#8098B7}.print-job em{grid-column:1/4;color:#EF4444;font-style:normal}.print-job button{height:20px;border:1px solid #315A83;border-radius:3px;color:#DDEBFF;background:#102A4A;font-size:8px}.print-state{padding:2px 5px;border:1px solid #315A83;border-radius:3px;color:#8FC2FF}.print-state.completed{color:#21C55D;border-color:#21C55D}.print-state.failed{color:#EF4444;border-color:#EF4444}.print-state.cancelled{color:#F6C343;border-color:#F6C343}
.dialog-overlay { position:fixed;inset:0;z-index:50;display:grid;place-items:center;background:rgba(2,8,16,.72);backdrop-filter:blur(3px); }.confirm-dialog { width:380px;padding:22px;border:1px solid #EF4444;border-radius:8px;text-align:center;background:#0D2036;box-shadow:0 20px 50px rgba(0,0,0,.55); }.confirm-icon { width:52px;height:52px;display:grid;place-items:center;margin:0 auto;border-radius:50%;color:#EF4444;background:rgba(239,68,68,.13); }.confirm-dialog h3 { margin:12px 0 6px;font-size:18px; }.confirm-dialog p { margin:0 0 18px;color:#9FB4CF;font-size:12px; }.confirm-dialog>div:last-child { display:flex;justify-content:center;gap:12px; }.confirm-dialog button { height:34px;padding:0 18px;border:1px solid #315A83;border-radius:5px;color:#DDEBFF;background:#102A4A; }.confirm-dialog button.danger { border-color:#EF4444;background:#A52232; }.toast { position:absolute;right:16px;bottom:16px;z-index:60;max-width:620px;padding:10px 14px;border:1px solid #2F80FF;border-radius:8px;color:#DDEBFF;background:rgba(10,24,43,.97);box-shadow:0 12px 28px rgba(0,0,0,.36);font-size:12px; }
.print-dialog{border-color:#2F80FF}.print-dialog .confirm-icon{color:#8FC2FF;background:rgba(47,128,255,.13)}.print-dialog label{display:grid;gap:6px;margin:10px 0;text-align:left;color:#9FB4CF;font-size:11px}.print-dialog select{height:32px;border:1px solid #315A83;border-radius:5px;color:#DDEBFF;background:#07192D}.print-dialog .preview-check{display:flex;align-items:center;justify-content:center}.print-dialog .preview-check input{width:15px;height:15px}.print-dialog button:disabled,.table-tools button:disabled,.viewer-toolbar button:disabled,.data-tabs button:disabled,.eye-btn:disabled,.operation-grid button:disabled,.scan-actions button:disabled,.directory-path button:disabled{opacity:.45;cursor:not-allowed}
.preview-fullscreen .preview-panel { position:fixed;inset:48px 48px 48px 328px;z-index:40;box-shadow:0 0 0 9999px rgba(2,8,16,.85); }.preview-fullscreen .report-render,.preview-fullscreen .report-paper { width:520px; }.preview-fullscreen .report-paper { min-height:700px; }.preview-fullscreen .report-paper h3 { margin-top:70px;font-size:25px; }.preview-fullscreen .report-paper dl { margin-top:45px;font-size:12px;gap:14px; }
@media(max-width:1500px){.report-page{min-width:1120px}.filters-grid{gap:8px}.top-row{grid-template-columns:.85fr 1.75fr}.bottom-row{grid-template-columns:1.05fr .78fr .7fr .9fr}.operation-grid button{font-size:11px}}
@media(max-height:800px){.report-page{grid-template-rows:42px 164px minmax(220px,1.4fr) minmax(160px,1fr);gap:7px;overflow:hidden}.directory-panel{grid-template-rows:24px 42px minmax(0,1fr) 20px}.filters-grid{grid-template-rows:repeat(2,48px);gap:7px}.scan-actions{padding:8px 0;gap:7px}}
</style>
