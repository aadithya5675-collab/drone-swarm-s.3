import { Component, type ReactNode } from 'react';

/** A view that throws shows a calm error instead of a blank screen; a stale bundle (site rebuilt) reloads once. */
export default class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { err: Error | null }> {
  state = { err: null as Error | null };
  static getDerivedStateFromError(err: Error) { return { err }; }
  componentDidCatch(err: Error) {
    if (/dynamically imported module|Importing a module script failed/.test(err.message) && !sessionStorage.getItem('rq-reloaded')) {
      try { sessionStorage.setItem('rq-reloaded', '1'); } catch { /* private mode */ }
      location.reload();
    }
  }
  componentDidUpdate(p: { resetKey: string }) { if (p.resetKey !== this.props.resetKey && this.state.err) this.setState({ err: null }); }
  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div className="glass mx-auto mt-16 max-w-lg p-6 text-sm">
        <div className="font-medium text-hi">This view hit an error.</div>
        <p className="mt-2 text-muted">{this.state.err.message}</p>
        <button className="mt-4 text-accent hover:underline" onClick={() => location.reload()}>Reload</button>
      </div>
    );
  }
}
