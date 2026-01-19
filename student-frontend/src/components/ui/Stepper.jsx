export default function Stepper({ steps, activeIndex = 0 }) {
  const safeSteps = Array.isArray(steps) ? steps : []
  const lastIdx = Math.max(0, safeSteps.length - 1)
  const clampedActive = Math.min(Math.max(activeIndex, 0), lastIdx)

  return (
    <div className="w-full">
      <div className="flex items-center">
        {safeSteps.map((step, idx) => {
          const isDone = idx < clampedActive
          const isActive = idx === clampedActive

          return (
            <div key={step?.key || step?.label || idx} className="flex-1 flex items-center">
              <div className="flex items-center gap-3 min-w-0">
                <div
                  className={
                    "h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0 border " +
                    (isDone
                      ? 'bg-blue-600 border-blue-600'
                      : isActive
                        ? 'bg-white border-blue-600'
                        : 'bg-white border-gray-300')
                  }
                >
                  <div
                    className={
                      "h-2.5 w-2.5 rounded-full " +
                      (isDone ? 'bg-white' : isActive ? 'bg-blue-600' : 'bg-gray-300')
                    }
                  />
                </div>

                <div className="min-w-0">
                  <div className={"text-sm font-medium truncate " + (isActive ? 'text-gray-900' : 'text-gray-600')}>
                    {step?.label}
                  </div>
                  {step?.sublabel ? (
                    <div className="text-xs text-gray-400 truncate">{step.sublabel}</div>
                  ) : null}
                </div>
              </div>

              {idx !== lastIdx ? (
                <div className="flex-1 px-3">
                  <div className={"h-[2px] rounded " + (idx < clampedActive ? 'bg-blue-600' : 'bg-gray-200')} />
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
