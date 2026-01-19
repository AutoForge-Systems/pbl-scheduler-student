import { AlertTriangle } from 'lucide-react'

export default function NoticeBanner({ title = 'Important', children }) {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-amber-900">{title}</div>
          <div className="text-sm text-amber-800 mt-1">{children}</div>
        </div>
      </div>
    </div>
  )
}
