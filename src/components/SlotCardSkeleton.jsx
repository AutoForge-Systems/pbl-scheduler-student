export default function SlotCardSkeleton() {
  return (
    <div className="card p-4 animate-pulse">
      <div className="space-y-3">
        <div className="h-4 w-36 bg-gray-200 rounded" />
        <div className="h-4 w-48 bg-gray-200 rounded" />
        <div className="h-4 w-40 bg-gray-200 rounded" />
        <div className="h-11 w-full bg-gray-200 rounded-lg mt-3" />
        <div className="h-3 w-56 bg-gray-100 rounded" />
      </div>
    </div>
  )
}
