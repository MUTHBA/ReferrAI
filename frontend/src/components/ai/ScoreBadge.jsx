// -----------------------------------------------------------------------------
// frontend/src/components/ai/ScoreBadge.jsx
//
// Reusable AI score badge with hover tooltip (AI-XAI-003). Renders a colored
// pill badge and an info icon; hovering the icon shows the plain-language
// explanation from the SHAP explainer. Color thresholds match the existing
// QualityBadge component in ReferralsPage:
//   green  ≥ 70   #15803d / #f0fdf4 / #bbf7d0
//   yellow 40–69  #a16207 / #fefce8 / #fde68a
//   red    < 40   #b91c1c / #fef2f2 / #fecaca
//   grey   null   #6b7280 / #f3f4f6 / #d1d5db  (shows "Pending")
// No external dependencies — pure inline styles + React state for tooltip.
// -----------------------------------------------------------------------------

import { useState } from 'react'

function badgeColors(score) {
  if (score === null || score === undefined) {
    return { bg: '#f3f4f6', color: '#6b7280', border: '#d1d5db', text: 'Pending' }
  }
  if (score >= 70) {
    return { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0', text: String(Math.round(score)) }
  }
  if (score >= 40) {
    return { bg: '#fefce8', color: '#a16207', border: '#fde68a', text: String(Math.round(score)) }
  }
  return { bg: '#fef2f2', color: '#b91c1c', border: '#fecaca', text: String(Math.round(score)) }
}

/**
 * ScoreBadge — colored AI score pill with an explanation tooltip.
 *
 * @param {number|null}  score        - AI score 0–100, or null for "Pending".
 * @param {string}       label        - Short label shown before the badge (e.g. "Churn Risk").
 * @param {string|null}  explanation  - Plain-language SHAP explanation string, or null.
 */
export default function ScoreBadge({ score, label, explanation }) {
  const [showTooltip, setShowTooltip] = useState(false)
  const colors = badgeColors(score)
  const tooltipText = explanation ?? 'Explanation not available yet.'

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      {label && (
        <span style={{ fontSize: '12px', color: '#6b7280', fontWeight: 500 }}>
          {label}
        </span>
      )}

      <span
        style={{
          display: 'inline-block',
          padding: '2px 9px',
          borderRadius: '12px',
          fontSize: '11px',
          fontWeight: 700,
          letterSpacing: '0.02em',
          border: `1px solid ${colors.border}`,
          backgroundColor: colors.bg,
          color: colors.color,
          whiteSpace: 'nowrap',
        }}
      >
        {colors.text}
      </span>

      {/* Info icon with tooltip */}
      <span
        role="img"
        aria-label="Explanation"
        style={{ position: 'relative', cursor: 'default', color: '#9ca3af', fontSize: '14px', lineHeight: 1 }}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        ⓘ
        {showTooltip && (
          <span
            role="tooltip"
            style={{
              position: 'absolute',
              bottom: 'calc(100% + 4px)',
              left: '50%',
              transform: 'translateX(-50%)',
              backgroundColor: '#1f2937',
              color: '#f9fafb',
              borderRadius: '6px',
              padding: '7px 11px',
              fontSize: '12px',
              lineHeight: '1.45',
              whiteSpace: 'normal',
              width: '220px',
              zIndex: 200,
              boxShadow: '0 2px 10px rgba(0,0,0,0.22)',
              pointerEvents: 'none',
            }}
          >
            {tooltipText}
          </span>
        )}
      </span>
    </div>
  )
}
