import React, { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-slate-100">
          <div className="w-full max-w-md p-8 bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl flex flex-col items-center text-center">
            <div className="w-16 h-16 bg-red-950/50 border border-red-500/30 rounded-2xl flex items-center justify-center text-red-500 mb-6 animate-pulse">
              <AlertTriangle size={32} />
            </div>
            
            <h1 className="text-2xl font-bold font-display text-white mb-2">
              Something went wrong
            </h1>
            
            <p className="text-slate-400 text-sm mb-6 leading-relaxed">
              An unexpected client-side error occurred.
            </p>

            <div className="w-full p-4 bg-slate-950/50 border border-slate-800 rounded-xl mb-6 text-left overflow-auto max-h-40">
              <p className="font-mono text-xs text-red-400 break-words">
                {this.state.error?.toString() || 'Unknown Error'}
              </p>
            </div>

            <button
              onClick={this.handleReload}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-medium rounded-xl shadow-lg shadow-purple-950/40 active:scale-[0.98] transition-all duration-200 cursor-pointer"
            >
              <RefreshCw size={18} />
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
