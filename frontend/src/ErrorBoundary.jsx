import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, info: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    this.setState({ info });
    if (import.meta.env.VITE_SHOW_DEBUG === 'true') {
      // eslint-disable-next-line no-console
      console.error('[ErrorBoundary]', error, info);
    }
  }
  handleReload = () => {
    this.setState({ hasError: false, error: null, info: null });
    window.location.reload();
  };
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
          <h2 style={{ marginTop: 0 }}>界面发生错误 (UI crashed)</h2>
          <p style={{ color: '#c00' }}>{this.state.error?.message}</p>
          <button onClick={this.handleReload} style={{ padding: '0.5rem 1rem', background: '#007bff', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}>刷新页面</button>
          {import.meta.env.VITE_SHOW_DEBUG === 'true' && this.state.info && (
            <pre style={{ marginTop: '1rem', maxHeight: 240, overflow: 'auto', background: '#f7f7f7', padding: '0.75rem', fontSize: 12 }}>{this.state.info.componentStack}</pre>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
