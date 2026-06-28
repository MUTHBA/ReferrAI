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
