<template>
  <section class="alarm-page">
    <header class="page-title-row">
      <div class="title-left">
        <div class="title-icon"><PanelsTopLeft :size="22" /></div>
        <div>
          <h1>告警诊断</h1>
          <p>0x77 告警、BMS保护与通信异常分析</p>
        </div>
      </div>
      <div class="title-actions">
        <span v-if="alarms.offline || dashboard.mock || dashboard.quality !== 'good'" class="mock-badge">{{ alarms.offline ? '后端离线，当前使用 Mock 告警数据' : dashboard.mock ? '显式 Mock 告警数据' : `数据质量：${dashboard.quality || 'unavailable'}` }}</span>
        <button class="layout-btn" type="button" @click="saveLayout">
          <Settings :size="15" />自定义布局
        </button>
      </div>
    </header>

    <article class="panel summary-panel">
      <h2>当前告警概览</h2>
      <div class="summary-grid">
        <div class="summary-item">
          <div><span>最高等级</span><strong class="green">{{ dashboard.summary.max_level }}</strong></div>
          <b class="green">{{ dashboard.summary.max_label }}</b>
        </div>
        <div class="summary-item">
          <div><span>当前告警数量</span><strong class="green">{{ dashboard.summary.current_count }}</strong></div>
          <b>项</b>
        </div>
        <div class="summary-item summary-status">
          <Ban :size="34" class="danger-icon" />
          <div><span>严重故障锁定</span><strong>{{ dashboard.summary.severe_locked ? '已锁定' : '未锁定' }}</strong></div>
        </div>
        <div class="summary-item summary-status">
          <CircleCheck :size="34" class="green" />
          <div><span>建议状态</span><strong>{{ dashboard.summary.recommendation }}</strong></div>
        </div>
      </div>
    </article>

    <section class="diagnosis-grid">
      <article class="panel matrix-panel">
        <h2>1. 0x77 告警矩阵（车辆综合告警）</h2>
        <div class="alarm-matrix">
          <div v-for="item in dashboard.warning_matrix_0x77" :key="item.key" :class="['alarm-cell', levelClass(item.status)]">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <b>{{ item.status }}</b>
          </div>
        </div>
        <div class="level-legend">
          <span><i class="normal"></i>0 Normal</span>
          <span><i class="warning"></i>1 Warning</span>
          <span><i class="fault"></i>2 Fault</span>
          <span><i class="critical"></i>3 Critical</span>
        </div>
      </article>

      <article class="panel protect-panel">
        <h2>2. BMS 保护（0x102）</h2>
        <div class="protect-grid">
          <div v-for="item in dashboard.bms_protect_0x102.items" :key="item.key" :class="['protect-cell', item.triggered ? 'triggered' : '']">
            <span>{{ item.label }}</span>
            <strong>{{ item.status || (item.triggered ? '已触发' : '未触发') }}</strong>
          </div>
        </div>
        <div class="bitmap-title">均衡状态 Bitmap（High → Low）</div>
        <div class="bitmap-grid">
          <div v-for="(bit, index) in dashboard.bms_protect_0x102.bitmap_bits.slice(0, 16)" :key="`protect-${index}`" :class="['bitmap-bit', bit === 1 ? 'on' : '']">
            <span>{{ 15 - index }}</span><strong>{{ bit === 1 ? 1 : 0 }}</strong>
          </div>
        </div>
        <div class="bitmap-note"><b>0 = 未触发</b><span>1 = 触发</span></div>
      </article>

      <article class="panel suggestion-panel">
        <h2>3. 诊断建议（依据当前状态）</h2>
        <div class="table-scroll">
          <table class="dense-table suggestion-table">
            <thead><tr><th>检查项</th><th>建议动作</th><th>是否允许人工放行</th><th>处理优先级</th></tr></thead>
            <tbody>
              <tr v-for="item in dashboard.diagnosis_suggestions" :key="item.check_item">
                <td>{{ item.check_item }}</td>
                <td>{{ item.suggestion }}</td>
                <td><span :class="['pill', item.allow_override ? 'normal' : 'critical']">{{ item.allow_override ? '是' : '否' }}</span></td>
                <td><span :class="['pill', priorityClass(item.priority)]">{{ item.priority }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <article class="panel history-panel">
      <h2>4. 历史告警记录</h2>
      <div class="history-scroll">
        <table class="dense-table history-table">
          <thead><tr><th>时间</th><th>通道</th><th>CAN ID</th><th>信号</th><th>等级</th><th>状态</th><th>建议</th><th>关联步骤</th><th>是否放行</th></tr></thead>
          <tbody>
            <tr v-for="item in dashboard.history" :key="item.id || `${item.time}-${item.signal}`">
              <td>{{ item.time }}</td><td>{{ item.channel }}</td><td class="mono">{{ item.can_id }}</td><td>{{ item.signal }}</td>
              <td><span :class="['level-text', historyLevelClass(item.level)]">{{ item.level }}</span></td>
              <td>{{ item.status }}</td><td>{{ item.suggestion }}</td><td>{{ item.related_step }}</td>
              <td><span :class="['pill', item.released ? 'normal' : 'critical']">{{ item.released ? '是' : '否' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <footer class="table-footer"><span>共 {{ dashboard.history.length }} 条</span><div><button>‹</button><b>1</b><button>›</button><span>20 条/页</span></div></footer>
    </article>

    <section class="chart-grid">
      <article class="panel chart-panel">
        <h2>5. 告警等级时间线（最近 30 分钟）</h2>
        <RealtimeLineChart :option="timelineOption" height="100%" />
      </article>
      <article class="panel chart-panel distribution-panel">
        <h2>6. 告警类别分布（最近 24 小时）</h2>
        <RealtimeLineChart :option="distributionOption" height="100%" />
      </article>
      <article class="panel bitmap-panel">
        <h2>7. BMS 保护位 Bitmap（0x102）</h2>
        <div class="bitmap-direction">High → Low</div>
        <div class="bitmap-grid large">
          <div v-for="(bit, index) in dashboard.bms_protect_0x102.bitmap_bits.slice(0, 16)" :key="`chart-${index}`" :class="['bitmap-bit', bit === 1 ? 'on' : '']">
            <span>{{ 15 - index }}</span><strong>{{ bit === 1 ? 1 : 0 }}</strong>
          </div>
        </div>
        <div class="bitmap-note"><b>0 = 未触发</b><span>1 = 触发</span></div>
      </article>
    </section>

    <section class="action-row">
      <button v-for="item in actionButtons" :key="item.action" :class="['action-card', item.variant]" type="button" @click="handleAction(item.action, item.title)">
        <span class="action-icon"><component :is="item.icon" :size="24" /></span>
        <span class="action-copy"><strong>{{ item.title }}</strong><small>{{ item.subtitle }}</small></span>
      </button>
    </section>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </section>
</template>

<script setup lang="ts">
import {
  Ban,
  CircleCheck,
  ClipboardCheck,
  FileDown,
  LocateFixed,
  PanelsTopLeft,
  Power,
  Settings,
  UserCheck,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { wsClient } from '../api/websocket'
import { apiPut, formatApiError } from '../api/http'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import { useAlarmsStore } from '../stores/alarms'

type AlarmAction = 'ack' | 'override-request' | 'export-diagnosis' | 'jump-can-frame' | 'safe-stop'

const alarms = useAlarmsStore()
const router = useRouter()
const dashboard = computed(() => alarms.dashboard)
const toast = ref('')
let toastTimer: number | undefined
let pollTimer: number | undefined
let wsReady = false
let wsDisposers: Array<() => void> = []

const actionButtons: Array<{ title: string; subtitle: string; action: AlarmAction; icon: Component; variant: string }> = [
  { title: '确认告警', subtitle: '确认当前告警状态', action: 'ack', icon: ClipboardCheck, variant: 'primary' },
  { title: '人工放行申请', subtitle: '提交人工放行申请', action: 'override-request', icon: UserCheck, variant: 'primary' },
  { title: '导出诊断', subtitle: '导出当前诊断报告', action: 'export-diagnosis', icon: FileDown, variant: 'primary' },
  { title: '跳转CAN帧', subtitle: '定位相关 CAN 消息', action: 'jump-can-frame', icon: LocateFixed, variant: 'primary' },
  { title: '触发安全停车', subtitle: '强制触发安全停车', action: 'safe-stop', icon: Power, variant: 'danger' },
]

const timelineOption = computed(() => {
  const chart = dashboard.value.charts.level_timeline
  const levelData = chart.x_axis.map((_, index) => Math.max(...chart.series.map((item) => Number(item.data[index] || 0))))
  return {
    backgroundColor: 'transparent',
    color: ['#21C55D'],
    tooltip: { trigger: 'axis', backgroundColor: '#10243D', borderColor: '#2B4D78', textStyle: { color: '#EAF2FF' }, formatter: (params: Array<{ value: number; axisValue: string }>) => `${params[0]?.axisValue}<br/>等级：${params[0]?.value}` },
    grid: { left: 34, right: 20, top: 20, bottom: 24, containLabel: true },
    xAxis: { type: 'category', data: chart.x_axis, boundaryGap: false, axisLine: { lineStyle: { color: '#315A83' } }, axisLabel: { color: '#8CA6C5', fontSize: 10 }, splitLine: { show: true, lineStyle: { color: '#143050' } } },
    yAxis: { type: 'value', min: 0, max: 3, interval: 1, axisLabel: { color: '#8CA6C5', fontSize: 10 }, splitLine: { lineStyle: { color: '#1A385C', type: 'dashed' } } },
    visualMap: { show: false, dimension: 1, pieces: [
      { value: 0, color: '#21C55D' }, { value: 1, color: '#F6C343' }, { value: 2, color: '#F97316' }, { value: 3, color: '#EF4444' },
    ] },
    series: [{ name: '告警等级', type: 'line', step: 'middle', data: levelData, symbol: 'circle', symbolSize: 6, lineStyle: { width: 2 }, areaStyle: { opacity: 0.04 } }],
  }
})

const distributionOption = computed(() => {
  const items = dashboard.value.charts.category_distribution
  const colors: Record<string, string> = { Normal: '#21C55D', Warning: '#F6C343', Fault: '#F97316', Critical: '#EF4444' }
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', backgroundColor: '#10243D', borderColor: '#2B4D78', textStyle: { color: '#EAF2FF' } },
    legend: { orient: 'vertical', right: 8, top: 'center', textStyle: { color: '#CFE2FF', fontSize: 11 }, itemWidth: 9, itemHeight: 9, formatter: (name: string) => {
      const item = items.find((entry) => entry.name === name)
      return `${name}    ${item?.value ?? 0} (${(item?.percent ?? 0).toFixed(1)}%)`
    } },
    graphic: [{ type: 'text', left: '26%', top: '44%', style: { text: '总计\n18', fill: '#EAF2FF', fontSize: 15, fontWeight: 700, textAlign: 'center', lineHeight: 20 } }],
    series: [{ type: 'pie', radius: ['47%', '68%'], center: ['28%', '55%'], avoidLabelOverlap: false, label: { show: false }, data: items.map((item) => ({ name: item.name, value: item.value, itemStyle: { color: colors[item.name] } })) }],
  }
})

onMounted(async () => {
  await alarms.loadDashboard()
  setupWebSocketRefresh()
  pollTimer = window.setInterval(() => void alarms.loadDashboard(), 2500)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  if (toastTimer) window.clearTimeout(toastTimer)
  wsDisposers.forEach((dispose) => dispose())
  wsDisposers = []
})

function levelClass(level: string) {
  return level.toLowerCase()
}

function priorityClass(priority: string) {
  return priority === '高' ? 'critical' : priority === '中' ? 'warning' : 'normal'
}

function historyLevelClass(level: string) {
  if (level.includes('Critical')) return 'critical'
  if (level.includes('Fault')) return 'fault'
  if (level.includes('Warning')) return 'warning'
  return 'normal'
}

function setupWebSocketRefresh() {
  try {
    if (!wsReady) {
      wsClient.connect()
      wsReady = true
    }
    ;['alarms.current', 'alarms.timeline', 'signals.threshold_status'].forEach((topic) => {
      wsDisposers.push(wsClient.on(topic, () => void alarms.loadDashboard()))
    })
  } catch {
    wsReady = false
  }
}

async function handleAction(action: AlarmAction, label: string) {
  try {
    const result = await alarms.runAction(action)
    showToast(`${label}：${result.message || '完成'}`)
    if (action === 'jump-can-frame') {
      window.setTimeout(() => void router.push({ path: '/can-monitor', query: { canId: dashboard.value.history[0]?.can_id || '0x77' } }), 700)
    }
  } catch (error) {
    showToast(`${label}：${formatActionError(error)}`)
  }
}

async function saveLayout() {
  try {
    const result = await apiPut<{ message: string }>('/alarms/dashboard-layout', { layout: { preset: 'diagnosis-default' } })
    showToast(`自定义布局：${result.message}`)
  } catch (error) {
    showToast(`自定义布局：${formatApiError(error)}`)
  }
}

function formatActionError(error: unknown) {
  return formatApiError(error)
}

function showToast(message: string) {
  toast.value = message
  if (toastTimer) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    if (toast.value === message) toast.value = ''
  }, 2800)
}
</script>

<style scoped>
.alarm-page {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-rows: 52px 100px 280px 210px minmax(0, 1fr) 70px;
  gap: 10px;
  color: #EAF2FF;
}

.panel {
  min-height: 0;
  overflow: hidden;
  border: 1px solid #1E3A5F;
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(16, 36, 61, 0.98), rgba(8, 23, 41, 0.98));
  box-shadow: 0 9px 22px rgba(0, 0, 0, 0.2);
}

.page-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
}

.title-left,
.title-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  color: #B9D9FF;
  border: 1px solid rgba(47, 128, 255, 0.5);
  background: linear-gradient(135deg, rgba(47, 128, 255, 0.42), rgba(34, 211, 238, 0.16));
}

.page-title-row h1 {
  margin: 0;
  font-size: 22px;
  line-height: 24px;
  font-weight: 800;
}

.page-title-row p {
  margin: 4px 0 0;
  color: #8CA6C5;
  font-size: 12px;
}

.mock-badge,
.layout-btn {
  height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 6px;
  font-size: 12px;
}

.mock-badge {
  padding: 0 10px;
  border: 1px solid rgba(246, 195, 67, 0.42);
  color: #F6C343;
  background: rgba(246, 195, 67, 0.1);
}

.layout-btn {
  padding: 0 11px;
  border: 1px solid #315A83;
  color: #CFE2FF;
  background: rgba(16, 36, 61, 0.8);
}

.panel h2 {
  margin: 0;
  color: #EAF2FF;
  font-size: 13px;
  line-height: 20px;
  font-weight: 800;
}

.summary-panel {
  display: grid;
  grid-template-rows: 24px minmax(0, 1fr);
  padding: 5px 12px 7px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 20px;
}

.summary-item {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  border: 1px solid #1E3A5F;
  border-radius: 7px;
  background: rgba(7, 23, 42, 0.78);
}

.summary-item div {
  display: flex;
  align-items: baseline;
  gap: 16px;
}

.summary-item span {
  color: #93AAC7;
  font-size: 12px;
}

.summary-item strong {
  color: #EAF2FF;
  font-size: 28px;
  line-height: 1;
}

.summary-item b {
  font-size: 16px;
}

.summary-status div {
  display: grid;
  gap: 7px;
}

.summary-status strong {
  font-size: 18px;
}

.green { color: #21C55D !important; }
.danger-icon { color: #FF334C; }

.diagnosis-grid {
  display: grid;
  grid-template-columns: 1.15fr 0.95fr 1.05fr;
  gap: 10px;
  min-height: 0;
}

.matrix-panel,
.protect-panel,
.suggestion-panel,
.chart-panel,
.bitmap-panel {
  display: grid;
  grid-template-rows: 26px minmax(0, 1fr);
  padding: 8px 10px;
}

.matrix-panel {
  grid-template-rows: 26px minmax(0, 1fr) 24px;
}

.alarm-matrix {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.alarm-cell {
  min-width: 0;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 5px;
  border: 1px solid #1E3A5F;
  border-radius: 6px;
  background: #081A2F;
}

.alarm-cell span {
  max-width: 100%;
  color: #C5D4E7;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alarm-cell strong {
  font-size: 25px;
  line-height: 1;
}

.alarm-cell b { font-size: 12px; }
.alarm-cell.normal strong, .alarm-cell.normal b { color: #21C55D; }
.alarm-cell.warning strong, .alarm-cell.warning b { color: #F6C343; }
.alarm-cell.fault strong, .alarm-cell.fault b { color: #F97316; }
.alarm-cell.critical strong, .alarm-cell.critical b { color: #EF4444; }

.level-legend {
  display: flex;
  align-items: end;
  gap: 24px;
  color: #AFC2DA;
  font-size: 11px;
}

.level-legend span { display: flex; align-items: center; gap: 5px; }
.level-legend i { width: 8px; height: 8px; border-radius: 50%; }
.level-legend .normal { background: #21C55D; }
.level-legend .warning { background: #F6C343; }
.level-legend .fault { background: #F97316; }
.level-legend .critical { background: #EF4444; }

.protect-panel {
  grid-template-rows: 26px 112px 24px 50px 22px;
}

.protect-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-template-rows: repeat(2, 1fr);
  gap: 7px;
}

.protect-cell {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 5px;
  border: 1px solid #1E3A5F;
  border-radius: 6px;
  background: #081A2F;
}

.protect-cell span { color: #C5D4E7; font-size: 12px; }
.protect-cell strong { color: #21C55D; font-size: 12px; }
.protect-cell.triggered { border-color: rgba(239, 68, 68, 0.7); }
.protect-cell.triggered strong { color: #EF4444; }

.bitmap-title,
.bitmap-direction {
  display: flex;
  align-items: end;
  color: #AFC2DA;
  font-size: 12px;
}

.bitmap-grid {
  display: grid;
  grid-template-columns: repeat(16, minmax(0, 1fr));
  gap: 4px;
  min-width: 0;
}

.bitmap-bit {
  min-width: 0;
  display: grid;
  grid-template-rows: 18px 24px;
  text-align: center;
  color: #AFC2DA;
  font-size: 10px;
}

.bitmap-bit strong {
  display: grid;
  place-items: center;
  border: 1px solid rgba(33, 197, 93, 0.48);
  border-radius: 4px;
  color: #21C55D;
  background: rgba(33, 197, 93, 0.04);
}

.bitmap-bit.on strong {
  color: #FFFFFF;
  border-color: #EF4444;
  background: rgba(239, 68, 68, 0.48);
}

.bitmap-note {
  display: flex;
  align-items: end;
  gap: 20px;
  color: #8CA6C5;
  font-size: 11px;
}

.bitmap-note b { color: #21C55D; font-weight: 500; }

.suggestion-panel { grid-template-rows: 26px minmax(0, 1fr); }
.table-scroll, .history-scroll { min-height: 0; overflow: auto; scrollbar-color: #2B5C90 #07172A; }

.dense-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 11px;
}

.dense-table th,
.dense-table td {
  height: 28px;
  padding: 0 7px;
  border: 1px solid #1E3A5F;
  color: #CFE2FF;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dense-table th {
  color: #AFC2DA;
  background: #0A2039;
  font-weight: 700;
}

.suggestion-table th:nth-child(1) { width: 27%; }
.suggestion-table th:nth-child(2) { width: 39%; }
.suggestion-table th:nth-child(3) { width: 20%; }
.suggestion-table th:nth-child(4) { width: 14%; }
.suggestion-table td:nth-child(n+3) { text-align: center; }

.pill {
  min-width: 22px;
  height: 19px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
  border: 1px solid #315A83;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 800;
}

.pill.normal { color: #21C55D; border-color: rgba(33, 197, 93, 0.6); background: rgba(33, 197, 93, 0.08); }
.pill.warning { color: #F6C343; border-color: rgba(246, 195, 67, 0.62); background: rgba(246, 195, 67, 0.08); }
.pill.critical { color: #EF4444; border-color: rgba(239, 68, 68, 0.68); background: rgba(239, 68, 68, 0.08); }

.history-panel {
  display: grid;
  grid-template-rows: 26px minmax(0, 1fr) 22px;
  padding: 7px 10px 4px;
}

.history-table th:nth-child(1) { width: 13%; }
.history-table th:nth-child(2) { width: 6%; }
.history-table th:nth-child(3) { width: 6%; }
.history-table th:nth-child(4) { width: 10%; }
.history-table th:nth-child(5) { width: 10%; }
.history-table th:nth-child(6) { width: 13%; }
.history-table th:nth-child(7) { width: 19%; }
.history-table th:nth-child(8) { width: 17%; }
.history-table th:nth-child(9) { width: 6%; }
.history-table th,
.history-table td { height: 24px; }

.level-text { font-weight: 800; }
.level-text.normal { color: #21C55D; }
.level-text.warning { color: #F6C343; }
.level-text.fault { color: #F97316; }
.level-text.critical { color: #EF4444; }

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #8CA6C5;
  font-size: 10px;
}

.table-footer div { display: flex; align-items: center; gap: 8px; }
.table-footer button { border: 0; background: transparent; color: #8CA6C5; }
.table-footer b { color: #2F80FF; }

.chart-grid {
  display: grid;
  grid-template-columns: 1.1fr 0.78fr 1.1fr;
  gap: 10px;
  min-height: 0;
}

.chart-panel { padding: 7px 10px; }
.distribution-panel { grid-template-rows: 26px minmax(0, 1fr); }
.bitmap-panel { grid-template-rows: 26px 24px minmax(0, 1fr) 24px; padding: 7px 10px; }
.bitmap-grid.large { align-items: center; }
.bitmap-grid.large .bitmap-bit { grid-template-rows: 20px 32px; font-size: 11px; }

.action-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) 1.3fr;
  gap: 12px;
  min-height: 0;
}

.action-card {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border: 1px solid #2F80FF;
  border-radius: 7px;
  color: #DDEBFF;
  background: linear-gradient(135deg, rgba(22, 105, 224, 0.68), rgba(10, 47, 95, 0.86));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 7px 16px rgba(0, 0, 0, 0.18);
}

.action-card:hover { filter: brightness(1.12); }
.action-card.danger { border-color: #EF334F; background: linear-gradient(135deg, rgba(153, 22, 39, 0.92), rgba(84, 15, 30, 0.96)); }

.action-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  color: #B9D9FF;
  background: rgba(47, 128, 255, 0.34);
}

.action-card.danger .action-icon { color: #FFE3E8; background: rgba(239, 68, 68, 0.26); }
.action-copy { min-width: 0; display: grid; gap: 5px; text-align: left; }
.action-copy strong { font-size: 15px; }
.action-copy small { color: #91A9C7; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.action-card.danger small { color: #FFABB8; }

.toast {
  position: absolute;
  right: 16px;
  bottom: 82px;
  z-index: 10;
  max-width: 620px;
  padding: 10px 14px;
  border: 1px solid #2F80FF;
  border-radius: 8px;
  color: #DDEBFF;
  background: rgba(10, 24, 43, 0.97);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.36);
  font-size: 13px;
}

@media (max-width: 1500px) {
  .alarm-page { min-width: 1120px; }
  .summary-grid { gap: 8px; }
  .diagnosis-grid { grid-template-columns: 1.1fr 0.95fr 1.05fr; }
  .level-legend { gap: 10px; }
  .action-copy strong { font-size: 13px; }
}
</style>
