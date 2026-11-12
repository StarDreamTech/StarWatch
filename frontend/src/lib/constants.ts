export const THEME_STORAGE_KEY = 'starwatch.theme'
export const SEARCH_DEBOUNCE_MS = 300
export const LIST_POLL_MS = 15_000
export const NOTICE_MS = 3_200
export const PAGE_SIZE = 20
export const SEARCH_LIMIT = 8
export const BELL_LIMIT = 8

export const TASK_TYPE_LABEL = {
  page_change: '网页监控',
  api_check: '接口探活',
  load_test: '压力测试',
} as const

export const OUTCOME_LABEL = {
  baseline: '建立基线',
  changed: '发生变化',
  unchanged: '没有变化',
  success: '成功',
  failure: '失败',
  blocked: '被拦截',
  empty: '内容为空',
  timeout: '超时',
} as const

export const OUTCOME_TONE = {
  baseline: 'blue',
  changed: 'cyan',
  unchanged: 'muted',
  success: 'emerald',
  failure: 'rose',
  blocked: 'amber',
  empty: 'orange',
  timeout: 'violet',
} as const

export const DIFF_LABEL = {
  added: '新增',
  removed: '移除',
  modified: '修改',
  unchanged: '未变',
} as const

export const CATEGORY_LABEL = {
  change: '变化',
  failure: '失败',
  block: '拦截',
} as const

export const DELIVERY_LABEL = {
  sent: '已送达',
  skipped: '未外发',
  failed: '投递失败',
  not_implemented: '通道未实现',
} as const

export const SLOT_LABEL: Record<string, string> = {
  requester: '请求器',
  proxy: '代理',
  extractor: '提取器',
  notifier: '通知',
  task: '任务类型',
}

export const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'] as const
export const EXTRACTOR_KINDS = ['css', 'xpath', 'jsonpath', 'regex'] as const
export const ASSERTION_KINDS = [
  'status',
  'latency_ms',
  'body_contains',
  'jsonpath',
  'header',
] as const

export function taskListPath(taskType: keyof typeof TASK_TYPE_LABEL): string {
  if (taskType === 'page_change') return '/pages'
  if (taskType === 'api_check') return '/checks'
  return '/load'
}

export function taskEditorPath(taskType: keyof typeof TASK_TYPE_LABEL, id?: string): string {
  const base = taskListPath(taskType)
  return id ? `${base}/${id}` : `${base}/new`
}
