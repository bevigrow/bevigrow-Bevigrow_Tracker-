interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  isDangerous?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  isDangerous = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onCancel} />
      <div className="relative w-96 rounded-lg bg-darkroast border border-caramel/15 p-6 shadow-lg">
        <h2 className="text-lg font-semibold text-latte mb-2">{title}</h2>
        <p className="text-latte/70 mb-6">{message}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded border border-caramel/30 text-latte/60 hover:bg-caramel/10 text-sm font-medium"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded text-sm font-medium ${
              isDangerous
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : 'bg-gold/20 text-gold hover:bg-gold/30'
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
