// -----------------------------------------------------------------------------
// frontend/src/components/common/ExplanationTooltip.jsx
//
// Hover tooltip that renders an AI explanation string next to any score or
// flag. The tooltip appears above the trigger element on hover/focus. Used by
// FraudAlertsPage and score cards across admin and partner views (AI-XAI-003).
// Pure CSS hover — no JS state, no portal, no dependency on a tooltip library.
// -----------------------------------------------------------------------------

import { useState } from 'react'

const styles = {
  wrapper: { position: 'relative', display: 'inline-block' },
  trigger: {
    cursor: 'help',
    borderBottom: '1px dashed #6b7280',
    fontSize: '13px',
    color: '#374151',
  },
  tooltip: {
    position: 'absolute',
    bottom: 'calc(100% + 6px)',
    left: '50%',
    transform: 'translateX(-50%)',
    backgroundColor: '#1f2937',
    color: '#f9fafb',
    padding: '8px 12px',
    borderRadius: '6px',
    fontSize: '12px',
    lineHeight: '1.5',
    whiteSpace: 'normal',
    width: '260px',
    zIndex: 50,
    boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
    pointerEvents: 'none',
  },
  arrow: {
    position: 'absolute',
    top: '100%',
    left: '50%',
    transform: 'translateX(-50%)',
    border: '5px solid transparent',
    borderTopColor: '#1f2937',
  },
}

export default function ExplanationTooltip({ explanation, label }) {
  const [visible, setVisible] = useState(false)

  if (!explanation) return null

  return (
    <span
      style={styles.wrapper}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      <span style={styles.trigger} tabIndex={0} role="button" aria-label="Show explanation">
        {label ?? 'Why?'}
      </span>
      {visible && (
        <span style={styles.tooltip} role="tooltip">
          {explanation}
          <span style={styles.arrow} />
        </span>
      )}
    </span>
  )
}
