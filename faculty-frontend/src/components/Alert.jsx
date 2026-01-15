import { AlertCircle, CheckCircle, Info, XCircle, X } from 'lucide-react'

const variants = {
  success: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    text: 'text-green-800',
    icon: CheckCircle,
    iconColor: 'text-green-500'
  },
  error: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-800',
    icon: XCircle,
    iconColor: 'text-red-500'
  },
  warning: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-200',
    text: 'text-yellow-800',
    icon: AlertCircle,
    iconColor: 'text-yellow-500'
  },
  info: {
    bg: 'bg-blue-50',
    border: 'border-blue-200',
    text: 'text-blue-800',
    icon: Info,
    iconColor: 'text-blue-500'
  }
}

export default function Alert({ 
  variant = 'info', 
  title, 
  children, 
  onClose,
  className = '' 
}) {
  const styles = variants[variant]
  const Icon = styles.icon

  return (
    <div className={`${styles.bg} ${styles.border} border rounded-lg p-4 ${className}`}>
      <div className="flex">
        <Icon className={`w-5 h-5 ${styles.iconColor} flex-shrink-0`} />
        <div className="ml-3 flex-1">
          {title && (
            <h3 className={`text-sm font-medium ${styles.text}`}>{title}</h3>
          )}
          {children && (
            <div className={`text-sm ${styles.text} ${title ? 'mt-1' : ''}`}>
              {children}
            </div>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className={`ml-auto ${styles.text} hover:opacity-70 rounded-lg p-2 -m-2 min-h-[44px] min-w-[44px] flex items-center justify-center`}
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}
