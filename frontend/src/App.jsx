// -----------------------------------------------------------------------------
// frontend/src/App.jsx
//
// Root React component and future home of the route configuration. Currently
// renders a minimal placeholder to confirm the Vite dev server is alive and
// serving the React app correctly. Replace the placeholder content with
// <BrowserRouter> + <Routes> and the admin/partner dashboard route definitions
// as UI features are implemented. Layout components (sidebar, nav, auth guard)
// should wrap the route tree here rather than in individual page components.
// -----------------------------------------------------------------------------

export default function App() {
  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem' }}>
      <h1>ReferrAI</h1>
      <p>Referral &amp; commission management platform</p>
    </div>
  )
}
