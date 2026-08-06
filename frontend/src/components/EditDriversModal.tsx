import type { Driver } from '../types'

interface EditDriversModalProps {
  drivers: Driver[]
  onClose: () => void
  onUpdateDriverField: (driverId: string, patch: Partial<Driver>) => void
  onPersistDriver: (driver: Driver) => void
  onDeleteDriver: (driverId: string) => void
}

export default function EditDriversModal({
  drivers,
  onClose,
  onUpdateDriverField,
  onPersistDriver,
  onDeleteDriver,
}: EditDriversModalProps) {
  return (
    <div className="import-modal-overlay" onClick={onClose}>
      <div className="import-modal" onClick={(e) => e.stopPropagation()}>
        <div className="import-modal-header">
          <h2>Edit Drivers</h2>
          <button className="collapse-toggle" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <p className="import-modal-hint">
          Update a driver's name, capacity, or shift, or remove them entirely. Changes save as you leave
          each field.
        </p>

        <div className="import-pending-list">
          {drivers.length === 0 && <p className="import-empty">No drivers yet.</p>}

          {drivers.map((driver) => (
            <div key={driver.id} className="import-pending-item driver-edit-form">
              <label>
                Name
                <input
                  value={driver.name}
                  onChange={(e) => onUpdateDriverField(driver.id, { name: e.target.value })}
                  onBlur={() => onPersistDriver(driver)}
                />
              </label>
              <div className="driver-edit-row">
                <label>
                  Capacity (cases)
                  <input
                    className="case-count-input"
                    type="number"
                    min={0}
                    value={driver.vehicle_capacity_cases}
                    onChange={(e) =>
                      onUpdateDriverField(driver.id, { vehicle_capacity_cases: Number(e.target.value) || 0 })
                    }
                    onBlur={() => onPersistDriver(driver)}
                  />
                </label>
                <label className="time-window-cell">
                  Shift
                  <input
                    type="time"
                    value={driver.shift_start}
                    onChange={(e) => onUpdateDriverField(driver.id, { shift_start: e.target.value })}
                    onBlur={() => onPersistDriver(driver)}
                  />
                  <span> – </span>
                  <input
                    type="time"
                    value={driver.shift_end}
                    onChange={(e) => onUpdateDriverField(driver.id, { shift_end: e.target.value })}
                    onBlur={() => onPersistDriver(driver)}
                  />
                </label>
              </div>
              <div className="import-review-actions">
                <button className="delete-driver-button" onClick={() => onDeleteDriver(driver.id)}>
                  Delete Driver
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
