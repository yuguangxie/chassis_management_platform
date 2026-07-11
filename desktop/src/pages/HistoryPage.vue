<template>
  <section class="history-page">
    <header class="page-title-row">
      <div class="title-left"><div class="title-icon"><History :size="22" /></div><div><h1>历史记录与追溯</h1><p>检测会话、断言、日志与原始数据追溯</p></div></div>
      <div class="title-actions">
        <span v-if="historyStore.offline || dashboard.mock" class="mock-badge">{{ historyStore.offline ? '后端离线，当前使用 Mock 历史数据' : '显式 Mock 历史数据' }}</span>
        <button class="auto-switch" role="switch" :aria-checked="autoRefresh" aria-label="自动刷新" @click="toggleAutoRefresh"><span></span><b>自动刷新</b></button>
        <select v-model="refreshSeconds" aria-label="刷新间隔" @change="onIntervalChange"><option value="10">10s</option><option value="30">30s</option><option value="60">60s</option><option value="0">关闭</option></select>
      </div>
    </header>

    <article class="panel filter-panel">
      <div class="filter-line first-line">
        <label><span>底盘编号</span><input v-model="filters.chassisNo" placeholder="请输入底盘编号" /></label>
        <label><span>VIN</span><input v-model="filters.vin" placeholder="请输入VIN" /></label>
        <label><span>序列号</span><input v-model="filters.serialNo" placeholder="请输入序列号" /></label>
        <label class="time-range"><span>时间范围</span><div><CalendarDays :size="14" /><input v-model="filters.startTime" /><em>~</em><input v-model="filters.endTime" /></div></label>
        <label><span>结果</span><select v-model="filters.result"><option>全部</option><option>PASS</option><option>FAIL</option><option>ABORTED</option><option>RUNNING</option></select></label>
      </div>
      <div class="filter-line second-line">
        <label><span>操作员</span><select v-model="filters.operator"><option>全部</option><option>op01</option><option>op02</option></select></label>
        <label><span>工位</span><select v-model="filters.station"><option>全部</option><option>EOL-STATION-01</option></select></label>
        <div class="filter-actions"><button class="primary" @click="queryHistory"><Search :size="15" />查询</button><button @click="resetFilters"><RotateCcw :size="15" />重置</button><button @click="exportHistory"><Download :size="15" />导出历史</button></div>
      </div>
    </article>

    <section class="history-main-row">
      <article class="panel session-panel">
        <h2>检测会话列表 <span>（共 {{ dashboard.pagination.total }} 条）</span></h2>
        <div class="table-scroll"><table class="dense-table session-table"><thead><tr><th>session_id</th><th>底盘编号</th><th>VIN</th><th>开始时间</th><th>结束时间</th><th>结果</th><th>失败步骤</th><th>操作员</th><th>报告</th></tr></thead><tbody>
          <tr v-for="row in dashboard.sessions" :key="row.session_id" :class="{ selected: row.session_id === historyStore.selectedSessionId }" @click="selectSession(row.session_id)">
            <td>{{ row.session_id }}</td><td>{{ row.chassis_no }}</td><td>{{ row.vin }}</td><td>{{ row.started_at }}</td><td>{{ row.ended_at }}</td><td><ResultPill :value="row.result" /></td><td>{{ row.failed_step }}</td><td>{{ row.operator }}</td><td><button class="report-btn" :aria-label="`查看报告 ${row.report_id || row.session_id}`" @click.stop="openReport(row)"><FileText :size="15" /></button></td>
          </tr>
        </tbody></table></div>
      </article>

      <article class="panel timeline-panel">
        <header><h2>会话详情：{{ selected.session_id }}</h2><div><span>总耗时：{{ selected.duration }}</span><ResultPill :value="selected.result" /></div></header>
        <div class="timeline-scroll">
          <div v-for="(item, index) in selected.timeline" :key="`${item.time}-${item.title}`" :class="['timeline-item', item.status.toLowerCase()]">
            <time>{{ item.time }}</time><div class="timeline-node"><component :is="timelineIcon(item.icon)" :size="14" /></div>
            <div class="timeline-copy"><strong>{{ item.title }}</strong><span>{{ item.description }}</span></div>
            <ResultPill v-if="item.status !== 'INFO'" :value="item.status" /><Info v-else :size="15" class="info-icon" />
            <i v-if="index < selected.timeline.length - 1"></i>
          </div>
        </div>
      </article>
    </section>

    <section class="history-log-row">
      <article class="panel log-panel"><h2>操作日志 <span>（与所选会话相关）</span></h2><div class="table-scroll"><table class="dense-table log-table"><thead><tr><th>时间</th><th>用户</th><th>动作</th><th>对象</th><th>参数摘要</th><th>结果</th></tr></thead><tbody><tr v-for="row in selected.operator_logs" :key="`${row.time}-${row.action}`"><td>{{ row.time }}</td><td>{{ row.user }}</td><td>{{ row.action }}</td><td>{{ row.target }}</td><td>{{ row.params }}</td><td><span class="success-pill">{{ row.result }}</span></td></tr></tbody></table></div></article>
      <article class="panel downloads-panel"><h2>原始数据与报告下载</h2><div class="download-cards"><button v-for="(item, index) in selected.downloads" :key="item.key" :class="`file-${index}`" :aria-label="`下载 ${item.name}`" @click="downloadFile(item)"><span class="file-icon"><component :is="downloadIcon(item.key)" :size="22" /></span><span class="file-copy"><strong>{{ item.name }}</strong><small>{{ item.extension }}</small></span><span class="file-footer"><b>{{ item.size }}</b><Download :size="15" /></span></button></div></article>
    </section>

    <section class="history-chart-row">
      <article class="panel chart-panel"><h2>某底盘多次检测结果趋势 <span>（VIN: {{ dashboard.charts.vehicle_result_trend.vin }}）</span></h2><RealtimeLineChart :option="trendOption" height="100%" /></article>
      <article class="panel chart-panel"><h2>失败原因 Pareto <span>（近 30 天）</span></h2><RealtimeLineChart :option="paretoOption" height="100%" /></article>
      <article class="panel session-actions-panel"><h2>会话操作</h2><div class="session-actions"><button @click="openDetail"><span><FolderSearch :size="26" /></span><strong>打开会话详情</strong><small>查看完整步骤与断言</small></button><button class="replay" @click="replayCurve"><span><ChartNoAxesCombined :size="26" /></span><strong>回放曲线</strong><small>多通道信号曲线回放</small></button><button class="bundle" @click="downloadBundle"><span><Download :size="26" /></span><strong>下载数据包</strong><small>下载所选会话全部数据</small></button></div></article>
    </section>

    <footer class="history-footer">
      <div class="summary-stats"><div><span>累计检测</span><strong class="green">{{ dashboard.summary.total_tests.toLocaleString() }}</strong></div><div><span>PASS率</span><strong class="green">{{ dashboard.summary.pass_rate }}%</strong></div><div><span>FAIL数</span><strong class="red">{{ dashboard.summary.fail_count }}</strong></div><div><span>告警总数</span><strong class="red">{{ dashboard.summary.alarm_count }}</strong></div><div><span>当前筛选结果</span><strong class="green">{{ dashboard.summary.filtered_count }} <small>条</small></strong></div></div>
      <div class="pagination"><span>共 {{ dashboard.pagination.total }} 条</span><select v-model.number="filters.pageSize" aria-label="每页数量" @change="changePage(1)"><option :value="20">20条/页</option><option :value="50">50条/页</option><option :value="100">100条/页</option></select><button aria-label="首页" @click="changePage(1)">|‹</button><button aria-label="上一页" @click="changePage(Math.max(1, filters.page - 1))">‹</button><button v-for="page in pageNumbers" :key="page" :class="{ active: page === dashboard.pagination.page }" @click="changePage(page)">{{ page }}</button><button aria-label="下一页" @click="changePage(Math.min(dashboard.pagination.total_pages || 1, filters.page + 1))">›</button><button aria-label="末页" @click="changePage(dashboard.pagination.total_pages || 1)">›|</button></div>
    </footer>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </section>
</template>

<script setup lang="ts">
import {
  BatteryCharging, CalendarDays, ChartNoAxesCombined, Database, Download, FileArchive, FileJson, FileSpreadsheet,
  CarFront, FileText, FolderSearch, Gauge, History, Info, Network, Power, RotateCcw, Search, Settings,
  TriangleAlert, UserRound,
} from 'lucide-vue-next'
import type { Component, PropType } from 'vue'
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { wsClient } from '../api/websocket'
import { formatApiError } from '../api/http'
import type { HistoryDownloadItem, HistorySessionItem, HistorySessionResult } from '../api/types'
import RealtimeLineChart from '../components/charts/RealtimeLineChart.vue'
import { fallbackHistoryDashboard } from '../mocks/fallbackData'
import { useHistoryStore, type HistoryQuery } from '../stores/history'

const historyStore = useHistoryStore()
const router = useRouter()
const dashboard = computed(() => historyStore.dashboard)
const emptySelected = {
  session_id: '', duration: '-', result: 'RUNNING' as const, timeline: [], operator_logs: [], downloads: [],
}
const selected = computed(() => dashboard.value.selected_session || (historyStore.offline ? fallbackHistoryDashboard.selected_session! : emptySelected))
const autoRefresh = ref(true)
const refreshSeconds = ref('30')
const toast = ref('')
let toastTimer: number | undefined
let refreshTimer: number | undefined
let wsReady = false
let wsDisposers: Array<() => void> = []

const filters = reactive({ chassisNo: '', vin: '', serialNo: '', startTime: '2026-03-25 00:00', endTime: '2026-04-01 23:59', result: '全部', operator: '全部', station: '全部', page: 1, pageSize: 20 })

const ResultPill = defineComponent({
  props: { value: { type: String as PropType<HistorySessionResult | 'INFO'>, required: true } },
  setup(props) { return () => h('span', { class: ['result-pill', props.value.toLowerCase()] }, props.value) },
})

const pageNumbers = computed(() => Array.from({ length: Math.min(7, dashboard.value.pagination.total_pages || 1) }, (_, index) => index + 1))

const trendOption = computed(() => {
  const chart = dashboard.value.charts.vehicle_result_trend
  return { backgroundColor:'transparent',color:['#21C55D','#EF4444'],tooltip:{trigger:'axis'},legend:{top:0,right:8,textStyle:{color:'#CFE2FF',fontSize:10},itemWidth:14},grid:{left:34,right:14,top:28,bottom:24,containLabel:true},xAxis:{type:'category',data:chart.x_axis,boundaryGap:false,axisLabel:{color:'#8CA6C5',fontSize:9},axisLine:{lineStyle:{color:'#315A83'}},splitLine:{show:true,lineStyle:{color:'#143050',type:'dashed'}}},yAxis:{type:'value',min:0,max:20,axisLabel:{color:'#8CA6C5',fontSize:9},splitLine:{lineStyle:{color:'#1A385C',type:'dashed'}}},series:[{name:'PASS',type:'line',smooth:false,data:chart.pass,symbol:'circle',symbolSize:6,label:{show:true,position:'top',color:'#DDEBFF',fontSize:9},lineStyle:{width:2}},{name:'FAIL',type:'scatter',data:chart.fail.map((value,index)=>value? [chart.x_axis[index],value]:null).filter(Boolean),symbolSize:7,label:{show:true,position:'top',color:'#EF4444',fontSize:9}}] }
})

const paretoOption = computed(() => {
  const chart = dashboard.value.charts.failure_pareto
  return { backgroundColor:'transparent',color:['#2F80FF','#F6C343'],tooltip:{trigger:'axis'},legend:{top:0,right:8,textStyle:{color:'#CFE2FF',fontSize:10},itemWidth:14},grid:{left:34,right:36,top:28,bottom:30,containLabel:true},xAxis:{type:'category',data:chart.categories,axisLabel:{color:'#8CA6C5',fontSize:9,interval:0},axisLine:{lineStyle:{color:'#315A83'}}},yAxis:[{type:'value',min:0,max:15,axisLabel:{color:'#8CA6C5',fontSize:9},splitLine:{lineStyle:{color:'#1A385C',type:'dashed'}}},{type:'value',min:0,max:100,axisLabel:{formatter:'{value}%',color:'#F6C343',fontSize:9},splitLine:{show:false}}],series:[{name:'失败次数',type:'bar',barWidth:'38%',data:chart.counts,label:{show:true,position:'top',color:'#DDEBFF',fontSize:9}},{name:'累计占比',type:'line',yAxisIndex:1,data:chart.cumulative_percent,symbol:'circle',symbolSize:5,label:{show:true,formatter:'{c}%',position:'top',color:'#F6C343',fontSize:9},lineStyle:{width:2}}] }
})

onMounted(async () => { await historyStore.loadDashboard(currentQuery()); setupWebSocket(); scheduleRefresh() })
onBeforeUnmount(() => { if(refreshTimer) window.clearInterval(refreshTimer); if(toastTimer) window.clearTimeout(toastTimer); wsDisposers.forEach((dispose)=>dispose()); wsDisposers=[] })
watch([autoRefresh, refreshSeconds], scheduleRefresh)

function currentQuery(): HistoryQuery { return { chassis_no:filters.chassisNo,vin:filters.vin,serial_no:filters.serialNo,start_time:filters.startTime==='2026-03-25 00:00'?'':filters.startTime,end_time:filters.endTime==='2026-04-01 23:59'?'':filters.endTime,result:filters.result,operator:filters.operator,station:filters.station,page:filters.page,page_size:filters.pageSize } }
async function queryHistory(){ filters.page=1; await historyStore.loadDashboard(currentQuery()); showToast(`查询完成：共 ${dashboard.value.pagination.total} 条`) }
async function resetFilters(){ Object.assign(filters,{chassisNo:'',vin:'',serialNo:'',startTime:'2026-03-25 00:00',endTime:'2026-04-01 23:59',result:'全部',operator:'全部',station:'全部',page:1,pageSize:20}); await historyStore.loadDashboard(currentQuery()); showToast('筛选条件已重置') }
async function exportHistory(){ try{const result=await historyStore.exportHistory(currentQuery());showToast(`导出历史：${result.message||'完成'}`)}catch(error){showToast(`导出历史：${formatError(error)}`)} }
async function changePage(page:number){ filters.page=page; await historyStore.loadDashboard(currentQuery()); }
async function selectSession(sid:string){ await historyStore.selectSession(sid) }
function openReport(row:HistorySessionItem){ void router.push({path:'/report-management',query:{report_id:row.report_id||'',session_id:row.session_id}}) }
async function downloadFile(item:HistoryDownloadItem){ try{const result=await historyStore.downloadFile(item);showToast(`${item.name}：已下载 ${result.filename}`)}catch(error){showToast(`${item.name}：${formatError(error)}`)} }
async function openDetail(){ try{const result=await historyStore.openDetail();showToast(`打开会话详情：${result.message||'完成'}`)}catch(error){showToast(`打开会话详情：${formatError(error)}`)} }
function replayCurve(){ void router.push({path:'/realtime-curve',query:{session_id:historyStore.selectedSessionId,mode:'history'}}) }
async function downloadBundle(){ try{const result=await historyStore.downloadBundle();showToast(`下载数据包：已下载 ${result.filename}`)}catch(error){showToast(`下载数据包：${formatError(error)}`)} }
function toggleAutoRefresh(){ autoRefresh.value=!autoRefresh.value; if(autoRefresh.value&&refreshSeconds.value==='0') refreshSeconds.value='30' }
function onIntervalChange(){ autoRefresh.value=refreshSeconds.value!=='0' }
function scheduleRefresh(){ if(refreshTimer) window.clearInterval(refreshTimer); refreshTimer=undefined; const seconds=Number(refreshSeconds.value); if(autoRefresh.value&&seconds>0) refreshTimer=window.setInterval(()=>void historyStore.loadDashboard(currentQuery(),true),seconds*1000) }
function setupWebSocket(){ try{if(!wsReady){wsClient.connect();wsReady=true}wsDisposers.push(wsClient.on('history.export_progress',()=>void historyStore.loadDashboard(currentQuery(),true)))}catch{wsReady=false} }
function timelineIcon(icon:string):Component { return {power:Power,network:Network,battery:BatteryCharging,settings:Settings,gauge:Gauge,steering:CarFront,user:UserRound,alarm:TriangleAlert,report:FileText}[icon]||Settings }
function downloadIcon(key:HistoryDownloadItem['key']):Component { return {raw_can:Database,decoded_signals:FileSpreadsheet,report_bundle:FileArchive,audit_log:FileJson,curve_replay:ChartNoAxesCombined}[key] }
function formatError(error:unknown){ return formatApiError(error) }
function showToast(message:string){toast.value=message;if(toastTimer)window.clearTimeout(toastTimer);toastTimer=window.setTimeout(()=>{if(toast.value===message)toast.value=''},2800)}
</script>

<style scoped>
.history-page{position:relative;height:100%;min-height:0;overflow:hidden;display:grid;grid-template-rows:52px 100px 300px 180px minmax(0,1fr) 62px;gap:10px;color:#EAF2FF}.panel{min-height:0;overflow:hidden;border:1px solid #1E3A5F;border-radius:8px;background:linear-gradient(180deg,rgba(16,36,61,.98),rgba(8,23,41,.98));box-shadow:0 9px 22px rgba(0,0,0,.2)}
.page-title-row{display:flex;align-items:center;justify-content:space-between;padding:0 4px}.title-left,.title-actions{display:flex;align-items:center;gap:10px}.title-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:6px;color:#B9D9FF;border:1px solid rgba(47,128,255,.5);background:linear-gradient(135deg,rgba(47,128,255,.42),rgba(34,211,238,.16))}.page-title-row h1{margin:0;font-size:22px;line-height:24px;font-weight:800}.page-title-row p{margin:4px 0 0;color:#8CA6C5;font-size:12px}.mock-badge{height:29px;display:inline-flex;align-items:center;padding:0 10px;border-radius:6px;border:1px solid rgba(246,195,67,.42);color:#F6C343;background:rgba(246,195,67,.1);font-size:11px}.title-actions select{height:30px;width:82px;border:1px solid #315A83;border-radius:5px;color:#CFE2FF;background:#081A2F;padding:0 8px;font-size:11px}.auto-switch{height:30px;display:flex;align-items:center;gap:7px;border:1px solid #315A83;border-radius:5px;color:#AFC2DA;background:#0B2038;padding:0 9px;font-size:11px}.auto-switch span{position:relative;width:25px;height:13px;border-radius:999px;background:#315A83}.auto-switch span::after{content:'';position:absolute;top:2px;left:2px;width:9px;height:9px;border-radius:50%;background:#8CA6C5;transition:.15s}.auto-switch[aria-checked=true] span{background:#176CD9}.auto-switch[aria-checked=true] span::after{left:14px;background:#EAF2FF}
.filter-panel{display:grid;grid-template-rows:1fr 1fr;padding:7px 12px}.filter-line{display:grid;align-items:end;gap:14px}.first-line{grid-template-columns:.75fr .85fr .75fr 1.55fr .65fr}.second-line{grid-template-columns:.75fr .85fr 1fr 2.25fr}.filter-line label{display:grid;gap:2px;min-width:0;color:#AFC2DA;font-size:10px;line-height:10px}.filter-line input,.filter-line select{width:100%;height:30px;border:1px solid #1E3A5F;border-radius:5px;outline:none;color:#DDEBFF;background:#081A2F;padding:0 9px;font-size:11px}.filter-line input::placeholder{color:#5F7899}.time-range div{height:30px;display:grid;grid-template-columns:20px 1fr 15px 1fr;align-items:center;border:1px solid #1E3A5F;border-radius:5px;background:#081A2F;padding:0 6px;color:#7D96B4}.time-range input{height:26px;border:0;padding:0 3px}.time-range em{text-align:center;font-style:normal}.filter-actions{grid-column:4;display:flex;justify-content:flex-end;align-items:end;gap:10px}.filter-actions button{height:32px;min-width:104px;display:flex;align-items:center;justify-content:center;gap:7px;border:1px solid #315A83;border-radius:5px;color:#CFE2FF;background:#102A4A;font-size:12px;font-weight:700}.filter-actions button.primary{border-color:#2F80FF;background:linear-gradient(135deg,#176CD9,#0E4A98)}
.history-main-row,.history-log-row{display:grid;grid-template-columns:1.55fr .95fr;gap:10px;min-height:0}.history-chart-row{display:grid;grid-template-columns:1fr 1fr .9fr;gap:10px;min-height:0}.panel h2{margin:0;color:#EAF2FF;font-size:13px;line-height:20px;font-weight:800}.panel h2 span{color:#8CA6C5;font-size:10px;font-weight:500}.session-panel,.log-panel{display:grid;grid-template-rows:30px minmax(0,1fr);padding:0 8px 8px}.session-panel h2,.log-panel h2{display:flex;align-items:center}.table-scroll{min-height:0;overflow:auto;scrollbar-color:#2B5C90 #07172A}.dense-table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:9px}.dense-table th,.dense-table td{height:29px;padding:0 6px;border:1px solid #1E3A5F;color:#CFE2FF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dense-table th{position:sticky;top:0;z-index:1;color:#AFC2DA;background:#0A2039;font-weight:700}.session-table tbody tr{cursor:pointer}.session-table tbody tr:hover,.session-table tbody tr.selected{background:rgba(47,128,255,.14)}.session-table tbody tr.selected{box-shadow:inset 3px 0 #2F80FF}.session-table th:nth-child(1){width:16%}.session-table th:nth-child(2){width:10%}.session-table th:nth-child(3){width:16%}.session-table th:nth-child(4){width:15%}.session-table th:nth-child(5){width:15%}.session-table th:nth-child(6){width:7%}.session-table th:nth-child(7){width:10%}.session-table th:nth-child(8){width:7%}.session-table th:nth-child(9){width:4%}.report-btn,.pagination button{border:0;color:#2F80FF;background:transparent}.result-pill,.success-pill{display:inline-flex;align-items:center;justify-content:center;min-width:40px;height:19px;border-radius:3px;font-size:9px;font-weight:800}.result-pill.pass,.success-pill{color:#21C55D;border:1px solid rgba(33,197,93,.6);background:rgba(33,197,93,.08)}.result-pill.fail,.result-pill.aborted{color:#EF4444;border:1px solid rgba(239,68,68,.65);background:rgba(239,68,68,.08)}.result-pill.running{color:#F6C343;border:1px solid rgba(246,195,67,.65);background:rgba(246,195,67,.08)}
.timeline-panel{display:grid;grid-template-rows:32px minmax(0,1fr);padding:0 10px 8px}.timeline-panel header{display:flex;align-items:center;justify-content:space-between}.timeline-panel header div{display:flex;align-items:center;gap:10px;color:#AFC2DA;font-size:10px}.timeline-scroll{min-height:0;overflow:auto;padding-right:3px;scrollbar-color:#2B5C90 #07172A}.timeline-item{position:relative;display:grid;grid-template-columns:72px 24px minmax(0,1fr) 48px;align-items:center;min-height:28px;padding:0}.timeline-item time{color:#9AB0CC;font-size:9px}.timeline-node{position:relative;z-index:1;width:20px;height:20px;display:grid;place-items:center;border-radius:50%;color:#CFE2FF;background:#176CD9;box-shadow:0 0 0 3px rgba(47,128,255,.12)}.timeline-item.info .timeline-node{background:#D28B0B}.timeline-copy{min-width:0;display:grid;grid-template-columns:42% 58%;gap:8px}.timeline-copy strong,.timeline-copy span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.timeline-copy strong{font-size:10px}.timeline-copy span{color:#8CA6C5;font-size:9px}.timeline-item>i{position:absolute;left:81px;top:20px;bottom:-8px;width:1px;background:#315A83}.info-icon{color:#2F80FF;justify-self:center}
.log-table th:nth-child(1){width:13%}.log-table th:nth-child(2){width:9%}.log-table th:nth-child(3){width:15%}.log-table th:nth-child(4){width:19%}.log-table th:nth-child(5){width:34%}.log-table th:nth-child(6){width:10%}.log-table th,.log-table td{height:28px}.downloads-panel{display:grid;grid-template-rows:30px minmax(0,1fr);padding:0 10px 10px}.downloads-panel h2{display:flex;align-items:center}.download-cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;min-height:0}.download-cards button{min-width:0;display:grid;grid-template-rows:42px minmax(0,1fr) 25px;border:1px solid #1E3A5F;border-radius:7px;text-align:left;color:#DDEBFF;background:#0A1C31;padding:8px;overflow:hidden}.file-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:6px;color:#74B5FF;background:rgba(47,128,255,.24)}.file-copy{display:grid;align-content:start;gap:4px;min-width:0}.file-copy strong{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.file-copy small{color:#8CA6C5;font-size:9px}.file-footer{display:flex;align-items:end;justify-content:space-between;color:#8CA6C5;font-size:9px}.file-footer svg{color:#BBD8FF}.download-cards .file-1{border-color:rgba(33,197,93,.35)}.file-1 .file-icon{color:#65E397;background:rgba(33,197,93,.2)}.download-cards .file-2{border-color:rgba(246,195,67,.38)}.file-2 .file-icon{color:#F6C343;background:rgba(246,195,67,.18)}.download-cards .file-3 .file-icon{color:#74B5FF;background:rgba(47,128,255,.24)}.download-cards .file-4{border-color:rgba(139,92,246,.4)}.file-4 .file-icon{color:#C3A7FF;background:rgba(139,92,246,.2)}
.chart-panel{display:grid;grid-template-rows:27px minmax(0,1fr);padding:0 8px 7px}.chart-panel h2{display:flex;align-items:center}.session-actions-panel{display:grid;grid-template-rows:30px minmax(0,1fr);padding:0 10px 10px}.session-actions-panel h2{display:flex;align-items:center}.session-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.session-actions button{min-width:0;display:grid;justify-items:center;align-content:center;gap:6px;border:1px solid #2F80FF;border-radius:7px;color:#DDEBFF;background:linear-gradient(135deg,rgba(23,108,217,.62),rgba(14,74,152,.48));padding:8px}.session-actions button span{width:42px;height:42px;display:grid;place-items:center;border-radius:7px;color:#83BDFF;background:rgba(47,128,255,.24)}.session-actions button strong{font-size:11px}.session-actions button small{max-width:100%;color:#8FB2D9;font-size:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.session-actions button.replay{border-color:rgba(33,197,93,.55);background:linear-gradient(135deg,rgba(14,111,65,.62),rgba(10,71,48,.48))}.session-actions button.replay span{color:#61E396;background:rgba(33,197,93,.18)}.session-actions button.bundle{border-color:rgba(139,92,246,.58);background:linear-gradient(135deg,rgba(93,55,161,.64),rgba(59,40,110,.48))}.session-actions button.bundle span{color:#C4A8FF;background:rgba(139,92,246,.2)}
.history-footer{display:flex;align-items:center;justify-content:space-between;min-height:0;border:1px solid #1E3A5F;border-radius:8px;background:linear-gradient(180deg,rgba(16,36,61,.98),rgba(8,23,41,.98));padding:0 12px}.summary-stats{height:42px;display:flex;align-items:center}.summary-stats>div{min-width:122px;height:42px;display:grid;place-items:center;border-right:1px solid #1E3A5F}.summary-stats span{color:#8CA6C5;font-size:9px}.summary-stats strong{font-size:18px;line-height:18px}.summary-stats small{font-size:9px}.green{color:#21C55D}.red{color:#EF4444}.pagination{display:flex;align-items:center;gap:5px;color:#AFC2DA;font-size:10px}.pagination select{height:30px;border:1px solid #315A83;border-radius:4px;color:#CFE2FF;background:#081A2F;padding:0 8px}.pagination button{width:31px;height:31px;border:1px solid #1E3A5F;border-radius:4px;color:#8CA6C5;background:#081A2F}.pagination button.active{color:#FFFFFF;border-color:#2F80FF;background:#176CD9}.toast{position:absolute;right:16px;bottom:74px;z-index:20;max-width:620px;padding:10px 14px;border:1px solid #2F80FF;border-radius:8px;color:#DDEBFF;background:rgba(10,24,43,.97);box-shadow:0 12px 28px rgba(0,0,0,.36);font-size:12px}
@media(max-width:1500px){.history-page{min-width:1120px}.history-main-row,.history-log-row{grid-template-columns:1.45fr 1fr}.filter-line{gap:8px}.summary-stats>div{min-width:100px}.timeline-copy{grid-template-columns:45% 55%}.download-cards{gap:5px}}
@media(max-height:800px){.history-page{grid-template-rows:52px 100px 290px 180px 180px 62px;overflow:auto;scrollbar-color:#2B5C90 #07172A}}
</style>
