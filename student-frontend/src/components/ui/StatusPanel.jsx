export default function StatusPanel({ title, subtitle, children }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-emerald-200 bg-white shadow-sm">
      <div className="bg-emerald-600 px-5 py-4">
        <div className="text-white text-base font-semibold">{title}</div>
        {subtitle ? <div className="text-emerald-50 text-sm">{subtitle}</div> : null}
      </div>
      <div className="px-5 py-5 bg-emerald-50/40">{children}</div>
    </div>
  )
}
