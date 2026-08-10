import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface SettingsModalProps {
  onClose: () => void
  onEditOffice: () => void
}

export default function SettingsModal({ onClose, onEditOffice }: SettingsModalProps) {
  const [autoAddImports, setAutoAddImports] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getSettings()
      .then((settings) => setAutoAddImports(settings.auto_add_imports))
      .catch((err: Error) => setError(err.message))
  }, [])

  const handleToggleAutoAddImports = () => {
    const next = !autoAddImports
    setAutoAddImports(next)
    setSaving(true)
    setError(null)
    api
      .updateSettings({ auto_add_imports: next })
      .catch((err: Error) => {
        setError(err.message)
        setAutoAddImports(!next)
      })
      .finally(() => setSaving(false))
  }

  return (
    <div className="import-modal-overlay" onClick={onClose}>
      <div className="import-modal" onClick={(e) => e.stopPropagation()}>
        <div className="import-modal-header">
          <h2>Settings</h2>
          <button className="collapse-toggle" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="settings-menu-list">
          <button className="settings-menu-item" onClick={onEditOffice}>
            Office Location
          </button>

          <label className="settings-toggle-item">
            <input type="checkbox" checked={autoAddImports} onChange={handleToggleAutoAddImports} disabled={saving} />
            <span>
              Automatically add imported orders
              <span className="settings-toggle-hint">
                Skips manual review — imports are added as orders as soon as OCR/QuickBooks extracts a name,
                address, and a locatable location. Anything missing still waits for review.
              </span>
            </span>
          </label>
          {error && <div className="import-error">{error}</div>}
        </div>
      </div>
    </div>
  )
}
