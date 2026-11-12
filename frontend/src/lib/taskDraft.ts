import type {
  AssertionKind,
  AssertionSpec,
  ExtractorKind,
  ExtractRule,
  HttpMethod,
  LoadSpec,
  NotifyCategory,
  ProxyConfig,
  RequestSpec,
  Task,
  TaskCreate,
  TaskType,
} from '@/types/api'

export interface Pair {
  key: string
  value: string
}

export interface RuleDraft {
  name: string
  kind: ExtractorKind
  expression: string
  attribute: string
}

export interface AssertionDraft {
  kind: AssertionKind
  expected: string
  path: string
}

export type BodyMode = 'none' | 'json' | 'form' | 'raw'

export interface TaskDraft {
  name: string
  description: string
  enabled: boolean
  schedule: string
  method: HttpMethod
  url: string
  timeoutSeconds: string
  followRedirects: boolean
  verifyTls: boolean
  headers: Pair[]
  query: Pair[]
  cookies: Pair[]
  bodyMode: BodyMode
  jsonText: string
  formPairs: Pair[]
  rawBody: string
  requester: string
  proxyProvider: string
  proxyUrl: string
  proxyUrls: string
  proxyEndpoint: string
  rules: RuleDraft[]
  assertions: AssertionDraft[]
  concurrency: string
  qps: string
  durationSeconds: string
  requestCount: string
  notifyProvider: string
  webhookUrl: string
  notifyOn: Record<NotifyCategory, boolean>
}

export type DraftResult = { ok: true; body: TaskCreate } | { ok: false; message: string }

const MIN_TIMEOUT = 0.1
const MAX_TIMEOUT = 120
const MAX_CONCURRENCY = 50
const MAX_QPS = 100
const MAX_DURATION = 60
const MAX_REQUESTS = 200

function pairsFrom(record: Record<string, string> | null | undefined): Pair[] {
  if (!record) return []
  return Object.entries(record).map(([key, value]) => ({ key, value }))
}

function textParam(params: Record<string, unknown>, key: string): string {
  const value = params[key]
  return typeof value === 'string' ? value : ''
}

function listParam(params: Record<string, unknown>, key: string): string {
  const value = params[key]
  if (!Array.isArray(value)) return ''
  return value.filter((item): item is string => typeof item === 'string').join('\n')
}

export function emptyDraft(taskType: TaskType): TaskDraft {
  return {
    name: '',
    description: '',
    enabled: true,
    schedule: taskType === 'load_test' ? '0 * * * *' : 'every 5 minutes',
    method: 'GET',
    url: 'https://',
    timeoutSeconds: '30',
    followRedirects: true,
    verifyTls: true,
    headers: [],
    query: [],
    cookies: [],
    bodyMode: 'none',
    jsonText: '',
    formPairs: [],
    rawBody: '',
    requester: 'httpx',
    proxyProvider: 'direct',
    proxyUrl: '',
    proxyUrls: '',
    proxyEndpoint: '',
    rules:
      taskType === 'page_change'
        ? [{ name: '标题', kind: 'css', expression: 'title', attribute: '' }]
        : [],
    assertions: taskType === 'api_check' ? [{ kind: 'status', expected: '200', path: '' }] : [],
    concurrency: '2',
    qps: '',
    durationSeconds: '',
    requestCount: '10',
    notifyProvider: 'none',
    webhookUrl: '',
    notifyOn: { change: true, failure: true, block: true },
  }
}

export function draftFromTask(task: Task): TaskDraft {
  const request = task.request
  let bodyMode: BodyMode = 'none'
  let jsonText = ''
  if (request.json_body !== null && request.json_body !== undefined) {
    bodyMode = 'json'
    jsonText = JSON.stringify(request.json_body, null, 2)
  } else if (request.form_body) {
    bodyMode = 'form'
  } else if (request.raw_body) {
    bodyMode = 'raw'
  }
  const notifyOn: Record<NotifyCategory, boolean> = {
    change: task.notify.on.includes('change'),
    failure: task.notify.on.includes('failure'),
    block: task.notify.on.includes('block'),
  }
  return {
    name: task.name,
    description: task.description,
    enabled: task.enabled,
    schedule: task.schedule.expression,
    method: request.method,
    url: request.url,
    timeoutSeconds: String(request.timeout_seconds),
    followRedirects: request.follow_redirects,
    verifyTls: request.verify_tls,
    headers: pairsFrom(request.headers),
    query: pairsFrom(request.query),
    cookies: pairsFrom(request.cookies),
    bodyMode,
    jsonText,
    formPairs: pairsFrom(request.form_body),
    rawBody: request.raw_body ?? '',
    requester: task.requester.name,
    proxyProvider: task.proxy.provider,
    proxyUrl: textParam(task.proxy.params, 'url'),
    proxyUrls: listParam(task.proxy.params, 'urls'),
    proxyEndpoint: textParam(task.proxy.params, 'endpoint'),
    rules: task.extract_rules.map((rule) => ({
      name: rule.name,
      kind: rule.kind,
      expression: rule.expression,
      attribute: rule.attribute ?? '',
    })),
    assertions: task.assertions.map((item) => ({
      kind: item.kind,
      expected: item.expected,
      path: item.path ?? '',
    })),
    concurrency: String(task.load?.concurrency ?? 2),
    qps: task.load?.qps === null || task.load?.qps === undefined ? '' : String(task.load.qps),
    durationSeconds:
      task.load?.duration_seconds === null || task.load?.duration_seconds === undefined
        ? ''
        : String(task.load.duration_seconds),
    requestCount:
      task.load?.request_count === null || task.load?.request_count === undefined
        ? ''
        : String(task.load.request_count),
    notifyProvider: task.notify.provider,
    webhookUrl: textParam(task.notify.params, 'url'),
    notifyOn,
  }
}

function pairsToRecord(pairs: Pair[], label: string): Record<string, string> | string {
  const record: Record<string, string> = {}
  for (const pair of pairs) {
    const key = pair.key.trim()
    if (!key && !pair.value.trim()) continue
    if (!key) return `${label}的名称不能为空`
    if (key in record) return `${label}「${key}」重复了`
    record[key] = pair.value
  }
  return record
}

function numberInRange(
  text: string,
  label: string,
  min: number,
  max: number,
  integer = false,
): number | string {
  const value = Number(text)
  if (!Number.isFinite(value) || value < min || value > max) {
    return `${label}需要在 ${min} 到 ${max} 之间`
  }
  if (integer && !Number.isInteger(value)) return `${label}需要是整数`
  return value
}

function optionalNumber(text: string, label: string, max: number): number | null | string {
  const trimmed = text.trim()
  if (!trimmed) return null
  const value = Number(trimmed)
  if (!Number.isFinite(value) || value <= 0 || value > max) {
    return `${label}需要是大于 0 且不超过 ${max} 的数字`
  }
  return value
}

export function payloadFromDraft(taskType: TaskType, draft: TaskDraft): DraftResult {
  const name = draft.name.trim()
  if (!name) return { ok: false, message: '请填写任务名称' }
  const schedule = draft.schedule.trim()
  if (!schedule) return { ok: false, message: '请填写调度表达式' }
  const url = draft.url.trim()
  if (!url) return { ok: false, message: '请填写目标地址' }
  const timeout = numberInRange(draft.timeoutSeconds, '超时时间', MIN_TIMEOUT, MAX_TIMEOUT)
  if (typeof timeout === 'string') return { ok: false, message: timeout }

  const headers = pairsToRecord(draft.headers, '请求头')
  const query = pairsToRecord(draft.query, '查询参数')
  const cookies = pairsToRecord(draft.cookies, 'Cookie')
  if (typeof headers === 'string') return { ok: false, message: headers }
  if (typeof query === 'string') return { ok: false, message: query }
  if (typeof cookies === 'string') return { ok: false, message: cookies }

  let jsonBody: unknown = null
  let formBody: Record<string, string> | null = null
  let rawBody: string | null = null
  if (draft.bodyMode === 'json') {
    const text = draft.jsonText.trim()
    if (!text) return { ok: false, message: 'JSON 正文不能为空' }
    try {
      jsonBody = JSON.parse(text) as unknown
    } catch {
      return { ok: false, message: 'JSON 正文无法解析' }
    }
  } else if (draft.bodyMode === 'form') {
    const form = pairsToRecord(draft.formPairs, '表单字段')
    if (typeof form === 'string') return { ok: false, message: form }
    formBody = form
  } else if (draft.bodyMode === 'raw') {
    rawBody = draft.rawBody
  }

  const request: RequestSpec = {
    method: draft.method,
    url,
    headers,
    query,
    json_body: jsonBody,
    form_body: formBody,
    raw_body: rawBody,
    cookies,
    timeout_seconds: timeout,
    follow_redirects: draft.followRedirects,
    verify_tls: draft.verifyTls,
  }

  const proxy = proxyConfig(draft)
  if ('message' in proxy) return { ok: false, message: proxy.message }

  const rules = collectRules(taskType, draft.rules)
  if ('message' in rules) return { ok: false, message: rules.message }
  const assertions = collectAssertions(draft.assertions)
  if ('message' in assertions) return { ok: false, message: assertions.message }
  const load = collectLoad(taskType, draft)
  if (load && 'message' in load) return { ok: false, message: load.message }

  const notifyOn = (Object.keys(draft.notifyOn) as NotifyCategory[]).filter(
    (key) => draft.notifyOn[key],
  )
  if (draft.notifyProvider === 'webhook' && !draft.webhookUrl.trim()) {
    return { ok: false, message: 'Webhook 需要填写接收地址' }
  }

  return {
    ok: true,
    body: {
      name,
      description: draft.description.trim(),
      enabled: draft.enabled,
      schedule,
      task_type: taskType,
      request,
      requester: { name: draft.requester, params: {} },
      proxy: proxy.config,
      extract_rules: rules.rules,
      assertions: assertions.assertions,
      load: load && 'spec' in load ? load.spec : null,
      notify: {
        provider: draft.notifyProvider,
        params: draft.notifyProvider === 'webhook' ? { url: draft.webhookUrl.trim() } : {},
        on: notifyOn,
      },
    },
  }
}

function proxyConfig(draft: TaskDraft): { config: ProxyConfig } | { message: string } {
  if (draft.proxyProvider === 'static') {
    if (!draft.proxyUrl.trim()) return { message: '静态代理需要填写 URL' }
    return { config: { provider: 'static', params: { url: draft.proxyUrl.trim() } } }
  }
  if (draft.proxyProvider === 'rotating') {
    const urls = draft.proxyUrls
      .split(/\n+/)
      .map((item) => item.trim())
      .filter(Boolean)
    if (urls.length === 0) return { message: '轮询代理至少需要一个 URL' }
    return { config: { provider: 'rotating', params: { urls } } }
  }
  if (draft.proxyProvider === 'pool_api') {
    return {
      config: {
        provider: 'pool_api',
        params: draft.proxyEndpoint.trim() ? { endpoint: draft.proxyEndpoint.trim() } : {},
      },
    }
  }
  return { config: { provider: draft.proxyProvider || 'direct', params: {} } }
}

function collectRules(
  taskType: TaskType,
  drafts: RuleDraft[],
): { rules: ExtractRule[] } | { message: string } {
  if (taskType !== 'page_change') return { rules: [] }
  const rules: ExtractRule[] = []
  const names = new Set<string>()
  for (const draft of drafts) {
    const name = draft.name.trim()
    const expression = draft.expression.trim()
    if (!name && !expression) continue
    if (!name || !expression) return { message: '提取规则的名称和表达式都要填写' }
    if (names.has(name)) return { message: `提取字段「${name}」重复了` }
    names.add(name)
    rules.push({
      name,
      kind: draft.kind,
      expression,
      attribute: draft.attribute.trim() || null,
    })
  }
  if (rules.length === 0) return { message: '网页监控至少需要一条提取规则' }
  return { rules }
}

function collectAssertions(
  drafts: AssertionDraft[],
): { assertions: AssertionSpec[] } | { message: string } {
  const assertions: AssertionSpec[] = []
  for (const draft of drafts) {
    const expected = draft.expected.trim()
    if (!expected && !draft.path.trim()) continue
    if (!expected) return { message: '断言需要填写期望值' }
    if ((draft.kind === 'jsonpath' || draft.kind === 'header') && !draft.path.trim()) {
      return { message: 'JSONPath 和响应头断言需要填写 path' }
    }
    assertions.push({
      kind: draft.kind,
      expected,
      path: draft.path.trim() || null,
    })
  }
  return { assertions }
}

function collectLoad(
  taskType: TaskType,
  draft: TaskDraft,
): { spec: LoadSpec } | { message: string } | null {
  if (taskType !== 'load_test') return null
  const concurrency = numberInRange(draft.concurrency, '并发', 1, MAX_CONCURRENCY, true)
  if (typeof concurrency === 'string') return { message: concurrency }
  const qps = optionalNumber(draft.qps, 'QPS', MAX_QPS)
  if (typeof qps === 'string') return { message: qps }
  const duration = optionalNumber(draft.durationSeconds, '持续时间', MAX_DURATION)
  if (typeof duration === 'string') return { message: duration }
  const count = optionalNumber(draft.requestCount, '请求次数', MAX_REQUESTS)
  if (typeof count === 'string') return { message: count }
  return {
    spec: {
      concurrency,
      qps,
      duration_seconds: duration,
      request_count: count === null ? null : Math.round(count),
    },
  }
}
