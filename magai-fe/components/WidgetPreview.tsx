'use client'

export function WidgetPreview({ iframeUrl }: { iframeUrl: string }) {
  return (
    <div className="w-full">
      <div className="mb-3 flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-green-500" />
        <span className="text-sm text-green-700 font-medium">Widget Live</span>
      </div>
      <div className="overflow-hidden rounded-xl border border-gray-200 shadow-sm">
        <iframe
          src={iframeUrl}
          width="100%"
          height="600"
          className="border-0"
          sandbox="allow-scripts allow-same-origin allow-forms"
        />
      </div>
      <div className="mt-3">
        <label className="mb-1 block text-xs font-medium text-gray-500">
          Embed Code
        </label>
        <code className="block rounded-lg bg-gray-50 p-3 text-xs text-gray-700 break-all">
          {`<iframe src="${iframeUrl}" width="100%" height="600px"></iframe>`}
        </code>
      </div>
    </div>
  )
}
