import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { OfficeLocation } from '../types'

interface OfficeSettingsModalProps {
  onClose: () => void
  onOfficeUpdated: (office: OfficeLocation) => void
}

export default function OfficeSettingsModal({ onClose, onOfficeUpdated }: OfficeSettingsModalProps) {
  const [current, setCurrent] = useState<OfficeLocation | null>(null)
  const [address, setAddress] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .getOffice()
      .then((office) => {
        setCurrent(office)
        setAddress(office.address ?? '')
      })
      .catch((err: Error) => setError(err.message))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const office = await api.setOffice(address)
      setCurrent(office)
      onOfficeUpdated(office)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="import-modal-overlay" onClick={onClose}>
      <div className="import-modal" onClick={(e) => e.stopPropagation()}>
        <div className="import-modal-header">
          <h2>Office Location</h2>
          <button className="collapse-toggle" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <p className="import-modal-hint">
          Every driver's route starts and ends here. Update the address below to move it — existing
          routes keep their current depot until you re-optimize.
        </p>

        <div className="office-settings-body import-review-form">
          {current && (
            <div className="office-current-coordinates">
              Current: {current.coordinates.lat.toFixed(4)}, {current.coordinates.lng.toFixed(4)}
              {!current.address && ' (default — no address set yet)'}
            </div>
          )}

          <label>
            Address
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="123 Main St, Chicago, IL 60601"
            />
          </label>

          {error && <div className="import-error">{error}</div>}

          <div className="import-review-actions">
            <button onClick={onClose}>Cancel</button>
            <button onClick={handleSave} disabled={saving || !address.trim()}>
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
