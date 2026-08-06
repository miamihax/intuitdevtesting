interface SettingsModalProps {
  onClose: () => void
  onEditOffice: () => void
}

export default function SettingsModal({ onClose, onEditOffice }: SettingsModalProps) {
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
        </div>
      </div>
    </div>
  )
}
