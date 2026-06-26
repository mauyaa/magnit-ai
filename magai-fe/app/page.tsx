'use client'

import { useState } from 'react'
import { URLInput } from '@/components/URLInput'
import { BlueprintCard } from '@/components/BlueprintCard'
import { WidgetPreview } from '@/components/WidgetPreview'
import { analyzeUrl, buildWidget } from '@/lib/api'
import type { Blueprint } from '@/types/widget'

export default function Home() {
  const [step, setStep] = useState<'input' | 'blueprints' | 'building' | 'done'>('input')
  const [url, setUrl] = useState('')
  const [blueprints, setBlueprints] = useState<Blueprint[]>([])
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [iframeUrl, setIframeUrl] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleAnalyze(targetUrl: string) {
    setIsLoading(true)
    setError('')
    setUrl(targetUrl)
    try {
      const data = await analyzeUrl(targetUrl)
      setBlueprints(data.blueprints)
      setStep('blueprints')
    } catch {
      setError('Failed to analyze URL. Make sure the backend is running.')
    } finally {
      setIsLoading(false)
    }
  }

  async function handleBuild() {
    if (selectedIndex === null) return
    setIsLoading(true)
    setError('')
    setStep('building')
    try {
      const data = await buildWidget(url, blueprints[selectedIndex])
      setIframeUrl(data.iframe_url)
      setStep('done')
    } catch {
      setError('Build failed. Please try again.')
      setStep('blueprints')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-gray-100 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <h1 className="text-xl font-bold text-gray-900">MagnetAI</h1>
          <span className="text-xs text-gray-400">Lead Magnet Generator</span>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center px-6 py-16">
        {step === 'input' && (
          <div className="flex flex-col items-center gap-8 text-center">
            <div className="max-w-xl space-y-3">
              <h2 className="text-4xl font-bold tracking-tight text-gray-900">
                Generate a lead magnet from any URL
              </h2>
              <p className="text-lg text-gray-500">
                Enter your business URL and we&apos;ll analyze your brand, propose 3 interactive
                widgets, and build one instantly.
              </p>
            </div>
            <URLInput onSubmit={handleAnalyze} isLoading={isLoading} />
            {error && <p className="text-sm text-red-500">{error}</p>}
          </div>
        )}

        {step === 'blueprints' && (
          <div className="flex w-full flex-col items-center gap-8">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-gray-900">Choose your widget</h2>
              <p className="mt-1 text-gray-500">
                We analyzed your site. Pick the lead magnet that fits best.
              </p>
            </div>
            <div className="grid w-full gap-4 md:grid-cols-3">
              {blueprints.map((bp, i) => (
                <BlueprintCard
                  key={i}
                  blueprint={bp}
                  isSelected={selectedIndex === i}
                  onSelect={() => setSelectedIndex(i)}
                />
              ))}
            </div>
            {error && <p className="text-sm text-red-500">{error}</p>}
            <button
              onClick={handleBuild}
              disabled={selectedIndex === null || isLoading}
              className="rounded-xl bg-blue-600 px-8 py-3 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? 'Building...' : 'Generate Widget'}
            </button>
          </div>
        )}

        {step === 'building' && (
          <div className="flex flex-col items-center gap-4">
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
            <p className="text-gray-500">Building your lead magnet widget...</p>
          </div>
        )}

        {step === 'done' && (
          <div className="flex w-full flex-col items-center gap-6">
            <h2 className="text-2xl font-bold text-gray-900">Your widget is ready!</h2>
            <WidgetPreview iframeUrl={iframeUrl} />
            <button
              onClick={() => {
                setStep('input')
                setBlueprints([])
                setSelectedIndex(null)
                setIframeUrl('')
              }}
              className="rounded-xl bg-gray-100 px-6 py-2 text-sm text-gray-600 hover:bg-gray-200"
            >
              Create Another
            </button>
          </div>
        )}
      </main>
    </div>
  )
}
