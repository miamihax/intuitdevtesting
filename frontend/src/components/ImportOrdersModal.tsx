import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { ConfirmImportFields, PendingImport, Store } from '../types'

interface ImportOrdersModalProps {
  onClose: () => void
  onStoreImported: (store: Store) => void
}

const DEFAULT_FIELDS: ConfirmImportFields = {
  name: '',
  address: '',
  time_window_start: '09:00',
  time_window_end: '19:00',
  case_count: 0,
}

export default function ImportOrdersModal({ onClose, onStoreImported }: ImportOrdersModalProps) {
  const [pendingImports, setPendingImports] = useState<PendingImport[]>([])
  const [edits, setEdits] = useState<Record<string, ConfirmImportFields>>({})
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  const [confirmErrors, setConfirmErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    let cancelled = false
    const poll = () => {
      api
        .getPendingImports()
        .then((items) => {
          if (!cancelled) setPendingImports(items)
        })
        .catch(() => {})
    }
    poll()
    const interval = setInterval(poll, 1500)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  const editFor = (p: PendingImport): ConfirmImportFields =>
    edits[p.id] ?? {
      ...DEFAULT_FIELDS,
      name: p.name ?? '',
      address: p.address ?? '',
      case_count: p.case_count ?? DEFAULT_FIELDS.case_count,
      time_window_start: p.time_window_start ?? DEFAULT_FIELDS.time_window_start,
      time_window_end: p.time_window_end ?? DEFAULT_FIELDS.time_window_end,
    }

  const handleFieldChange = (p: PendingImport, patch: Partial<ConfirmImportFields>) => {
    setEdits((prev) => ({ ...prev, [p.id]: { ...editFor(p), ...patch } }))
  }

  const handleFilesSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    setUploading(true)
    setUploadError(null)
    try {
      for (const file of Array.from(files)) {
        await api.uploadImportFile(file)
      }
      const items = await api.getPendingImports()
      setPendingImports(items)
    } catch (err) {
      setUploadError((err as Error).message)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleConfirm = async (p: PendingImport) => {
    setConfirmingId(p.id)
    setConfirmErrors((prev) => ({ ...prev, [p.id]: '' }))
    try {
      const store = await api.confirmImport(p.id, editFor(p))
      onStoreImported(store)
      setPendingImports((prev) => prev.filter((item) => item.id !== p.id))
    } catch (err) {
      setConfirmErrors((prev) => ({ ...prev, [p.id]: (err as Error).message }))
    } finally {
      setConfirmingId(null)
    }
  }

  const handleDismiss = async (p: PendingImport) => {
    try {
      await api.dismissImport(p.id)
    } catch {
      // Already gone server-side (or never existed) — fine to drop it locally too.
    }
    setPendingImports((prev) => prev.filter((item) => item.id !== p.id))
  }

  return (
    <div className="import-modal-overlay" onClick={onClose}>
      <div className="import-modal" onClick={(e) => e.stopPropagation()}>
        <div className="import-modal-header">
          <h2>Import Orders</h2>
          <button className="collapse-toggle" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <p className="import-modal-hint">
          Upload a scanned invoice (PDF, PNG, or JPG). It's scanned automatically with OCR — invoice #,
          address, and location are pulled out for you to review before adding it as an order. Connect
          QuickBooks to skip scanning entirely — new and updated invoices show up here automatically.
        </p>

        <label className="import-file-picker">
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            multiple
            onChange={handleFilesSelected}
            disabled={uploading}
          />
          {uploading ? 'Uploading…' : 'Choose invoice file(s)'}
        </label>
        {uploadError && <div className="import-error">{uploadError}</div>}

        <a className="import-quickbooks-link" href={api.quickbooksConnectUrl} target="_blank" rel="noreferrer">
          Connect QuickBooks
        </a>

        <div className="import-pending-list">
          {pendingImports.length === 0 && <p className="import-empty">No imports yet — choose a file above.</p>}

          {pendingImports.map((p) => (
            <div key={p.id} className="import-pending-item">
              <div className="import-pending-filename">
                {p.file_name}
                {p.source === 'quickbooks' && <span className="import-source-badge">QuickBooks</span>}
              </div>

              {p.status === 'processing' && <div className="import-status">Scanning…</div>}

              {p.status === 'error' && (
                <>
                  <div className="import-status import-status-error">Couldn't read this file: {p.error}</div>
                  <div className="import-review-actions">
                    <button onClick={() => handleDismiss(p)}>Dismiss</button>
                  </div>
                </>
              )}

              {p.status === 'ready' && (
                <div className="import-review-form">
                  <div className="import-invoice-number">Invoice # {p.invoice_number ?? '—'}</div>
                  <label>
                    Location
                    <input
                      value={editFor(p).name}
                      onChange={(e) => handleFieldChange(p, { name: e.target.value })}
                    />
                  </label>
                  <label>
                    Address
                    <input
                      value={editFor(p).address}
                      onChange={(e) => handleFieldChange(p, { address: e.target.value })}
                    />
                  </label>
                  {p.approximate_location && (
                    <div className="import-approximate-warning">
                      ⚠ Exact address not found — located to the ZIP code area only. Verify or adjust it.
                    </div>
                  )}
                  {p.suggested_address && p.suggested_address !== editFor(p).address && (
                    <div className="import-suggested-address">
                      <span>
                        {p.suggested_address_source === 'bill_to'
                          ? 'Found in Bill To section: '
                          : 'Found via web search: '}
                        {p.suggested_address}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleFieldChange(p, { address: p.suggested_address! })}
                      >
                        Use this address
                      </button>
                    </div>
                  )}
                  <div className="import-review-row">
                    <label className="time-window-cell">
                      Window
                      <input
                        type="time"
                        value={editFor(p).time_window_start}
                        onChange={(e) => handleFieldChange(p, { time_window_start: e.target.value })}
                      />
                      <span> – </span>
                      <input
                        type="time"
                        value={editFor(p).time_window_end}
                        onChange={(e) => handleFieldChange(p, { time_window_end: e.target.value })}
                      />
                    </label>
                    <label>
                      Cases
                      <input
                        className="case-count-input"
                        type="number"
                        min={0}
                        value={editFor(p).case_count}
                        onChange={(e) =>
                          handleFieldChange(p, { case_count: Number(e.target.value) || 0 })
                        }
                      />
                    </label>
                  </div>
                  {confirmErrors[p.id] && <div className="import-error">{confirmErrors[p.id]}</div>}
                  <div className="import-review-actions">
                    <button onClick={() => handleDismiss(p)}>Dismiss</button>
                    <button onClick={() => handleConfirm(p)} disabled={confirmingId === p.id}>
                      {confirmingId === p.id ? 'Adding…' : 'Add Order'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
