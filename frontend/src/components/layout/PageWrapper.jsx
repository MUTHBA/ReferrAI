// -----------------------------------------------------------------------------
// frontend/src/components/layout/PageWrapper.jsx
//
// Thin padded <main> wrapper applied around each page's content inside
// AdminLayout/PartnerLayout, so individual pages don't each need their own
// padding/scroll styling.
// -----------------------------------------------------------------------------

const styles = {
  main: {
    flex: 1,
    padding: '32px',
    overflowY: 'auto',
  },
}

export default function PageWrapper({ children }) {
  return <main style={styles.main}>{children}</main>
}
