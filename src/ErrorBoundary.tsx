import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  name?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.log(`[ErrorBoundary: ${this.props.name ?? 'unknown'}] Error caught:`, error);
    console.log(`[ErrorBoundary: ${this.props.name ?? 'unknown'}] Component stack:`, info.componentStack);
  }

  render() {
    if (this.state.hasError && this.state.error) {
      const err = this.state.error;
      return (
        <div className="min-h-screen bg-white flex items-center justify-center px-4">
          <div className="w-full max-w-2xl">
            <div className="bg-red-50 border-2 border-red-400 rounded-xl p-6">
              <h2 className="text-red-700 font-bold text-lg mb-1">
                Component Error {this.props.name ? `(${this.props.name})` : ''}
              </h2>
              <p className="text-red-600 font-medium text-sm mb-4">{err.message}</p>
              <pre className="bg-red-100 border border-red-300 rounded-lg p-4 text-xs text-red-800 overflow-auto max-h-64 whitespace-pre-wrap">
                {err.stack}
              </pre>
              <button
                className="mt-4 bg-red-600 hover:bg-red-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
                onClick={() => this.setState({ hasError: false, error: null })}
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
