// -----------------------------------------------------------------------------
// frontend/src/hooks/useAuth.js
//
// Re-exports the useAuth hook from AuthContext so components import hooks
// from src/hooks/ consistently (matching the other use*.js hooks in this
// folder) without needing to know the hook is defined alongside its
// Provider in context/AuthContext.jsx.
// -----------------------------------------------------------------------------

export { useAuth } from '../context/AuthContext.jsx'
