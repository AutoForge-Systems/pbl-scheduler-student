import { GraduationCap } from 'lucide-react'

export default function PageHeader({
  title,
  subtitle,
  icon: Icon = GraduationCap,
  right,
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 rounded-xl bg-blue-600 flex items-center justify-center flex-shrink-0">
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div className="min-w-0">
          <div className="text-xl sm:text-2xl font-semibold text-gray-900 truncate">{title}</div>
          {subtitle ? <div className="text-sm text-gray-500">{subtitle}</div> : null}
        </div>
      </div>

      {right ? <div className="flex items-center gap-2">{right}</div> : null}
    </div>
  )
}
