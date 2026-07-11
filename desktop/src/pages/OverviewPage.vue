<template>
  <div class="overview-page">
    <section class="page-title">
      <div class="title-left">
        <div class="title-icon"><LayoutDashboard :size="20" /></div>
        <div>
          <h1>总览工作台</h1>
          <p>生产下线全局状态与快捷入口</p>
        </div>
      </div>
      <div class="title-actions">
        <span v-if="offline" class="offline-pill">后端离线 · Mock展示</span>
        <span v-else-if="summary.mock || summary.quality !== 'good'" class="offline-pill loading">{{ summary.mock ? '显式 Mock 数据' : `数据质量：${summary.quality || 'unavailable'}` }}</span>
        <span v-else-if="loading" class="offline-pill loading">正在刷新</span>
        <button class="layout-btn" type="button"><SlidersHorizontal :size="16" />自定义布局</button>
      </div>
    </section>

    <section class="kpi-row" aria-label="overview kpi">
      <div v-for="item in kpiCards" :key="item.title" :class="['kpi-card', item.tone]">
        <div class="kpi-icon"><component :is="item.icon" :size="22" /></div>
        <div class="kpi-copy">
          <span>{{ item.title }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </section>

    <section class="status-row">
      <article class="panel can-panel">
        <header class="panel-head">
          <h2>CAN状态</h2>
        </header>
        <div class="can-columns">
          <div v-for="name in canNames" :key="name" class="can-column">
            <div class="can-title">
              <strong>{{ name }}</strong>
              <span class="status-dot"><i :class="summary.channels[name].online ? 'online' : 'offline'"></i>{{ summary.channels[name].online ? 'online' : 'offline' }}</span>
            </div>
            <dl>
              <div><dt>本地：</dt><dd>{{ summary.channels[name].local }}</dd></div>
              <div><dt>设备：</dt><dd>{{ summary.channels[name].device }}</dd></div>
              <div><dt>协议：</dt><dd>{{ summary.channels[name].protocol }}</dd></div>
              <div><dt>帧率：</dt><dd>{{ summary.channels[name].fps }} fps</dd></div>
              <div><dt>错误帧：</dt><dd>{{ summary.channels[name].error_frames }}</dd></div>
              <div><dt>最后报文：</dt><dd>{{ summary.channels[name].last_frame_ms }} ms</dd></div>
            </dl>
          </div>
        </div>
      </article>

      <article class="panel vehicle-panel">
        <header class="panel-head">
          <h2>当前车辆 / 当前检测</h2>
        </header>
        <div class="vehicle-kv">
          <span>底盘编号：</span><strong>{{ summary.current_vehicle.chassis_no }}</strong>
          <span>VIN：</span><strong>{{ summary.current_vehicle.vin }}</strong>
          <span>序列号：</span><strong>{{ summary.current_vehicle.serial_no }}</strong>
          <span>检测方案：</span><strong>{{ summary.current_vehicle.test_plan }}</strong>
          <span>操作员：</span><strong>{{ summary.current_vehicle.operator }}</strong>
          <span>当前步骤：</span><strong class="blue">{{ summary.current_vehicle.current_step }}</strong>
          <span>会话：</span><strong>{{ summary.current_vehicle.session_id }}</strong>
        </div>
      </article>

      <article class="panel alarm-panel">
        <header class="panel-head alarm-title">
          <TriangleAlert :size="18" />
          <h2>告警摘要</h2>
        </header>
        <div class="alarm-metrics">
          <div>
            <span>最高告警(0x77)</span>
            <strong>{{ summary.alarm_summary.max_alarm_level }} {{ summary.alarm_summary.max_alarm_label }}</strong>
          </div>
          <div>
            <span>BMS保护状态</span>
            <strong>{{ summary.alarm_summary.bms_protect_status }}</strong>
          </div>
          <div>
            <span>急停状态</span>
            <strong><i class="red-ring"></i>{{ summary.alarm_summary.emergency_stop ? '已触发' : '未触发' }}</strong>
          </div>
        </div>
        <div class="protect-grid">
          <span v-for="item in summary.alarm_summary.protection_items" :key="item.name" class="protect-chip">
            {{ item.name }} <b>{{ item.status }}</b>
          </span>
        </div>
      </article>
    </section>

    <section class="shortcut-row" aria-label="quick actions">
      <button v-for="item in shortcuts" :key="item.title" :class="['shortcut-card', item.tone]" type="button" @click="item.action">
        <span class="shortcut-icon"><component :is="item.icon" :size="22" /></span>
        <span class="shortcut-text">
          <strong>{{ item.title }}</strong>
          <small>{{ item.desc }}</small>
        </span>
      </button>
    </section>

    <section class="chart-row">
      <article class="panel chart-panel result-chart">
        <header class="panel-head compact-head">
          <h2>今日结果统计</h2>
        </header>
        <div class="donut-layout">
          <DonutChart :option="donutOption" />
          <div class="result-legend">
            <div v-for="item in resultItems" :key="item.name">
              <i :style="{ backgroundColor: resultColor(item.name) }"></i>
              <span>{{ item.name }}</span>
              <strong>{{ item.value }} ({{ item.percent.toFixed(1) }}%)</strong>
            </div>
          </div>
        </div>
      </article>

      <article class="panel chart-panel">
        <header class="panel-head compact-head">
          <h2>小时产能（台）</h2>
          <span>今日产量：{{ summary.charts.today_result.total }} 台</span>
        </header>
        <BarChart :option="barOption" />
      </article>

      <article class="panel chart-panel">
        <header class="panel-head compact-head">
          <h2>帧率趋势（最近30分钟）</h2>
          <span>单位 fps</span>
        </header>
        <RealtimeLineChart :option="lineOption" />
      </article>
    </section>

    <section class="panel table-panel">
      <header class="panel-head table-head">
        <h2>最近会话</h2>
        <button type="button" @click="router.push('/history')">查看更多 &gt;</button>
      </header>
      <div class="session-table-wrap">
        <table class="session-table">
          <thead>
            <tr>
              <th>Session ID</th>
              <th>底盘编号</th>
              <th>VIN</th>
              <th>开始时间</th>
              <th>结束时间</th>
              <th>结果</th>
              <th>操作员</th>
              <th>报告</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in summary.recent_sessions.slice(0, 4)" :key="row.session_id">
              <td class="mono">{{ row.session_id }}</td>
              <td>{{ row.chassis_no }}</td>
              <td class="mono">{{ row.vin }}</td>
              <td>{{ row.started_at }}</td>
              <td>{{ row.ended_at }}</td>
              <td><span :class="['result-pill', row.result.toLowerCase()]">{{ row.result }}</span></td>
              <td>{{ row.operator }}</td>
              <td>
                <button v-if="row.report" class="report-btn" type="button" :title="row.report"><FileText :size="15" /></button>
                <span v-else class="muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="actionMessage" :class="['action-message', actionTone]">{{ actionMessage }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Box,
  CircleCheck,
  ClipboardList,
  Clock,
  FileText,
  FolderOpen,
  LayoutDashboard,
  MonitorDot,
  Play,
  ShieldAlert,
  ShieldX,
  SlidersHorizontal,
  TriangleAlert,
} from 'lucide-vue-next'
import BarChart from '../components/charts/BarChart.vue'
import DonutChart from '../components/charts/DonutChart.vue'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import { apiGet, apiPost, formatApiError, isNetworkError } from '../api/http'
import type { OverviewSummary } from '../api/types'
import { fallbackOverviewSummary } from '../mocks/fallbackData'

const router = useRouter()
const summary = ref<OverviewSummary>({ ...structuredClone(fallbackOverviewSummary), data_source: 'frontend-explicit-fallback', mock: true, quality: 'mock' })
const loading = ref(false)
const offline = ref(false)
const actionMessage = ref('')
const actionTone = ref<'ok' | 'warn' | 'bad'>('ok')
let refreshTimer: number | undefined
let messageTimer: number | undefined
const canNames = ['CAN1', 'CAN2'] as const

async function loadSummary() {
  loading.value = true
  try {
    const data = await apiGet<OverviewSummary>('/overview/summary')
    summary.value = data
    offline.value = false
  } catch (error) {
    if (isNetworkError(error)) {
      offline.value = true
      summary.value = { ...structuredClone(fallbackOverviewSummary), data_source: 'frontend-explicit-fallback', mock: true, quality: 'mock' }
    } else {
      offline.value = false
      showMessage(formatApiError(error), 'bad')
    }
  } finally {
    loading.value = false
  }
}

function showMessage(message: string, tone: 'ok' | 'warn' | 'bad' = 'ok') {
  actionMessage.value = message
  actionTone.value = tone
  if (messageTimer) window.clearTimeout(messageTimer)
  messageTimer = window.setTimeout(() => { actionMessage.value = '' }, 2600)
}

async function scanReports() {
  try {
    await apiPost('/reports/scan', {})
    showMessage('报告目录已刷新，可在报告管理中查看。')
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '报告目录刷新失败', 'warn')
  }
}

async function safeStop() {
  try {
    await apiPost('/control/safe-stop', {})
    showMessage('安全停车指令已提交。')
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '安全停车失败', 'bad')
  }
}

const shortcuts = [
  { title: '新建检测', desc: '创建新的下线检测会话', icon: Play, tone: 'primary', action: () => router.push('/auto-test') },
  { title: '继续上次会话', desc: '恢复当前车辆检测流程', icon: ClipboardList, tone: 'primary', action: () => router.push('/auto-test') },
  { title: '打开报告目录', desc: '刷新并查看报告文件', icon: FolderOpen, tone: 'primary', action: scanReports },
  { title: '进入安全停车', desc: '发送安全停车控制', icon: ShieldAlert, tone: 'warning', action: safeStop },
  { title: '进入CAN监控', desc: '查看原始帧与解码信号', icon: MonitorDot, tone: 'primary', action: () => router.push('/can-monitor') },
  { title: '进入手动控制', desc: '受控发送 0x121 指令', icon: SlidersHorizontal, tone: 'primary', action: () => router.push('/manual-control') },
]

const kpiCards = computed(() => [
  { title: '今日检测数', value: String(summary.value.kpi.today_total), icon: ClipboardList, tone: 'blue' },
  { title: 'PASS率', value: `${summary.value.kpi.pass_rate.toFixed(1)}%`, icon: CircleCheck, tone: 'green' },
  { title: 'FAIL数', value: String(summary.value.kpi.fail_count), icon: ShieldX, tone: 'red' },
  { title: '平均检测时长', value: summary.value.kpi.avg_duration, icon: Clock, tone: 'blue' },
  { title: '当前软件版本', value: summary.value.kpi.software_version, icon: Box, tone: 'blue' },
])

const resultItems = computed(() => summary.value.charts.today_result.items)
const chartText = '#AFC2DD'
const gridLine = '#1E3A5F'

function resultColor(name: string) {
  if (name === 'PASS') return '#21C55D'
  if (name === 'FAIL') return '#EF4444'
  if (name === 'RUNNING') return '#F6C343'
  return '#7C8BA3'
}

const donutOption = computed(() => ({
  backgroundColor: 'transparent',
  color: resultItems.value.map((item) => resultColor(item.name)),
  tooltip: { trigger: 'item' },
  graphic: [
    { type: 'text', left: 'center', top: '41%', style: { text: '总计', fill: '#95A8C6', fontSize: 12, textAlign: 'center' } },
    { type: 'text', left: 'center', top: '52%', style: { text: String(summary.value.charts.today_result.total), fill: '#EAF2FF', fontSize: 28, fontWeight: 800, textAlign: 'center' } },
  ],
  series: [{
    type: 'pie',
    radius: ['60%', '78%'],
    center: ['50%', '52%'],
    avoidLabelOverlap: false,
    label: { show: false },
    labelLine: { show: false },
    data: resultItems.value.map((item) => ({ name: item.name, value: item.value })),
  }],
}))

const barOption = computed(() => ({
  backgroundColor: 'transparent',
  grid: { left: 32, right: 12, top: 18, bottom: 28 },
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: summary.value.charts.hourly_output.map((item) => item.hour),
    axisLine: { lineStyle: { color: gridLine } },
    axisTick: { show: false },
    axisLabel: { color: chartText, fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    splitLine: { lineStyle: { color: gridLine, type: 'dashed' } },
    axisLabel: { color: chartText, fontSize: 11 },
  },
  series: [{
    type: 'bar',
    barWidth: 18,
    data: summary.value.charts.hourly_output.map((item) => item.value),
    label: { show: true, position: 'top', color: '#CFE3FF', fontSize: 11 },
    itemStyle: { color: '#2F80FF', borderRadius: [4, 4, 0, 0] },
  }],
}))

const lineOption = computed(() => ({
  backgroundColor: 'transparent',
  legend: { right: 6, top: 0, itemWidth: 14, itemHeight: 8, textStyle: { color: chartText, fontSize: 11 } },
  grid: { left: 40, right: 16, top: 30, bottom: 28 },
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: summary.value.charts.fps_trend.map((item) => item.time),
    boundaryGap: false,
    axisLine: { lineStyle: { color: gridLine } },
    axisTick: { show: false },
    axisLabel: { color: chartText, fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    min: 0,
    max: 1200,
    splitLine: { lineStyle: { color: gridLine, type: 'dashed' } },
    axisLabel: { color: chartText, fontSize: 11 },
  },
  series: [
    { name: 'CAN1', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 3, color: '#21C55D' }, areaStyle: { color: 'rgba(33, 197, 93, .08)' }, data: summary.value.charts.fps_trend.map((item) => item.can1) },
    { name: 'CAN2', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 3, color: '#2F80FF' }, areaStyle: { color: 'rgba(47, 128, 255, .08)' }, data: summary.value.charts.fps_trend.map((item) => item.can2) },
  ],
}))

onMounted(() => {
  void loadSummary()
  refreshTimer = window.setInterval(() => void loadSummary(), 2500)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (messageTimer) window.clearTimeout(messageTimer)
})
</script>

<style scoped>
.overview-page {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: 44px 92px 240px 88px 205px minmax(0, 1fr);
  gap: 12px;
  overflow: hidden;
}

.page-title,
.kpi-card,
.panel,
.shortcut-card {
  border: 1px solid #1E3A5F;
  background: linear-gradient(145deg, rgba(16, 36, 61, .96), rgba(11, 26, 46, .96));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04), 0 10px 28px rgba(0, 0, 0, .12);
}

.page-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-radius: 8px;
  padding: 0 14px;
  min-width: 0;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.title-icon,
.kpi-icon,
.shortcut-icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  background: linear-gradient(145deg, rgba(47, 128, 255, .34), rgba(47, 128, 255, .1));
  border: 1px solid rgba(47, 128, 255, .52);
  color: #A9D1FF;
}

.title-icon {
  width: 30px;
  height: 30px;
  border-radius: 7px;
}

h1,
h2,
p {
  margin: 0;
}

.page-title h1 {
  font-size: 20px;
  line-height: 1.05;
  font-weight: 800;
}

.page-title p {
  margin-top: 3px;
  color: #95A8C6;
  font-size: 12px;
}

.title-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.layout-btn,
.table-head button {
  height: 30px;
  border: 1px solid rgba(47, 128, 255, .46);
  border-radius: 6px;
  background: rgba(47, 128, 255, .12);
  color: #DCEBFF;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 12px;
}

.offline-pill {
  height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border: 1px solid rgba(246, 195, 67, .55);
  border-radius: 999px;
  color: #F6C343;
  background: rgba(246, 195, 67, .08);
  font-size: 12px;
}

.offline-pill.loading {
  border-color: rgba(47, 128, 255, .45);
  color: #9CCBFF;
  background: rgba(47, 128, 255, .08);
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
}

.kpi-card {
  border-radius: 9px;
  padding: 15px 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.kpi-card.green {
  border-color: rgba(33, 197, 93, .5);
  background: linear-gradient(145deg, rgba(17, 48, 46, .96), rgba(12, 31, 48, .96));
}

.kpi-card.red {
  border-color: rgba(239, 68, 68, .45);
  background: linear-gradient(145deg, rgba(54, 25, 34, .94), rgba(15, 30, 51, .96));
}

.kpi-card.green .kpi-icon {
  border-color: rgba(33, 197, 93, .58);
  color: #A5F3C5;
  background: rgba(33, 197, 93, .14);
}

.kpi-card.red .kpi-icon {
  border-color: rgba(239, 68, 68, .58);
  color: #FFB4B4;
  background: rgba(239, 68, 68, .13);
}

.kpi-icon {
  width: 46px;
  height: 46px;
  border-radius: 8px;
}

.kpi-copy {
  min-width: 0;
}

.kpi-copy span {
  display: block;
  color: #95A8C6;
  font-size: 13px;
  margin-bottom: 8px;
}

.kpi-copy strong {
  display: block;
  color: #F1F7FF;
  font-family: 'DIN Alternate', Consolas, sans-serif;
  font-size: 31px;
  line-height: 1;
  white-space: nowrap;
}

.status-row,
.chart-row {
  display: grid;
  gap: 12px;
  min-height: 0;
}

.status-row {
  grid-template-columns: 1.08fr 1fr 1.35fr;
}

.chart-row {
  grid-template-columns: .96fr 1.05fr 1.24fr;
}

.panel {
  border-radius: 9px;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.panel-head {
  height: 44px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(30, 58, 95, .78);
}

.panel-head h2 {
  color: #EEF6FF;
  font-size: 15px;
  font-weight: 800;
}

.panel-head span {
  color: #9CB0CC;
  font-size: 12px;
}

.compact-head {
  height: 36px;
}

.can-columns {
  height: calc(100% - 44px);
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.can-column {
  padding: 15px 15px 12px;
  min-width: 0;
}

.can-column + .can-column {
  border-left: 1px solid rgba(30, 58, 95, .82);
}

.can-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 13px;
}

.can-title strong {
  font-size: 19px;
  letter-spacing: .3px;
}

.status-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #A7B9D5;
  font-size: 12px;
}

.status-dot i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.status-dot .online {
  background: #21C55D;
  box-shadow: 0 0 10px rgba(33, 197, 93, .75);
}

.status-dot .offline {
  background: #EF4444;
  box-shadow: 0 0 10px rgba(239, 68, 68, .75);
}

dl {
  margin: 0;
  display: grid;
  gap: 9px;
}

dl div,
.vehicle-kv {
  min-width: 0;
}

dl div {
  display: flex;
  align-items: center;
}

dt,
dd {
  margin: 0;
  font-size: 13px;
}

dt {
  color: #8FA5C4;
  width: 76px;
  flex: 0 0 auto;
}

dd {
  color: #EAF2FF;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vehicle-kv {
  height: calc(100% - 44px);
  padding: 14px 16px;
  display: grid;
  grid-template-columns: 86px minmax(0, 1fr);
  grid-auto-rows: 24px;
  align-content: start;
  row-gap: 6px;
}

.vehicle-kv span {
  color: #8FA5C4;
  font-size: 13px;
}

.vehicle-kv strong {
  min-width: 0;
  color: #EAF2FF;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.blue {
  color: #63A7FF !important;
}

.alarm-title {
  justify-content: flex-start;
  gap: 9px;
}

.alarm-title svg {
  color: #F6C343;
}

.alarm-metrics {
  height: 66px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 12px 14px 9px;
}

.alarm-metrics div {
  min-width: 0;
  border: 1px solid rgba(30, 58, 95, .82);
  border-radius: 7px;
  background: rgba(7, 17, 31, .38);
  padding: 8px 10px;
}

.alarm-metrics span {
  display: block;
  color: #8FA5C4;
  font-size: 12px;
  margin-bottom: 5px;
}

.alarm-metrics strong {
  color: #EAF2FF;
  font-size: 13px;
  white-space: nowrap;
}

.red-ring {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid #EF4444;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: -2px;
}

.protect-grid {
  padding: 7px 14px 13px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.protect-chip {
  height: 29px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 9px;
  border: 1px solid rgba(33, 197, 93, .46);
  border-radius: 999px;
  color: #BFE9D0;
  background: rgba(33, 197, 93, .07);
  font-size: 12px;
  white-space: nowrap;
}

.protect-chip b {
  color: #21C55D;
  font-weight: 800;
}

.shortcut-row {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
}

.shortcut-card {
  border-radius: 8px;
  padding: 12px 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  color: #EAF2FF;
  text-align: left;
}

.shortcut-card:hover {
  border-color: rgba(47, 128, 255, .74);
  background: linear-gradient(145deg, rgba(19, 49, 86, .98), rgba(12, 30, 52, .98));
}

.shortcut-card.warning {
  border-color: rgba(246, 195, 67, .46);
}

.shortcut-card.warning .shortcut-icon {
  border-color: rgba(246, 195, 67, .6);
  background: rgba(246, 195, 67, .13);
  color: #FFE29A;
}

.shortcut-icon {
  width: 44px;
  height: 44px;
  border-radius: 8px;
}

.shortcut-text {
  min-width: 0;
  display: grid;
  gap: 5px;
}

.shortcut-text strong {
  font-size: 15px;
  white-space: nowrap;
}

.shortcut-text small {
  color: #91A7C6;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chart-panel {
  padding-bottom: 0;
}

.chart-panel :deep(.chart) {
  height: 168px;
}

.donut-layout {
  height: calc(100% - 36px);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  align-items: center;
  padding: 0 8px 5px 4px;
}

.donut-layout :deep(.chart) {
  height: 164px;
}

.result-legend {
  display: grid;
  gap: 10px;
  padding-right: 4px;
}

.result-legend div {
  display: grid;
  grid-template-columns: 10px 68px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  color: #AFC2DD;
  font-size: 12px;
}

.result-legend i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.result-legend strong {
  color: #EAF2FF;
  font-size: 12px;
  white-space: nowrap;
}

.table-panel {
  position: relative;
}

.table-head button {
  background: transparent;
  border-color: transparent;
  color: #75B2FF;
  padding-right: 0;
}

.session-table-wrap {
  height: calc(100% - 44px);
  overflow: auto;
}

.session-table-wrap::-webkit-scrollbar {
  width: 8px;
}

.session-table-wrap::-webkit-scrollbar-thumb {
  background: #17385E;
  border-radius: 999px;
}

.session-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.session-table th,
.session-table td {
  height: 26px;
  padding: 0 12px;
  border-bottom: 1px solid rgba(30, 58, 95, .64);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.session-table th {
  height: 30px;
  color: #8FA5C4;
  background: rgba(7, 17, 31, .48);
  font-size: 12px;
  font-weight: 750;
}

.session-table td {
  color: #DDEBFF;
  font-size: 12px;
}

.session-table th:nth-child(1) { width: 19%; }
.session-table th:nth-child(2) { width: 11%; }
.session-table th:nth-child(3) { width: 17%; }
.session-table th:nth-child(4) { width: 15%; }
.session-table th:nth-child(5) { width: 15%; }
.session-table th:nth-child(6) { width: 8%; }
.session-table th:nth-child(7) { width: 7%; }
.session-table th:nth-child(8) { width: 8%; }

.result-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 66px;
  height: 22px;
  border-radius: 999px;
  border: 1px solid currentColor;
  font-size: 11px;
  font-weight: 800;
}

.result-pill.pass {
  color: #21C55D;
  background: rgba(33, 197, 93, .08);
}

.result-pill.fail {
  color: #EF4444;
  background: rgba(239, 68, 68, .08);
}

.result-pill.running {
  color: #F6C343;
  background: rgba(246, 195, 67, .08);
}

.report-btn {
  width: 28px;
  height: 24px;
  display: inline-grid;
  place-items: center;
  border: 1px solid rgba(47, 128, 255, .42);
  border-radius: 5px;
  background: rgba(47, 128, 255, .1);
  color: #9CCBFF;
}

.muted {
  color: #7286A5;
}

.mono {
  font-family: Consolas, 'JetBrains Mono', monospace;
}

.action-message {
  position: absolute;
  right: 14px;
  bottom: 10px;
  margin: 0;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(7, 17, 31, .92);
  border: 1px solid currentColor;
  font-size: 12px;
}

.action-message.ok { color: #21C55D; }
.action-message.warn { color: #F6C343; }
.action-message.bad { color: #EF4444; }

@media (max-width: 1500px), (max-height: 860px) {
  .overview-page {
    height: auto;
    min-height: 100%;
    overflow: visible;
    grid-template-rows: 42px 82px 218px 82px 190px 150px;
    gap: 10px;
  }

  .kpi-copy strong { font-size: 26px; }
  .kpi-icon,
  .shortcut-icon { width: 40px; height: 40px; }
  .protect-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chart-panel :deep(.chart) { height: 154px; }
  .donut-layout :deep(.chart) { height: 150px; }
}
</style>
