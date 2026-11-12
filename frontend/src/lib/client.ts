import type { ErrorBody, Health } from '@/types/api'

const API_PREFIX = '/api'

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  return configured && configured.length > 0 ? configured.replace(/\/$/, '') : API_PREFIX
}

function isErrorBody(value: unknown): value is ErrorBody {
  if (!value || typeof value !== 'object') return false
  const body = value as { code?: unknown; message?: unknown }
  return typeof body.code === 'string' && typeof body.message === 'string'
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  let response: Response
  try {
    response = await fetch(`${apiBase()}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'network', '无法连接调度器，请确认服务已经启动')
  }
  if (response.status === 204) {
    return undefined as T
  }
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const body = isErrorBody(payload) ? payload : null
    throw new ApiError(response.status, body?.code ?? 'http_error', body?.message ?? '请求失败')
  }
  return payload as T
}

export function withQuery(
  path: string,
  params: Record<string, string | number | boolean | undefined>,
): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `${path}?${text}` : path
}

export async function fetchHealth(): Promise<Health> {
  let response: Response
  try {
    response = await fetch(`${apiBase()}/health`)
  } catch {
    throw new ApiError(0, 'network', '无法连接调度器')
  }
  const payload: unknown = await response.json().catch(() => null)
  if (!payload || typeof payload !== 'object' || !('status' in payload)) {
    throw new ApiError(response.status, 'health', '健康检查没有返回有效结果')
  }
  return payload as Health
}
