<template>
  <div class="signal-dashboard-page">
    <section class="page-header">
      <div class="title-block">
        <div class="title-icon"><LayoutDashboard /></div>
        <div>
          <h1>信号仪表盘</h1>
          <p>关键反馈信号可视化与状态监控</p>
        </div>
        <span v-if="signals.offline || data.mock || data.quality !== 'good'" class="offline-badge">{{ signals.offline ? '后端离线 / Mock 数据' : data.mock ? '显式 Mock 数据' : `数据质量：${data.quality || 'unavailable'}` }}</span>
      </div>
      <button class="header-action" @click="saveLayout"><Settings :size="16" />自定义布局</button>
    </section>

    <section class="row row-one">
      <article class="panel bms-card">
        <CardHead title="BMS 信号" status="正常"><BatteryCharging :size="18" /></CardHead>
        <div class="bms-grid">
          <MetricTile label="总压" :value="data.bms.total_voltage" unit="V" :trend="data.bms.trend.voltage" tone="blue" />
          <MetricTile label="电流" :value="data.bms.current" unit="A" :trend="data.bms.trend.current" tone="green" />
          <MetricTile label="SOC" :value="data.bms.soc" unit="%" :trend="data.bms.trend.soc" tone="blue" />
          <MetricTile label="NTC温度" :value="data.bms.ntc_temperature" unit="°C" :trend="data.bms.trend.ntc" tone="blue" />
          <MetricTile label="单体最高电压" :value="data.bms.cell_max_voltage" unit="V" tone="white" />
          <MetricTile label="单体最低电压" :value="data.bms.cell_min_voltage" unit="V" tone="white" />
          <MetricTile label="单体压差" :value="data.bms.cell_delta_mv" unit="mV" tone="white" />
          <div class="metric-tile discharge">
            <span>充放电状态</span>
            <strong><Snowflake :size="24" />{{ data.bms.charge_discharge_state }}</strong>
          </div>
        </div>
      </article>

      <article class="panel vehicle-card">
        <CardHead title="车辆状态" status="正常"><CarFront :size="18" /></CardHead>
        <div class="vehicle-list">
          <StatusLine label="当前档位" :value="data.vehicle.gear"><Cog :size="18" /></StatusLine>
          <StatusLine label="当前驱动模式" :value="data.vehicle.drive_mode" accent><SatelliteDish :size="18" /></StatusLine>
          <StatusLine label="点火状态" :value="data.vehicle.ignition" accent><KeyRound :size="18" /></StatusLine>
          <StatusLine label="驻车状态" :value="data.vehicle.parking" accent><CircleParking :size="18" /></StatusLine>
          <StatusLine label="车辆速度" :value="`${data.vehicle.speed.toFixed(1)} km/h`" accent><Gauge :size="18" /></StatusLine>
        </div>
      </article>

      <article class="panel wheel-card">
        <CardHead title="轮速（km/h）" status="正常"><Crosshair :size="18" /></CardHead>
        <div class="wheel-layout">
          <WheelValue label="左前" :value="data.wheel_speed.front_left" class="wheel-fl" />
          <WheelValue label="右前" :value="data.wheel_speed.front_right" class="wheel-fr" />
          <WheelValue label="左后" :value="data.wheel_speed.rear_left" class="wheel-rl" />
          <WheelValue label="右后" :value="data.wheel_speed.rear_right" class="wheel-rr" />
          <div class="chassis-diagram" aria-label="车辆底盘四轮示意图">
            <div class="axle front"></div>
            <div class="axle rear"></div>
            <div class="spine"></div>
            <div class="body center"></div>
            <div class="wheel w1"></div>
            <div class="wheel w2"></div>
            <div class="wheel w3"></div>
            <div class="wheel w4"></div>
          </div>
        </div>
      </article>
    </section>

    <section class="row row-two">
      <article class="panel steering-card">
        <CardHead title="转向反馈" status="正常"><ShieldCheck :size="18" /></CardHead>
        <div class="split-trends">
          <TrendBlock title="前转角反馈" :value="data.steering.front_feedback" unit="°" :cmd="data.steering.front_cmd" :feedback="data.steering.front_feedback" :trend="data.steering.front_trend" color="#2F80FF" />
          <TrendBlock title="后转角反馈" :value="data.steering.rear_feedback" unit="°" :cmd="data.steering.rear_cmd" :feedback="data.steering.rear_feedback" :trend="data.steering.rear_trend" color="#21C55D" />
        </div>
      </article>

      <article class="panel motor-card">
        <CardHead title="电机信号" status="正常"><Activity :size="18" /></CardHead>
        <div class="motor-grid">
          <MetricTile label="电机转速" :value="data.motor.speed_rpm" unit="rpm" :trend="data.motor.speed_trend" tone="blue" />
          <MetricTile label="电机相电流" :value="data.motor.phase_current_a" unit="A" :trend="data.motor.current_trend" tone="green" />
          <div class="heartbeat-tile">
            <span>心跳状态</span>
            <strong>{{ data.motor.heartbeat }}</strong>
            <em>{{ data.motor.heartbeat_status }}</em>
          </div>
        </div>
      </article>

      <article class="panel light-card">
        <CardHead title="灯光 & 制动"><BadgeInfo :size="18" /></CardHead>
        <div class="light-grid">
          <LightItem label="左转灯" :state="data.lights_brake.left_turn"><ArrowLeft :size="28" /></LightItem>
          <LightItem label="右转灯" :state="data.lights_brake.right_turn"><ArrowRight :size="28" /></LightItem>
          <LightItem label="位置灯" :state="data.lights_brake.position_light" active><Sun :size="30" /></LightItem>
          <LightItem label="近光灯" :state="data.lights_brake.low_beam"><ListFilter :size="28" /></LightItem>
          <LightItem label="制动请求" :state="data.lights_brake.brake_request" danger><CircleAlert :size="30" /></LightItem>
        </div>
      </article>
    </section>

    <section class="row row-three">
      <article class="panel alarm-card">
        <CardHead title="告警状态" status="正常"><ShieldCheck :size="18" /></CardHead>
        <div class="alarm-body">
          <div class="alarm-level">
            <span>告警等级</span>
            <strong>{{ data.alarm.level }}</strong>
            <em>{{ data.alarm.label }}</em>
          </div>
          <div class="threshold-list">
            <h3>阈值状态</h3>
            <div v-for="item in data.alarm.thresholds" :key="item.name" class="threshold-row">
              <span>{{ item.name }}</span>
              <b><i></i>{{ item.status }}</b>
            </div>
          </div>
        </div>
      </article>

      <article class="panel watch-card">
        <div class="watch-head">
          <div>
            <h2>信号监视表（Watchlist）</h2>
            <span>最后更新：{{ data.status.updated_at }}</span>
          </div>
          <div class="watch-actions">
            <button @click="saveWatchlist">保存配置</button>
            <button @click="exportSnapshot">导出快照</button>
            <button @click="resetLayout">重置布局</button>
          </div>
        </div>
        <div class="watch-table-wrap">
          <table class="watch-table">
            <thead>
              <tr>
                <th>信号名</th>
                <th>CAN ID</th>
                <th>通道</th>
                <th>值</th>
                <th>单位</th>
                <th>阈值</th>
                <th>质量</th>
                <th>最后更新时间</th>
                <th>趋势</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.watchlist" :key="`${row.signal_name}-${row.can_id}`">
                <td>{{ row.signal_name }}</td>
                <td class="mono">{{ row.can_id }}</td>
                <td>{{ row.channel }}</td>
                <td :class="['value-cell', Number(row.value) < 0 || row.unit === 'A' ? 'green' : 'blue']">{{ row.value }}</td>
                <td>{{ row.unit }}</td>
                <td>{{ row.threshold }}</td>
                <td><span class="quality">{{ row.quality }}</span></td>
                <td>{{ row.updated_at }}</td>
                <td><Sparkline :values="row.trend" :color="Number(row.value) < 0 || row.unit === 'A' ? '#21C55D' : '#2F80FF'" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, type PropType } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  Activity,
  BadgeInfo,
  BatteryCharging,
  CarFront,
  CircleAlert,
  CircleParking,
  Cog,
  Crosshair,
  Gauge,
  KeyRound,
  LayoutDashboard,
  ListFilter,
  SatelliteDish,
  Settings,
  ShieldCheck,
  Snowflake,
  Sun,
} from 'lucide-vue-next'
import { apiDownload, apiPost, apiPut, formatApiError } from '../api/http'
import { wsClient } from '../api/websocket'
import { useSignalsStore } from '../stores/signals'

const signals = useSignalsStore()
const data = computed(() => signals.dashboard)
const toast = ref('')
let refreshTimer: number | undefined

const Sparkline = defineComponent({
  props: {
    values: { type: Array as PropType<number[]>, required: true },
    color: { type: String, default: '#2F80FF' },
    height: { type: Number, default: 34 },
    min: { type: Number, default: undefined },
    max: { type: Number, default: undefined },
  },
  setup(props) {
    return () => h('svg', { class: 'sparkline', viewBox: `0 0 100 ${props.height}`, preserveAspectRatio: 'none' }, [
      h('polyline', { points: sparkPoints(props.values, 100, props.height, props.min, props.max), fill: 'none', stroke: props.color, 'stroke-width': 3, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }),
    ])
  },
})

const CardHead = defineComponent({
  props: { title: { type: String, required: true }, status: { type: String, default: '' } },
  setup(props, { slots }) {
    return () => h('div', { class: 'card-head' }, [
      h('div', { class: 'card-title' }, [h('span', { class: 'head-icon' }, slots.default?.()), h('h2', props.title)]),
      props.status ? h('span', { class: 'status-badge' }, props.status) : null,
    ])
  },
})

const MetricTile = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: [Number, String], required: true },
    unit: { type: String, default: '' },
    trend: { type: Array as PropType<number[]>, default: () => [] },
    tone: { type: String, default: 'blue' },
  },
  setup(props) {
    return () => h('div', { class: ['metric-tile', props.tone] }, [
      h('span', props.label),
      h('strong', [formatValue(props.value), props.unit ? h('small', ` ${props.unit}`) : null]),
      props.trend.length ? h(Sparkline, { values: props.trend, color: props.tone === 'green' ? '#21C55D' : '#2F80FF', height: 28 }) : null,
    ])
  },
})

const StatusLine = defineComponent({
  props: { label: { type: String, required: true }, value: { type: String, required: true }, accent: { type: Boolean, default: false } },
  setup(props, { slots }) {
    return () => h('div', { class: 'vehicle-row' }, [
      h('span', { class: 'row-label' }, [slots.default?.(), props.label]),
      h('strong', { class: props.accent ? 'accent' : '' }, props.value),
    ])
  },
})

const WheelValue = defineComponent({
  props: { label: { type: String, required: true }, value: { type: Number, required: true } },
  setup(props) {
    return () => h('div', { class: 'wheel-value' }, [h('span', props.label), h('strong', props.value.toFixed(1))])
  },
})

const TrendBlock = defineComponent({
  props: {
    title: { type: String, required: true },
    value: { type: Number, required: true },
    unit: { type: String, required: true },
    cmd: { type: Number, required: true },
    feedback: { type: Number, required: true },
    trend: { type: Array as PropType<number[]>, required: true },
    color: { type: String, required: true },
  },
  setup(props) {
    return () => h('div', { class: 'trend-block' }, [
      h('span', props.title),
      h('strong', [props.value.toFixed(1), h('small', ` ${props.unit}`)]),
      h('p', `指令 ${props.cmd.toFixed(1)}° | 反馈 ${props.feedback.toFixed(1)}°`),
      h('div', { class: 'mini-chart' }, [
        h('span', { class: 'axis top' }, '45°'),
        h(Sparkline, { values: props.trend, color: props.color, height: 58, min: -45, max: 45 }),
        h('span', { class: 'axis bottom' }, '-45°'),
      ]),
    ])
  },
})

const LightItem = defineComponent({
  props: { label: { type: String, required: true }, state: { type: String, required: true }, active: { type: Boolean, default: false }, danger: { type: Boolean, default: false } },
  setup(props, { slots }) {
    return () => h('div', { class: ['light-item', props.active ? 'active' : '', props.danger ? 'danger' : ''] }, [
      h('span', props.label),
      h('i', slots.default?.()),
      h('strong', props.state),
    ])
  },
})

onMounted(async () => {
  signals.bindWebSocket()
  if (!wsClient.ws || wsClient.ws.readyState > WebSocket.OPEN) wsClient.connect()
  await signals.loadDashboard()
  refreshTimer = window.setInterval(() => {
    void signals.loadDashboard()
  }, 2500)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})

function sparkPoints(values: number[], width: number, height: number, fixedMin?: number, fixedMax?: number): string {
  if (!values.length) return ''
  const min = fixedMin ?? Math.min(...values)
  const max = fixedMax ?? Math.max(...values)
  const range = max - min || 1
  return values.map((value, index) => {
    const x = values.length === 1 ? width : (index / (values.length - 1)) * width
    const y = height - ((value - min) / range) * (height - 6) - 3
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

function formatValue(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return '--'
  if (typeof value !== 'number') return value
  if (Math.abs(value) >= 100) return value.toFixed(0)
  if (Math.abs(value) >= 10) return value.toFixed(1)
  return value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '')
}

async function saveLayout() {
  await runAction(() => apiPut('/signals/dashboard-layout', { layout: { preset: 'default' } }), '自定义布局')
}

async function saveWatchlist() {
  await runAction(() => apiPut('/signals/watchlist', { signals: data.value.watchlist.map((item) => item.signal_name) }), '保存配置')
}

async function exportSnapshot() {
  await runAction(() => apiPost('/signals/snapshot'), '导出快照')
}

async function resetLayout() {
  await runAction(() => apiPost('/signals/dashboard-layout/reset'), '重置布局')
}

async function runAction(action: () => Promise<unknown>, label: string) {
  try {
    const result = await action() as { message?: string; details?: Record<string, unknown> }
    const url = typeof result.details?.download_url === 'string' ? result.details.download_url : ''
    if (url) await apiDownload(url, typeof result.details?.file_name === 'string' ? result.details.file_name : undefined)
    showToast(`${label}：${result.message || '完成'}`)
  } catch (error) {
    showToast(`${label}：${formatApiError(error)}`)
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
.signal-dashboard-page {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: grid;
  grid-template-rows: 56px 310px 220px minmax(0, 1fr);
  gap: 12px;
  color: #d7e7fb;
}

.page-header,
.panel {
  border: 1px solid rgba(30, 58, 95, .98);
  border-radius: 8px;
  background: linear-gradient(145deg, rgba(16, 36, 61, .96), rgba(10, 22, 40, .98));
  box-shadow: inset 0 1px 0 rgba(84, 138, 203, .12), 0 12px 28px rgba(0, 0, 0, .16);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 8px 14px;
}

.title-block,
.card-title,
.row-label,
.watch-actions,
.header-action {
  display: flex;
  align-items: center;
}

.title-block {
  gap: 12px;
  min-width: 0;
}

.title-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  color: #8FC4FF;
  border: 1px solid rgba(47, 128, 255, .45);
  border-radius: 8px;
  background: linear-gradient(145deg, rgba(47, 128, 255, .28), rgba(47, 128, 255, .08));
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  font-size: 20px;
  font-weight: 760;
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

button {
  border: 0;
  font: inherit;
  cursor: pointer;
}

.header-action,
.watch-actions button {
  gap: 7px;
  height: 34px;
  padding: 0 12px;
  color: #CFE4FF;
  border: 1px solid rgba(47, 128, 255, .48);
  border-radius: 6px;
  background: linear-gradient(180deg, rgba(47, 128, 255, .24), rgba(47, 128, 255, .10));
  font-size: 12px;
}

.watch-actions {
  gap: 8px;
}

.watch-actions button {
  height: 28px;
  padding: 0 10px;
}

.row {
  min-height: 0;
  display: grid;
  gap: 12px;
}

.row-one {
  grid-template-columns: 1.1fr .77fr 1fr;
}

.row-two {
  grid-template-columns: 1fr .82fr .9fr;
}

.row-three {
  grid-template-columns: .56fr 2.34fr;
}

.panel {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.card-head {
  height: 42px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(30, 58, 95, .82);
}

.card-title {
  gap: 8px;
}

.card-head h2,
.watch-head h2 {
  font-size: 15px;
  font-weight: 720;
}

.head-icon {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  color: #6FB0FF;
  border-radius: 6px;
  background: rgba(47, 128, 255, .14);
}

.status-badge {
  min-width: 50px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #39F172;
  border: 1px solid rgba(33, 197, 93, .48);
  border-radius: 6px;
  background: rgba(33, 197, 93, .10);
  font-size: 12px;
  font-weight: 700;
}

.bms-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 2px;
  padding: 10px;
}

.metric-tile {
  min-width: 0;
  min-height: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 8px 11px;
  border: 1px solid rgba(30, 58, 95, .92);
  border-radius: 6px;
  background: rgba(8, 26, 45, .72);
}

.metric-tile span,
.light-item span,
.trend-block span,
.heartbeat-tile span {
  color: #9CB5D5;
  font-size: 12px;
}

.metric-tile strong {
  color: #EAF2FF;
  font-size: 27px;
  line-height: 1;
  font-weight: 780;
}

.metric-tile small {
  color: #D7E7FB;
  font-size: 16px;
  font-weight: 650;
}

.metric-tile.blue strong,
.value-cell.blue {
  color: #58A5FF;
}

.metric-tile.green strong,
.value-cell.green {
  color: #32E56D;
}

.metric-tile.discharge strong {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #32E56D;
  font-size: 22px;
}

.sparkline {
  width: 100%;
  height: 28px;
  opacity: .95;
}

.vehicle-list {
  flex: 1;
  min-height: 0;
  padding: 8px 12px 10px;
  display: grid;
  grid-template-rows: repeat(5, 1fr);
}

.vehicle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(30, 58, 95, .75);
}

.vehicle-row:last-child {
  border-bottom: 0;
}

.row-label {
  gap: 9px;
  color: #A9BCD8;
  font-size: 13px;
}

.row-label svg {
  color: #9CB5D5;
}

.vehicle-row strong {
  color: #EAF2FF;
  font-size: 23px;
  font-weight: 780;
}

.vehicle-row strong.accent {
  color: #39F172;
  font-size: 18px;
}

.wheel-layout {
  flex: 1;
  min-height: 0;
  position: relative;
  padding: 14px 18px 18px;
}

.wheel-value {
  position: absolute;
  width: 138px;
  height: 78px;
  display: grid;
  place-content: center;
  gap: 6px;
  border: 1px solid rgba(50, 86, 135, .95);
  border-radius: 7px;
  background: rgba(8, 26, 45, .74);
}

.wheel-value span {
  color: #B3C8E2;
  font-size: 13px;
  text-align: center;
}

.wheel-value strong {
  color: #58A5FF;
  font-size: 32px;
  line-height: 1;
}

.wheel-fl { left: 18px; top: 16px; }
.wheel-fr { right: 18px; top: 16px; }
.wheel-rl { left: 18px; bottom: 20px; }
.wheel-rr { right: 18px; bottom: 20px; }

.chassis-diagram {
  position: absolute;
  inset: 22px 168px 20px;
}

.spine {
  position: absolute;
  left: 50%;
  top: 20px;
  bottom: 20px;
  width: 12px;
  transform: translateX(-50%);
  border: 1px solid rgba(159, 185, 216, .72);
  background: linear-gradient(180deg, rgba(127, 160, 194, .48), rgba(57, 83, 113, .35));
}

.body.center {
  position: absolute;
  left: 50%;
  top: 46%;
  width: 34px;
  height: 58px;
  transform: translate(-50%, -50%);
  border: 1px solid rgba(159, 185, 216, .76);
  border-radius: 5px;
  background: rgba(97, 127, 158, .42);
}

.axle {
  position: absolute;
  left: 25%;
  right: 25%;
  height: 7px;
  border: 1px solid rgba(159, 185, 216, .68);
  background: rgba(83, 110, 143, .35);
}

.axle.front { top: 40px; }
.axle.rear { bottom: 40px; }

.wheel {
  position: absolute;
  width: 22px;
  height: 62px;
  border: 1px solid rgba(159, 185, 216, .68);
  border-radius: 8px;
  background: repeating-linear-gradient(90deg, rgba(146, 168, 193, .42), rgba(146, 168, 193, .42) 2px, rgba(68, 91, 119, .45) 3px, rgba(68, 91, 119, .45) 5px);
}

.w1 { left: 18%; top: 10px; }
.w2 { right: 18%; top: 10px; }
.w3 { left: 18%; bottom: 10px; }
.w4 { right: 18%; bottom: 10px; }

.split-trends,
.motor-grid,
.light-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 8px;
  padding: 10px;
}

.split-trends {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.trend-block,
.heartbeat-tile {
  min-width: 0;
  min-height: 0;
  border: 1px solid rgba(30, 58, 95, .9);
  border-radius: 7px;
  background: rgba(8, 26, 45, .72);
  padding: 9px 10px;
}

.trend-block strong {
  display: block;
  margin-top: 5px;
  color: #EAF2FF;
  font-size: 30px;
  line-height: 1;
}

.trend-block small {
  font-size: 16px;
}

.trend-block p {
  margin-top: 7px;
  color: #C0D0E5;
  font-size: 12px;
}

.mini-chart {
  position: relative;
  height: 72px;
  margin-top: 5px;
  padding: 6px 2px 0 26px;
  background-image: linear-gradient(rgba(72,119,170,.18) 1px, transparent 1px), linear-gradient(90deg, rgba(72,119,170,.18) 1px, transparent 1px);
  background-size: 100% 24px, 28px 100%;
}

.mini-chart .sparkline {
  height: 58px;
}

.axis {
  position: absolute;
  left: 0;
  color: #8EA7C8;
  font-size: 10px;
}

.axis.top { top: 3px; }
.axis.bottom { bottom: 0; }

.motor-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.heartbeat-tile {
  display: grid;
  place-items: center;
  text-align: center;
}

.heartbeat-tile strong {
  color: #EAF2FF;
  font-size: 17px;
}

.heartbeat-tile em {
  min-width: 82px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #39F172;
  border: 1px solid rgba(33, 197, 93, .48);
  border-radius: 7px;
  background: rgba(33, 197, 93, .10);
  font-style: normal;
  font-size: 18px;
  font-weight: 760;
}

.light-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0;
  padding: 10px;
}

.light-item {
  min-width: 0;
  display: grid;
  place-items: center;
  gap: 10px;
  border-right: 1px solid rgba(30, 58, 95, .78);
  color: #CCD9EA;
  background: rgba(8, 26, 45, .46);
}

.light-item:first-child {
  border-radius: 7px 0 0 7px;
}

.light-item:last-child {
  border-right: 0;
  border-radius: 0 7px 7px 0;
}

.light-item i {
  display: grid;
  place-items: center;
  height: 34px;
  color: #BFD3EE;
  font-style: normal;
}

.light-item.active i,
.light-item.active strong {
  color: #39F172;
}

.light-item.danger i {
  color: #EF4444;
}

.light-item strong {
  color: #EAF2FF;
  font-size: 15px;
}

.alarm-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: .88fr 1.18fr;
  gap: 10px;
  padding: 10px;
}

.alarm-level {
  display: grid;
  place-items: center;
  border-right: 1px solid rgba(30, 58, 95, .82);
}

.alarm-level span,
.alarm-level em {
  color: #B8C9E0;
  font-size: 13px;
  font-style: normal;
}

.alarm-level strong {
  color: #39F172;
  font-size: 52px;
  line-height: 1;
}

.threshold-list {
  min-width: 0;
  display: grid;
  align-content: center;
  gap: 9px;
}

.threshold-list h3 {
  color: #BFD2EA;
  font-size: 13px;
}

.threshold-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  color: #B8C9E0;
  font-size: 12px;
}

.threshold-row b {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #39F172;
  font-weight: 650;
}

.threshold-row i {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #21C55D;
  box-shadow: 0 0 10px rgba(33, 197, 93, .72);
}

.watch-head {
  height: 44px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(30, 58, 95, .82);
}

.watch-head span {
  color: #8EA7C8;
  font-size: 11px;
}

.watch-table-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
  scrollbar-color: #28527D #081A2D;
}

.watch-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.watch-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  height: 31px;
  color: #94ACCA;
  background: #0A1A2D;
  border-bottom: 1px solid rgba(30, 58, 95, .9);
  font-size: 11px;
  font-weight: 650;
}

.watch-table td {
  height: 31px;
  padding: 0 9px;
  color: #D7E7FB;
  border-bottom: 1px solid rgba(30, 58, 95, .48);
  border-right: 1px solid rgba(30, 58, 95, .36);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.watch-table th:nth-child(1) { width: 150px; }
.watch-table th:nth-child(2) { width: 88px; }
.watch-table th:nth-child(3) { width: 78px; }
.watch-table th:nth-child(4) { width: 94px; }
.watch-table th:nth-child(5) { width: 70px; }
.watch-table th:nth-child(6) { width: 136px; }
.watch-table th:nth-child(7) { width: 88px; }
.watch-table th:nth-child(8) { width: 184px; }
.watch-table th:nth-child(9) { width: 126px; }

.watch-table tbody tr:hover {
  background: rgba(47, 128, 255, .10);
}

.mono {
  font-family: Consolas, Monaco, monospace;
}

.value-cell {
  font-weight: 760;
}

.quality {
  color: #39F172;
  font-weight: 700;
}

.watch-table .sparkline {
  height: 20px;
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
  .signal-dashboard-page {
    grid-template-rows: 54px 292px 210px minmax(0, 1fr);
    gap: 10px;
  }

  .row {
    gap: 10px;
  }

  .metric-tile strong {
    font-size: 23px;
  }

  .wheel-value {
    width: 112px;
  }

  .chassis-diagram {
    left: 135px;
    right: 135px;
  }
}
</style>
