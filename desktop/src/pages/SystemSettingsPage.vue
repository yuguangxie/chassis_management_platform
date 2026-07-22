<template>
  <section class="system-settings-page">
    <header class="page-title-row">
      <div class="title-left">
        <div class="title-icon"><Settings :size="22" /></div>
        <div><h1>系统设置</h1><p>阈值、存储、DBC、权限、Mock 与维护模式</p></div>
      </div>
      <div class="title-actions">
        <PageDataState :loading="settingsStore.loading || settingsStore.operationLoading" :error="settingsStore.error" :stale="settingsStore.offline" />
        <span v-if="auth.principal" class="status-pill saved"><span></span>{{ auth.principal.username }} / {{ auth.principal.role }}</span>
        <span v-else-if="settingsStore.externalUpdated" class="status-pill external">配置已在外部更新</span>
        <span :class="['status-pill', settingsStore.dirty ? 'dirty' : 'saved']"><span></span>{{ settingsStore.dirty ? '存在未保存修改' : '配置已保存' }}</span>
        <button v-if="auth.isAdmin" :disabled="writeDisabled" @click="chooseConfigFile"><Upload :size="14" />导入配置</button>
        <button v-if="auth.isAdmin" :disabled="writeDisabled" @click="exportConfig"><Download :size="14" />导出配置</button>
        <button v-if="auth.isAdmin" :disabled="writeDisabled" @click="createBackup"><Database :size="14" />一致性备份</button>
        <button v-if="auth.isAdmin" :disabled="writeDisabled" @click="restoreLatestBackup"><RotateCcw :size="14" />恢复备份</button>
        <button v-if="auth.isAdmin" :disabled="writeDisabled" @click="previewCleanup"><HardDrive :size="14" />清理预检</button>
        <button v-if="auth.isAdmin" :disabled="writeDisabled" @click="recheckStorage"><Activity :size="14" />存储复检</button>
        <button v-if="auth.can('engineer')" class="primary" :disabled="hasInvalidThreshold || writeDisabled" @click="saveSettings"><Save :size="14" />保存设置</button>
      </div>
    </header>

    <section class="settings-row-one">
      <article class="settings-card basic-card">
        <CardTitle number="1" title="基础设置"><SlidersHorizontal :size="16" /></CardTitle>
        <div class="field-grid card-scroll">
          <label><span>工位号</span><input v-model="settings.basic.station_id" @input="markDirty" /></label>
          <label><span>工控机 IP</span><input v-model="settings.basic.host_ip" @input="markDirty" /></label>
          <label><span>默认控制通道</span><select v-model="settings.basic.control_channel" @change="markDirty"><option>CAN1</option><option>CAN2</option></select></label>
          <label><span>时区</span><select v-model="settings.basic.timezone" @change="markDirty"><option>UTC+08:00</option><option>UTC+00:00</option></select></label>
          <label class="wide"><span>默认报告目录</span><input :value="settings.basic.report_directory" disabled title="由签名 data_root 派生" /></label>
          <label class="wide"><span>SQLite 数据库路径</span><input :value="settings.basic.database_path" disabled title="由签名 data_root 派生" /></label>
          <label class="wide"><span>日志根目录</span><input :value="settings.basic.log_directory" disabled title="由签名 data_root 派生" /></label>
          <label><span>默认语言</span><select v-model="settings.basic.language" @change="markDirty"><option value="zh-CN">简体中文</option><option value="en-US">English</option></select></label>
          <div class="field-toggle"><span>自动保存配置</span><ToggleSwitch :active="settings.basic.auto_save" label="自动保存配置" @toggle="toggleBasicAutoSave" /></div>
        </div>
      </article>

      <article class="settings-card dbc-card">
        <CardTitle number="2" title="DBC 管理"><Cable :size="16" /></CardTitle>
        <div class="dbc-content">
          <div class="dbc-meta">
            <div><span>当前文件</span><strong :title="settings.dbc.filename">{{ settings.dbc.filename }}</strong></div>
            <div><span>版本 / Hash</span><strong>{{ settings.dbc.version }} · {{ settings.dbc.hash }}</strong></div>
            <div><span>加载状态</span><b :class="['dbc-status', settings.dbc.status]"><i></i>{{ dbcStatusLabel }}</b></div>
            <div><span>报文 / 信号</span><strong>{{ settings.dbc.message_count }} / {{ settings.dbc.signal_count }}</strong></div>
            <div class="full"><span>最近加载</span><strong>{{ settings.dbc.loaded_at }}</strong></div>
          </div>
          <div class="override-list">
            <div v-for="item in settings.dbc.overrides" :key="item.key"><CheckCircle2 :size="12" /><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
          </div>
        <div class="mini-actions"><button disabled title="尚未实现：生产 DBC 只能通过签名配置包部署"><FolderOpen :size="13" />选择 DBC（尚未实现）</button><button class="primary" :disabled="writeDisabled" @click="reloadDbc"><RefreshCw :size="13" />重载 DBC</button><button disabled title="覆盖规则已在当前卡片展示"><FileText :size="13" />覆盖规则（已展示）</button><button @click="viewMessages"><ListTree :size="13" />报文列表</button></div>
        </div>
      </article>

      <article class="settings-card storage-card">
        <CardTitle number="3" title="报告与存储"><HardDrive :size="16" /></CardTitle>
        <div class="storage-content card-scroll">
          <label><span>唯一 data_root</span><input :value="settings.storage.data_root" disabled title="仅通过签名生产配置变更" /></label>
          <label><span>原始 CAN 日志</span><input :value="settings.storage.raw_can_directory" disabled title="由 data_root 派生" /></label>
          <label><span>解码信号日志</span><input :value="settings.storage.decoded_signal_directory" disabled title="由 data_root 派生" /></label>
          <div class="storage-policy"><label><span>保留天数</span><input type="number" v-model.number="settings.storage.retention_days" @input="markDirty" /><em>天</em></label><label><span>最大日志</span><input type="number" v-model.number="settings.storage.max_log_gb" @input="markDirty" /><em>GB</em></label></div>
          <div class="format-toggles"><span title="清理必须由管理员预检并确认">自动清理：禁用</span><ToggleSwitch :active="settings.storage.word_enabled" label="Word" @toggle="toggleStorage('word_enabled')" /><ToggleSwitch :active="settings.storage.pdf_enabled" label="PDF" @toggle="toggleStorage('pdf_enabled')" /><ToggleSwitch :active="settings.storage.csv_enabled" label="CSV" @toggle="toggleStorage('csv_enabled')" /><ToggleSwitch :active="settings.storage.parquet_enabled" label="Parquet" @toggle="toggleStorage('parquet_enabled')" /></div>
          <div class="disk-summary"><div><span>磁盘使用 {{ settings.storage.disk_used_gb }} / {{ settings.storage.disk_total_gb }} GB</span><strong :class="diskLevel">{{ settings.storage.disk_used_percent }}%</strong></div><div class="disk-progress"><i :class="diskLevel" :style="{ width:`${Math.min(settings.storage.disk_used_percent,100)}%` }"></i></div><small v-if="settings.storage.measurement_error" class="danger">测量失败：{{ settings.storage.measurement_error }}</small><small v-else>剩余 {{ settings.storage.disk_free_gb }} GB · 路径由签名 data_root 固定派生</small></div>
        </div>
      </article>
    </section>

    <section class="settings-row-two">
      <article class="settings-card threshold-card">
        <CardTitle number="4" title="阈值设置"><Gauge :size="16" /><template #meta><span class="table-count">{{ settings.thresholds.length }} 项 · 单击数值编辑</span></template></CardTitle>
        <div class="table-scroll threshold-scroll"><table class="dense-table threshold-table"><thead><tr><th>配置项</th><th>当前值</th><th>允许范围</th><th>单位</th><th>作用域</th><th>说明</th><th>状态</th></tr></thead><tbody>
          <tr v-for="row in settings.thresholds" :key="row.key" :class="{ dangerous:row.dangerous, invalid:row.status === 'invalid' }">
            <td><TriangleAlert v-if="row.dangerous" :size="11" />{{ row.label }}</td>
            <td><button v-if="typeof row.value === 'boolean'" :class="['bool-value', row.value && 'on']" @click="toggleThresholdBoolean(row)">{{ row.value ? '开启' : '关闭' }}</button><input v-else type="number" :value="row.value" @input="updateThresholdValue(row,$event)" /></td>
            <td>{{ formatRange(row) }}</td><td>{{ row.unit }}</td><td><span :class="['scope-pill', row.dangerous && 'risk']">{{ row.scope }}</span></td><td>{{ row.description }}</td><td><span :class="['row-state', thresholdState(row)]"><i></i>{{ thresholdStateLabel(row) }}</span></td>
          </tr>
        </tbody></table></div>
      </article>

      <article class="settings-card audit-card">
        <CardTitle number="5" title="权限与审计"><ShieldCheck :size="16" /><template #meta><span class="admin-badge">ADMIN 审批</span></template></CardTitle>
        <div class="audit-content">
          <div class="table-scroll role-scroll"><table class="dense-table role-table"><thead><tr><th>角色</th><th>查看</th><th>检测</th><th>手动控制</th><th>配置</th><th>维护</th><th>删除报告</th></tr></thead><tbody><tr v-for="role in settings.roles" :key="role.role" :class="{ admin:role.role==='admin' }"><td><span :class="['role-pill',role.role]">{{ role.role }}</span></td><td>{{ role.view }}</td><td>{{ role.test }}</td><td>{{ role.manual_control }}</td><td>{{ role.config }}</td><td>{{ role.maintenance }}</td><td><span :class="['yes-no',role.delete_report?'yes':'no']">{{ role.delete_report?'是':'否' }}</span></td></tr></tbody></table></div>
          <div class="subhead"><History :size="13" />最近配置历史 <span>修改权限配置必须经过后端审批</span></div>
          <div class="table-scroll history-scroll"><table class="dense-table config-history-table"><thead><tr><th>时间</th><th>用户</th><th>配置项</th><th>旧值</th><th>新值</th><th>原因</th><th>结果</th></tr></thead><tbody><tr v-for="row in settings.config_history" :key="`${row.time}-${row.key}`"><td>{{ row.time }}</td><td><span :class="['history-user',row.user.includes('admin')&&'admin']">{{ row.user }}</span></td><td>{{ row.key }}</td><td>{{ row.old_value }}</td><td>{{ row.new_value }}</td><td>{{ row.reason }}</td><td><span class="success-pill">{{ row.result }}</span></td></tr></tbody></table></div>
        </div>
      </article>
    </section>

    <section class="settings-row-three">
      <article class="settings-card maintenance-card">
        <CardTitle number="6" title="维护模式"><Wrench :size="16" /><template #meta><span :class="['maintenance-state',settings.maintenance.maintenance_mode&&'on']"><i></i>{{ settings.maintenance.maintenance_mode?'维护中':'安全锁定' }}</span></template></CardTitle>
        <div class="maintenance-content">
          <div class="maintenance-warning"><ShieldAlert :size="20" /><div><strong>维护模式可能导致车辆异常运动</strong><span>仅允许管理员在台架或封闭环境中启用，全部操作记录审计。</span></div></div>
          <div class="feature-list">
            <button v-for="feature in featureRows" :key="feature.key" :class="['feature-row',feature.risk&&'risk',feature.permanent&&'permanent']" :disabled="!auth.isAdmin || writeDisabled" @click="toggleFeature(feature)"><span><component :is="feature.icon" :size="14" />{{ feature.label }}</span><small>{{ feature.note }}</small><i :class="{ on:Boolean(settings.maintenance[feature.key]) }"><b></b></i></button>
          </div>
          <div v-if="auth.isAdmin" class="maintenance-actions"><button class="mock" :disabled="writeDisabled" @click="openDialog('mock')"><Bot :size="14" />{{ settings.maintenance.mock_can_gateway?'关闭 Mock':'启用 Mock' }}</button><button :class="settings.maintenance.maintenance_mode?'exit':'enter'" :disabled="writeDisabled" @click="toggleMaintenance"><ShieldAlert :size="14" />{{ settings.maintenance.maintenance_mode?'退出维护模式':'进入维护模式' }}</button></div>
        </div>
      </article>

      <article class="settings-card trend-card">
        <CardTitle number="7" title="日志空间趋势"><Activity :size="16" /><template #meta><select v-model="trendRange" aria-label="日志趋势范围"><option value="7d">最近7天</option><option value="30d">最近30天</option></select></template></CardTitle>
        <div class="trend-content"><RealtimeLineChart :option="storageTrendOption" height="132px" /><div class="storage-kpis"><div><span>当前日志</span><strong>{{ settings.storage_summary.current_log_gb }} GB</strong></div><div><span>数据库</span><strong>{{ settings.storage_summary.database_gb }} GB</strong></div><div><span>报告</span><strong>{{ settings.storage_summary.reports_gb }} GB</strong></div><div><span>Raw CAN</span><strong>{{ settings.storage_summary.raw_can_gb }} GB</strong></div></div><div class="cleanup-line"><CheckCircle2 :size="13" /><span>最近清理 {{ settings.storage_summary.last_cleanup }}</span><span>下次 {{ settings.storage_summary.next_cleanup }}</span><b>{{ settings.storage_summary.cleanup_status }} / 磁盘{{ settings.storage_summary.disk_alarm }}</b></div></div>
      </article>

      <article class="settings-card safety-card">
        <CardTitle number="8" title="安全默认值与系统版本"><LockKeyhole :size="16" /></CardTitle>
        <div class="safety-version-grid">
          <div class="safe-rules"><div v-for="item in settings.safe_defaults" :key="item.label"><CheckCircle2 :size="12" /><span>{{ item.label }}</span><b>{{ item.enabled?'生效':'失效' }}</b></div></div>
          <div class="version-list"><div><span>软件版本</span><b>{{ settings.version.software }}</b></div><div><span>配置版本</span><b>{{ settings.version.config }}</b></div><div><span>检测方案</span><b>{{ settings.version.test_plan }}</b></div><div><span>Python / Node</span><b>{{ settings.version.python }} / {{ settings.version.node }}</b></div><div><span>Electron</span><b>{{ settings.version.electron }}</b></div><div><span>平台</span><b>{{ settings.version.platform }}</b></div><div><span>构建时间</span><b>{{ settings.version.build_time }}</b></div></div>
        </div>
        <div class="safety-actions"><button v-if="auth.isAdmin" class="danger-outline" :disabled="writeDisabled" @click="openDialog('restore')"><RotateCcw :size="13" />恢复安全默认</button><button disabled title="版本详情已在当前卡片展示"><Info :size="13" />版本详情（已展示）</button></div>
      </article>
    </section>

    <footer class="settings-action-bar">
      <ActionButton v-if="auth.can('engineer')" tone="primary" title="保存设置" subtitle="保存所有配置变更" :icon="Save" :disabled="writeDisabled" @click="saveSettings" />
      <ActionButton v-if="auth.isAdmin" title="导入配置" subtitle="校验、预览后应用" :icon="Upload" :disabled="writeDisabled" @click="chooseConfigFile" />
      <ActionButton v-if="auth.isAdmin" title="导出配置" subtitle="导出签名配置包" :icon="Download" :disabled="writeDisabled" @click="exportConfig" />
      <ActionButton title="重载 DBC" subtitle="重新扫描并加载 assets" :icon="RefreshCw" :disabled="writeDisabled" @click="reloadDbc" />
      <ActionButton v-if="auth.isAdmin" tone="warning" :title="settings.maintenance.mock_can_gateway?'关闭 Mock':'启用 Mock'" subtitle="切换 MockCanGateway" :icon="Bot" :disabled="writeDisabled" @click="openDialog('mock')" />
      <ActionButton v-if="auth.isAdmin" tone="warning" :title="settings.maintenance.maintenance_mode?'退出维护模式':'进入维护模式'" subtitle="需管理员二次确认" :icon="ShieldAlert" :disabled="writeDisabled" @click="toggleMaintenance" />
      <ActionButton v-if="auth.isAdmin" tone="danger" title="恢复安全默认" subtitle="仅恢复安全相关参数" :icon="RotateCcw" :disabled="writeDisabled" @click="openDialog('restore')" />
    </footer>

    <div v-if="dialogMode" class="dialog-overlay" role="dialog" aria-modal="true" :aria-label="dialogTitle">
      <div class="danger-dialog">
        <div class="dialog-icon"><ShieldAlert :size="28" /></div><h3>{{ dialogTitle }}</h3><p>{{ dialogImpact }}</p>
        <label><span>变更原因</span><input v-model="dialogReason" placeholder="请输入台架环境、目的和影响说明" /></label>
        <label><span>输入确认文本 <b>{{ dialogExpected }}</b></span><input v-model="dialogConfirmation" :placeholder="dialogExpected" /></label>
        <div class="dialog-actions"><button @click="closeDialog">取消</button><button class="confirm-danger" :disabled="dialogConfirmation!==dialogExpected || dialogReason.trim().length<2" @click="confirmDialog">确认执行</button></div>
      </div>
    </div>
    <input ref="configFileInput" class="hidden-file-input" type="file" accept="application/json,.json" @change="previewConfigFile" />
    <div v-if="configPreview" class="dialog-overlay" role="dialog" aria-modal="true" aria-label="配置差异预览">
      <div class="config-preview-dialog">
        <h3>签名配置包差异预览</h3>
        <p :class="configPreview.compatible ? 'preview-ok' : 'preview-blocked'">{{ configPreview.message }}</p>
        <div class="preview-summary">
          <span>配置版本 {{ configPreview.summary.config_version }}</span>
          <span>差异 {{ configPreview.diff.length }} 项</span>
          <span>阻断 {{ configPreview.blocking_checks.length }} 项</span>
        </div>
        <div class="preview-diff">
          <div v-for="item in configPreview.diff" :key="item.path"><b>{{ item.path }}</b><span>{{ formatPreviewValue(item.current) }} → {{ formatPreviewValue(item.proposed) }}</span></div>
          <p v-if="!configPreview.diff.length">运行配置与导入包一致</p>
        </div>
        <div v-if="configPreview.blocking_checks.length" class="preview-blockers">
          <strong>阻断规则：</strong>{{ configPreview.blocking_checks.map(item=>item.rule).join('、') }}
        </div>
        <label><span>应用原因</span><input v-model="configApplyReason" placeholder="说明变更目的和影响" /></label>
        <div class="dialog-actions"><button @click="closeConfigPreview">取消</button><button class="confirm-danger" :disabled="!configPreview.compatible || configApplyReason.trim().length<2" @click="applyImportedConfig">确认 APPLY</button></div>
      </div>
    </div>
    <div v-if="toast" class="toast">{{ toast }}</div>
  </section>
</template>

<script setup lang="ts">
import {
  Activity, Bot, Cable, CheckCircle2, Database, Download, FileText, FolderOpen, Gauge, HardDrive, History,
  Info, ListTree, LockKeyhole, RefreshCw, RotateCcw, Save, Settings, ShieldAlert, ShieldCheck,
  SlidersHorizontal, TriangleAlert, Upload, Wrench,
} from 'lucide-vue-next'
import type { Component, PropType } from 'vue'
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import type { ConfigurationPreviewResult, SignedConfigurationPackage, SystemMaintenanceSettings, SystemThresholdSetting } from '../api/types'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import { useSettingsStore } from '../stores/settings'
import { useAuthStore } from '../stores/auth'
import PageDataState from '../components/PageDataState.vue'

const settingsStore = useSettingsStore()
const auth = useAuthStore()
const router = useRouter()
const settings = computed(() => settingsStore.dashboard)
const writeDisabled = computed(() => settingsStore.offline || settingsStore.loading || settingsStore.operationLoading)
const toast = ref('')
const trendRange = ref('7d')
const dialogMode = ref<'save'|'maintenance'|'mock'|'restore'|'feature'|null>(null)
const dialogConfirmation = ref('')
const dialogReason = ref('')
const pendingFeature = ref<FeatureRow | null>(null)
const configFileInput = ref<HTMLInputElement | null>(null)
const importedPackage = ref<SignedConfigurationPackage | null>(null)
const configPreview = ref<ConfigurationPreviewResult | null>(null)
const configApplyReason = ref('')
let toastTimer: number | undefined
let pollTimer: number | undefined

type FeatureKey = 'mock_can_gateway'|'enable_0x123'|'enable_0x126'|'allow_canopen_nmt'|'enable_pid_debug'|'dual_control_channel_allowed'
interface FeatureRow { key:FeatureKey; label:string; note:string; risk:boolean; permanent?:boolean; icon:Component }

const featureRows: FeatureRow[] = [
  {key:'mock_can_gateway',label:'MockCanGateway',note:'必须明确显示 Mock 模式',risk:true,icon:Bot},
  {key:'enable_0x123',label:'启用 0x123',note:'SCU_Torque_Command，默认关闭',risk:true,icon:TriangleAlert},
  {key:'enable_0x126',label:'启用 0x126',note:'角速度 126~525 deg/s，默认关闭',risk:true,icon:TriangleAlert},
  {key:'allow_canopen_nmt',label:'允许 CANopen NMT',note:'默认禁止主动发送',risk:true,icon:Cable},
  {key:'enable_pid_debug',label:'PID 调试 0x710 / 0x715',note:'仅维护台架可用',risk:true,icon:Activity},
  {key:'dual_control_channel_allowed',label:'双控制通道',note:'永久禁止，不可选择',risk:true,permanent:true,icon:LockKeyhole},
]

const CardTitle = defineComponent({
  props:{number:{type:String,required:true},title:{type:String,required:true}},
  setup(props,{slots}){return()=>h('header',{class:'card-title'},[h('div',{class:'card-title-main'},[h('span',{class:'card-number'},props.number),slots.default?.(),h('h2',props.title)]),slots.meta?.()])},
})
const ToggleSwitch = defineComponent({
  props:{active:{type:Boolean,required:true},label:{type:String,required:true}},emits:['toggle'],
  setup(props,{emit}){return()=>h('button',{class:['mini-toggle',props.active&&'on'],role:'switch','aria-checked':props.active,'aria-label':props.label,onClick:()=>emit('toggle')},[h('i',[h('b')]),h('span',props.label)])},
})
const ActionButton = defineComponent({
  props:{tone:{type:String,default:''},title:{type:String,required:true},subtitle:{type:String,required:true},icon:{type:[Object,Function] as PropType<Component>,required:true},disabled:{type:Boolean,default:false}},emits:['click'],
  setup(props,{emit}){return()=>h('button',{class:['action-button',props.tone],disabled:props.disabled,onClick:()=>emit('click')},[h('span',{class:'action-icon'},[h(props.icon,{size:23})]),h('span',{class:'action-copy'},[h('strong',props.title),h('small',props.subtitle)])])},
})

const hasInvalidThreshold = computed(() => settings.value.thresholds.some(item => item.status === 'invalid'))
const hasDangerousChanges = computed(() => {
  const original = new Map(settingsStore.original.thresholds.map(item=>[item.key,item.value]))
  return settings.value.thresholds.some(item=>item.dangerous && original.get(item.key)!==item.value)
})
const dbcStatusLabel = computed(() => settings.value.dbc.status==='loaded'?'已加载':settings.value.dbc.status==='raw-only'?'raw-only':'加载失败')
const diskLevel = computed(() => settings.value.storage.disk_used_percent>=85?'danger':settings.value.storage.disk_used_percent>=70?'warning':'normal')
const dialogExpected = computed(() => dialogMode.value==='maintenance'||dialogMode.value==='feature'?'MAINTENANCE':dialogMode.value==='mock'?'MOCK':dialogMode.value==='restore'?'RESTORE':'SAVE')
const dialogTitle = computed(() => ({save:'保存危险参数',maintenance:'进入维护模式',mock:settings.value.maintenance.mock_can_gateway?'关闭 MockCanGateway':'启用 MockCanGateway',restore:'恢复安全默认值',feature:`变更 ${pendingFeature.value?.label||'危险功能'}`}[dialogMode.value||'save']))
const dialogImpact = computed(() => ({save:'危险阈值会影响车辆控制与检测判定，后端将再次校验范围和权限。',maintenance:'维护模式可能导致车辆异常运动，仅允许管理员在封闭台架中使用。',mock:'Mock 模式不得伪装为真实硬件，切换将同步顶部状态并写入审计。',restore:'仅恢复速度、转角、告警、扩展报文和控制通道等安全参数，保留工位号与路径。',feature:`${pendingFeature.value?.note||''}，启用前必须确认维护模式与现场安全条件。`}[dialogMode.value||'save']))
const storageTrendOption = computed(() => ({backgroundColor:'transparent',color:['#2F80FF'],tooltip:{trigger:'axis'},grid:{left:35,right:12,top:14,bottom:24,containLabel:true},xAxis:{type:'category',data:settings.value.storage_trend.map(item=>item.date),axisLabel:{color:'#8CA6C5',fontSize:9},axisLine:{lineStyle:{color:'#315A83'}}},yAxis:{type:'value',name:'GB',nameTextStyle:{color:'#8CA6C5',fontSize:9},axisLabel:{color:'#8CA6C5',fontSize:9},splitLine:{lineStyle:{color:'#1B3A5E',type:'dashed'}}},series:[{name:'日志空间',type:'bar',barWidth:'44%',data:settings.value.storage_trend.map(item=>item.used_gb),itemStyle:{color:'#2F80FF',borderRadius:[3,3,0,0]},label:{show:true,position:'top',color:'#CFE2FF',fontSize:9}}]}))

onMounted(async()=>{await settingsStore.loadDashboard();settingsStore.bindWebSocket();pollTimer=window.setInterval(()=>void settingsStore.loadDashboard(true),8000);window.addEventListener('beforeunload',beforeUnload)})
onBeforeUnmount(()=>{if(pollTimer)window.clearInterval(pollTimer);if(toastTimer)window.clearTimeout(toastTimer);window.removeEventListener('beforeunload',beforeUnload)})
onBeforeRouteLeave(()=>!settingsStore.dirty||window.confirm('存在未保存的系统设置修改，确认离开吗？'))

function markDirty(){settingsStore.markDirty()}
function toggleBasicAutoSave(){settings.value.basic.auto_save=!settings.value.basic.auto_save;markDirty()}
function toggleStorage(key:'auto_cleanup'|'word_enabled'|'pdf_enabled'|'csv_enabled'|'parquet_enabled'){settings.value.storage[key]=!settings.value.storage[key];markDirty()}
function syncReportPath(){settings.value.storage.report_directory=settings.value.basic.report_directory;markDirty()}
function syncStorageReportPath(){settings.value.basic.report_directory=settings.value.storage.report_directory;markDirty()}
function syncDatabasePath(){settings.value.storage.database_path=settings.value.basic.database_path;markDirty()}
function updateThresholdValue(row:SystemThresholdSetting,event:Event){const value=Number((event.target as HTMLInputElement).value);row.value=value;validateThreshold(row);markDirty()}
function toggleThresholdBoolean(row:SystemThresholdSetting){row.value=!Boolean(row.value);validateThreshold(row);markDirty()}
function validateThreshold(row:SystemThresholdSetting){if(typeof row.value==='boolean'){row.status='modified';return}const value=Number(row.value);row.status=(row.min!==null&&value<row.min)||(row.max!==null&&value>row.max)?'invalid':'modified'}
function formatRange(row:SystemThresholdSetting){return row.min===null&&row.max===null?'关闭 / 开启':`${row.min ?? '—'} ~ ${row.max ?? '—'}`}
function thresholdState(row:SystemThresholdSetting){return row.status==='invalid'?'invalid':row.dangerous?'warning':'normal'}
function thresholdStateLabel(row:SystemThresholdSetting){return row.status==='invalid'?'越界':row.dangerous?'需审批':'正常'}
function viewMessages(){void router.push('/can-monitor')}
function openDialog(mode:NonNullable<typeof dialogMode.value>,feature?:FeatureRow){pendingFeature.value=feature||null;dialogMode.value=mode;dialogConfirmation.value='';dialogReason.value=mode==='restore'?'恢复系统安全默认值':''}
function closeDialog(){dialogMode.value=null;pendingFeature.value=null;dialogConfirmation.value='';dialogReason.value=''}
async function confirmDialog(){try{let result:{message?:string}|undefined;if(dialogMode.value==='save')result=await settingsStore.save(dialogReason.value);if(dialogMode.value==='maintenance')result=await settingsStore.enterMaintenance(dialogConfirmation.value,dialogReason.value);if(dialogMode.value==='restore')result=await settingsStore.restoreSafeDefaults(dialogConfirmation.value,dialogReason.value);if(dialogMode.value==='mock'){const next={...settings.value.maintenance,mock_can_gateway:!settings.value.maintenance.mock_can_gateway};result=await settingsStore.updateFeatures(next,dialogConfirmation.value,dialogReason.value)}if(dialogMode.value==='feature'&&pendingFeature.value){const next={...settings.value.maintenance,[pendingFeature.value.key]:!settings.value.maintenance[pendingFeature.value.key]};result=await settingsStore.updateFeatures(next,dialogConfirmation.value,dialogReason.value)}showToast(result?.message||'操作完成');closeDialog()}catch(error){showToast(formatError(error))}}
function toggleFeature(feature:FeatureRow){if(feature.permanent){showToast('双控制通道由后端永久禁止，不能启用');return}if(feature.key!=='mock_can_gateway'&&!settings.value.maintenance.maintenance_mode){showToast('请先由管理员进入维护模式');return}openDialog(feature.key==='mock_can_gateway'?'mock':'feature',feature)}
async function toggleMaintenance(){if(settings.value.maintenance.maintenance_mode){try{const result=await settingsStore.exitMaintenance();showToast(result.message||'已退出维护模式')}catch(error){showToast(formatError(error))}}else openDialog('maintenance')}
function saveSettings(){if(hasInvalidThreshold.value){showToast('存在超出允许范围的阈值，无法保存');return}if(!settingsStore.dirty){showToast('当前配置没有修改');return}if(hasDangerousChanges.value)openDialog('save');else void runOperation(()=>settingsStore.save('常规系统配置调整'))}
function chooseConfigFile(){configFileInput.value?.click()}
async function previewConfigFile(event:Event){
  const input=event.target as HTMLInputElement
  const file=input.files?.[0]
  input.value=''
  if(!file)return
  try{
    const parsed=JSON.parse(await file.text()) as SignedConfigurationPackage
    const preview=await settingsStore.previewConfig(parsed)
    importedPackage.value=parsed
    configPreview.value=preview
    configApplyReason.value=''
  }catch(error){showToast(formatError(error))}
}
function closeConfigPreview(){importedPackage.value=null;configPreview.value=null;configApplyReason.value=''}
async function applyImportedConfig(){
  if(!importedPackage.value||!configPreview.value?.compatible)return
  try{const result=await settingsStore.applyConfig(importedPackage.value,configApplyReason.value);showToast(result.message||'签名配置已应用');closeConfigPreview()}
  catch(error){showToast(formatError(error))}
}
function formatPreviewValue(value:unknown){if(value===null)return'null';if(typeof value==='object')return JSON.stringify(value);return String(value)}
async function exportConfig(){await runOperation(()=>settingsStore.exportConfig())}

async function createBackup(){try{const result=await settingsStore.createBackup();showToast(`备份完成：${String(result.backup_id||'已验证')}`)}catch(error){showToast(formatError(error))}}
async function restoreLatestBackup(){
  try{
    const backups=await settingsStore.listBackups();const target=backups.find(item=>item.valid)
    if(!target){showToast('没有通过 hash 和 schema 校验的可恢复备份');return}
    const expected=`RESTORE ${target.backup_id}`;const confirmation=window.prompt(`将使用最近有效备份 ${target.backup_id}。当前库会先生成回滚副本。请输入：${expected}`)||''
    if(confirmation!==expected){showToast('恢复已取消：确认文字不匹配');return}
    await settingsStore.restoreBackup(target.backup_id,confirmation);showToast(`恢复完成：${target.backup_id}`);await settingsStore.loadDashboard()
  }catch(error){showToast(formatError(error))}
}
async function recheckStorage(){try{await settingsStore.recheckStorage();showToast('存储路径、空间、写入和数据库完整性复检通过')}catch(error){showToast(formatError(error))}}
async function previewCleanup(){
  try{
    const cutoff=new Date(Date.now()-settings.value.storage.retention_days*86400000).toISOString()
    const preview=await settingsStore.previewRetention(cutoff)
    const confirmed=window.confirm(`清理预检：${preview.session_count} 个会话、${preview.file_count} 个文件、${preview.total_bytes} 字节。未归档报告、活跃会话和审计记录受保护。是否提交管理员清理任务？`)
    if(!confirmed){showToast('清理已取消，仅完成 dry-run');return}
    const job=await settingsStore.startRetention(cutoff)
    showToast(`清理任务已提交：${String(job.id||'queued')}`)
  }catch(error){showToast(formatError(error))}
}
async function reloadDbc(){await runOperation(()=>settingsStore.reloadDbc())}
async function runOperation(operation:()=>Promise<{message?:string}>){try{const result=await operation();showToast(result.message||'操作完成')}catch(error){showToast(formatError(error))}}
function formatError(error:unknown){if(!(error instanceof Error))return'操作失败';if(error.message.includes('Failed to fetch'))return'后端离线，操作未执行；当前继续显示 Mock 系统配置';try{const parsed=JSON.parse(error.message) as {detail?:{message?:string};message?:string};return parsed.detail?.message||parsed.message||error.message}catch{return error.message}}
function showToast(message:string){toast.value=message;if(toastTimer)window.clearTimeout(toastTimer);toastTimer=window.setTimeout(()=>{if(toast.value===message)toast.value=''},3000)}
function beforeUnload(event:BeforeUnloadEvent){if(settingsStore.dirty){event.preventDefault();event.returnValue=''}}
</script>

<style scoped>
.system-settings-page{position:relative;height:100%;min-height:0;overflow:hidden;display:grid;grid-template-rows:42px 232px 230px minmax(240px,1fr) 78px;gap:10px;color:#EAF2FF}.page-title-row{display:flex;align-items:center;justify-content:space-between;padding:0 4px}.title-left,.title-actions{display:flex;align-items:center;gap:9px}.title-icon{width:34px;height:34px;display:grid;place-items:center;border:1px solid rgba(47,128,255,.55);border-radius:6px;color:#B9D9FF;background:linear-gradient(135deg,rgba(47,128,255,.43),rgba(34,211,238,.15))}.page-title-row h1{margin:0;font-size:22px;line-height:24px}.page-title-row p{margin:4px 0 0;color:#95A8C6;font-size:12px}.title-actions>button{height:31px;display:flex;align-items:center;gap:6px;padding:0 10px;border:1px solid #315A83;border-radius:5px;color:#CFE2FF;background:#102A4A;font-size:11px;font-weight:700}.title-actions>button.primary{border-color:#2F80FF;background:linear-gradient(135deg,#176CD9,#0E4A98)}.title-actions>button:disabled{opacity:.45}.offline-pill,.status-pill{height:28px;display:inline-flex;align-items:center;gap:6px;padding:0 9px;border:1px solid;border-radius:5px;font-size:10px}.offline-pill,.status-pill.dirty,.status-pill.external{color:#F6C343;border-color:rgba(246,195,67,.5);background:rgba(246,195,67,.1)}.status-pill.saved{color:#21C55D;border-color:rgba(33,197,93,.45);background:rgba(33,197,93,.08)}.status-pill span{width:7px;height:7px;border-radius:50%;background:currentColor}
.settings-row-one,.settings-row-two,.settings-row-three{display:grid;gap:10px;min-height:0}.settings-row-one{grid-template-columns:1.05fr 1.05fr 1fr}.settings-row-two{grid-template-columns:1.45fr 1fr}.settings-row-three{grid-template-columns:1fr 1.05fr 1fr}.settings-card{min-height:0;overflow:hidden;border:1px solid #1E3A5F;border-radius:8px;background:linear-gradient(180deg,rgba(16,36,61,.98),rgba(8,23,41,.98));box-shadow:0 8px 22px rgba(0,0,0,.22);padding:0 10px 8px}.card-title{height:31px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #1E3A5F}.card-title-main{display:flex;align-items:center;gap:6px;color:#8FC2FF}.card-title h2{margin:0;color:#EAF2FF;font-size:13px}.card-number{width:17px;height:17px;display:grid;place-items:center;border:1px solid rgba(47,128,255,.6);border-radius:4px;color:#A9D0FF;background:rgba(47,128,255,.16);font:700 9px Consolas}.card-scroll,.table-scroll{min-height:0;overflow:auto;scrollbar-color:#2B5C90 #07172A}.table-count{color:#7F97B6;font-size:9px}
.field-grid{height:calc(100% - 31px);display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:29px;gap:2px 8px;padding-top:3px}.field-grid label{display:grid;grid-template-columns:86px 1fr;align-items:center;min-width:0;color:#95A8C6;font-size:10px}.field-grid label.wide{grid-column:span 2}.field-grid input,.field-grid select,.storage-content input,.trend-card select{min-width:0;width:100%;height:24px;border:1px solid #24486F;border-radius:4px;outline:none;color:#DDEBFF;background:#07192D;padding:0 7px;font-size:10px}.path-input{display:grid;grid-template-columns:1fr 24px}.path-input input{border-radius:4px 0 0 4px}.path-input button{height:24px;border:1px solid #24486F;border-left:0;border-radius:0 4px 4px 0;color:#7FB5F3;background:#0D2948}.field-toggle{display:flex;align-items:center;justify-content:space-between;color:#95A8C6;font-size:10px}.mini-toggle{height:22px;display:flex;align-items:center;gap:5px;border:0;color:#8095B2;background:transparent;font-size:9px}.mini-toggle i{position:relative;width:24px;height:12px;border-radius:10px;background:#314D6D}.mini-toggle i b{position:absolute;top:2px;left:2px;width:8px;height:8px;border-radius:50%;background:#8EA3BC}.mini-toggle.on{color:#21C55D}.mini-toggle.on i{background:#167849}.mini-toggle.on i b{left:14px;background:#E4FFF0}
.dbc-content{height:calc(100% - 31px);display:grid;grid-template-rows:55px minmax(0,1fr) 29px;gap:4px;padding-top:5px}.dbc-meta{display:grid;grid-template-columns:1.25fr 1fr;gap:3px 8px}.dbc-meta>div{min-width:0;display:grid;grid-template-columns:62px 1fr;align-items:center;font-size:9px}.dbc-meta>div.full{grid-column:span 2}.dbc-meta span{color:#8298B5}.dbc-meta strong{overflow:hidden;color:#DDEBFF;text-overflow:ellipsis;white-space:nowrap}.dbc-status{display:flex;align-items:center;gap:5px}.dbc-status i{width:7px;height:7px;border-radius:50%;background:currentColor}.dbc-status.loaded{color:#21C55D}.dbc-status.raw-only{color:#F6C343}.dbc-status.failed{color:#EF4444}.override-list{min-height:0;overflow:hidden;display:grid;grid-template-rows:repeat(5,1fr);border-top:1px solid #173456}.override-list>div{min-width:0;display:grid;grid-template-columns:15px 123px 1fr;align-items:center;border-bottom:1px solid #153153;color:#21C55D;font-size:9px}.override-list span{color:#AFC2DA}.override-list strong{overflow:hidden;color:#DDEBFF;text-overflow:ellipsis;white-space:nowrap}.mini-actions{display:grid;grid-template-columns:repeat(4,1fr);gap:5px}.mini-actions button,.safety-actions button{height:27px;display:flex;align-items:center;justify-content:center;gap:4px;border:1px solid #315A83;border-radius:4px;color:#BFD2E9;background:#0C2643;font-size:9px}.mini-actions button.primary{border-color:#2F80FF;background:#145EBA}.mini-actions button:disabled,.safety-actions button:disabled,.action-button:disabled{opacity:.42;cursor:not-allowed}
.storage-content{height:calc(100% - 31px);display:grid;grid-template-rows:repeat(3,26px) 29px 22px 37px;gap:2px;padding-top:2px}.storage-content>label{display:grid;grid-template-columns:86px 1fr;align-items:center;color:#95A8C6;font-size:9px}.storage-policy{display:grid;grid-template-columns:1fr 1fr;gap:7px}.storage-policy label{display:grid;grid-template-columns:65px 1fr 22px;align-items:center;color:#95A8C6;font-size:9px}.storage-policy em{font-style:normal;text-align:right}.format-toggles{display:flex;align-items:center;justify-content:space-between}.format-toggles .mini-toggle{padding:0}.disk-summary{display:grid;gap:2px}.disk-summary>div:first-child{display:flex;justify-content:space-between;color:#95A8C6;font-size:9px}.disk-summary strong.normal{color:#21C55D}.disk-summary strong.warning{color:#F6C343}.disk-summary strong.danger{color:#EF4444}.disk-progress{height:5px;overflow:hidden;border-radius:5px;background:#07172A}.disk-progress i{display:block;height:100%;background:#21C55D}.disk-progress i.warning{background:#F6C343}.disk-progress i.danger{background:#EF4444}.disk-summary small{color:#6F86A5;font-size:8px}
.threshold-scroll{height:calc(100% - 31px)}.dense-table{width:100%;border-collapse:collapse;table-layout:fixed;color:#BFD0E6;font-size:9px}.dense-table th{position:sticky;top:0;z-index:2;height:25px;color:#8FA8C7;background:#0A2038;font-weight:600}.dense-table td{height:27px;padding:0 6px;border-top:1px solid #173456;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.threshold-table th:nth-child(1){width:18%}.threshold-table th:nth-child(2){width:10%}.threshold-table th:nth-child(3){width:12%}.threshold-table th:nth-child(4){width:7%}.threshold-table th:nth-child(5){width:10%}.threshold-table th:nth-child(6){width:31%}.threshold-table th:nth-child(7){width:12%}.threshold-table td:first-child{color:#DDEBFF}.threshold-table td:first-child svg{margin-right:4px;color:#F6C343;vertical-align:-2px}.threshold-table tr.dangerous{background:rgba(246,195,67,.025)}.threshold-table tr.invalid{background:rgba(239,68,68,.1)}.threshold-table input{width:62px;height:21px;border:1px solid #315A83;border-radius:3px;color:#EAF2FF;background:#07192D;padding:0 5px;text-align:right;font-size:9px}.bool-value{height:21px;min-width:48px;border:1px solid #5B708A;border-radius:3px;color:#8EA3BC;background:#132338;font-size:9px}.bool-value.on{color:#F6C343;border-color:#F6C343;background:#392C0B}.scope-pill,.row-state,.role-pill,.yes-no,.success-pill{display:inline-flex;align-items:center;justify-content:center;height:18px;padding:0 6px;border:1px solid #315A83;border-radius:3px;color:#8FC2FF;background:#0B2644;font-size:8px}.scope-pill.risk{color:#F6C343;border-color:rgba(246,195,67,.55);background:#2A220D}.row-state{gap:4px}.row-state i{width:5px;height:5px;border-radius:50%;background:currentColor}.row-state.normal{color:#21C55D;border-color:rgba(33,197,93,.4);background:#082B1D}.row-state.warning{color:#F6C343;border-color:rgba(246,195,67,.45);background:#2A220D}.row-state.invalid{color:#EF4444;border-color:rgba(239,68,68,.6);background:#38131B}
.audit-content{height:calc(100% - 31px);display:grid;grid-template-rows:91px 23px minmax(0,1fr)}.role-scroll,.history-scroll{min-height:0}.role-table th:nth-child(1){width:12%}.role-table th:nth-child(2){width:15%}.role-table th:nth-child(3){width:15%}.role-table th:nth-child(4){width:16%}.role-table th:nth-child(5){width:16%}.role-table th:nth-child(6){width:16%}.role-table th:nth-child(7){width:10%}.role-table th{height:22px}.role-table td{height:22px;padding:0 4px;font-size:8px}.role-table tr.admin{background:rgba(246,195,67,.055)}.role-pill.viewer{color:#95A8C6}.role-pill.operator{color:#2F80FF}.role-pill.engineer{color:#21C55D}.role-pill.admin{color:#F6C343;border-color:#F6C343}.yes-no.yes{color:#F6C343;border-color:#F6C343}.yes-no.no{color:#EF4444;border-color:rgba(239,68,68,.45)}.admin-badge{height:19px;display:flex;align-items:center;padding:0 7px;border:1px solid rgba(246,195,67,.5);border-radius:3px;color:#F6C343;background:#2A220D;font-size:8px}.subhead{display:flex;align-items:center;gap:5px;border-top:1px solid #1E3A5F;color:#CFE2FF;font-size:9px}.subhead svg{color:#2F80FF}.subhead span{margin-left:auto;color:#6F86A5;font-size:8px}.config-history-table th{height:21px}.config-history-table td{height:22px;padding:0 4px;font-size:8px}.config-history-table th:nth-child(1){width:19%}.config-history-table th:nth-child(2){width:10%}.config-history-table th:nth-child(3){width:17%}.config-history-table th:nth-child(4),.config-history-table th:nth-child(5){width:13%}.config-history-table th:nth-child(6){width:18%}.config-history-table th:nth-child(7){width:10%}.history-user.admin{color:#F6C343}.success-pill{color:#21C55D;border-color:rgba(33,197,93,.4);background:#082B1D}
.maintenance-card{border-color:rgba(246,195,67,.55);box-shadow:inset 0 0 0 1px rgba(246,195,67,.05),0 8px 22px rgba(0,0,0,.22)}.maintenance-content{height:calc(100% - 31px);display:grid;grid-template-rows:43px minmax(0,1fr) 30px;gap:5px;padding-top:5px}.maintenance-warning{display:flex;align-items:center;gap:8px;padding:0 8px;border:1px solid rgba(246,195,67,.55);border-radius:5px;color:#F6C343;background:linear-gradient(90deg,rgba(246,195,67,.15),rgba(239,68,68,.06))}.maintenance-warning strong{display:block;font-size:10px}.maintenance-warning span{display:block;margin-top:2px;color:#C6AA68;font-size:8px}.maintenance-state{display:flex;align-items:center;gap:5px;color:#F6C343;font-size:9px}.maintenance-state i{width:7px;height:7px;border-radius:50%;background:currentColor}.maintenance-state.on{color:#EF4444}.feature-list{min-height:0;display:grid;grid-template-rows:repeat(6,1fr)}.feature-row{display:grid;grid-template-columns:1fr 1fr 29px;align-items:center;border:0;border-bottom:1px solid #263B4F;color:#DDEBFF;background:transparent;text-align:left;font-size:9px}.feature-row>span{display:flex;align-items:center;gap:5px}.feature-row>span svg{color:#F6C343}.feature-row small{overflow:hidden;color:#7F93AB;text-overflow:ellipsis;white-space:nowrap;font-size:8px}.feature-row>i{position:relative;width:25px;height:13px;border-radius:8px;background:#334C68}.feature-row>i b{position:absolute;top:2px;left:2px;width:9px;height:9px;border-radius:50%;background:#8EA3BC}.feature-row>i.on{background:#A62B38}.feature-row>i.on b{left:14px;background:#FFF}.feature-row.permanent{opacity:.48}.maintenance-actions{display:grid;grid-template-columns:1fr 1.2fr;gap:6px}.maintenance-actions button{display:flex;align-items:center;justify-content:center;gap:5px;border:1px solid;border-radius:4px;font-size:9px}.maintenance-actions .mock{color:#F6C343;border-color:#A87820;background:#32260C}.maintenance-actions .enter{color:#FFE1B2;border-color:#EF4444;background:#5A1825}.maintenance-actions .exit{color:#21C55D;border-color:#21C55D;background:#0C3B27}
.trend-card select{width:86px;height:23px;font-size:9px}.trend-content{height:calc(100% - 31px);display:grid;grid-template-rows:132px 50px 25px;gap:5px}.storage-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:5px}.storage-kpis>div{display:grid;place-items:center;border-right:1px solid #1E3A5F}.storage-kpis>div:last-child{border-right:0}.storage-kpis span{color:#7F97B6;font-size:8px}.storage-kpis strong{color:#8FC2FF;font-size:13px}.cleanup-line{display:flex;align-items:center;gap:7px;border-top:1px solid #1E3A5F;color:#7F97B6;font-size:8px}.cleanup-line svg,.cleanup-line b{color:#21C55D}.cleanup-line b{margin-left:auto}
.safety-card{position:relative}.safety-version-grid{height:calc(100% - 67px);display:grid;grid-template-columns:1.05fr .95fr;gap:9px;padding-top:5px}.safe-rules,.version-list{min-height:0;display:grid}.safe-rules{grid-template-rows:repeat(9,1fr);border-right:1px solid #1E3A5F;padding-right:8px}.safe-rules>div{display:grid;grid-template-columns:16px 1fr 28px;align-items:center;border-bottom:1px solid #153153;color:#21C55D;font-size:8px}.safe-rules span{color:#B8C9DC}.safe-rules b{font-size:8px}.version-list{grid-template-rows:repeat(7,1fr)}.version-list>div{display:grid;grid-template-columns:65px 1fr;align-items:center;border-bottom:1px solid #153153;font-size:8px}.version-list span{color:#7F97B6}.version-list b{overflow:hidden;color:#DDEBFF;text-overflow:ellipsis;white-space:nowrap}.safety-actions{position:absolute;left:10px;right:10px;bottom:7px;display:grid;grid-template-columns:1fr 1fr;gap:6px}.safety-actions .danger-outline{color:#F6C343;border-color:#B17D1D;background:#30250D}
.settings-action-bar{display:grid;grid-template-columns:repeat(4,1fr) 1.05fr 1.15fr 1.15fr;gap:9px;min-height:0}.action-button{min-width:0;display:grid;grid-template-columns:42px 1fr;align-items:center;border:1px solid #315A83;border-radius:7px;color:#CFE2FF;background:linear-gradient(180deg,#102A4A,#0A1D33);text-align:left}.action-button:hover{border-color:#2F80FF}.action-button.primary{border-color:#2F80FF;background:linear-gradient(135deg,#176CD9,#0E4A98)}.action-button.warning{border-color:#A87820;background:linear-gradient(135deg,#4A3512,#241E10);color:#FFE7A1}.action-button.danger{border-color:#EF4444;background:linear-gradient(135deg,#6A1927,#35131B);color:#FFDCE2}.action-icon{display:grid;place-items:center;color:#73B4FF}.warning .action-icon{color:#F6C343}.danger .action-icon{color:#FF7186}.action-copy{min-width:0;display:grid;gap:3px}.action-copy strong{font-size:11px}.action-copy small{overflow:hidden;color:#8FA5C1;text-overflow:ellipsis;white-space:nowrap;font-size:8px}
.dialog-overlay{position:fixed;inset:0;z-index:80;display:grid;place-items:center;background:rgba(2,8,16,.78);backdrop-filter:blur(3px)}.danger-dialog{width:440px;padding:20px;border:1px solid #EF4444;border-radius:8px;background:#0D2036;box-shadow:0 24px 64px rgba(0,0,0,.6)}.dialog-icon{width:48px;height:48px;display:grid;place-items:center;margin:0 auto;border-radius:50%;color:#F6C343;background:rgba(246,195,67,.12);box-shadow:0 0 0 1px rgba(246,195,67,.35)}.danger-dialog h3{margin:10px 0 5px;text-align:center;font-size:18px}.danger-dialog>p{margin:0 0 14px;color:#9FB4CF;text-align:center;font-size:11px;line-height:1.5}.danger-dialog label{display:grid;gap:5px;margin-top:10px;color:#9FB4CF;font-size:10px}.danger-dialog label b{color:#F6C343}.danger-dialog input{height:32px;border:1px solid #315A83;border-radius:5px;outline:none;color:#EAF2FF;background:#07192D;padding:0 9px}.dialog-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:16px}.dialog-actions button{height:32px;padding:0 16px;border:1px solid #315A83;border-radius:5px;color:#DDEBFF;background:#102A4A}.dialog-actions .confirm-danger{border-color:#EF4444;background:#A52232}.dialog-actions button:disabled{opacity:.4}.toast{position:absolute;right:16px;bottom:88px;z-index:70;max-width:620px;padding:10px 14px;border:1px solid #2F80FF;border-radius:7px;color:#DDEBFF;background:rgba(10,24,43,.98);box-shadow:0 12px 28px rgba(0,0,0,.4);font-size:11px}
.hidden-file-input{display:none}.config-preview-dialog{width:min(760px,80vw);max-height:80vh;overflow:auto;padding:20px;border:1px solid #2F80FF;border-radius:8px;background:#0D2036;box-shadow:0 24px 64px rgba(0,0,0,.6)}.config-preview-dialog h3{margin:0 0 8px}.config-preview-dialog>p{font-size:11px}.preview-ok{color:#21C55D}.preview-blocked,.preview-blockers{color:#F6C343}.preview-summary{display:flex;gap:16px;padding:8px;border:1px solid #24486F;border-radius:5px;color:#BFD2E9;font-size:10px}.preview-diff{max-height:300px;overflow:auto;margin-top:10px;border-top:1px solid #24486F}.preview-diff>div{display:grid;grid-template-columns:240px 1fr;gap:10px;padding:7px;border-bottom:1px solid #173456;font-size:9px}.preview-diff span{overflow-wrap:anywhere;color:#9FB4CF}.preview-blockers{margin-top:8px;font-size:10px}.config-preview-dialog>label{display:grid;gap:5px;margin-top:12px;color:#9FB4CF;font-size:10px}.config-preview-dialog input{height:32px;border:1px solid #315A83;border-radius:5px;color:#EAF2FF;background:#07192D;padding:0 9px}
@media(max-width:1500px){.system-settings-page{min-width:1120px}.settings-row-one{grid-template-columns:1fr 1fr 1fr}.title-actions{gap:5px}.title-actions>button{padding:0 7px}.dense-table{font-size:8px}.feature-row{grid-template-columns:1fr .85fr 29px}.settings-action-bar{gap:6px}}
@media(max-height:800px){.system-settings-page{grid-template-rows:42px minmax(150px,1fr) minmax(150px,1fr) minmax(140px,1fr) 60px;gap:7px;overflow:hidden}.settings-action-bar{gap:6px}.action-button{grid-template-columns:30px 1fr}.action-copy small{display:none}.card-title{height:27px}.field-grid{height:calc(100% - 27px);grid-auto-rows:26px}.dbc-content,.storage-content,.audit-content{height:calc(100% - 27px)}}
</style>
