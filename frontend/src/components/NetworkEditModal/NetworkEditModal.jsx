import React, { useState, useEffect, useRef } from 'react'
import './NetworkEditModal.css'

function NetworkEditModal({ network, onClose, onSave }) {
  const [form, setForm] = useState({
    name: '', description: '', encryption_type: 'NONE', encryption_key: ''
  })
  const [logoFile, setLogoFile] = useState(null)
  const [logoPreview, setLogoPreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const fileRef = useRef(null)

  useEffect(() => {
    if (network) {
      setForm({
        name: network.name || '',
        description: network.description || '',
        encryption_type: network.encryption_type || 'NONE',
        encryption_key: network.encryption_key || '',
      })
      setLogoPreview(network.logo_url || null)
    }
  }, [network])

  const handleLogoChange = (e) => {
    const file = e.target.files[0]
    if (file) {
      setLogoFile(file)
      setLogoPreview(URL.createObjectURL(file))
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMessage('')

    try {
      // Save network details
      const res = await fetch(`/api/networks/${network.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      })
      if (!res.ok) throw new Error('Failed to save network')

      // Upload logo if selected
      if (logoFile) {
        const fd = new FormData()
        fd.append('logo', logoFile)
        const logoRes = await fetch(`/api/networks/${network.id}/logo`, {
          method: 'POST', body: fd
        })
        if (!logoRes.ok) throw new Error('Failed to upload logo')
      }

      setMessage('✅ Saved successfully')
      setTimeout(() => { onSave?.(); onClose() }, 800)
    } catch (err) {
      setMessage(`❌ ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  if (!network) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content glass" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Edit Network</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          {/* Logo */}
          <div className="modal-logo-section">
            <div className="logo-preview" onClick={() => fileRef.current?.click()}>
              {logoPreview
                ? <img src={logoPreview} alt="Logo" />
                : <span className="logo-placeholder">📡<br/>Upload Logo</span>
              }
            </div>
            <input ref={fileRef} type="file" accept="image/*" onChange={handleLogoChange} hidden />
          </div>

          {/* Name */}
          <label className="modal-label">
            Network Name
            <input type="text" value={form.name} onChange={e => setForm({...form, name: e.target.value})}
                   className="modal-input" placeholder="e.g. Metro DMR Net" />
          </label>

          {/* Description */}
          <label className="modal-label">
            Description
            <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})}
                      className="modal-input modal-textarea" placeholder="Network notes..." rows={3} />
          </label>

          {/* Protocol (read-only) */}
          <label className="modal-label">
            Protocol
            <input type="text" value={network.protocol || ''} className="modal-input" disabled />
          </label>

          {/* Encryption Type */}
          <label className="modal-label">
            Encryption Type
            <select value={form.encryption_type} onChange={e => setForm({...form, encryption_type: e.target.value})}
                    className="modal-input">
              <option value="NONE">None</option>
              <option value="AES-256">AES-256</option>
              <option value="DES">DES</option>
              <option value="RC4">RC4</option>
              <option value="ARC4">ARC4</option>
              <option value="HYTERA_BP">Hytera Basic Privacy</option>
              <option value="UNKNOWN">Unknown</option>
            </select>
          </label>

          {/* Encryption Key */}
          <label className="modal-label">
            Decryption Key
            <input type="text" value={form.encryption_key}
                   onChange={e => setForm({...form, encryption_key: e.target.value})}
                   className="modal-input mono" placeholder="Enter hex key (e.g. 0x1A2B3C4D...)" />
          </label>

          {message && <div className="modal-message">{message}</div>}

          <div className="modal-actions">
            <button type="button" className="modal-btn secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="modal-btn primary" disabled={saving}>
              {saving ? 'Saving...' : '💾 Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default NetworkEditModal
