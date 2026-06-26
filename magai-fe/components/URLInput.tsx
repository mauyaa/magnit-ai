'use client'

import { useState } from 'react'

export function URLInput({
  onSubmit,
  isLoading,
}: {
  onSubmit: (url: string) => void
  isLoading: boolean
}) {
  const [url, setUrl] = useState('')

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (url.trim()) onSubmit(url.trim())
      }}
      className="flex w-full max-w-2xl gap-3"
    >
      <input
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="Enter your website URL (e.g., https://example.com)"
        className="flex-1 rounded-xl border border-gray-300 px-5 py-3 text-sm shadow-sm outline-none transition focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
        required
      />
      <button
        type="submit"
        disabled={isLoading}
        className="rounded-xl bg-blue-600 px-6 py-3 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-50"
      >
        {isLoading ? 'Analyzing...' : 'Generate Ideas'}
      </button>
    </form>
  )
}
