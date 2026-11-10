import {
  Bell,
  Blocks,
  Gauge,
  Globe,
  HeartPulse,
  LayoutDashboard,
  List,
  Plus,
  ScrollText,
  Settings,
} from '@lucide/vue'
import type { Component } from 'vue'
import type { TaskType } from '@/types/api'

export type ModuleId =
  'overview' | 'pages' | 'checks' | 'load' | 'alerts' | 'plugins' | 'runs' | 'settings'

export type Accent = 'cyan' | 'blue' | 'emerald' | 'amber' | 'rose' | 'violet' | 'orange' | 'indigo'

export interface NavChild {
  name: string
  description: string
  to: string
  icon: Component
}

export interface NavModule {
  id: ModuleId
  name: string
  en: string
  accent: Accent
  to: string
  icon: Component
  children: NavChild[]
}

export const MODULES: NavModule[] = [
  {
    id: 'overview',
    name: '总览',
    en: 'Overview',
    accent: 'cyan',
    to: '/',
    icon: LayoutDashboard,
    children: [
      { name: '运行概览', description: '任务、今日运行和异常', to: '/', icon: LayoutDashboard },
    ],
  },
  {
    id: 'pages',
    name: '网页监控',
    en: 'Pages',
    accent: 'blue',
    to: '/pages',
    icon: Globe,
    children: [
      { name: '监控列表', description: '按字段比较页面变化', to: '/pages', icon: List },
      {
        name: '新建监控',
        description: 'CSS、XPath、JSONPath 或正则',
        to: '/pages/new',
        icon: Plus,
      },
    ],
  },
  {
    id: 'checks',
    name: '接口探活',
    en: 'API',
    accent: 'emerald',
    to: '/checks',
    icon: HeartPulse,
    children: [
      { name: '探活列表', description: '状态码、耗时和正文断言', to: '/checks', icon: List },
      { name: '新建探活', description: '为接口设置期望结果', to: '/checks/new', icon: Plus },
    ],
  },
  {
    id: 'load',
    name: '压力测试',
    en: 'Load',
    accent: 'amber',
    to: '/load',
    icon: Gauge,
    children: [
      { name: '压测列表', description: '并发、QPS 和延迟汇总', to: '/load', icon: List },
      { name: '新建压测', description: '开始前会再次确认', to: '/load/new', icon: Plus },
    ],
  },
  {
    id: 'alerts',
    name: '告警通知',
    en: 'Alerts',
    accent: 'rose',
    to: '/alerts',
    icon: Bell,
    children: [{ name: '站内通知', description: '变化、失败和拦截', to: '/alerts', icon: Bell }],
  },
  {
    id: 'plugins',
    name: '插件与代理',
    en: 'Plugins',
    accent: 'violet',
    to: '/plugins',
    icon: Blocks,
    children: [
      { name: '已注册插件', description: '请求器、代理、提取和通知', to: '/plugins', icon: Blocks },
    ],
  },
  {
    id: 'runs',
    name: '运行记录',
    en: 'Runs',
    accent: 'orange',
    to: '/runs',
    icon: ScrollText,
    children: [
      { name: '全部运行', description: '结果、差异和响应正文', to: '/runs', icon: ScrollText },
    ],
  },
  {
    id: 'settings',
    name: '设置',
    en: 'Settings',
    accent: 'indigo',
    to: '/settings',
    icon: Settings,
    children: [
      { name: '外观与连接', description: '主题和调度器状态', to: '/settings', icon: Settings },
    ],
  },
]

export function moduleById(id: ModuleId): NavModule {
  const found = MODULES.find((item) => item.id === id)
  if (!found) return MODULES[0]
  return found
}

export function moduleForTask(taskType: TaskType): NavModule {
  if (taskType === 'page_change') return moduleById('pages')
  if (taskType === 'api_check') return moduleById('checks')
  return moduleById('load')
}
