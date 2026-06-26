'use client'

import type { Blueprint } from '@/types/widget'

export function BlueprintCard({
  blueprint,
  onSelect,
  isSelected,
}: {
  blueprint: Blueprint
  onSelect: () => void
  isSelected: boolean
}) {
  return (
    <button
      onClick={onSelect}
      className={`rounded-xl border-2 p-6 text-left transition-all ${
        isSelected
          ? 'border-blue-500 bg-blue-50 shadow-md'
          : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-sm'
      }`}
    >
      <div className="mb-2 inline-block rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">
        {blueprint.type.replace(/_/g, ' ')}
      </div>
      <h3 className="mb-1 text-lg font-semibold">{blueprint.title}</h3>
      <p className="mb-2 text-sm text-gray-600">{blueprint.description}</p>
      <p className="text-xs text-gray-400">{blueprint.rationale}</p>
    </button>
  )
}
