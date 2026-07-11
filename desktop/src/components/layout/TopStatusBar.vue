<template>
  <header class="topbar">
    <div class="cell station"><span>工位</span><strong>{{ store.status.station_id }}</strong></div>
    <div class="cell"><span>用户</span><strong>{{ store.status.operator }}</strong></div>
    <div class="cell"><span>软件版本</span><strong>{{ store.status.software_version }}</strong></div>
    <div class="cell dbc"><span>DBC版本</span><strong :title="dbcVersion">{{ dbcVersion }}</strong></div>
    <div class="cell database">
      <span>数据库</span>
      <strong>SQLite <b :class="store.status.database.writable ? 'ok' : 'bad'">{{ store.status.database.writable ? '正常' : '异常' }}</b></strong>
    </div>
    <div class="cell"><span>控制通道</span><strong>{{ store.status.control_channel }}</strong></div>
    <div class="cell compact">
      <span>CAN1</span>
      <strong><i :class="['dot', can1.online ? 'on' : 'off']"></i>{{ can1.online ? 'online' : 'offline' }}</strong>
    </div>
    <div class="cell compact">
      <span>CAN2</span>
      <strong><i :class="['dot', can2.online ? 'on' : 'off']"></i>{{ can2.online ? 'online' : 'offline' }}</strong>
    </div>
    <div class="cell estop">
      <span>急停</span>
      <strong :class="store.status.emergency_stop ? 'bad-text' : ''"><i class="ring"></i>{{ store.status.emergency_stop ? '已触发' : '未触发' }}</strong>
    </div>
    <div class="cell alarm">
      <span>最高告警</span>
      <strong><b :class="store.status.max_alarm_level > 0 ? 'warn' : 'ok'">{{ store.status.max_alarm_level }}</b> {{ store.status.max_alarm_level > 0 ? 'Warning' : 'Normal' }}</strong>
    </div>
    <div class="cell time"><span>当前时间</span><strong>{{ time }}</strong></div>
    <div class="cell mock"><span>Mock</span><strong :class="store.status.mock_enabled ? 'warn-text' : ''">{{ store.status.mock_enabled ? '开启' : '关闭' }}</strong></div>
  </header>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { fallbackChannels } from '../../mocks/fallbackData'
import { useAppStatusStore } from '../../stores/appStatus'

const store = useAppStatusStore()
const time = ref('')
let timer: number | undefined

const dbcVersion = computed(() => store.status.dbc.version || 'Yunle_CAN_Integrated_CANdb')
const channelMap = computed(() => {
  const source = store.channels.length ? store.channels : (store.status.channels.length ? store.status.channels : fallbackChannels)
  return Object.fromEntries(source.map((item) => [item.channel, item]))
})
const can1 = computed(() => channelMap.value.CAN1 ?? fallbackChannels[0])
const can2 = computed(() => channelMap.value.CAN2 ?? fallbackChannels[1])

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function formatLocalTime(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function tick() {
  time.value = formatLocalTime(new Date())
}

onMounted(() => {
  tick()
  timer = window.setInterval(tick, 1000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.topbar {
  height: var(--topbar-height);
  display: grid;
  grid-template-columns: 150px 82px 112px minmax(190px, 1.2fr) 142px 112px 90px 90px 112px 132px 178px 74px;
  align-items: stretch;
  background: linear-gradient(180deg, #0A1729, #081425);
  border-bottom: 1px solid #1E3A5F;
  overflow: hidden;
}

.cell {
  min-width: 0;
  padding: 12px 11px 10px;
  border-right: 1px solid rgba(30, 58, 95, .92);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 7px;
}

.cell span {
  color: #8FA5C4;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.cell strong {
  min-width: 0;
  color: #EAF2FF;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.station strong,
.time strong {
  font-family: Consolas, 'Microsoft YaHei UI', sans-serif;
  letter-spacing: 0;
}

.dbc strong {
  max-width: 100%;
}

.ok,
.warn,
.bad {
  border: 1px solid currentColor;
  padding: 1px 6px;
  border-radius: 999px;
  margin-left: 5px;
  font-size: 12px;
  font-weight: 750;
}

.ok { color: #21C55D; background: rgba(33, 197, 93, .08); }
.warn,
.warn-text { color: #F6C343; }
.bad,
.bad-text { color: #EF4444; }

.dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-right: 6px;
  box-shadow: 0 0 10px currentColor;
}

.dot.on { background: #21C55D; color: #21C55D; }
.dot.off { background: #EF4444; color: #EF4444; }

.ring {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #EF4444;
  margin-right: 6px;
  vertical-align: -2px;
}

@media (max-width: 1500px) {
  .topbar {
    grid-template-columns: 134px 76px 104px minmax(150px, 1fr) 120px 104px 78px 78px 94px 112px 154px 64px;
  }

  .cell {
    padding-inline: 8px;
  }
}
</style>
