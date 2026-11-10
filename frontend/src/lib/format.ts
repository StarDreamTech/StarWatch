const DATE_TIME = new Intl.DateTimeFormat('zh-CN', {
  hour12: false,
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return DATE_TIME.format(date)
}

export function formatLatency(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value)} ms`
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('zh-CN').format(value)
}

export function clip(value: string, max: number): string {
  if (value.length <= max) return value
  return `${value.slice(0, max)}…`
}
