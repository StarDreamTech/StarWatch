export type TaskType = 'page_change' | 'api_check' | 'load_test'
export type Outcome =
  'baseline' | 'changed' | 'unchanged' | 'success' | 'failure' | 'blocked' | 'empty' | 'timeout'
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS'
export type NotifyCategory = 'change' | 'failure' | 'block'
export type DeliveryStatus = 'sent' | 'skipped' | 'failed' | 'not_implemented'
export type DiffStatus = 'added' | 'removed' | 'modified' | 'unchanged'
export type ExtractorKind = 'css' | 'xpath' | 'jsonpath' | 'regex'
export type AssertionKind = 'status' | 'latency_ms' | 'body_contains' | 'jsonpath' | 'header'

export interface ErrorBody {
  code: string
  message: string
  details: Record<string, unknown>
}

export interface Health {
  status: 'ok' | 'degraded'
  service: string
  mongo: 'ok' | 'down' | 'skipped'
}

export interface Schedule {
  kind: 'cron' | 'interval'
  expression: string
  interval_seconds: number | null
}

export interface RequestSpec {
  method: HttpMethod
  url: string
  headers: Record<string, string>
  query: Record<string, string>
  json_body: unknown
  form_body: Record<string, string> | null
  raw_body: string | null
  cookies: Record<string, string>
  timeout_seconds: number
  follow_redirects: boolean
  verify_tls: boolean
}

export interface NamedConfig {
  name: string
  params: Record<string, unknown>
}

export interface ProxyConfig {
  provider: string
  params: Record<string, unknown>
}

export interface ExtractRule {
  name: string
  kind: ExtractorKind
  expression: string
  attribute: string | null
}

export interface AssertionSpec {
  kind: AssertionKind
  expected: string
  path: string | null
}

export interface LoadSpec {
  concurrency: number
  qps: number | null
  duration_seconds: number | null
  request_count: number | null
}

export interface NotifySpec {
  provider: string
  params: Record<string, unknown>
  on: NotifyCategory[]
}

export interface Task {
  id: string
  name: string
  description: string
  enabled: boolean
  schedule: Schedule
  task_type: TaskType
  request: RequestSpec
  requester: NamedConfig
  proxy: ProxyConfig
  extract_rules: ExtractRule[]
  assertions: AssertionSpec[]
  load: LoadSpec | null
  notify: NotifySpec
  next_run_at: string
  last_run_at: string | null
  last_outcome: Outcome | null
  running: boolean
  created_at: string
  updated_at: string
}

export interface TaskCreate {
  name: string
  description: string
  enabled: boolean
  schedule: string
  task_type: TaskType
  request: RequestSpec
  requester: NamedConfig
  proxy: ProxyConfig
  extract_rules: ExtractRule[]
  assertions: AssertionSpec[]
  load: LoadSpec | null
  notify: NotifySpec
}

export interface FieldDiff {
  name: string
  status: DiffStatus
  before: string[]
  after: string[]
}

export interface DiffResult {
  changed: boolean
  fields: FieldDiff[]
}

export interface LoadSample {
  status_code: number | null
  outcome: Outcome
  latency_ms: number | null
  error_type: string | null
}

export interface LoadSummary {
  total: number
  succeeded: number
  failed: number
  blocked: number
  timeouts: number
  latency_ms_p50: number | null
  latency_ms_p95: number | null
  status_histogram: Record<string, number>
  samples: LoadSample[]
}

export interface RunSummary {
  id: string
  task_id: string
  task_name: string
  task_type: TaskType
  outcome: Outcome
  error_type: string | null
  summary: string
  started_at: string
  finished_at: string
  latency_ms: number | null
  status_code: number | null
}

export interface Run extends RunSummary {
  error_message: string | null
  headers: Record<string, string>
  body: string
  body_truncated: boolean
  extracted: Record<string, string[]>
  previous: Record<string, string[]> | null
  diff: DiffResult | null
  load: LoadSummary | null
  final_url: string | null
  requester: string
  proxy_label: string | null
  created_at: string
}

export interface Notification {
  id: string
  task_id: string
  task_name: string
  run_id: string
  category: NotifyCategory
  outcome: Outcome
  title: string
  message: string
  provider: string
  delivery: DeliveryStatus
  delivery_detail: string | null
  read: boolean
  created_at: string
}

export interface PluginInfo {
  slot: string
  name: string
  description: string
  implemented: boolean
}

export interface Stats {
  tasks: number
  enabled: number
  page_change: number
  api_check: number
  load_test: number
  runs_today: number
  changed_today: number
  problems_today: number
  unread_notifications: number
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}
