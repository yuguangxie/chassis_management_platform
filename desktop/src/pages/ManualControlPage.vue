<template>
  <section class="manual-page">
    <header class="page-title">
      <div class="title-left">
        <div class="title-icon"><Gamepad2 :size="22" /></div>
        <div>
          <h1>手动下发控制</h1>
          <p>基于 0x121 主控制报文的安全手动控制</p>
        </div>
      </div>
      <div class="title-actions">
        <PageDataState :loading="control.loading" :error="control.error" :stale="control.offline || control.stale" />
        <button class="small-btn ghost" disabled title="尚未实现：本工作包不提供控制页面布局编辑器"><Settings :size="15" />自定义布局（尚未实现）</button>
      </div>
    </header>

    <section class="interlock-row">
      <article class="panel interlock-panel">
        <h2>1. 安全互锁状态</h2>
        <div class="interlock-grid">
          <div v-for="item in control.interlock.items" :key="item.key" :class="['interlock-item', item.status]">
            <component :is="item.status === 'warning' ? AlertTriangle : item.status === 'fail' ? XCircle : CheckCircle2" :size="22" />
            <span>{{ item.label }}</span>
            <strong>{{ statusValue(item) }}</strong>
            <small v-if="subValue(item)">{{ subValue(item) }}</small>
          </div>
        </div>
      </article>
      <article :class="['panel', 'allow-card', control.status.can_send_allowed ? 'allow' : 'block']">
        <h2>控制状态</h2>
        <ShieldCheck :size="50" />
        <strong>{{ control.status.can_send_allowed ? '允许发送' : '禁止发送' }}</strong>
        <p v-if="!control.status.can_send_allowed">{{ control.interlock.reasons?.join('，') || '安全联锁未通过' }}</p>
      </article>
    </section>

    <section class="control-grid">
      <article class="panel input-card">
        <h2>2. 0x121 主控制报文（输入控制）</h2>
        <div class="form-rows">
          <div class="control-line">
            <span class="label">档位请求</span>
            <div class="segmented">
              <button v-for="gear in ['D', 'N', 'R']" :key="gear" :class="{ active: control.command.gear === gear }" @click="control.command.gear = gear as 'D' | 'N' | 'R'">{{ gear }}</button>
            </div>
          </div>
          <div class="control-line">
            <span class="label">驱动模式</span>
            <div class="segmented">
              <button v-for="mode in ['Manual', 'Remote', 'Auto']" :key="mode" :class="{ active: control.command.drive_mode === mode }" @click="control.command.drive_mode = mode as 'Manual' | 'Remote' | 'Auto'">{{ mode }}</button>
            </div>
          </div>
          <div class="control-line">
            <span class="label">目标速度</span>
            <div class="number-field">
              <input v-model.number="control.command.target_speed" type="number" min="0" max="8" step="0.1" />
              <b>km/h</b>
              <small>范围：0.0 ~ 8.0</small>
            </div>
          </div>
          <AngleSlider label="前转角" v-model="control.command.front_steer" />
          <AngleSlider label="后转角" v-model="control.command.rear_steer" />
          <div class="control-line compact-line">
            <span class="label">制动使能</span>
            <button :class="['toggle', { on: control.command.brake_enable }]" @click="control.command.brake_enable = !control.command.brake_enable"><i></i><span>{{ control.command.brake_enable ? '使能' : '关闭' }}</span></button>
          </div>
          <div class="light-line">
            <span class="label">灯光控制</span>
            <LightToggle label="左转灯" v-model="control.command.left_turn" />
            <LightToggle label="右转灯" v-model="control.command.right_turn" />
            <LightToggle label="位置灯" v-model="control.command.position_light" />
            <LightToggle label="近光灯" v-model="control.command.low_beam" />
          </div>
          <div class="control-line compact-line">
            <span class="label">控制模式</span>
            <div class="segmented narrow">
              <button :class="{ active: control.command.control_mode === 'speed' }" @click="control.command.control_mode = 'speed'">速度模式</button>
              <button :class="{ active: control.command.control_mode === 'current' }" @click="control.command.control_mode = 'current'">电流模式</button>
            </div>
          </div>
        </div>
      </article>

      <div class="middle-stack">
        <article class="panel tx-card">
          <h2>3. 发送状态</h2>
          <div class="tx-grid">
            <div><span>当前主控制报文</span><strong>{{ control.status.control_message }}</strong></div>
            <div><span>发送周期</span><strong>{{ control.status.period_ms }} ms</strong></div>
            <div><span>控制通道</span><strong class="green">{{ control.status.control_channel }}</strong></div>
            <div><span>最后发送时间</span><strong>{{ control.status.last_tx_time }}</strong></div>
            <div><span>周期发送状态</span><strong class="green"><i class="dot"></i>{{ control.status.periodic_running ? '发送中' : '已停止' }}</strong></div>
            <div><span>失败次数</span><strong>{{ control.status.tx_fail_count }}</strong></div>
          </div>
        </article>

        <article class="panel preview-card">
          <h2>4. 0x121 报文预览（当前待发）</h2>
          <table class="byte-table">
            <tbody>
              <tr><th>Byte</th><td v-for="(_, index) in control.preview.bytes_hex" :key="index">Byte{{ index }}</td></tr>
              <tr><th>Hex</th><td v-for="(byte, index) in control.preview.bytes_hex" :key="`h-${index}`">{{ byte }}</td></tr>
              <tr><th>Dec</th><td v-for="(byte, index) in control.preview.bytes_dec" :key="`d-${index}`">{{ byte }}</td></tr>
            </tbody>
          </table>
          <div class="field-notes">
            <strong>字段说明（部分）</strong>
            <p v-for="note in control.preview.field_notes" :key="note">• {{ note }}</p>
          </div>
          <div class="warn-note"><AlertTriangle :size="16" />注意：SCU_Steering_Angle_Front / SCU_Steering_Angle_Rear 为 int8 有符号（补码）格式，不可按 DBC 原始 unsigned 直接发送。</div>
        </article>
      </div>

      <article class="panel feedback-card">
        <h2>5. 实时反馈（当前状态）</h2>
        <div class="feedback-list">
          <FeedbackRow label="当前档位" :value="freshFeedback(control.feedback.gear)" :icon="KeyRound" />
          <FeedbackRow label="车辆速度" :value="freshFeedback(`${control.feedback.vehicle_speed.toFixed(1)} km/h`)" :icon="Gauge" />
          <FeedbackRow label="前转角反馈" :value="freshFeedback(signed(control.feedback.front_steer_feedback))" :icon="MoveHorizontal" />
          <FeedbackRow label="后转角反馈" :value="freshFeedback(`${control.feedback.rear_steer_feedback}°`)" :icon="MoveHorizontal" />
          <FeedbackRow label="四轮轮速（FL / FR / RL / RR）" :value="freshFeedback(control.feedback.wheel_speeds)" :icon="CircleGauge" />
          <FeedbackRow label="灯光反馈" :value="freshFeedback(control.feedback.light_feedback)" :icon="Lightbulb" />
          <FeedbackRow label="制动状态" :value="freshFeedback(control.feedback.brake_status)" :icon="Disc3" tone="green" />
          <FeedbackRow label="告警状态" :value="freshFeedback(control.feedback.alarm_status)" :icon="TriangleAlert" tone="green" />
          <div v-for="field in control.feedback.fields || []" :key="field.rule" :data-feedback-rule="field.rule" :class="['feedback-quality-row', field.status]">
            <span>{{ field.label }}</span>
            <strong>{{ field.status === 'valid' ? '可信' : '阻断' }}</strong>
            <small>{{ feedbackFieldMeta(field) }}</small>
          </div>
        </div>
      </article>
    </section>

    <section class="chart-row">
      <article class="panel chart-card">
        <h2>6. 速度命令 vs 速度反馈</h2>
        <RealtimeLineChart :option="speedOption" height="100%" />
      </article>
      <article class="panel chart-card">
        <h2>7. 转角命令 vs 转角反馈</h2>
        <RealtimeLineChart :option="steerOption" height="100%" />
      </article>
    </section>

    <section class="panel action-panel">
      <h2>8. 操作控制</h2>
      <div class="action-row">
        <ActionButton title="发送一次" desc="立即发送 0x121" :icon="Send" variant="primary" :disabled="motionWriteDisabled" @click="sendOnce" />
        <ActionButton title="开始周期发送" desc="按设定周期持续发送" :icon="PlayCircle" variant="primary" :disabled="motionWriteDisabled" @click="startPeriodic" />
        <ActionButton title="停止周期发送" desc="停止发送 0x121" :icon="Square" variant="neutral" :disabled="control.offline" @click="stopPeriodic" />
        <ActionButton title="安全停车" desc="下发停车指令并制动" :icon="ParkingCircle" variant="warning" :disabled="control.offline" @click="safeStop" />
        <ActionButton title="急停" desc="立即下发急停指令" :icon="OctagonAlert" variant="danger" :disabled="control.offline" @click="emergencyStop" />
        <ActionButton title="解除急停确认" desc="需二次确认解除急停" :icon="BadgeCheck" variant="dangerOutline" :disabled="control.offline" @click="releaseEmergency" />
        <ActionButton title="恢复默认控制值" desc="清空输入并恢复默认" :icon="RefreshCw" variant="primary" :disabled="control.offline" @click="resetDefaults" />
      </div>
    </section>

    <footer class="safety-tip">安全提示：请确保车辆处于安全环境，确认周围无人、无障碍物后再进行手动控制操作。手动控制仅限调试/测试用途，严禁在公共道路或非封闭区域使用。</footer>
    <div v-if="toast" class="toast">{{ toast }}</div>
  </section>
</template>

<script setup lang="ts">
import {
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
  CircleGauge,
  Disc3,
  Gamepad2,
  Gauge,
  KeyRound,
  Lightbulb,
  MoveHorizontal,
  OctagonAlert,
  ParkingCircle,
  PlayCircle,
  RefreshCw,
  Send,
  Settings,
  ShieldCheck,
  Square,
  TriangleAlert,
  XCircle,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { apiPost } from '../api/http'
import type { ManualFeedbackField, ManualInterlockItem } from '../api/types'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import PageDataState from '../components/PageDataState.vue'
import { useControlStore } from '../stores/control'

type ActionResponse = { ok?: boolean; stub?: boolean; message?: string; emergency_stop?: boolean }

const control = useControlStore()
const toast = ref('')
const motionWriteDisabled = computed(() => control.offline || control.loading || control.stale || !control.status.can_send_allowed)
let toastTimer: number | undefined
let pollTimer: number | undefined

const AngleSlider = defineComponent({
  props: { modelValue: { type: Number, required: true }, label: { type: String, required: true } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('div', { class: 'angle-line' }, [
      h('span', { class: 'label' }, props.label),
      h('span', { class: 'range-label' }, '-120'),
      h('input', {
        type: 'range',
        min: -120,
        max: 120,
        value: props.modelValue,
        onInput: (event: Event) => emit('update:modelValue', Number((event.target as HTMLInputElement).value)),
      }),
      h('span', { class: 'range-label' }, '+120'),
      h('input', {
        class: 'angle-input',
        type: 'number',
        min: -120,
        max: 120,
        value: props.modelValue,
        onInput: (event: Event) => emit('update:modelValue', Number((event.target as HTMLInputElement).value)),
      }),
      h('b', '°'),
      h('small', '范围：-120 ~ +120'),
    ])
  },
})

const LightToggle = defineComponent({
  props: { modelValue: { type: Boolean, required: true }, label: { type: String, required: true } },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('button', {
      class: ['light-toggle', { on: props.modelValue }],
      onClick: () => emit('update:modelValue', !props.modelValue),
    }, [h('span', props.label), h('strong', props.modelValue ? '开' : '关')])
  },
})

const FeedbackRow = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true },
    icon: { type: Function as unknown as () => Component, required: true },
    tone: { type: String, default: '' },
  },
  setup(props) {
    return () => h('div', { class: 'feedback-row' }, [
      h(props.icon, { size: 16 }),
      h('span', props.label),
      h('strong', { class: props.tone }, props.value),
    ])
  },
})

const ActionButton = defineComponent({
  props: {
    title: { type: String, required: true },
    desc: { type: String, required: true },
    icon: { type: Function as unknown as () => Component, required: true },
    variant: { type: String, required: true },
    disabled: { type: Boolean, default: false },
  },
  emits: ['click'],
  setup(props, { emit }) {
    return () => h('button', { class: ['action-btn', props.variant], disabled: props.disabled, onClick: () => emit('click') }, [
      h('span', { class: 'action-icon' }, [h(props.icon, { size: props.variant === 'danger' ? 30 : 25 })]),
      h('span', { class: 'action-text' }, [h('strong', props.title), h('small', props.desc)]),
    ])
  },
})

const speedOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', backgroundColor: '#10243D', borderColor: '#2B4D78', textStyle: { color: '#EAF2FF' } },
  legend: { top: 0, right: 20, textStyle: { color: '#B9CBE2', fontSize: 12 } },
  grid: { left: 48, right: 24, top: 36, bottom: 28, containLabel: true },
  xAxis: axisX(control.offline || control.stale ? [] : control.curves.speed.x_axis),
  yAxis: axisY('km/h', 0, 10),
  series: [
    line('目标速度（km/h）', control.offline || control.stale ? [] : control.curves.speed.target_speed, '#2F80FF'),
    line('反馈速度（km/h）', control.offline || control.stale ? [] : control.curves.speed.feedback_speed, '#21C55D'),
  ],
}))

const steerOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', backgroundColor: '#10243D', borderColor: '#2B4D78', textStyle: { color: '#EAF2FF' } },
  legend: { top: 0, right: 20, textStyle: { color: '#B9CBE2', fontSize: 12 } },
  grid: { left: 48, right: 24, top: 36, bottom: 28, containLabel: true },
  xAxis: axisX(control.offline || control.stale ? [] : control.curves.steering.x_axis),
  yAxis: axisY('°', -120, 120),
  series: [
    line('前转角命令（°）', control.offline || control.stale ? [] : control.curves.steering.front_cmd, '#2F80FF'),
    line('前转角反馈（°）', control.offline || control.stale ? [] : control.curves.steering.front_feedback, '#60A5FA'),
    line('后转角命令（°）', control.offline || control.stale ? [] : control.curves.steering.rear_cmd, '#21C55D'),
    line('后转角反馈（°）', control.offline || control.stale ? [] : control.curves.steering.rear_feedback, '#21C55D', 'dashed'),
  ],
}))

onMounted(async () => {
  await control.loadAll()
  pollTimer = window.setInterval(() => {
    void Promise.all([control.loadStatus(), control.loadInterlock(), control.loadFeedback(), control.loadCurves()])
  }, 2500)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  if (toastTimer) window.clearTimeout(toastTimer)
})

watch(() => control.command, () => {
  void control.refreshPreview()
}, { deep: true })

function statusValue(item: ManualInterlockItem) {
  if (item.key === 'speed_limit' || item.key === 'steering_limit') return '正常'
  if (item.key === 'control_channel') return '警告'
  return item.value
}

function subValue(item: ManualInterlockItem) {
  if (item.key === 'speed_limit' || item.key === 'steering_limit' || item.key === 'control_channel') return item.value
  return ''
}

function axisX(data: string[]) {
  return { type: 'category', data, boundaryGap: false, axisLine: { lineStyle: { color: '#315A83' } }, axisLabel: { color: '#7F96B4', fontSize: 10 }, splitLine: { show: true, lineStyle: { color: '#143050' } } }
}

function axisY(name: string, min: number, max: number) {
  return { type: 'value', name, min, max, nameTextStyle: { color: '#AFC2DA' }, axisLabel: { color: '#7F96B4', fontSize: 10 }, splitLine: { lineStyle: { color: '#1A385C' } }, axisLine: { lineStyle: { color: '#315A83' } } }
}

function line(name: string, data: number[], color: string, type = 'solid') {
  return { name, type: 'line', smooth: true, symbol: 'none', data, itemStyle: { color }, lineStyle: { color, width: 2, type } }
}

function signed(value: number) {
  return `${value > 0 ? '+' : ''}${value}°`
}

function freshFeedback(value: string) {
  return control.offline || control.stale ? '—（stale）' : value
}

function feedbackFieldMeta(field: ManualFeedbackField) {
  const age = field.age_ms === null ? 'age missing' : `${Math.round(field.age_ms)} ms`
  const source = field.channel && field.can_id ? `${field.channel}/${field.can_id}` : 'source missing'
  return `${age} · ${field.quality} · ${source}`
}

async function sendOnce() {
  await runAction('发送一次', () => apiPost<ActionResponse>('/control/121/send-once', control.command))
  await control.loadStatus()
}

async function startPeriodic() {
  await runAction('开始周期发送', () => apiPost<ActionResponse>('/control/121/start-periodic', control.command))
  await control.loadStatus()
}

async function stopPeriodic() {
  await runAction('停止周期发送', () => apiPost<ActionResponse>('/control/121/stop', {}))
  await control.loadStatus()
}

async function safeStop() {
  await runAction('安全停车', () => apiPost<ActionResponse>('/control/safe-stop', {}))
  await control.loadStatus()
}

async function emergencyStop() {
  await runAction('急停', () => apiPost<ActionResponse>('/control/emergency-stop', {}))
  await control.loadStatus()
}

async function releaseEmergency() {
  if (!window.confirm('确认解除急停？请确认车辆速度为 0、周围环境安全、告警状态正常。')) return
  await runAction('解除急停确认', () => apiPost<ActionResponse>('/control/emergency-stop/release', { confirmation: 'RELEASE', reason: '桌面端人工二次确认' }))
  await control.loadStatus()
}

async function resetDefaults() {
  control.resetDefaults()
  await runAction('恢复默认控制值', () => apiPost<ActionResponse>('/control/reset-defaults', {}))
}

async function runAction(label: string, fn: () => Promise<ActionResponse>) {
  try {
    const result = await fn()
    showToast(`${label}：${result.message || (result.stub ? '接口已预留，当前为 Mock 模式' : '完成')}`)
  } catch (error) {
    showToast(`${label}：${formatActionError(error)}`)
  }
}

function formatActionError(error: unknown) {
  if (!(error instanceof Error)) return '接口不可用，当前为 Mock 模式'
  try {
    const parsed = JSON.parse(error.message) as { detail?: { message?: string; details?: { reasons?: Array<{ label?: string }> } } }
    const reason = parsed.detail?.details?.reasons?.[0]?.label
    return reason ? `${parsed.detail?.message || '安全联锁阻止控制'}：${reason}` : parsed.detail?.message || error.message
  } catch {
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
.manual-page {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-rows: 42px 115px 360px 185px 100px 32px;
  gap: 9px;
  color: #EAF2FF;
}

.panel,
.page-title,
.safety-tip {
  border: 1px solid #1E3A5F;
  background: linear-gradient(180deg, rgba(16, 36, 61, 0.98), rgba(10, 24, 43, 0.98));
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
  border-radius: 8px;
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
  background: linear-gradient(135deg, rgba(47, 128, 255, 0.3), rgba(34, 211, 238, 0.14));
  border: 1px solid rgba(47, 128, 255, 0.46);
}

.page-title h1 {
  margin: 0;
  font-size: 21px;
  line-height: 24px;
}

.page-title p {
  margin: 3px 0 0;
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

.interlock-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 10px;
  min-height: 0;
}

.panel {
  min-height: 0;
  overflow: hidden;
  padding: 10px;
}

.panel h2 {
  margin: 0 0 8px;
  font-size: 14px;
  line-height: 18px;
}

.interlock-panel {
  display: grid;
  grid-template-rows: 22px minmax(0, 1fr);
}

.interlock-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
  min-height: 0;
}

.interlock-item {
  display: grid;
  place-items: center;
  gap: 3px;
  border: 1px solid #1E3A5F;
  border-radius: 7px;
  background: #0A1A2E;
  color: #21C55D;
  padding: 5px 4px;
  text-align: center;
}

.interlock-item.warning {
  color: #F6C343;
  border-color: rgba(246, 195, 67, 0.45);
  background: rgba(246, 195, 67, 0.08);
}

.interlock-item.fail {
  color: #EF4444;
  border-color: rgba(239, 68, 68, 0.48);
  background: rgba(239, 68, 68, 0.08);
}

.interlock-item span {
  color: #CFE2FF;
  font-size: 11px;
  font-weight: 700;
}

.interlock-item strong {
  color: currentColor;
  font-size: 12px;
}

.interlock-item small {
  color: #9CB3CC;
  font-size: 11px;
}

.allow-card {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 6px;
  text-align: center;
}

.allow-card h2 {
  justify-self: start;
  align-self: start;
  width: 100%;
}

.allow-card svg,
.allow-card strong {
  color: #21C55D;
}

.allow-card.block svg,
.allow-card.block strong {
  color: #EF4444;
}

.allow-card strong {
  font-size: 27px;
  letter-spacing: 0;
}

.allow-card p {
  margin: 0;
  color: #FCA5A5;
  font-size: 12px;
}

.control-grid {
  display: grid;
  grid-template-columns: 1.05fr 1.15fr 1fr;
  gap: 10px;
  min-height: 0;
}

.input-card {
  display: grid;
  grid-template-rows: 22px minmax(0, 1fr);
}

.form-rows {
  display: grid;
  grid-template-rows: repeat(8, minmax(0, 1fr));
  gap: 6px;
  min-height: 0;
}

.control-line,
.angle-line,
.light-line {
  display: grid;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.control-line {
  grid-template-columns: 86px minmax(0, 1fr);
}

.angle-line {
  grid-template-columns: 86px 34px minmax(0, 1fr) 34px 72px 16px 105px;
}

.light-line {
  grid-template-columns: 86px repeat(4, minmax(0, 1fr));
}

.label {
  color: #AFC2DA;
  font-size: 12px;
}

.segmented {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  padding: 3px;
  border: 1px solid #24466F;
  border-radius: 6px;
  background: #07172A;
}

.segmented.narrow {
  grid-template-columns: repeat(2, 1fr);
}

.segmented button {
  height: 27px;
  border: 0;
  border-radius: 5px;
  color: #AFC2DA;
  background: transparent;
  font-size: 12px;
  cursor: pointer;
}

.segmented button.active {
  color: #FFFFFF;
  background: linear-gradient(135deg, #2F80FF, #1764D8);
}

.number-field {
  display: grid;
  grid-template-columns: 130px 48px 1fr;
  align-items: center;
  gap: 8px;
}

input,
button {
  font-family: inherit;
}

input[type='number'] {
  height: 28px;
  border: 1px solid #24466F;
  border-radius: 6px;
  background: #07172A;
  color: #DDEBFF;
  padding: 0 8px;
  outline: none;
}

.number-field b,
.angle-line b {
  color: #AFC2DA;
  font-size: 12px;
}

.number-field small,
.angle-line small {
  color: #7289A8;
  font-size: 11px;
}

input[type='range'] {
  width: 100%;
  height: 4px;
  accent-color: #2F80FF;
}

.range-label {
  color: #AFC2DA;
  font-size: 12px;
}

.angle-input {
  text-align: center;
}

.toggle {
  width: 92px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #24466F;
  border-radius: 999px;
  background: #07172A;
  color: #AFC2DA;
  padding: 0 8px;
  cursor: pointer;
}

.toggle i {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #56677E;
}

.toggle.on {
  border-color: rgba(33, 197, 93, 0.65);
  color: #D5FFE2;
  background: rgba(33, 197, 93, 0.12);
}

.toggle.on i {
  background: #21C55D;
}

.light-toggle {
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  border: 1px solid #24466F;
  border-radius: 6px;
  background: #07172A;
  color: #AFC2DA;
  padding: 0 8px;
  font-size: 12px;
  cursor: pointer;
}

.light-toggle.on {
  border-color: rgba(47, 128, 255, 0.7);
  color: #FFFFFF;
  background: rgba(47, 128, 255, 0.16);
}

.middle-stack {
  display: grid;
  grid-template-rows: 122px minmax(0, 1fr);
  gap: 10px;
  min-height: 0;
}

.tx-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border: 1px solid #1E3A5F;
  border-radius: 6px;
  overflow: hidden;
}

.tx-grid div {
  min-width: 0;
  display: grid;
  place-items: center;
  gap: 4px;
  min-height: 39px;
  border-right: 1px solid #1E3A5F;
  border-bottom: 1px solid #1E3A5F;
  text-align: center;
}

.tx-grid div:nth-child(3n) {
  border-right: 0;
}

.tx-grid div:nth-last-child(-n+3) {
  border-bottom: 0;
}

.tx-grid span,
.feedback-row span {
  color: #8CA6C5;
  font-size: 12px;
}

.tx-grid strong {
  color: #EAF2FF;
  font-size: 13px;
}

.green {
  color: #21C55D !important;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 5px;
  border-radius: 50%;
  background: #21C55D;
}

.preview-card {
  display: grid;
  grid-template-rows: 22px 70px 78px 40px;
  gap: 6px;
}

.byte-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 12px;
}

.byte-table th,
.byte-table td {
  height: 22px;
  border: 1px solid #24466F;
  text-align: center;
  color: #DDEBFF;
  font-family: Consolas, 'JetBrains Mono', monospace;
}

.byte-table th {
  color: #AFC2DA;
  background: #0B2038;
}

.field-notes {
  overflow: hidden;
  color: #AFC2DA;
  font-size: 11px;
}

.field-notes strong {
  display: block;
  margin-bottom: 3px;
  color: #DDEBFF;
}

.field-notes p {
  margin: 1px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.warn-note {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(246, 195, 67, 0.65);
  border-radius: 6px;
  background: rgba(246, 195, 67, 0.1);
  color: #FFD166;
  padding: 0 10px;
  font-size: 11px;
}

.feedback-card {
  display: grid;
  grid-template-rows: 22px minmax(0, 1fr);
}

.feedback-list {
  border: 1px solid #1E3A5F;
  border-radius: 6px;
  overflow: auto;
}

.feedback-row {
  display: grid;
  grid-template-columns: 24px 1fr auto;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 10px;
  border-bottom: 1px solid #1E3A5F;
}

.feedback-row:last-child {
  border-bottom: 0;
}

.feedback-row svg {
  color: #8FB6E8;
}

.feedback-row strong {
  color: #EAF2FF;
  font-size: 13px;
  text-align: right;
}

.feedback-quality-row{display:grid;grid-template-columns:1fr 46px 1.4fr;align-items:center;gap:6px;min-height:27px;padding:0 10px;border-bottom:1px solid #173456;color:#AFC2DA;font-size:9px}.feedback-quality-row strong{color:#21C55D}.feedback-quality-row.invalid strong{color:#EF4444}.feedback-quality-row small{overflow:hidden;color:#7F96B4;text-align:right;text-overflow:ellipsis;white-space:nowrap}

.chart-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  min-height: 0;
}

.chart-card {
  display: grid;
  grid-template-rows: 24px minmax(0, 1fr);
  padding: 9px 10px 6px;
}

.action-panel {
  display: grid;
  grid-template-rows: 22px minmax(0, 1fr);
}

.action-row {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 10px;
}

.action-btn {
  min-width: 0;
  display: grid;
  grid-template-columns: 44px 1fr;
  align-items: center;
  gap: 9px;
  border: 1px solid #2B5C90;
  border-radius: 7px;
  background: rgba(47, 128, 255, 0.12);
  color: #DDEBFF;
  padding: 8px 10px;
  text-align: left;
  cursor: pointer;
}
.action-btn:disabled,.small-btn:disabled{opacity:.42;cursor:not-allowed;filter:saturate(.45)}

.action-icon {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: rgba(47, 128, 255, 0.18);
}

.action-text {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.action-text strong {
  font-size: 15px;
  line-height: 18px;
}

.action-text small {
  color: #8CA6C5;
  font-size: 11px;
  white-space: normal;
}

.action-btn.primary {
  border-color: #2F80FF;
}

.action-btn.warning {
  border-color: rgba(246, 195, 67, 0.72);
  background: rgba(246, 195, 67, 0.12);
  color: #FFE5A0;
}

.action-btn.warning .action-icon {
  background: rgba(246, 195, 67, 0.18);
}

.action-btn.neutral {
  border-color: #315A83;
  background: rgba(49, 90, 131, 0.12);
}

.action-btn.danger,
.action-btn.dangerOutline {
  color: #FFE5E5;
  border-color: rgba(239, 68, 68, 0.9);
}

.action-btn.danger {
  background:
    repeating-linear-gradient(135deg, rgba(239, 68, 68, 0.22) 0 8px, rgba(122, 22, 22, 0.22) 8px 16px),
    rgba(239, 68, 68, 0.2);
}

.action-btn.danger .action-icon,
.action-btn.dangerOutline .action-icon {
  background: rgba(239, 68, 68, 0.22);
}

.action-btn.dangerOutline {
  background: rgba(239, 68, 68, 0.08);
}

.safety-tip {
  display: flex;
  align-items: center;
  padding: 0 14px;
  color: #AFC2DA;
  font-size: 12px;
}

.toast {
  position: absolute;
  right: 16px;
  bottom: 142px;
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
  .manual-page {
    grid-template-rows: 42px 132px 360px 185px 100px 32px;
  }
  .interlock-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-height: 800px) {
  /* Keep all safety decisions and the emergency-stop action in the first viewport.
     Curves remain available at larger heights; the dense input card owns local scroll here. */
  .manual-page {
    grid-template-rows: 42px 100px minmax(0, 1fr) 88px;
    gap: 7px;
  }
  .page-title h1 { font-size: 18px; }
  .page-title p { display: none; }
  .interlock-grid { grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 5px; }
  .interlock-item { padding: 3px; }
  .interlock-item span,
  .interlock-item strong { font-size: 10px; }
  .interlock-item small { display: none; }
  .allow-card strong { font-size: 20px; }
  .allow-card svg { width: 34px; height: 34px; }
  .control-grid { overflow: auto; scrollbar-color: #2B5C90 #07172A; }
  .chart-row,
  .safety-tip { display: none; }
  .action-panel { grid-row: 4; padding: 6px 8px; }
  .action-panel h2 { display: none; }
  .action-row { height: 100%; }
  .action-row :deep(button) { min-height: 0; padding-block: 4px; }
  .action-row :deep(small) { display: none; }
}
</style>
