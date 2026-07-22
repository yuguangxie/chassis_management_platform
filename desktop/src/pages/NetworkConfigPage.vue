<template>
  <div class="network-page">
    <section class="page-title">
      <div class="title-left">
        <div class="title-icon"><Network :size="22" /></div>
        <div>
          <h1>网络与 CAN 通道配置</h1>
          <p>双通道通信参数、连接自检与控制通道配置</p>
        </div>
      </div>
      <div class="title-actions">
        <PageDataState :loading="loading" :error="error" :stale="offline" :empty="!config.channels.length" />
        <button class="help-btn" type="button" disabled title="尚未实现：联机帮助文档入口"><CircleHelp :size="16" />使用说明（尚未实现）</button>
      </div>
    </section>

    <section class="top-grid">
      <article class="panel local-panel">
        <header class="panel-head">
          <div><Network :size="18" /><h2>本机网络</h2></div>
        </header>
        <div class="form-list">
          <div class="field-row">
            <span>工控机 IP</span>
            <b>{{ config.local_network.host_ip }}</b>
          </div>
          <div class="field-row">
            <span>选中网卡</span>
            <button class="select-like" type="button" disabled title="网卡只能通过经过校验的配置包修改">{{ config.local_network.nic_name }}<ChevronDown :size="14" /></button>
          </div>
          <div class="field-row">
            <span>子网掩码</span>
            <b>{{ config.local_network.subnet_mask }}</b>
          </div>
          <div class="field-row">
            <span>链路速率</span>
            <b>{{ config.local_network.link_speed }}</b>
          </div>
        </div>
        <div class="port-box">
          <div class="port-head">
            <span>端口占用检测</span>
            <button type="button" title="刷新检测" @click="() => runSelfTest()"><RefreshCw :size="16" /></button>
          </div>
          <div class="port-grid">
            <div v-for="port in config.local_network.ports" :key="port.port">
              <span>{{ port.port }} {{ port.protocol }}</span>
              <b>{{ portStatusLabel(port.status) }}</b>
            </div>
          </div>
        </div>
      </article>

      <article v-for="channel in config.channels" :key="channel.name" class="panel channel-panel">
        <header class="panel-head">
          <div><Network :size="18" /><h2>{{ channel.name }} 配置（通道{{ channel.name === 'CAN1' ? '1' : '2' }}）</h2></div>
        </header>
        <div class="channel-form">
          <div class="seg-row">
            <span>协议选择</span>
            <div class="segmented">
              <button :class="{ active: channel.protocol === 'UDP' }" type="button" :disabled="!auth.isAdmin" @click="channel.protocol = 'UDP'">UDP</button>
              <button :class="{ active: channel.protocol === 'TCP' }" type="button" :disabled="!auth.isAdmin" @click="channel.protocol = 'TCP'">TCP</button>
            </div>
          </div>
          <ConfigInput label="本地IP" :value="channel.local_ip" :editable="auth.isAdmin" @update:value="channel.local_ip = $event" />
          <ConfigInput label="本地端口" :value="String(channel.local_port)" :editable="auth.isAdmin" input-type="number" @update:value="channel.local_port = Number($event)" />
          <ConfigInput label="设备IP" :value="channel.device_ip" :editable="auth.isAdmin" @update:value="channel.device_ip = $event" />
          <ConfigInput label="设备端口" :value="String(channel.device_port)" :editable="auth.isAdmin" input-type="number" @update:value="channel.device_port = Number($event)" />
          <div class="switch-grid">
            <span>发送允许</span><ToggleVisual :enabled="channel.tx_enabled" />
            <span>接收状态</span><ActiveState :status="channel.rx_status" />
          </div>
          <div class="period-row">
            <span>发送周期</span>
            <div class="input-like"><b>{{ channel.period_ms }}</b><em>ms</em></div>
          </div>
          <div class="switch-grid last">
            <span>{{ channel.name === 'CAN2' ? '默认控制通道' : '控制权限' }}</span>
            <ToggleVisual :enabled="channel.control_enabled" :disabled="!channel.control_enabled" />
            <span class="switch-label" :class="{ enabled: channel.control_enabled }">{{ channel.control_enabled ? 'enabled' : 'disabled' }}</span>
          </div>
        </div>
      </article>

      <article class="panel diagnosis-panel">
        <header class="panel-head">
          <div><Activity :size="18" /><h2>连接诊断与自检</h2></div>
        </header>
        <div class="diagnosis-list">
          <div v-for="item in diagnosisRows" :key="item.label" class="diagnosis-row">
            <span>{{ item.label }}</span>
            <b>{{ item.value }}</b>
            <CircleCheck v-if="item.ok" :size="17" />
            <CircleX v-else :size="17" class="diagnosis-fail" />
          </div>
        </div>
        <button class="retest-btn" type="button" @click="() => runSelfTest()"><RefreshCw :size="16" />重新检测</button>
      </article>
    </section>

    <section class="middle-grid">
      <article class="panel table-panel">
        <header class="panel-head">
          <div><ListChecks :size="18" /><h2>通道配置总览</h2></div>
        </header>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>通道</th><th>协议</th><th>本地IP</th><th>本地端口</th><th>设备IP</th><th>设备端口</th><th>控制通道</th><th>发送周期</th><th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="channel in config.channels" :key="channel.name">
                <td>{{ channel.name }}</td>
                <td>{{ channel.protocol }}</td>
                <td>{{ channel.local_ip }}</td>
                <td>{{ channel.local_port }}</td>
                <td>{{ channel.device_ip }}</td>
                <td>{{ channel.device_port }}</td>
                <td>{{ channel.control_enabled ? '是（默认）' : '否' }}</td>
                <td>{{ channel.period_ms }} ms</td>
                <td><ActiveState :status="channel.status" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="info-note"><Info :size="16" />说明：系统默认使用 UDP 协议进行通信，界面保留 TCP 选项以兼容特殊场景需求。</div>
      </article>

      <article class="panel chart-panel">
        <header class="panel-head chart-head">
          <div><Activity :size="18" /><h2>各通道帧率（fps）趋势</h2></div>
          <button class="mini-select" type="button" disabled title="当前后端仅提供最近一分钟聚合">最近1分钟 <ChevronDown :size="13" /></button>
        </header>
        <RealtimeLineChart :option="fpsOption" />
      </article>

      <article class="panel chart-panel">
        <header class="panel-head chart-head">
          <div><BarChart3 :size="18" /><h2>错误帧累计（个）</h2></div>
          <button class="mini-select" type="button" disabled title="当前后端仅提供累计错误摘要">当前累计 <ChevronDown :size="13" /></button>
        </header>
        <BarChart :option="errorOption" />
      </article>
    </section>

    <section class="action-row">
      <button v-for="action in visibleActions" :key="action.title" :class="['action-card', action.tone]" type="button" :disabled="loading || (offline && !action.allowOffline)" @click="action.run">
        <span class="action-icon"><component :is="action.icon" :size="31" /></span>
        <span>
          <strong>{{ action.title }}</strong>
          <small>{{ action.desc }}</small>
        </span>
      </button>
    </section>

    <p v-if="toast" :class="['toast', toastTone]">{{ toast }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Activity,
  BarChart3,
  ChevronDown,
  CircleCheck,
  CircleHelp,
  CircleX,
  Info,
  ListChecks,
  Network,
  PlayCircle,
  RefreshCw,
  Save,
  Square,
} from 'lucide-vue-next'
import BarChart from '../components/charts/BarChart.vue'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import { apiGet, apiPost, apiPut, formatApiError } from '../api/http'
import type { CanMonitorStatistics, NetworkChannelConfig, NetworkConfigSummary, NetworkSelfTestResult } from '../api/types'
import { fallbackCanMonitorStatistics, fallbackNetworkConfig, fallbackNetworkSelfTest } from '../mocks/fallbackData'
import { useAuthStore, type Role } from '../stores/auth'
import PageDataState from '../components/PageDataState.vue'

const ConfigInput = defineComponent({
  props: { label: { type: String, required: true }, value: { type: String, required: true }, editable: { type: Boolean, default: false }, inputType: { type: String, default: 'text' } },
  emits: ['update:value'],
  setup(props, { emit }) {
    return () => h('div', { class: 'field-row compact-field' }, [
      h('span', props.label),
      props.editable
        ? h('input', { class: 'input-like text-input', type: props.inputType, value: props.value, onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value) })
        : h('b', { class: 'input-like text-input' }, props.value),
    ])
  },
})

const ToggleVisual = defineComponent({
  props: { enabled: { type: Boolean, required: true }, disabled: { type: Boolean, default: false } },
  setup(props) {
    return () => h('span', { class: ['toggle-visual', props.enabled ? 'on' : 'off', props.disabled && !props.enabled ? 'disabled' : ''] }, [h('i')])
  },
})

const ActiveState = defineComponent({
  props: { status: { type: String, required: true } },
  setup(props) {
    return () => h('span', { class: ['active-state', props.status === 'active' ? 'on' : 'off'] }, [
      h('i'),
      props.status || 'unknown',
    ])
  },
})

const config = ref<NetworkConfigSummary>(structuredClone(fallbackNetworkConfig))
const auth = useAuthStore()
const selfTest = ref<NetworkSelfTestResult>(fallbackNetworkSelfTest)
const statistics = ref<CanMonitorStatistics>(structuredClone(fallbackCanMonitorStatistics))
const loading = ref(false)
const offline = ref(false)
const error = ref('')
const appliedConfig = ref<NetworkConfigSummary>(structuredClone(fallbackNetworkConfig))

function cloneConfig(value: NetworkConfigSummary): NetworkConfigSummary {
  return JSON.parse(JSON.stringify(value)) as NetworkConfigSummary
}
const toast = ref('')
const toastTone = ref<'ok' | 'warn' | 'bad'>('ok')
let toastTimer: number | undefined

const diagnosisRows = computed(() => [
  { label: '端点测量延迟', value: selfTest.value.ping_latency_ms === null ? '未测量（不伪造 ping）' : `${selfTest.value.ping_latency_ms.toFixed(2)} ms`, ok: selfTest.value.ping_latency_ms !== null },
  { label: 'UDP 收帧确认（批准来源）', value: selfTest.value.udp_loopback === 'pass' ? '通过' : '未确认', ok: selfTest.value.udp_loopback === 'pass' },
  { label: '13字节协议合法率', value: `${selfTest.value.protocol_valid_rate.toFixed(2)} %`, ok: selfTest.value.protocol_valid_rate === 100 },
  { label: 'DLC 校验', value: selfTest.value.dlc_check === 'pass' ? '通过' : '失败', ok: selfTest.value.dlc_check === 'pass' },
  { label: '保留位校验', value: selfTest.value.reserved_bits_check === 'pass' ? '通过' : '失败', ok: selfTest.value.reserved_bits_check === 'pass' },
  { label: '粘包/半包统计（1分钟）', value: `${selfTest.value.sticky_half_packets.sticky} / ${selfTest.value.sticky_half_packets.half}`, ok: selfTest.value.sticky_half_packets.half === 0 },
  { label: '最近错误', value: selfTest.value.last_error || '无', ok: !selfTest.value.last_error },
  ...(selfTest.value.channels||[]).map(item=>({label:`${item.channel} 端点/收帧/TCP`,value:`${item.bind_status} / ${item.endpoint_status} / ${formatFrameAge(item.last_frame_age_ms)} / ${item.tcp_state}`,ok:item.bind_status !== 'occupied_or_unbindable' && item.endpoint_status === 'receive_confirmed'})),
])

function portStatusLabel(status:string){return({owned_by_runtime:'当前进程使用',available:'可绑定',occupied_or_unbindable:'占用/不可绑定',not_diagnosed:'未检测','not-diagnosed':'未检测'} as Record<string,string>)[status]||status}
function formatFrameAge(value:number|null|undefined){return value===null||value===undefined?'无批准来源帧':`${Math.round(value)} ms`}

function mergeConfig(data: Partial<NetworkConfigSummary>): NetworkConfigSummary {
  const next = {
    ...fallbackNetworkConfig,
    ...data,
    local_network: { ...fallbackNetworkConfig.local_network, ...data.local_network },
    channels: data.channels?.length ? data.channels : fallbackNetworkConfig.channels,
  }
  next.local_network.ports = next.local_network.ports?.length ? next.local_network.ports : fallbackNetworkConfig.local_network.ports
  return structuredClone(next)
}

async function loadConfig() {
  loading.value = true
  try {
    const data = await apiGet<NetworkConfigSummary>('/config/channels')
    config.value = mergeConfig(data)
    appliedConfig.value = cloneConfig(config.value)
    offline.value = false
    error.value = ''
  } catch (cause) {
    config.value = structuredClone(fallbackNetworkConfig)
    offline.value = true
    appliedConfig.value = cloneConfig(config.value)
    error.value = formatApiError(cause)
  } finally {
    loading.value = false
  }
}

async function loadStatistics() {
  try {
    statistics.value = await apiGet<CanMonitorStatistics>('/can/statistics/monitor')
  } catch (cause) {
    statistics.value = { ...structuredClone(fallbackCanMonitorStatistics), fps_trend: [], period_jitter: [], can_id_distribution: [], footer_status: { ...fallbackCanMonitorStatistics.footer_status, rx_fps: 0, tx_fps: 0 } }
    error.value = formatApiError(cause)
  }
}

function showToast(message: string, tone: 'ok' | 'warn' | 'bad' = 'ok') {
  toast.value = message
  toastTone.value = tone
  if (toastTimer) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => { toast.value = '' }, 2800)
}

async function saveConfig() {
  try {
    const response = await apiPut<NetworkConfigSummary & { message?: string; saved?: boolean; reconnected?: boolean }>('/config/channels', config.value)
    config.value = mergeConfig(response)
    appliedConfig.value = cloneConfig(config.value)
    error.value = ''
    await Promise.all([runSelfTest(false), loadStatistics()])
    showToast(response.message || '配置已保存、应用并通过运行态重连')
  } catch (cause) {
    config.value = cloneConfig(appliedConfig.value)
    error.value = formatApiError(cause)
    showToast(`配置应用失败，界面已回滚到上一已应用版本：${error.value}`, 'bad')
  }
}

async function runSelfTest(notify = true) {
  try {
    const result = await apiPost<NetworkSelfTestResult>('/can/channels/self-test', {})
    selfTest.value = { ...fallbackNetworkSelfTest, ...result }
    for(const measurement of result.channels||[]){const channel=config.value.channels.find(item=>item.name===measurement.channel);if(channel)Object.assign(channel,measurement)}
    error.value = ''
    offline.value = false
    if (notify) showToast(result.message || '连接自检完成')
  } catch (cause) {
    selfTest.value = { ...fallbackNetworkSelfTest, ping_latency_ms: null, udp_loopback: 'unavailable', protocol_valid_rate: 0, last_error: '诊断未执行' }
    error.value = formatApiError(cause)
    if (notify) showToast(`诊断未执行：${error.value}`, 'bad')
  }
}

async function connectChannel(channel: NetworkChannelConfig['name']) {
  try {
    const result = await apiPost<{ message?: string; stub?: boolean }>(`/can/channels/${channel}/connect`, {})
    showToast(result.message || `${channel} 已启动`)
  } catch (error) {
    showToast(error instanceof Error ? error.message : `${channel} 启动失败`, 'bad')
  }
}

async function stopAll() {
  try {
    const result = await apiPost<{ message?: string; stub?: boolean }>('/can/channels/stop-all', {})
    showToast(result.message || '所有通道已停止', result.stub ? 'warn' : 'ok')
  } catch (error) {
    showToast(error instanceof Error ? error.message : '停止全部失败', 'bad')
  }
}

async function restoreDefaults() {
  try {
    const result = await apiPost<NetworkConfigSummary & { message?: string }>('/config/channels/restore-defaults', {})
    config.value = mergeConfig(result)
    appliedConfig.value = cloneConfig(config.value)
    showToast(result.message || '已恢复并应用回环安全默认配置')
  } catch (cause) {
    config.value = cloneConfig(appliedConfig.value)
    error.value = formatApiError(cause)
    showToast(`恢复默认值失败，未改变当前运行配置：${error.value}`, 'bad')
  }
}

const actions = [
  { title: '保存并应用', desc: '原子应用，失败自动回滚', icon: Save, tone: 'primary', run: saveConfig, role: 'admin' as Role, allowOffline: false },
  { title: '测试连接', desc: '执行端口与设备诊断', icon: Network, tone: 'primary', run: () => runSelfTest(), role: 'engineer' as Role, allowOffline: true },
  { title: '启动CAN1', desc: '启动通道1通信', icon: PlayCircle, tone: 'primary', run: () => connectChannel('CAN1'), role: 'engineer' as Role, allowOffline: false },
  { title: '启动CAN2', desc: '启动通道2通信', icon: PlayCircle, tone: 'primary', run: () => connectChannel('CAN2'), role: 'engineer' as Role, allowOffline: false },
  { title: '停止全部', desc: '停止所有通道通信', icon: Square, tone: 'danger', run: stopAll, role: 'engineer' as Role, allowOffline: false },
  { title: '恢复默认', desc: '恢复回环安全默认配置', icon: RefreshCw, tone: 'primary', run: restoreDefaults, role: 'admin' as Role, allowOffline: false },
]
const visibleActions = computed(() => actions.filter((action) => auth.can(action.role)))

const chartText = '#AFC2DD'
const gridLine = '#1E3A5F'
const timeline = computed(() => offline.value ? [] : statistics.value.fps_trend.map(item => item.time.slice(0, 5)))

const fpsOption = computed(() => ({
  backgroundColor: 'transparent',
  legend: { top: 2, right: 6, itemWidth: 16, itemHeight: 8, textStyle: { color: chartText, fontSize: 12 } },
  grid: { left: 42, right: 16, top: 34, bottom: 28 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: timeline.value, boundaryGap: false, axisLine: { lineStyle: { color: gridLine } }, axisTick: { show: false }, axisLabel: { color: chartText, fontSize: 11 } },
  yAxis: { type: 'value', min: 0, max: 1500, interval: 300, splitLine: { lineStyle: { color: gridLine, type: 'dashed' } }, axisLabel: { color: chartText, fontSize: 11 } },
  series: [
    { name: 'CAN1', type: 'line', smooth: true, showSymbol: true, symbolSize: 5, lineStyle: { color: '#21C55D', width: 3 }, itemStyle: { color: '#21C55D' }, data: offline.value ? [] : statistics.value.fps_trend.map(item=>item.can1) },
    { name: 'CAN2', type: 'line', smooth: true, showSymbol: true, symbolSize: 5, lineStyle: { color: '#2F80FF', width: 3 }, itemStyle: { color: '#2F80FF' }, data: offline.value ? [] : statistics.value.fps_trend.map(item=>item.can2) },
  ],
}))

const errorOption = computed(() => ({
  backgroundColor: 'transparent',
  legend: { top: 2, right: 6, itemWidth: 16, itemHeight: 8, textStyle: { color: chartText, fontSize: 12 } },
  grid: { left: 34, right: 14, top: 34, bottom: 28 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: ['超时', '错误帧', '协议错误'], axisLine: { lineStyle: { color: gridLine } }, axisTick: { show: false }, axisLabel: { color: chartText, fontSize: 11 } },
  yAxis: { type: 'value', min: 0, max: 5, interval: 1, splitLine: { lineStyle: { color: gridLine } }, axisLabel: { color: chartText, fontSize: 11 } },
  series: [
    { name: '累计', type: 'bar', barWidth: 18, data: offline.value ? [] : [statistics.value.error_summary.timeout_count, statistics.value.error_summary.error_frame_count, statistics.value.error_summary.protocol_error_count], label: { show: true, position: 'top', color: '#CFE3FF', fontSize: 11 }, itemStyle: { color: '#2F80FF' } },
  ],
}))

onMounted(() => {
  void Promise.all([loadConfig(), loadStatistics()])
})

onBeforeUnmount(() => {
  if (toastTimer) window.clearTimeout(toastTimer)
})
</script>

<style scoped>
.network-page {
  position: relative;
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: 42px 365px minmax(0, 1fr) 116px;
  gap: 14px;
  overflow: hidden;
}

.page-title,
.panel,
.action-card {
  border: 1px solid #1E3A5F;
  background: linear-gradient(145deg, rgba(16, 36, 61, .96), rgba(9, 23, 42, .97));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .04), 0 10px 28px rgba(0, 0, 0, .12);
}

.page-title {
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 13px;
  min-width: 0;
}

.title-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: #A9D1FF;
  border: 1px solid rgba(47, 128, 255, .52);
  background: rgba(47, 128, 255, .14);
}

h1,
h2,
p {
  margin: 0;
}

.page-title h1 {
  font-size: 25px;
  line-height: 1;
  font-weight: 850;
}

.page-title p {
  margin-top: 6px;
  color: #8FA5C4;
  font-size: 13px;
}

.title-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mock-pill,
.help-btn,
.mini-select,
.retest-btn {
  height: 32px;
  border-radius: 6px;
  border: 1px solid rgba(47, 128, 255, .45);
  background: rgba(47, 128, 255, .08);
  color: #DCEBFF;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 12px;
  font-size: 13px;
}

.mock-pill {
  border-color: rgba(246, 195, 67, .52);
  color: #F6C343;
  background: rgba(246, 195, 67, .08);
}

.mock-pill.loading {
  border-color: rgba(47, 128, 255, .45);
  color: #9CCBFF;
}

.top-grid {
  display: grid;
  grid-template-columns: 1.05fr 1.08fr 1.08fr 1.12fr;
  gap: 14px;
  min-height: 0;
}

.middle-grid {
  display: grid;
  grid-template-columns: 1.78fr .94fr .94fr;
  gap: 14px;
  min-height: 0;
}

.panel {
  border-radius: 9px;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.panel-head {
  height: 52px;
  padding: 0 14px;
  border-bottom: 1px solid rgba(30, 58, 95, .78);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-head > div {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.panel-head svg {
  color: #62A8FF;
  flex: 0 0 auto;
}

.panel-head h2 {
  color: #F1F7FF;
  font-size: 16px;
  font-weight: 820;
  white-space: nowrap;
}

.form-list,
.channel-form {
  padding: 12px 14px 0;
}

.field-row,
.seg-row,
.period-row {
  min-height: 38px;
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  align-items: center;
  border-bottom: 1px solid rgba(30, 58, 95, .58);
}

.field-row span,
.seg-row span,
.period-row span,
.switch-grid span {
  color: #9BAECB;
  font-size: 13px;
}

.field-row b {
  color: #EAF2FF;
  font-size: 13px;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-field {
  grid-template-columns: 84px minmax(0, 1fr);
}

.select-like,
.input-like {
  min-width: 0;
  height: 31px;
  border: 1px solid rgba(47, 128, 255, .24);
  border-radius: 5px;
  background: rgba(7, 17, 31, .46);
  color: #DDEBFF;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 10px;
  font-size: 12px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.input-like {
  color: #EAF2FF;
  font-weight: 750;
}

.text-input {
  justify-content: flex-start;
}
input.text-input{width:100%;outline:none;font-family:inherit;font-weight:700}

.input-like em {
  color: #9BAECB;
  font-style: normal;
  font-weight: 500;
}

.port-box {
  margin: 10px 14px 0;
  border: 1px solid rgba(30, 58, 95, .82);
  border-radius: 7px;
  overflow: hidden;
}

.port-head {
  height: 40px;
  padding: 0 12px;
  border-bottom: 1px solid rgba(30, 58, 95, .66);
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #DCEBFF;
  font-weight: 700;
}

.port-head button {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 5px;
  background: rgba(47, 128, 255, .1);
  color: #9CCBFF;
  display: grid;
  place-items: center;
}

.port-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.port-grid div {
  height: 41px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-right: 1px solid rgba(30, 58, 95, .66);
}

.port-grid div:last-child {
  border-right: 0;
}

.port-grid span {
  color: #DDEBFF;
  font-weight: 700;
}

.port-grid b {
  color: #21C55D;
}

.segmented {
  height: 31px;
  border: 1px solid rgba(47, 128, 255, .28);
  border-radius: 5px;
  padding: 2px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  background: rgba(7, 17, 31, .35);
}

.segmented button {
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #C1D1E8;
}

.segmented button.active {
  color: #FFFFFF;
  background: linear-gradient(180deg, #0E65D8, #0B4FAE);
  box-shadow: 0 0 14px rgba(47, 128, 255, .25);
}

.switch-grid {
  min-height: 38px;
  display: grid;
  grid-template-columns: 84px 62px 84px minmax(0, 1fr);
  align-items: center;
  border-bottom: 1px solid rgba(30, 58, 95, .58);
}

.switch-grid.last {
  grid-template-columns: 118px 62px minmax(0, 1fr);
  border-bottom: 0;
}

.toggle-visual {
  width: 42px;
  height: 22px;
  border-radius: 999px;
  padding: 2px;
  display: inline-flex;
  align-items: center;
  background: #314158;
  border: 1px solid #43536B;
}

.toggle-visual i {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #DDE8F8;
  transition: transform .16s ease;
}

.toggle-visual.on {
  background: linear-gradient(90deg, #21C55D, #39D67A);
  border-color: rgba(80, 230, 135, .7);
}

.toggle-visual.on i {
  transform: translateX(18px);
}

.toggle-visual.disabled {
  opacity: .72;
}

.switch-label {
  color: #8FA5C4;
  font-weight: 700;
}

.switch-label.enabled {
  color: #21C55D;
}

.active-state {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #9BAECB;
  font-weight: 750;
}

.active-state i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #66758A;
}

.active-state.on {
  color: #21C55D;
}

.active-state.on i {
  background: #21C55D;
  box-shadow: 0 0 10px rgba(33, 197, 93, .8);
}

.diagnosis-list {
  margin: 12px 14px 0;
  border: 1px solid rgba(30, 58, 95, .82);
  border-radius: 7px;
  overflow: hidden;
}

.diagnosis-row {
  height: 34px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 88px 24px;
  align-items: center;
  padding: 0 10px;
  border-bottom: 1px solid rgba(30, 58, 95, .6);
}

.diagnosis-row:last-child {
  border-bottom: 0;
}

.diagnosis-row span {
  color: #B9C8DE;
  font-size: 13px;
}

.diagnosis-row b {
  color: #DDEBFF;
  text-align: right;
  font-size: 13px;
}

.diagnosis-row svg {
  justify-self: end;
  color: #21C55D;
  fill: rgba(33, 197, 93, .18);
}
.diagnosis-row svg.diagnosis-fail{color:#EF4444;fill:rgba(239,68,68,.16)}

.retest-btn {
  float: right;
  margin: 10px 14px 0 0;
  min-width: 132px;
}

.table-panel {
  display: grid;
  grid-template-rows: 52px minmax(0, 1fr) 44px;
}

.table-wrap {
  min-height: 0;
  overflow: hidden;
  padding: 14px 14px 0;
}

table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;
  border: 1px solid rgba(30, 58, 95, .82);
  border-radius: 7px;
  overflow: hidden;
}

th,
td {
  height: 42px;
  padding: 0 6px;
  text-align: center;
  border-right: 1px solid rgba(30, 58, 95, .62);
  border-bottom: 1px solid rgba(30, 58, 95, .62);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

th:last-child,
td:last-child {
  border-right: 0;
}

tbody tr:last-child td {
  border-bottom: 0;
}

th {
  color: #AFC2DD;
  background: rgba(7, 17, 31, .52);
  font-size: 12px;
}

td {
  color: #E2EEFF;
  font-size: 13px;
  font-weight: 650;
}

th:nth-child(1), td:nth-child(1) { width: 58px; }
th:nth-child(2), td:nth-child(2) { width: 54px; }
th:nth-child(3), td:nth-child(3) { width: 104px; }
th:nth-child(4), td:nth-child(4) { width: 66px; }
th:nth-child(5), td:nth-child(5) { width: 104px; }
th:nth-child(6), td:nth-child(6) { width: 66px; }
th:nth-child(7), td:nth-child(7) { width: 84px; }
th:nth-child(8), td:nth-child(8) { width: 76px; }
th:nth-child(9), td:nth-child(9) { width: 78px; }

.info-note {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 16px 13px;
  color: #9BAECB;
  font-size: 13px;
}

.info-note svg {
  color: #8BBFFF;
}

.chart-panel :deep(.chart) {
  height: calc(100% - 52px);
  min-height: 190px;
}

.mini-select {
  height: 28px;
  padding: 0 9px;
  color: #9FB3D0;
  background: rgba(7, 17, 31, .32);
  border-color: rgba(30, 58, 95, .84);
}

.action-row {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
}

.action-card {
  height: 100%;
  border-radius: 9px;
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 0 24px;
  color: #EAF2FF;
  text-align: left;
}
.action-card:disabled,.help-btn:disabled,.mini-select:disabled,.select-like:disabled{opacity:.5;cursor:not-allowed}

.action-card.primary {
  border-color: rgba(47, 128, 255, .78);
  background: linear-gradient(145deg, rgba(14, 56, 105, .92), rgba(11, 30, 53, .98));
}

.action-card.danger {
  border-color: rgba(239, 68, 68, .8);
  background: linear-gradient(145deg, rgba(84, 28, 40, .88), rgba(27, 25, 42, .98));
}

.action-card:hover {
  filter: brightness(1.08);
}

.action-icon {
  width: 58px;
  height: 58px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: #8EC3FF;
  border: 1px solid rgba(47, 128, 255, .65);
  background: rgba(47, 128, 255, .12);
}

.action-card.danger .action-icon {
  color: #FF9BA1;
  border-color: rgba(239, 68, 68, .78);
  background: rgba(239, 68, 68, .13);
}

.action-card strong,
.action-card small {
  display: block;
  white-space: nowrap;
}

.action-card strong {
  font-size: 18px;
  line-height: 1.2;
}

.action-card small {
  margin-top: 7px;
  color: #9DB0CB;
  font-size: 13px;
}

.toast {
  position: absolute;
  right: 16px;
  bottom: 132px;
  z-index: 5;
  max-width: 560px;
  margin: 0;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(7, 17, 31, .94);
  border: 1px solid currentColor;
  font-size: 13px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, .25);
}

.toast.ok { color: #21C55D; }
.toast.warn { color: #F6C343; }
.toast.bad { color: #EF4444; }

@media (max-width: 1500px), (max-height: 860px) {
  .network-page {
    height: auto;
    min-height: 100%;
    overflow: visible;
    grid-template-rows: 42px 340px 300px 104px;
    gap: 10px;
  }

  .top-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .middle-grid {
    grid-template-columns: 1fr;
  }

  .action-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
