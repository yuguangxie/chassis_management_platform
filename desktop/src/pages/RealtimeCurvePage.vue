<template>
  <section class="curve-page">
    <header class="page-title">
      <div class="title-left">
        <div class="title-icon"><LineChart :size="22" /></div>
        <div>
          <h1>报文信号曲线</h1>
          <p>实时与历史信号曲线、回放与快照</p>
        </div>
      </div>
      <div class="title-actions">
        <span v-if="signals.offline || signals.curveTimeseries.mock || signals.curveTimeseries.quality !== 'good'" class="mock-badge">{{ signals.offline ? '后端离线，当前使用 Mock 曲线数据' : signals.curveTimeseries.mock ? '显式 Mock 曲线数据' : `数据质量：${signals.curveTimeseries.quality || 'unavailable'}` }}</span>
        <button class="small-btn ghost" @click="loadHistory"><Database :size="15" />加载历史会话</button>
        <button class="small-btn primary" @click="addSignal"><Plus :size="15" />添加信号</button>
      </div>
    </header>

    <section class="curve-toolbar">
      <div class="group-tabs">
        <button
          v-for="group in signals.curveConfig.groups"
          :key="group.key"
          :class="{ active: activeGroup === group.key }"
          @click="activeGroup = group.key"
        >
          {{ group.label }}
        </button>
      </div>
      <label class="select-field">
        <span>时间窗口</span>
        <select v-model="timeWindow">
          <option>30秒</option>
          <option>1分钟</option>
          <option>5分钟</option>
          <option>10分钟</option>
          <option>历史</option>
        </select>
      </label>
      <label class="select-field">
        <span>采样频率</span>
        <select v-model="sampleRate">
          <option>10 Hz</option>
          <option>20 Hz</option>
          <option>50 Hz</option>
          <option>100 Hz</option>
          <option>原始</option>
        </select>
      </label>
      <label class="select-field">
        <span>降采样方式</span>
        <select v-model="downsample">
          <option>平均值</option>
          <option>最大值</option>
          <option>最小值</option>
          <option>最后值</option>
          <option>LTTB</option>
        </select>
      </label>
      <label class="select-field compact">
        <span>播放速度</span>
        <select v-model="playbackSpeed">
          <option>0.5x</option>
          <option>1.0x</option>
          <option>2.0x</option>
          <option>5.0x</option>
        </select>
      </label>
      <div class="tool-actions">
        <button class="small-btn ghost" @click="pauseCurve"><Pause :size="15" />暂停曲线</button>
        <button class="small-btn success" @click="resumeCurve"><Play :size="15" />继续</button>
        <button class="small-btn ghost" @click="resetZoom"><RotateCcw :size="15" />缩放复位</button>
        <button class="small-btn ghost" @click="exportCsv"><Download :size="15" />导出CSV</button>
        <button class="small-btn primary" @click="saveSnapshot"><Camera :size="15" />保存快照</button>
      </div>
    </section>

    <main class="curve-main">
      <aside class="signal-panel">
        <div class="panel-head">
          <h2>信号列表（{{ selectedNames.length }}/256）</h2>
          <button title="信号列表设置"><Settings :size="16" /></button>
        </div>
        <label class="search-box">
          <Search :size="15" />
          <input v-model="searchKeyword" placeholder="搜索信号名称" />
        </label>
        <div class="signal-table-scroll">
          <table class="signal-table">
            <thead>
              <tr>
                <th></th>
                <th>信号</th>
                <th>CAN ID</th>
                <th>颜色</th>
                <th>单位</th>
                <th>当前值</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="signal in filteredSignals" :key="signal.name">
                <td>
                  <label class="check-wrap">
                    <input type="checkbox" :checked="selectedNames.includes(signal.name)" @change="toggleSignal(signal.name)" />
                    <span></span>
                  </label>
                </td>
                <td class="signal-name">{{ signal.name }}</td>
                <td class="mono">{{ signal.can_id }}</td>
                <td><i class="color-swatch" :style="{ background: signal.color }"></i></td>
                <td>{{ signal.unit }}</td>
                <td class="value-cell">{{ signal.current_value }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="signal-foot">已选择 {{ selectedNames.length }} 个信号</div>
      </aside>

      <section class="chart-grid">
        <article class="chart-card">
          <ChartTitle index="1" title="目标速度 vs 车辆速度" />
          <RealtimeLineChart :key="chartKey" :option="speedVehicleOption" height="100%" />
        </article>
        <article class="chart-card">
          <ChartTitle index="2" title="目标速度 vs 四轮轮速" />
          <RealtimeLineChart :key="chartKey + 1" :option="wheelSpeedOption" height="100%" />
        </article>
        <article class="chart-card steering-card">
          <ChartTitle index="3" title="转向角命令 vs 反馈" />
          <div class="steering-split">
            <RealtimeLineChart :key="chartKey + 2" :option="frontSteeringOption" height="100%" />
            <RealtimeLineChart :key="chartKey + 3" :option="rearSteeringOption" height="100%" />
          </div>
        </article>
        <article class="chart-card">
          <ChartTitle index="4" title="BMS 总压 / 电流 / SOC" />
          <RealtimeLineChart :key="chartKey + 4" :option="bmsOption" height="100%" />
        </article>
        <article class="chart-card">
          <ChartTitle index="5" title="电机转速 / 相电流" />
          <RealtimeLineChart :key="chartKey + 5" :option="motorOption" height="100%" />
        </article>
        <article class="chart-card">
          <ChartTitle index="6" title="告警等级时间线" />
          <RealtimeLineChart :key="chartKey + 6" :option="alarmOption" height="100%" />
        </article>
      </section>
    </main>

    <footer class="replay-panel">
      <section class="replay-card settings-card">
        <h2>历史回放设置</h2>
        <label><span>会话</span><select v-model="sessionId"><option>EOL-20260401-0001</option></select></label>
        <label><span>数据源</span><select v-model="dataSource"><option>本地存储</option></select></label>
        <label><span>时区</span><select v-model="timezone"><option>UTC+08:00</option></select></label>
      </section>

      <section class="replay-card playback-card">
        <div class="range-grid">
          <span>开始时间</span><strong>{{ signals.replay.start_time }}</strong>
          <span>结束时间</span><strong>{{ signals.replay.end_time }}</strong>
          <span>时长</span><strong>{{ signals.replay.duration }}</strong>
        </div>
        <div class="playback-controls">
          <button title="跳到开始" @click="seekReplay('start')"><SkipBack :size="16" /></button>
          <button title="后退" @click="seekReplay('back')"><StepBack :size="16" /></button>
          <button class="play-round" title="播放/暂停" @click="togglePlayback"><Play :size="20" /></button>
          <button title="前进" @click="seekReplay('forward')"><StepForward :size="16" /></button>
          <button title="跳到末尾" @click="seekReplay('end')"><SkipForward :size="16" /></button>
        </div>
        <div class="progress-row">
          <span>{{ signals.replay.current }} / {{ signals.replay.duration }}</span>
          <div class="progress-track"><i :style="{ width: `${signals.replay.progress_percent}%` }"></i></div>
        </div>
      </section>

      <section class="replay-card fault-card">
        <h2><AlertTriangle :size="16" />跳转到故障</h2>
        <label>
          <span>故障事件</span>
          <select v-model="selectedFault">
            <option value="">选择故障事件</option>
            <option v-for="event in signals.faultEvents" :key="event.id" :value="event.id">{{ event.label }}</option>
          </select>
        </label>
        <div class="fault-bottom">
          <span>事件时间：{{ faultTime }}</span>
          <button class="small-btn warning" @click="jumpFault">跳转</button>
        </div>
      </section>
    </footer>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </section>
</template>

<script setup lang="ts">
import {
  AlertTriangle,
  Camera,
  Database,
  Download,
  LineChart,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Search,
  Settings,
  SkipBack,
  SkipForward,
  StepBack,
  StepForward,
} from 'lucide-vue-next'
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { CurveChart, CurveSeries } from '../api/types'
import { apiDownload, apiPost, apiPut, formatApiError } from '../api/http'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import { useSignalsStore } from '../stores/signals'

type ActionResponse = { ok?: boolean; message?: string; details?: Record<string, unknown> }

const ChartTitle = defineComponent({
  props: { index: { type: String, required: true }, title: { type: String, required: true } },
  setup(props) {
    return () => h('div', { class: 'chart-title' }, [
      h('span', props.index),
      h('strong', props.title),
    ])
  },
})

const signals = useSignalsStore()
const route = useRoute()
const activeGroup = ref('speed')
const routeHistory = route.query.mode === 'history' && typeof route.query.session_id === 'string'
const timeWindow = ref(routeHistory ? '历史' : '5分钟')
const sampleRate = ref('100 Hz')
const downsample = ref('平均值')
const playbackSpeed = ref('1.0x')
const searchKeyword = ref('')
const selectedNames = ref<string[]>([])
const paused = ref(false)
const chartKey = ref(0)
const sessionId = ref(typeof route.query.session_id === 'string' ? route.query.session_id : 'EOL-20260401-0001')
const dataSource = ref('本地存储')
const timezone = ref('UTC+08:00')
const selectedFault = ref('')
const toast = ref('')
let toastTimer: number | undefined
let pollTimer: number | undefined
let replayTimer: number | undefined

const filteredSignals = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  if (!keyword) return signals.curveConfig.signals
  return signals.curveConfig.signals.filter((item) => item.name.toLowerCase().includes(keyword) || item.can_id.toLowerCase().includes(keyword))
})

const faultTime = computed(() => signals.faultEvents.find((event) => event.id === selectedFault.value)?.time || '--')

const speedVehicleOption = computed(() => makeLineOption(signals.curveTimeseries.charts.speed_vs_vehicle, 'km/h', { min: 0, max: 50 }))
const wheelSpeedOption = computed(() => makeLineOption(signals.curveTimeseries.charts.speed_vs_wheels, 'km/h', { min: 0, max: 50 }))
const frontSteeringOption = computed(() => makeLineOption(filterChart(signals.curveTimeseries.charts.steering, ['Front_Steer_Cmd', 'Front_Steer_Fdbk']), '前转角 deg', { min: -45, max: 45 }, '前转角'))
const rearSteeringOption = computed(() => makeLineOption(filterChart(signals.curveTimeseries.charts.steering, ['Rear_Steer_Cmd', 'Rear_Steer_Fdbk']), '后转角 deg', { min: -45, max: 45 }, '后转角'))
const bmsOption = computed(() => makeDualAxisOption(signals.curveTimeseries.charts.bms, ['V / A', 'SOC %'], [{ min: -40, max: 640 }, { min: 0, max: 100 }]))
const motorOption = computed(() => makeDualAxisOption(signals.curveTimeseries.charts.motor, ['rpm', '相电流 A'], [{ min: 0, max: 1800 }, { min: 0, max: 50 }]))
const alarmOption = computed(() => makeAlarmOption(signals.curveTimeseries.charts.alarm_timeline))

onMounted(async () => {
  await Promise.all([signals.loadCurveConfig(), signals.loadCurveTimeseries(makeQuery()), signals.loadReplay(sessionId.value), signals.loadFaultEvents(sessionId.value)])
  selectedNames.value = signals.curveConfig.signals.filter((item) => item.selected).map((item) => item.name)
  signals.bindWebSocket()
  pollTimer = window.setInterval(() => {
    if (!paused.value) void signals.loadCurveTimeseries(makeQuery())
  }, 2500)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  if (replayTimer) window.clearInterval(replayTimer)
  if (toastTimer) window.clearTimeout(toastTimer)
  signals.setCurvePaused(false)
})

watch([activeGroup, timeWindow, sampleRate, downsample], () => {
  if (!paused.value) void signals.loadCurveTimeseries(makeQuery())
})

watch(() => signals.curveConfig.signals, (items) => {
  if (!selectedNames.value.length) selectedNames.value = items.filter((item) => item.selected).map((item) => item.name)
})

function makeQuery() {
  const params = new URLSearchParams({
    group: activeGroup.value,
    window: timeWindow.value,
    sample_rate: sampleRate.value,
    downsample: downsample.value,
    mode: timeWindow.value === '历史' ? 'history' : 'live',
  })
  params.set('signals', selectedNames.value.join(','))
  if (timeWindow.value === '历史') params.set('session_id', sessionId.value)
  return `?${params.toString()}`
}

function selectedSeries(chart: CurveChart) {
  if (chart === signals.curveTimeseries.charts.alarm_timeline) return chart.series
  const active = new Set(selectedNames.value)
  const filtered = chart.series.filter((series) => active.has(series.name))
  return filtered.length ? filtered : chart.series
}

function filterChart(chart: CurveChart, names: string[]): CurveChart {
  return { x_axis: chart.x_axis, series: chart.series.filter((series) => names.includes(series.name)) }
}

function makeLineOption(chart: CurveChart, yName: string, range: { min: number; max: number }, subtitle = '') {
  const series = selectedSeries(chart)
  return baseOption(chart.x_axis, series.map((item) => ({
    name: item.name,
    type: 'line',
    smooth: true,
    symbol: 'none',
    data: item.data,
    itemStyle: { color: item.color },
    lineStyle: { color: item.color, width: 2 },
  })), [{ name: yName, type: 'value', min: range.min, max: range.max }], subtitle)
}

function makeDualAxisOption(chart: CurveChart, axisNames: string[], ranges: Array<{ min: number; max: number }>) {
  const series = selectedSeries(chart)
  return baseOption(chart.x_axis, series.map((item) => ({
    name: item.name,
    type: 'line',
    smooth: true,
    symbol: 'none',
    yAxisIndex: item.y_axis || 0,
    data: item.data,
    itemStyle: { color: item.color },
    lineStyle: { color: item.color, width: 2 },
  })), axisNames.map((name, index) => ({ name, type: 'value', min: ranges[index].min, max: ranges[index].max })))
}

function makeAlarmOption(chart: CurveChart) {
  return baseOption(chart.x_axis, chart.series.map((item) => ({
    name: item.name,
    type: 'line',
    step: 'end',
    symbol: 'none',
    data: item.data,
    itemStyle: { color: item.color },
    lineStyle: { color: item.color, width: 6 },
    connectNulls: false,
  })), [{ type: 'value', min: 0, max: 4, interval: 1, axisLabel: { formatter: alarmLabel } }])
}

function baseOption(xAxis: string[], series: unknown[], yAxis: unknown[], subtitle = '') {
  return {
    backgroundColor: 'transparent',
    color: (series as CurveSeries[]).map((item) => item.color).filter(Boolean),
    tooltip: { trigger: 'axis', backgroundColor: '#10243D', borderColor: '#2B4D78', textStyle: { color: '#EAF2FF' } },
    legend: { top: subtitle ? 18 : 2, right: 8, itemWidth: 14, itemHeight: 8, textStyle: { color: '#AFC2DA', fontSize: 11 } },
    grid: { left: 44, right: yAxis.length > 1 ? 46 : 18, top: subtitle ? 44 : 34, bottom: 24, containLabel: true },
    xAxis: { type: 'category', data: xAxis, boundaryGap: false, axisLine: { lineStyle: { color: '#315A83' } }, axisLabel: { color: '#7F96B4', fontSize: 10 }, splitLine: { show: true, lineStyle: { color: '#143050' } } },
    yAxis: (yAxis as Array<Record<string, unknown>>).map((axis, index) => ({
      ...axis,
      position: index === 1 ? 'right' : 'left',
      nameTextStyle: { color: '#7F96B4', fontSize: 10 },
      axisLabel: { color: '#7F96B4', fontSize: 10, ...(axis.axisLabel as Record<string, unknown> || {}) },
      axisLine: { lineStyle: { color: '#315A83' } },
      splitLine: { show: index === 0, lineStyle: { color: '#143050' } },
    })),
    graphic: subtitle ? [{ type: 'text', left: 8, top: 4, style: { text: subtitle, fill: '#8FB6E8', fontSize: 11 } }] : [],
    series,
  }
}

function alarmLabel(value: number) {
  return ['正常', '提示', '次要', '主要', '严重'][value] || ''
}

function toggleSignal(name: string) {
  selectedNames.value = selectedNames.value.includes(name) ? selectedNames.value.filter((item) => item !== name) : [...selectedNames.value, name]
  void apiPut<ActionResponse>('/signals/curve-selection', { signals: selectedNames.value }).catch((error) => showToast(`保存曲线选择：${formatApiError(error)}`))
}

function pauseCurve() {
  paused.value = true
  signals.setCurvePaused(true)
  showToast('暂停曲线：曲线刷新已暂停')
}

function resumeCurve() {
  paused.value = false
  signals.setCurvePaused(false)
  void signals.loadCurveTimeseries(makeQuery())
  showToast('继续：曲线刷新已恢复')
}

function resetZoom() {
  chartKey.value += 10
  showToast('缩放复位：图表视图已复位')
}

async function loadHistory() {
  await Promise.all([signals.loadReplay(sessionId.value), signals.loadFaultEvents(sessionId.value)])
  showToast('加载历史会话：已加载真实回放元数据')
}

function addSignal() {
  void runAction('保存关注信号', () => apiPost<ActionResponse>('/signals/watchlist', { signals: selectedNames.value }))
}

function exportCsv() {
  void runAction('导出CSV', () => apiPost<ActionResponse>('/signals/export-csv', { signals: selectedNames.value }))
}

function saveSnapshot() {
  void runAction('保存快照', () => apiPost<ActionResponse>('/signals/snapshot', { page: 'realtime-curve' }))
}

async function seekReplay(action: string) {
  const current = signals.replay.progress_percent || 0
  let progress = action === 'start' ? 0 : action === 'end' ? 100 : action === 'back' ? current - 5 : action === 'forward' ? current + 5 : current
  const fault = signals.faultEvents.find((item) => item.id === action)
  if (fault) {
    const start = Date.parse(signals.replay.start_time)
    const end = Date.parse(signals.replay.end_time)
    const at = Date.parse(fault.time)
    if (Number.isFinite(start) && Number.isFinite(end) && end > start && Number.isFinite(at)) progress = (at - start) / (end - start) * 100
  }
  try {
    signals.replay = await apiPost<typeof signals.replay>(
      `/test-sessions/${encodeURIComponent(sessionId.value)}/replay/seek`,
      { progress_percent: Math.max(0, Math.min(100, progress)) },
    )
  } catch (error) {
    showToast(`回放跳转：${formatApiError(error)}`)
  }
}

function togglePlayback() {
  if (replayTimer) {
    window.clearInterval(replayTimer)
    replayTimer = undefined
    showToast('历史回放已暂停')
    return
  }
  const speed = Number.parseFloat(playbackSpeed.value) || 1
  replayTimer = window.setInterval(() => {
    if (signals.replay.progress_percent >= 100) {
      if (replayTimer) window.clearInterval(replayTimer)
      replayTimer = undefined
      return
    }
    void seekReplay('forward')
  }, Math.max(250, 1000 / speed))
  showToast('历史回放已开始')
}

function jumpFault() {
  if (!selectedFault.value) {
    showToast('跳转到故障：请选择故障事件')
    return
  }
  void seekReplay(selectedFault.value)
}

async function runAction(label: string, fn: () => Promise<ActionResponse>) {
  try {
    const result = await fn()
    const url = typeof result.details?.download_url === 'string' ? result.details.download_url : ''
    if (url) await apiDownload(url, typeof result.details?.file_name === 'string' ? result.details.file_name : undefined)
    showToast(`${label}：${result.message || '完成'}`)
  } catch (error) {
    showToast(`${label}：${formatApiError(error)}`)
  }
}

function showToast(message: string) {
  toast.value = message
  if (toastTimer) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    if (toast.value === message) toast.value = ''
  }, 2600)
}
</script>

<style scoped>
.curve-page {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-rows: 52px 72px minmax(0, 1fr) 160px;
  gap: 10px;
  color: #EAF2FF;
}

.page-title,
.curve-toolbar,
.signal-panel,
.chart-card,
.replay-card {
  border: 1px solid #1E3A5F;
  background: linear-gradient(180deg, rgba(16, 36, 61, 0.98), rgba(10, 24, 43, 0.98));
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
}

.page-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  border-radius: 8px;
}

.title-left,
.title-actions,
.tool-actions,
.group-tabs,
.playback-controls,
.fault-bottom {
  display: flex;
  align-items: center;
}

.title-left { gap: 10px; min-width: 0; }
.title-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: #A8D0FF;
  background: linear-gradient(135deg, rgba(47, 128, 255, 0.3), rgba(34, 211, 238, 0.14));
  border: 1px solid rgba(47, 128, 255, 0.46);
}

.page-title h1 {
  margin: 0;
  font-size: 21px;
  line-height: 24px;
  font-weight: 700;
}

.page-title p {
  margin: 3px 0 0;
  color: #8CA6C5;
  font-size: 12px;
}

.title-actions { gap: 8px; }

.mock-badge {
  height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(246, 195, 67, 0.42);
  color: #F6C343;
  background: rgba(246, 195, 67, 0.1);
  font-size: 12px;
}

.curve-toolbar {
  display: grid;
  grid-template-columns: minmax(360px, 1.25fr) repeat(4, minmax(112px, 0.32fr)) minmax(460px, 1.35fr);
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  min-width: 0;
}

.group-tabs {
  height: 38px;
  min-width: 0;
  padding: 3px;
  gap: 4px;
  border: 1px solid #1E3A5F;
  border-radius: 7px;
  background: #07172A;
}

.group-tabs button {
  flex: 1;
  min-width: 0;
  height: 30px;
  border: 0;
  border-radius: 5px;
  color: #9DB3CF;
  background: transparent;
  font-size: 12px;
  cursor: pointer;
}

.group-tabs button.active {
  color: #FFFFFF;
  background: linear-gradient(135deg, #2F80FF, #1764D8);
  box-shadow: 0 0 14px rgba(47, 128, 255, 0.35);
}

.select-field {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.select-field span {
  color: #7F96B4;
  font-size: 11px;
}

select,
input {
  width: 100%;
  height: 32px;
  min-width: 0;
  border: 1px solid #24466F;
  border-radius: 6px;
  background: #07172A;
  color: #DDEBFF;
  padding: 0 10px;
  outline: none;
}

select:focus,
input:focus {
  border-color: #2F80FF;
  box-shadow: 0 0 0 2px rgba(47, 128, 255, 0.14);
}

.tool-actions {
  justify-content: flex-end;
  gap: 7px;
  min-width: 0;
}

.small-btn {
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid #2B5C90;
  border-radius: 6px;
  background: rgba(47, 128, 255, 0.12);
  color: #CFE2FF;
  padding: 0 10px;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}

.small-btn.primary {
  border-color: #2F80FF;
  color: #FFFFFF;
  background: linear-gradient(135deg, #2F80FF, #1764D8);
}

.small-btn.success {
  border-color: rgba(33, 197, 93, 0.6);
  color: #BFF7D0;
  background: rgba(33, 197, 93, 0.12);
}

.small-btn.warning {
  border-color: rgba(246, 195, 67, 0.65);
  color: #FFE5A0;
  background: rgba(246, 195, 67, 0.14);
}

.small-btn.ghost:hover,
.small-btn.success:hover,
.small-btn.warning:hover {
  transform: translateY(-1px);
  border-color: #2F80FF;
}

.curve-main {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 10px;
  min-height: 0;
  overflow: hidden;
}

.signal-panel {
  min-height: 0;
  border-radius: 8px;
  padding: 10px;
  display: grid;
  grid-template-rows: 28px 36px minmax(0, 1fr) 28px;
  gap: 8px;
  overflow: hidden;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-head h2,
.replay-card h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
}

.panel-head button {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border: 1px solid #24466F;
  border-radius: 6px;
  background: #07172A;
  color: #8FB6E8;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 9px;
  border: 1px solid #24466F;
  border-radius: 6px;
  background: #07172A;
  color: #7F96B4;
}

.search-box input {
  height: 30px;
  border: 0;
  padding: 0;
  background: transparent;
}

.signal-table-scroll {
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  border: 1px solid #1B3557;
  border-radius: 6px;
}

.signal-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 11px;
}

.signal-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  box-sizing: border-box;
  height: 28px;
  color: #9EB6D2;
  font-weight: 600;
  background: #0B2038;
  border-bottom: 1px solid #1E3A5F;
}

.signal-table td {
  box-sizing: border-box;
  height: 31px;
  padding: 0 5px;
  color: #C8D9ED;
  border-bottom: 1px solid rgba(30, 58, 95, 0.65);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.signal-table th:nth-child(1),
.signal-table td:nth-child(1) { width: 26px; text-align: center; }
.signal-table th:nth-child(2),
.signal-table td:nth-child(2) { width: 96px; }
.signal-table th:nth-child(3),
.signal-table td:nth-child(3) { width: 40px; }
.signal-table th:nth-child(4),
.signal-table td:nth-child(4) { width: 28px; text-align: center; }
.signal-table th:nth-child(5),
.signal-table td:nth-child(5) { width: 34px; }
.signal-table th:nth-child(6),
.signal-table td:nth-child(6) { width: 48px; }

.signal-name { color: #E8F2FF; }
.mono {
  font-family: Consolas, 'JetBrains Mono', monospace;
  color: #91C9FF;
}
.value-cell { color: #21C55D; font-weight: 700; }

.check-wrap {
  display: inline-grid;
  place-items: center;
  width: 15px;
  height: 15px;
  cursor: pointer;
}

.check-wrap input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.check-wrap span {
  width: 14px;
  height: 14px;
  border: 1px solid #315A83;
  border-radius: 3px;
  background: #07172A;
}

.check-wrap input:checked + span {
  border-color: #2F80FF;
  background: linear-gradient(135deg, #2F80FF, #1764D8);
  box-shadow: inset 0 0 0 3px #07172A;
}

.color-swatch {
  display: inline-block;
  width: 16px;
  height: 8px;
  border-radius: 99px;
  box-shadow: 0 0 8px currentColor;
}

.signal-foot {
  display: flex;
  align-items: center;
  color: #8CA6C5;
  font-size: 12px;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(3, minmax(0, 1fr));
  gap: 10px;
  min-height: 0;
  overflow: hidden;
}

.chart-card {
  display: grid;
  grid-template-rows: 28px minmax(0, 1fr);
  min-height: 0;
  overflow: hidden;
  border-radius: 8px;
  padding: 8px 8px 4px;
}

.chart-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #EAF2FF;
}

.chart-title span {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 5px;
  color: #FFFFFF;
  background: rgba(47, 128, 255, 0.85);
  font-size: 11px;
  font-weight: 700;
}

.chart-title strong {
  font-size: 13px;
}

.steering-split {
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.replay-panel {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr) 340px;
  gap: 10px;
  min-height: 0;
  overflow: hidden;
}

.replay-card {
  min-height: 0;
  border-radius: 8px;
  padding: 10px;
  overflow: hidden;
}

.settings-card,
.fault-card {
  display: grid;
  grid-template-rows: 24px repeat(3, 1fr);
  gap: 7px;
}

.settings-card label,
.fault-card label {
  display: grid;
  grid-template-columns: 72px 1fr;
  align-items: center;
  gap: 8px;
  color: #8CA6C5;
  font-size: 12px;
}

.playback-card {
  display: grid;
  grid-template-rows: 48px 48px 42px;
  gap: 7px;
}

.range-grid {
  display: grid;
  grid-template-columns: 64px 1fr 64px 1fr 42px 90px;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 12px;
}

.range-grid span,
.progress-row span,
.fault-bottom span {
  color: #8CA6C5;
}

.range-grid strong {
  min-width: 0;
  color: #DDEBFF;
  font-family: Consolas, 'JetBrains Mono', monospace;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.playback-controls {
  justify-content: center;
  gap: 10px;
}

.playback-controls button {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border: 1px solid #2B5C90;
  border-radius: 7px;
  background: #07172A;
  color: #CFE2FF;
  cursor: pointer;
}

.playback-controls .play-round {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border-color: rgba(33, 197, 93, 0.7);
  color: #FFFFFF;
  background: linear-gradient(135deg, #21C55D, #149447);
}

.progress-row {
  display: grid;
  grid-template-columns: 140px 1fr;
  align-items: center;
  gap: 12px;
  font-size: 12px;
}

.progress-track {
  height: 9px;
  border: 1px solid #1E3A5F;
  border-radius: 99px;
  background: #07172A;
  overflow: hidden;
}

.progress-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #21C55D, #2F80FF);
}

.fault-card h2 {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #F6C343;
}

.fault-bottom {
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
}

.toast {
  position: absolute;
  right: 16px;
  bottom: 176px;
  z-index: 5;
  max-width: 520px;
  padding: 10px 14px;
  border: 1px solid #2F80FF;
  border-radius: 8px;
  background: rgba(10, 24, 43, 0.96);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35);
  color: #DDEBFF;
  font-size: 13px;
}

.signal-table-scroll::-webkit-scrollbar { width: 8px; height: 8px; }
.signal-table-scroll::-webkit-scrollbar-track { background: #07172A; }
.signal-table-scroll::-webkit-scrollbar-thumb { background: #24466F; border-radius: 99px; }

@media (max-width: 1500px) {
  .curve-page {
    grid-template-rows: 52px 104px minmax(0, 1fr) 160px;
  }
  .curve-toolbar {
    grid-template-columns: minmax(360px, 1fr) repeat(4, minmax(110px, 0.3fr));
  }
  .tool-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}
</style>
