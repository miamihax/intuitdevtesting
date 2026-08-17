import type { Settings } from '../types'

interface SettingsModalProps {
  settings: Settings
  onSettingsChange: (settings: Settings) => void
  onClose: () => void
  onEditOffice: () => void
}

export default function SettingsModal({ settings, onSettingsChange, onClose, onEditOffice }: SettingsModalProps) {
  const updateSetting = (patch: Partial<Settings>) => {
    onSettingsChange({ ...settings, ...patch })
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
            <input
              type="checkbox"
              checked={settings.auto_add_imports}
              onChange={() => updateSetting({ auto_add_imports: !settings.auto_add_imports })}
            />
            <span>
              Automatically add imported orders
              <span className="settings-toggle-hint">
                Skips manual review — imports are added as orders as soon as OCR/QuickBooks extracts a name,
                address, and an exact geocode match. Anything missing, or an address that only resolves to its
                ZIP code's general area, still waits for review.
              </span>
            </span>
          </label>

          <div className="settings-menu-item settings-unit-row">
            <span>Distance unit</span>
            <div className="unit-toggle-buttons">
              <button
                type="button"
                className={settings.distance_unit === 'mi' ? 'unit-toggle-active' : undefined}
                onClick={() => updateSetting({ distance_unit: 'mi' })}
              >
                mi
              </button>
              <button
                type="button"
                className={settings.distance_unit === 'km' ? 'unit-toggle-active' : undefined}
                onClick={() => updateSetting({ distance_unit: 'km' })}
              >
                km
              </button>
            </div>
          </div>

          <div className="settings-menu-item settings-unit-row">
            <span>Time format</span>
            <div className="unit-toggle-buttons">
              <button
                type="button"
                className={settings.time_format === '12h' ? 'unit-toggle-active' : undefined}
                onClick={() => updateSetting({ time_format: '12h' })}
              >
                12h
              </button>
              <button
                type="button"
                className={settings.time_format === '24h' ? 'unit-toggle-active' : undefined}
                onClick={() => updateSetting({ time_format: '24h' })}
              >
                24h
              </button>
            </div>
          </div>

          <div className="settings-menu-item settings-unit-row">
            <span>Theme</span>
            <div className="unit-toggle-buttons">
              <button
                type="button"
                className={settings.theme === 'dark' ? 'unit-toggle-active' : undefined}
                onClick={() => updateSetting({ theme: 'dark' })}
              >
                Dark
              </button>
              <button
                type="button"
                className={settings.theme === 'light' ? 'unit-toggle-active' : undefined}
                onClick={() => updateSetting({ theme: 'light' })}
              >
                Light
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
