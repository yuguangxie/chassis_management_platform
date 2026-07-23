<template>
  <section class="auto-test-page">
    <header class="page-title">
      <div class="title-left">
        <div class="title-icon"><ClipboardCheck :size="22" /></div>
        <div>
          <h1>一键检测</h1>
          <p>标准下线流程执行，断言判定与报告生成</p>
        </div>
      </div>
      <div class="title-actions">
        <PageDataState :loading="eol.initialLoading" :error="eol.error" :stale="eol.offline" :empty="!dashboard.steps.length" />
        <button class="small-btn ghost" disabled title="尚未实现：检测页布局编辑器">
          <Settings :size="15" />自定义布局（尚未实现）
        </button>
      </div>
    </header>

    <section class="summary-row">
      <article class="panel info-card">
        <header class="session-form-title"><h2>检测身份</h2><span v-if="dashboard.mock_session_allowed" class="mock-label">Mock 模式</span><button v-if="dashboard.mock_session_allowed" type="button" class="mock-generate" :disabled="Boolean(dashboard.session.session_id)" @click="generateMockIdentity">生成模拟会话数据</button></header>
        <div class="info-grid">
          <label class="info-field"><span>底盘编号</span><input v-model.trim="eol.identityDraft.chassis_no" :disabled="Boolean(dashboard.session.session_id)" autocomplete="off" /></label>
          <label class="info-field"><span>车辆识别码（VIN）</span><input v-model.trim="eol.identityDraft.vin" :disabled="Boolean(dashboard.session.session_id)" autocomplete="off" maxlength="17" /></label>
          <label class="info-field"><span>序列号</span><input v-model.trim="eol.identityDraft.serial_no" :disabled="Boolean(dashboard.session.session_id)" autocomplete="off" /></label>
          <label class="info-field"><span>车型</span><input v-model.trim="eol.identityDraft.vehicle_series" :disabled="Boolean(dashboard.session.session_id)" autocomplete="off" /></label>
          <label class="info-field"><span>工单号</span><input v-model.trim="eol.identityDraft.work_order_id" :disabled="Boolean(dashboard.session.session_id)" autocomplete="off" /></label>
          <InfoField label="操作员" :value="dashboard.session.operator" />
          <InfoField label="工位号" :value="dashboard.session.station_id" />
          <InfoField label="检测方案" :value="dashboard.session.test_plan" />
          <InfoField label="会话编号" :value="dashboard.session.session_id || '-'" />
          <label class="info-field remark-field">
            <span>备注</span>
            <input v-model="eol.identityDraft.remarks" :disabled="Boolean(dashboard.session.session_id)" placeholder="请输入备注信息（选填）" />
          </label>
        </div>
      </article>

      <article class="panel result-card">
        <h2>整体结果</h2>
        <div class="result-body">
          <div :class="['status-ring', statusClass(dashboard.session.overall_status)]">
            <span>{{ localizeStatus(dashboard.session.overall_status) }}</span>
          </div>
          <div class="result-metrics">
            <div class="metric big"><span>已用时间</span><strong>{{ dashboard.session.elapsed }}</strong></div>
            <div class="metric"><span>预计剩余</span><strong>{{ dashboard.session.remaining }}</strong></div>
            <div class="metric"><span>已完成</span><strong>{{ dashboard.session.completed }} / {{ dashboard.session.total }}</strong></div>
            <div class="metric pass"><span>通过</span><strong>{{ dashboard.session.passed }}</strong></div>
            <div class="metric fail"><span>失败</span><strong>{{ dashboard.session.failed }}</strong></div>
            <div class="metric"><span>待执行</span><strong>{{ dashboard.session.waiting }}</strong></div>
          </div>
        </div>
      </article>
    </section>

    <section class="panel stepper-card">
      <div class="steps">
        <div v-for="step in dashboard.steps" :key="step.index" :class="['step-item', statusClass(step.status)]">
          <div class="step-node">
            <CheckCircle2 v-if="step.status === 'PASS'" :size="22" />
            <XCircle v-else-if="step.status === 'FAIL'" :size="22" />
            <span v-else>{{ step.index }}</span>
          </div>
          <strong>{{ step.name }}</strong>
          <small>{{ localizeStatus(step.status) }}</small>
        </div>
      </div>
      <footer>
        <span>当前步骤 <b>{{ dashboard.session.current_step_index }} / {{ dashboard.session.total }}</b></span>
        <span>已用时间 <b>{{ dashboard.session.elapsed }}</b></span>
        <span>预计剩余 <b>{{ dashboard.session.remaining }}</b></span>
      </footer>
    </section>

    <section class="step-detail-row">
      <article class="panel detail-card">
        <h2>步骤详情（当前步骤：{{ dashboard.session.current_step_name }}）</h2>
        <div class="detail-list">
          <div>
            <span>步骤描述</span>
            <p>{{ dashboard.current_step.description }}</p>
          </div>
          <div>
            <span>执行指令（CAN）</span>
            <strong>{{ dashboard.current_step.command }}</strong>
          </div>
          <div class="detail-pair">
            <span>周期：<b>{{ dashboard.current_step.period_ms }}ms</b></span>
            <span>超时：<b>{{ dashboard.current_step.timeout_ms }}ms</b></span>
          </div>
        </div>
      </article>

      <article class="panel measure-card">
        <h2>实时测量值</h2>
        <div class="measure-list">
          <div v-for="item in dashboard.measurements" :key="item.name">
            <span>{{ item.name }}</span>
              <strong>{{ eol.offline ? '—（数据陈旧）' : item.value }} <small v-if="!eol.offline">{{ item.unit }}</small></strong>
          </div>
        </div>
      </article>

      <article class="panel assert-card">
        <h2>检测断言</h2>
        <table class="dense-table">
          <thead>
            <tr><th>断言</th><th>阈值</th><th>测量值</th><th>结果</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in dashboard.assertions" :key="item.description">
              <td>{{ item.description }}</td>
              <td>{{ item.threshold }}</td>
              <td>{{ item.value }}</td>
              <td><StatusBadge :status="item.result" /></td>
            </tr>
          </tbody>
        </table>
      </article>

      <article class="panel chart-card">
        <h2>实时曲线（关键指标）</h2>
        <RealtimeLineChart :option="realtimeOption" height="100%" />
      </article>
    </section>

    <section class="bottom-data-row">
      <article class="panel table-card">
        <h2>当前步骤断言列表</h2>
        <div class="table-scroll">
          <table class="dense-table">
            <thead>
              <tr><th>描述</th><th>信号</th><th>阈值</th><th>测量值</th><th>结果</th><th>失败原因</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in dashboard.assertions" :key="`list-${item.description}`">
                <td>{{ item.description }}</td>
                <td>{{ item.signal }}</td>
                <td>{{ item.threshold }}</td>
                <td>{{ item.value }}</td>
                <td><StatusBadge :status="item.result" /></td>
                <td>{{ item.fail_reason || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel table-card">
        <h2>步骤日志</h2>
        <div class="table-scroll">
          <table class="dense-table log-table">
            <thead>
              <tr><th>时间</th><th>步骤</th><th>动作</th><th>CAN命令</th><th>反馈</th><th>状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="log in dashboard.step_logs" :key="`${log.time}-${log.action}`">
                <td>{{ log.time }}</td>
                <td>{{ log.step }}</td>
                <td>{{ log.action }}</td>
                <td>{{ log.can_command }}</td>
                <td>{{ log.feedback }}</td>
                <td><StatusBadge :status="log.status" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel stats-card">
        <h2>关键统计（已完成步骤）</h2>
        <div class="stats-body">
          <div class="pass-donut"><span>通过率</span><strong>{{ dashboard.stats.pass_rate }}%</strong></div>
          <div class="stats-legend">
            <p><i class="green"></i>通过 <b>{{ dashboard.stats.passed }} ({{ stepPercent(dashboard.stats.passed) }}%)</b></p>
            <p><i class="red"></i>失败 <b>{{ dashboard.stats.failed }} ({{ stepPercent(dashboard.stats.failed) }}%)</b></p>
            <p><i class="gray"></i>待执行 <b>{{ dashboard.stats.waiting }} ({{ stepPercent(dashboard.stats.waiting) }}%)</b></p>
          </div>
        </div>
        <footer class="stats-footer">
          <div><span>总耗时</span><strong>{{ dashboard.stats.total_elapsed }}</strong></div>
          <div><span>平均每步耗时</span><strong>{{ dashboard.stats.avg_step_duration }}</strong></div>
        </footer>
      </article>
    </section>

    <section class="action-row">
      <IndustrialActionButton title="开始检测" subtitle="校验身份并确认后创建会话" variant="primary" :loading="pendingAction === '开始检测'" :disabled="writeDisabled" @click="startTest"><template #icon><PlayCircle :size="24" /></template></IndustrialActionButton>
      <IndustrialActionButton title="暂停" subtitle="安全暂停当前会话" variant="warning" :loading="pendingAction === '暂停'" :disabled="writeDisabled" @click="runAction('暂停', 'pause')"><template #icon><PauseCircle :size="24" /></template></IndustrialActionButton>
      <IndustrialActionButton title="继续" subtitle="恢复已暂停会话" variant="neutral" :loading="pendingAction === '继续'" :disabled="writeDisabled" @click="runAction('继续', 'resume')"><template #icon><PlayCircle :size="24" /></template></IndustrialActionButton>
      <IndustrialActionButton title="中止" subtitle="中止并进入安全终态" variant="danger" :loading="pendingAction === '中止'" :disabled="writeDisabled" @click="abortTest"><template #icon><Square :size="24" /></template></IndustrialActionButton>
      <IndustrialActionButton title="急停" subtitle="立即请求安全停车" variant="danger" :loading="pendingAction === '急停'" :disabled="writeDisabled" @click="emergencyStop"><template #icon><OctagonAlert :size="25" /></template></IndustrialActionButton>
      <IndustrialActionButton title="生成报告" subtitle="生成当前会话报告" variant="neutral" :loading="pendingAction === '生成报告'" :disabled="writeDisabled" @click="runAction('生成报告', 'report')"><template #icon><FileText :size="24" /></template></IndustrialActionButton>
      <IndustrialActionButton title="查看关联日志" subtitle="读取当前会话日志" variant="neutral" :loading="pendingAction === '查看关联日志'" :disabled="writeDisabled" @click="viewLogs"><template #icon><ScrollText :size="24" /></template></IndustrialActionButton>
    </section>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </section>
</template>

<script setup lang="ts">
import {
  CheckCircle2,
  ClipboardCheck,
  FileText,
  OctagonAlert,
  PauseCircle,
  PlayCircle,
  ScrollText,
  Settings,
  Square,
  XCircle,
} from 'lucide-vue-next'
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { apiGet } from '../api/http'
import { wsClient } from '../api/websocket'
import type { AutoTestStepStatus } from '../api/types'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import { useEolStore } from '../stores/eol'
import PageDataState from '../components/PageDataState.vue'
import IndustrialActionButton from '../components/common/IndustrialActionButton.vue'
import { localizeStatus } from '../ui/uiStatusLabels'

type ActionName = 'start' | 'pause' | 'resume' | 'abort' | 'emergency-stop' | 'report'

const eol = useEolStore()
const dashboard = computed(() => eol.dashboard)
const writeDisabled = computed(() => eol.offline || eol.initialLoading || eol.actionPending)
const toast = ref('')
const pendingAction = ref('')
let toastTimer: number | undefined
let pollTimer: number | undefined
let wsReady = false
let wsDisposers: Array<() => void> = []
let refreshTimer: number | undefined

const InfoField = defineComponent({
  props: { label: { type: String, required: true }, value: { type: String, required: true } },
  setup(props) {
    return () => h('div', { class: 'info-field' }, [h('span', props.label), h('strong', props.value)])
  },
})

const StatusBadge = defineComponent({
  props: { status: { type: String, required: true } },
  setup(props) {
    return () => h('span', { class: ['status-badge', statusClass(props.status)] }, localizeStatus(props.status))
  },
})

const realtimeOption = computed(() => {
  const realtime = dashboard.value.charts.realtime
  return {
    backgroundColor: 'transparent',
    color: ['#2F80FF', '#21C55D', '#F6C343', '#EF4444'],
    tooltip: { trigger: 'axis', backgroundColor: '#10243D', borderColor: '#2B4D78', textStyle: { color: '#EAF2FF' } },
    legend: { type: 'scroll', top: 0, left: 10, right: 8, textStyle: { color: '#B9CBE2', fontSize: 10 }, itemWidth: 14, itemHeight: 7 },
    grid: { left: 40, right: 44, top: 42, bottom: 26, containLabel: true },
    xAxis: {
      type: 'category',
      data: eol.offline ? [] : realtime.x_axis,
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#315A83' } },
      axisLabel: { color: '#8CA6C5', fontSize: 9, hideOverlap: true, interval: 'auto' },
      splitLine: { show: true, lineStyle: { color: '#143050' } },
    },
    yAxis: [
      {
        type: 'value',
        min: -120,
        max: 120,
        splitNumber: 4,
        axisLabel: { color: '#8CA6C5', fontSize: 9, hideOverlap: true },
        splitLine: { lineStyle: { color: '#1A385C' } },
      },
      {
        type: 'value',
        min: 0,
        max: 400,
        splitNumber: 4,
        axisLabel: { color: '#F6C343', fontSize: 9, hideOverlap: true },
        splitLine: { show: false },
      },
      {
        type: 'value',
        min: 0,
        max: 3,
        position: 'right',
        offset: 34,
        axisLabel: { color: '#EF4444', fontSize: 9, hideOverlap: true },
        splitLine: { show: false },
      },
    ],
    series: realtime.series.map((item) => ({
      name: item.name,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      data: eol.offline ? [] : item.data,
      yAxisIndex: item.name.includes('总压') ? 1 : item.name.includes('告警') ? 2 : 0,
      lineStyle: { width: 2 },
    })),
  }
})

onMounted(async () => {
  await eol.loadDashboard()
  setupWebSocketRefresh()
  pollTimer = window.setInterval(() => {
    void eol.loadDashboard(true)
  }, 2500)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  if (toastTimer) window.clearTimeout(toastTimer)
  wsDisposers.forEach((dispose) => dispose())
  wsDisposers = []
  if (refreshTimer) window.clearTimeout(refreshTimer)
})

function statusClass(status: string) {
  const normalized = status.toUpperCase()
  if (normalized === 'PASS') return 'pass'
  if (normalized === 'FAIL' || normalized === 'ABORTED') return 'fail'
  if (normalized === 'RUNNING' || normalized === 'PAUSED') return 'running'
  return 'wait'
}

function stepPercent(value:number) {
  const total = dashboard.value.stats.passed + dashboard.value.stats.failed + dashboard.value.stats.waiting
  return total ? (value / total * 100).toFixed(1) : '0.0'
}

function setupWebSocketRefresh() {
  const refreshTopics = ['test.session_progress', 'test.step_update', 'test.assertion_update', 'control.interlock_status', 'alarms.summary']
  try {
    if (!wsReady) {
      wsClient.connect()
      wsReady = true
    }
    refreshTopics.forEach((topic) => {
      wsDisposers.push(wsClient.on(topic, () => {
        scheduleBackgroundRefresh()
      }))
    })
  } catch {
    wsReady = false
  }
}

async function startTest() {
  const error = validateIdentity()
  if (error) {
    showToast(error)
    return
  }
  const draft = eol.identityDraft
  if (!window.confirm(`请确认检测对象：\n底盘号：${draft.chassis_no}\nVIN：${draft.vin}\n序列号：${draft.serial_no}\n工单号：${draft.work_order_id}`)) return
  await runAction('开始检测', 'start')
}

function generateMockIdentity() {
  try {
    eol.generateMockIdentity()
    showToast('已生成显式 Mock 身份；开始检测前仍需人工确认')
  } catch (error) {
    showToast(formatActionError(error))
  }
}

function validateIdentity() {
  const draft = eol.identityDraft
  if (!/^[A-Z0-9][A-Z0-9._-]{2,63}$/i.test(draft.chassis_no)) return '底盘编号格式无效'
  if (!/^[A-HJ-NPR-Z0-9]{17}$/i.test(draft.vin)) return '车辆识别码（VIN）必须为 17 位且不能包含 I、O、Q'
  if (!/^[A-Z0-9][A-Z0-9._-]{2,63}$/i.test(draft.serial_no)) return '序列号格式无效'
  if (!/^[A-Z0-9_-]{1,32}$/i.test(draft.vehicle_series)) return '车型格式无效'
  if (!/^[A-Z0-9][A-Z0-9._-]{2,63}$/i.test(draft.work_order_id)) return '工单号格式无效'
  return ''
}

async function abortTest() {
  await runAction('中止', 'abort')
}

async function emergencyStop() {
  await runAction('急停', 'emergency-stop')
}

async function viewLogs() {
  pendingAction.value = '查看关联日志'
  try {
    const sid = dashboard.value.session.session_id
    await apiGet(`/eol/sessions/${sid}/logs`)
    showToast('查看关联日志：日志接口已返回，当前保持在本页预览')
  } catch {
    showToast('查看关联日志：接口不可用，当前使用 Mock 日志')
  } finally { pendingAction.value = '' }
}

async function runAction(label: string, action: ActionName) {
  pendingAction.value = label
  try {
    const result = await eol.runSessionAction(action)
    showToast(`${label}：${result.message || (result.stub ? '接口已预留，当前为 Mock 模式' : '完成')}`)
  } catch (error) {
    showToast(`${label}：${formatActionError(error)}`)
  } finally { pendingAction.value = '' }
}

function scheduleBackgroundRefresh() {
  if (refreshTimer) return
  refreshTimer = window.setTimeout(() => {
    refreshTimer = undefined
    void eol.loadDashboard(true)
  }, 250)
}

function formatActionError(error: unknown) {
  if (!(error instanceof Error)) return '接口不可用，当前为 Mock 模式'
  try {
    const parsed = JSON.parse(error.message) as { detail?: { message?: string } }
    return parsed.detail?.message || error.message
  } catch {
    if (error.message.includes('Failed to fetch')) return '接口暂不可用，当前保持 Mock 检测数据'
    return error.message
  }
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
.auto-test-page {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-rows: 42px 150px 122px minmax(190px, 1.12fr) minmax(185px, 1fr) 70px;
  gap: 9px;
  color: #EAF2FF;
}

.panel,
.page-title {
  min-height: 0;
  overflow: hidden;
  border: 1px solid #1E3A5F;
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(16, 36, 61, 0.98), rgba(10, 24, 43, 0.98));
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
}

.page-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
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
  border-radius: 8px;
  color: #A8D0FF;
  background: linear-gradient(135deg, rgba(47, 128, 255, 0.32), rgba(34, 211, 238, 0.14));
  border: 1px solid rgba(47, 128, 255, 0.46);
}

.page-title h1 {
  margin: 0;
  font-size: 22px;
  line-height: 24px;
  font-weight: 800;
}

.page-title p {
  margin: 4px 0 0;
  color: #8CA6C5;
  font-size: 12px;
}

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
  cursor: pointer;
}

.summary-row {
  display: grid;
  grid-template-columns: 2fr 1.25fr;
  gap: 12px;
  min-height: 0;
}

.panel {
  padding: 10px 12px;
}

.panel h2 {
  margin: 0 0 6px;
  font-size: 14px;
  line-height: 18px;
  font-weight: 800;
}

.info-card {
  display: grid;
  grid-template-rows: 24px minmax(0, 1fr);
}

.session-form-title { display:flex; align-items:flex-start; gap:8px; min-width:0; }
.session-form-title h2 { margin-right:auto; }
.mock-label { padding:2px 6px; border:1px solid rgba(246,195,67,.5); border-radius:4px; color:#F6C343; background:rgba(246,195,67,.1); font-size:9px; }
.mock-generate { height:20px; padding:0 7px; border:1px solid #2F80FF; border-radius:5px; color:#CFE2FF; background:#134E91; font-size:9px; cursor:pointer; }
.mock-generate:hover:not(:disabled) { filter:brightness(1.18); box-shadow:0 0 10px rgba(47,128,255,.3); }
.mock-generate:disabled { opacity:.42; cursor:not-allowed; }

.info-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  grid-template-rows: repeat(2, 42px);
  gap: 10px;
}

.info-field {
  min-width: 0;
  display: grid;
  grid-template-columns: 78px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  border: 1px solid #1E3A5F;
  border-radius: 6px;
  background: #0A1A2E;
  padding: 0 10px;
}

.info-field span {
  color: #AFC2DA;
  font-size: 12px;
  font-weight: 700;
}

.info-field:has(input:focus) { border-color:#2F80FF; box-shadow:0 0 0 1px rgba(47,128,255,.2); }
.info-field input:disabled { color:#8298B5; cursor:not-allowed; }

.info-field strong,
.info-field input {
  min-width: 0;
  color: #F0F6FF;
  font-size: 13px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remark-field {
  grid-column: span 2;
}

.info-field input {
  height: 30px;
  border: 0;
  outline: none;
  background: transparent;
  font-family: inherit;
}

.result-card {
  display: grid;
  grid-template-rows: 24px minmax(0, 1fr);
}

.result-body {
  display: grid;
  grid-template-columns: 156px 1fr;
  align-items: center;
  min-height: 0;
}

.status-ring {
  width: 118px;
  height: 118px;
  display: grid;
  place-items: center;
  justify-self: center;
  border-radius: 50%;
  color: #F6C343;
  background:
    radial-gradient(circle, #10243D 54%, transparent 55%),
    repeating-conic-gradient(#F6C343 0deg 5deg, rgba(246, 195, 67, 0.18) 5deg 12deg);
}

.status-ring span {
  font-size: 20px;
  font-weight: 900;
}

.status-ring.pass {
  color: #21C55D;
  background: radial-gradient(circle, #10243D 54%, transparent 55%), repeating-conic-gradient(#21C55D 0deg 6deg, rgba(33, 197, 93, 0.18) 6deg 12deg);
}

.status-ring.fail {
  color: #EF4444;
  background: radial-gradient(circle, #10243D 54%, transparent 55%), repeating-conic-gradient(#EF4444 0deg 6deg, rgba(239, 68, 68, 0.18) 6deg 12deg);
}

.result-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border: 1px solid #1E3A5F;
  border-radius: 6px;
  overflow: hidden;
}

.metric {
  min-height: 43px;
  display: grid;
  align-content: center;
  gap: 3px;
  padding: 0 10px;
  border-right: 1px solid #1E3A5F;
  border-bottom: 1px solid #1E3A5F;
}

.metric:nth-child(3n) {
  border-right: 0;
}

.metric:nth-last-child(-n+3) {
  border-bottom: 0;
}

.metric span {
  color: #8CA6C5;
  font-size: 12px;
}

.metric strong {
  color: #EAF2FF;
  font-size: 16px;
}

.metric.big strong {
  color: #2F80FF;
  font-size: 22px;
}

.metric.pass strong {
  color: #21C55D;
}

.metric.fail strong {
  color: #EF4444;
}

.stepper-card {
  display: grid;
  grid-template-rows: minmax(0, 1fr) 22px;
  padding: 7px 18px 5px;
}

.steps {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  align-items: start;
  min-height: 0;
}

.step-item {
  position: relative;
  display: grid;
  grid-template-rows: 36px minmax(0, 28px) 12px;
  justify-items: center;
  gap: 2px;
  min-width: 0;
  text-align: center;
}

.step-item:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 18px;
  left: calc(50% + 24px);
  right: calc(-50% + 24px);
  height: 2px;
  background: #24466F;
}

.step-item.pass:not(:last-child)::after {
  background: #21C55D;
}

.step-node {
  position: relative;
  z-index: 1;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 2px solid #315A83;
  border-radius: 50%;
  background: #07172A;
  color: #8CA6C5;
  font-weight: 900;
}

.step-item.pass .step-node {
  border-color: #21C55D;
  color: #07111F;
  background: #21C55D;
}

.step-item.running .step-node {
  border-color: #2F80FF;
  color: #FFFFFF;
  background: #1764D8;
  box-shadow: 0 0 0 4px rgba(47, 128, 255, 0.18);
}

.step-item.fail .step-node {
  border-color: #EF4444;
  color: #FFFFFF;
  background: #EF4444;
}

.step-item strong {
  max-width: 100%;
  color: #DDEBFF;
  font-size: 12px;
  line-height: 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-item small {
  color: #7F96B4;
  font-size: 10px;
}

.step-item.pass small {
  color: #21C55D;
}

.step-item.running small {
  color: #2F80FF;
}

.stepper-card footer {
  display: flex;
  align-items: center;
  gap: 18px;
  border-top: 1px solid #1E3A5F;
  color: #8CA6C5;
  font-size: 12px;
}

.stepper-card footer b {
  margin-left: 6px;
  color: #CFE2FF;
}

.step-detail-row {
  display: grid;
  grid-template-columns: 1fr 0.82fr 1.08fr 1.35fr;
  gap: 10px;
  min-height: 0;
}

.detail-card,
.measure-card,
.assert-card,
.chart-card,
.table-card,
.stats-card {
  display: grid;
  grid-template-rows: 24px minmax(0, 1fr);
}

.stats-card {
  grid-template-rows: 24px minmax(0, 1fr) 48px;
}

.detail-list {
  display: grid;
  gap: 10px;
  min-height: 0;
}

.detail-list div {
  border-bottom: 1px solid #1E3A5F;
  padding-bottom: 8px;
}

.detail-list span {
  display: block;
  color: #8CA6C5;
  font-size: 12px;
  margin-bottom: 6px;
}

.detail-list p {
  margin: 0;
  color: #DDEBFF;
  font-size: 13px;
  line-height: 20px;
}

.detail-list strong {
  color: #EAF2FF;
  font-size: 14px;
}

.detail-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  border-bottom: 0 !important;
}

.detail-pair b {
  color: #21C55D;
}

.measure-list {
  border: 1px solid #1E3A5F;
  border-radius: 6px;
  overflow: hidden;
}

.measure-list div {
  min-height: 25px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 0 10px;
  border-bottom: 1px solid #1E3A5F;
}

.measure-list div:last-child {
  border-bottom: 0;
}

.measure-list span {
  color: #AFC2DA;
  font-size: 12px;
}

.measure-list strong {
  color: #EAF2FF;
  font-size: 13px;
}

.measure-list small {
  color: #8CA6C5;
}

.dense-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 12px;
}

.dense-table th,
.dense-table td {
  height: 30px;
  border: 1px solid #1E3A5F;
  padding: 0 8px;
  color: #CFE2FF;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dense-table th {
  color: #AFC2DA;
  background: #0B2038;
  font-weight: 800;
}

.log-table td:nth-child(4),
.log-table td:nth-child(5) {
  font-family: Consolas, 'JetBrains Mono', monospace;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  height: 22px;
  border-radius: 5px;
  border: 1px solid #315A83;
  color: #8CA6C5;
  font-size: 11px;
  font-weight: 900;
}

.status-badge.pass {
  color: #21C55D;
  border-color: rgba(33, 197, 93, 0.65);
  background: rgba(33, 197, 93, 0.1);
}

.status-badge.fail {
  color: #EF4444;
  border-color: rgba(239, 68, 68, 0.7);
  background: rgba(239, 68, 68, 0.1);
}

.status-badge.running {
  color: #2F80FF;
  border-color: rgba(47, 128, 255, 0.7);
  background: rgba(47, 128, 255, 0.12);
}

.bottom-data-row {
  display: grid;
  grid-template-columns: 1.12fr 1.36fr 0.78fr;
  gap: 10px;
  min-height: 0;
}

.table-scroll {
  min-height: 0;
  overflow: auto;
  scrollbar-color: #2B5C90 #07172A;
}

.stats-body {
  display: grid;
  grid-template-columns: 150px 1fr;
  align-items: center;
  min-height: 0;
}

.pass-donut {
  width: 130px;
  height: 130px;
  display: grid;
  place-items: center;
  justify-self: center;
  align-content: center;
  border-radius: 50%;
  background:
    radial-gradient(circle, #10243D 53%, transparent 54%),
    conic-gradient(#21C55D 0 360deg, #315A83 0);
}

.pass-donut span {
  color: #CFE2FF;
  font-size: 12px;
}

.pass-donut strong {
  color: #FFFFFF;
  font-size: 25px;
}

.stats-legend {
  display: grid;
  gap: 10px;
}

.stats-legend p {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 0;
  color: #CFE2FF;
  font-size: 13px;
}

.stats-legend i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.stats-legend .green { background: #21C55D; }
.stats-legend .red { background: #EF4444; }
.stats-legend .gray { background: #9CA3AF; }

.stats-footer {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-top: 1px solid #1E3A5F;
  padding-top: 10px;
}

.stats-footer div {
  display: grid;
  gap: 5px;
  color: #8CA6C5;
  font-size: 12px;
}

.stats-footer strong {
  color: #DDEBFF;
  font-size: 18px;
}

.action-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr) 1.2fr 1.2fr;
  gap: 10px;
  min-height: 0;
}

.action-btn {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px solid #2B5C90;
  border-radius: 8px;
  color: #DDEBFF;
  background: rgba(47, 128, 255, 0.12);
  font-size: 18px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.action-btn.primary {
  background: linear-gradient(135deg, #2F80FF, #1764D8);
  border-color: #2F80FF;
}

.action-btn.secondary {
  background: linear-gradient(135deg, rgba(47, 128, 255, 0.22), rgba(23, 100, 216, 0.16));
}

.action-btn.warning {
  color: #FFF7D6;
  background: linear-gradient(135deg, #D89A09, #AE7600);
  border-color: #F6C343;
}

.action-btn.danger {
  color: #FFE5E5;
  background: linear-gradient(135deg, #D72E3A, #9F1725);
  border-color: rgba(239, 68, 68, 0.95);
}

.action-btn.hot {
  background:
    repeating-linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0 8px, rgba(122, 22, 22, 0.35) 8px 16px),
    linear-gradient(135deg, #E11D48, #991B1B);
}

.action-btn.outline {
  background: rgba(16, 36, 61, 0.82);
  border-color: #315A83;
}
.action-btn:disabled{opacity:.42;cursor:not-allowed;filter:saturate(.45)}

.toast {
  position: absolute;
  right: 16px;
  bottom: 88px;
  z-index: 5;
  max-width: 620px;
  padding: 10px 14px;
  border: 1px solid #2F80FF;
  border-radius: 8px;
  background: rgba(10, 24, 43, 0.96);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.35);
  color: #DDEBFF;
  font-size: 13px;
}

@media (max-width: 1500px) {
  .auto-test-page {
    grid-template-rows: 42px 150px 122px 230px 230px 70px;
  }

  .steps {
    grid-template-columns: repeat(12, minmax(0, 1fr));
    row-gap: 0;
  }

  .step-item:nth-child(6)::after {
    display: block;
  }

  .step-item {
    grid-template-rows: 28px minmax(0, 24px) 10px;
    gap: 1px;
  }

  .step-node {
    width: 28px;
    height: 28px;
    border-width: 1px;
    font-size: 11px;
  }

  .step-item:not(:last-child)::after {
    top: 14px;
    left: calc(50% + 18px);
    right: calc(-50% + 18px);
  }

  .step-item strong {
    font-size: 9px;
    line-height: 11px;
  }

  .step-item small {
    font-size: 8px;
  }

  .info-field {
    grid-template-columns: 60px minmax(0, 1fr);
    gap: 4px;
    padding-inline: 6px;
  }

  .info-field span,
  .info-field strong,
  .info-field input {
    font-size: 11px;
  }
}

@media (max-height: 800px) {
  .auto-test-page {
    grid-template-rows: 42px 116px 104px minmax(132px, 1.15fr) minmax(132px, 1fr) 70px;
    gap: 7px;
  }

  .info-grid { grid-template-rows: repeat(2, 36px); gap: 7px; }
  .steps { min-height: 0; }
  .stepper-card { padding-inline: 12px; }
  .stepper-card footer { gap: 12px; font-size: 10px; }
  .stats-card { grid-template-rows: 20px minmax(0, 1fr); }
  .stats-card h2 { font-size: 12px; line-height: 16px; }
  .stats-footer { display: none; }
  .action-card { gap: 8px; }
  .action-copy small { display: none; }
}
</style>
