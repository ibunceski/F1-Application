import React from 'react';

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error('[render-error]', error, info);
    }
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-f1-dark px-4">
        <div className="card max-w-2xl p-6">
          <p className="section-label">Runtime Error</p>
          <h1 className="mt-2 text-2xl font-bold text-f1-white">Something went wrong</h1>
          <p className="mt-3 text-sm leading-relaxed text-f1-muted">The dashboard hit an unexpected render error.</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 rounded bg-f1-red px-4 py-2 text-sm font-semibold text-white"
          >
            Reload page
          </button>
          {import.meta.env.DEV ? (
            <details className="mt-5 rounded border border-f1-border bg-f1-dark p-3">
              <summary className="cursor-pointer text-sm font-semibold text-f1-text">Error details</summary>
              <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap text-xs text-f1-muted">
                {this.state.error.stack || this.state.error.message}
              </pre>
            </details>
          ) : null}
        </div>
      </div>
    );
  }
}
