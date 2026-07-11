import { defineStore } from 'pinia'
import { apiGet } from '../api/http'
import { wsClient } from '../api/websocket'
import type { CanFrameRow, ChannelStatus, OverviewSummary, SignalValue, StatusSnapshot } from '../api/types'
import { fallbackStatus, fallbackChannels } from '../mocks/fallbackData'

interface State { backendOnline: boolean; error: string; status: StatusSnapshot; channels: ChannelStatus[]; signals: Record<string, SignalValue>; frames: CanFrameRow[]; timeseries: Record<string, Array<{t:string; value:number}>>; wsBound: boolean }

export const useAppStatusStore = defineStore('appStatus', {
  state: (): State => ({ backendOnline: false, error: '', status: fallbackStatus, channels: fallbackChannels, signals: {}, frames: [], timeseries: {}, wsBound: false }),
  actions: {
    async refresh() {
      try {
        const overview = await apiGet<OverviewSummary & {status: StatusSnapshot; signals: { signals: Record<string, SignalValue> }}>('/overview/summary')
        const overviewChannels: ChannelStatus[] = overview.channels
          ? Object.entries(overview.channels).map(([channel, item]) => {
            const [localIp, localPort] = item.local.split(':')
            const [deviceIp, devicePort] = item.device.split(':')
            return {
              channel,
              protocol: item.protocol,
              local_ip: localIp,
              local_port: Number(localPort),
              device_ip: deviceIp,
              device_port: Number(devicePort),
              online: item.online,
              fps: item.fps,
              error_count: item.error_frames,
              last_frame_hex: item.last_data_hex,
            }
          })
          : []
        this.channels = overviewChannels.length ? overviewChannels : (overview.status.channels.length ? overview.status.channels : fallbackChannels)
        this.status = {
          ...overview.status,
          station_id: overview.station?.station_id ?? overview.status.station_id,
          operator: overview.station?.operator ?? overview.status.operator,
          software_version: overview.station?.software_version ?? overview.status.software_version,
          control_channel: overview.station?.control_channel ?? overview.status.control_channel,
          emergency_stop: overview.alarm_summary?.emergency_stop ?? overview.status.emergency_stop,
          mock_enabled: overview.station?.mock_enabled ?? overview.status.mock_enabled,
          max_alarm_level: overview.alarm_summary?.max_alarm_level ?? overview.status.max_alarm_level,
          database: {
            type: overview.station?.database.name ?? overview.status.database.type,
            writable: (overview.station?.database.status ?? 'normal') === 'normal',
          },
          dbc: {
            ...overview.status.dbc,
            version: overview.station?.dbc_version ?? overview.status.dbc.version,
          },
          channels: this.channels,
        }
        this.signals = overview.signals.signals
        this.backendOnline = true
        this.error = ''
      } catch (e) {
        this.backendOnline = false
        this.error = e instanceof Error ? e.message : String(e)
      }
    },
    connectWs() {
      if (this.wsBound) return
      this.wsBound = true
      wsClient.on('can.channel_status', (payload) => { this.channels = payload as ChannelStatus[] })
      wsClient.on('signals.current', (payload) => { const p = payload as { signals: Record<string, SignalValue> }; this.signals = p.signals })
      wsClient.on('signals.timeseries.batch', () => { /* owned by the signals store */ })
      wsClient.on('system.version', (payload) => { this.status = payload as StatusSnapshot })
      wsClient.on('system.maintenance_changed', (payload) => {
        const update = payload as { mock_can_gateway?: boolean }
        if (typeof update.mock_can_gateway === 'boolean') this.status.mock_enabled = update.mock_can_gateway
      })
      wsClient.connect()
    }
  }
})
