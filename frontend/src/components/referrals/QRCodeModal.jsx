// -----------------------------------------------------------------------------
// frontend/src/components/referrals/QRCodeModal.jsx
//
// Overlay modal that displays a QR code image received as a raw base64 PNG
// string. The data URI prefix is added here so the caller only stores the
// plain base64 value (matching the API response and the DB column). Clicking
// the backdrop or the Close button calls onClose. Uses the same inline-style
// approach as every other component in this project — no CSS files.
// -----------------------------------------------------------------------------

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 50,
  },
  modal: {
    backgroundColor: '#ffffff',
    borderRadius: '12px',
    padding: '28px 24px 24px',
    maxWidth: '340px',
    width: '90%',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '20px',
    boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
  },
  title: {
    fontSize: '16px',
    fontWeight: 700,
    margin: 0,
    color: '#111827',
  },
  img: {
    width: '100%',
    maxWidth: '260px',
    display: 'block',
    borderRadius: '4px',
  },
  closeBtn: {
    padding: '8px 24px',
    borderRadius: '6px',
    border: '1px solid #d1d5db',
    backgroundColor: '#ffffff',
    cursor: 'pointer',
    fontWeight: 500,
    fontSize: '14px',
    color: '#374151',
  },
}

export default function QRCodeModal({ base64PngData, onClose }) {
  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <p style={styles.title}>Referral QR Code</p>
        <img
          src={`data:image/png;base64,${base64PngData}`}
          alt="Referral QR Code"
          style={styles.img}
        />
        <button type="button" style={styles.closeBtn} onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  )
}
