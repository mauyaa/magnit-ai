const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function analyzeUrl(url: string) {
  const res = await fetch(`${API_BASE}/api/widgets/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) throw new Error('Analysis failed')
  return res.json()
}

export async function buildWidget(url: string, blueprint: any) {
  const res = await fetch(`${API_BASE}/api/widgets/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, blueprint }),
  })
  if (!res.ok) throw new Error('Build failed')
  return res.json()
}

export async function getWidgetStatus(widgetId: string) {
  const res = await fetch(`${API_BASE}/api/widgets/${widgetId}`)
  if (!res.ok) throw new Error('Widget not found')
  return res.json()
}
