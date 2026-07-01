// -----------------------------------------------------------------------------
// frontend/src/api/aiScores.js
//
// API wrapper for the GET /api/v1/ai-scores/{entity_id} endpoint (AI-XAI-003).
// Returns the most recent ai_scores row for a given entity UUID and score type.
// getLatestScore returns null (not throws) on 404 so callers can treat a
// missing score as "Pending" without try/catch boilerplate.
// -----------------------------------------------------------------------------

import axiosInstance from './axiosInstance.js'

/**
 * Fetch the most recent AI score for an entity.
 *
 * @param {string} entityId  - UUID of the entity (partner_id, conversion_id, etc.)
 * @param {string} scoreType - 'quality' | 'fraud_risk' | 'churn_risk' | 'ranking'
 * @returns {Promise<{score: number, explanation: string|null, ...}|null>}
 *          The score object, or null if no score exists yet (404).
 */
export async function getLatestScore(entityId, scoreType) {
  try {
    const { data } = await axiosInstance.get(`/ai-scores/${entityId}`, {
      params: { score_type: scoreType },
    })
    return data
  } catch (err) {
    if (err.response?.status === 404) return null
    throw err
  }
}
