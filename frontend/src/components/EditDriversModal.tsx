import { useState } from 'react'
import { api } from '../api/client'
import type { Driver, UpdateDriverFields } from '../types'

interface EditDriversModalProps {
  drivers: Driver[]
  onClose: () => void
  onDriverCreated: (driver: Driver) => void
  onUpdateDriverField: (driverId: string, patch: Partial<Driver>) => void
  onPersistDriver: (driver: Driver) => void
  onDeleteDriver: (driverId: string) => void
}

const NEW_DRIVER_DEFAULTS: UpdateDriverFields = {
  name: '',
  vehicle_capacity_cases: 60,
  shift_start: '08:00',
  shift_end: '16:00',
}

export default function EditDriversModal({
  drivers,
  onClose,
  onDriverCreated,
  onUpdateDriverField,
  onPersistDriver,
  onDeleteDriver,
}: EditDriversModalProps) {
  const [newDriver, setNewDriver] = useState<UpdateDriverFields>(NEW_DRIVER_DEFAULTS)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const handleAddDriver = async () => {
    setCreating(true)
    setCreateError(null)
    try {
      const driver = await api.createDriver(newDriver)
      onDriverCreated(driver)
      setNewDriver(NEW_DRIVER_DEFAULTS)
    } catch (err) {
      setCreateError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

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
          Update a driver's name, capacity, or shift, remove them entirely, or add a new one below.
          Changes save as you leave each field.
        </p>

        <div className="import-pending-item driver-edit-form new-driver-form">
          <label>
            Name
            <input
              value={newDriver.name}
              onChange={(e) => setNewDriver((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="New driver's name"
            />
          </label>
          <div className="driver-edit-row">
            <label>
              Capacity (cases)
              <input
                className="case-count-input"
                type="number"
                min={0}
                value={newDriver.vehicle_capacity_cases}
                onChange={(e) =>
                  setNewDriver((prev) => ({ ...prev, vehicle_capacity_cases: Number(e.target.value) || 0 }))
                }
              />
            </label>
            <label className="time-window-cell">
              Shift
              <input
                type="time"
                value={newDriver.shift_start}
                onChange={(e) => setNewDriver((prev) => ({ ...prev, shift_start: e.target.value }))}
              />
              <span> – </span>
              <input
                type="time"
                value={newDriver.shift_end}
                onChange={(e) => setNewDriver((prev) => ({ ...prev, shift_end: e.target.value }))}
              />
            </label>
          </div>
          {createError && <div className="import-error">{createError}</div>}
          <div className="import-review-actions">
            <button onClick={handleAddDriver} disabled={creating || !newDriver.name.trim()}>
              {creating ? 'Adding…' : 'Add Driver'}
            </button>
          </div>
        </div>

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
