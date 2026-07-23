import { describe, expect, it } from 'vitest'
import {
  binaryStateLabel,
  localizeStatus,
  normalizeBinaryState,
  qualityIsUsable,
  statusTone,
} from './uiStatusLabels'

describe('统一中文状态字典', () => {
  it.each([
    ['online', '在线'], ['offline', '离线'], ['unavailable', '不可用'],
    ['stale', '数据陈旧'], ['invalid', '无效'], ['PASS', '通过'],
    ['FAIL', '失败'], ['RUNNING', '运行中'], ['admin', '管理员'],
    ['Manual', '手动'], ['ON', '开启'], ['RELEASED', '已释放'],
  ])('将 %s 显示为 %s', (raw, expected) => {
    expect(localizeStatus(raw)).toBe(expected)
  })

  it('未知状态不伪装成正常状态', () => {
    expect(localizeStatus('vendor-specific')).toBe('vendor-specific')
    expect(statusTone('unavailable')).toBe('danger')
    expect(qualityIsUsable('stale')).toBe(false)
  })

  it.each([
    ['not-measured', '未测量'],
    ['receive_confirmed', '收帧已确认'],
    ['not_applicable', '不适用'],
    ['owned_by_runtime', '当前进程使用'],
  ])('诊断枚举 %s 显示为中文', (value, expected) => {
    expect(localizeStatus(value)).toBe(expected)
  })

  it.each([
    [true, 'good', 'on', '开启'], [1, 'good', 'on', '开启'], ['ON', 'good', 'on', '开启'],
    [false, 'good', 'off', '关闭'], [0, 'good', 'off', '关闭'], ['OFF', 'good', 'off', '关闭'],
    ['unexpected', 'good', 'unknown', '未知'], ['ON', 'stale', 'unknown', '数据陈旧'],
    [true, 'invalid', 'unknown', '无效'], [true, 'unavailable', 'unknown', '未知'],
  ] as const)('归一化二值状态 %#', (value, quality, state, label) => {
    expect(normalizeBinaryState(value, quality)).toBe(state)
    expect(binaryStateLabel(state, quality)).toBe(label)
  })
})
