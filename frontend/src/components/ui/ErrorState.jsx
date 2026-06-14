import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export const ErrorState = ({
  title = "Error loading data",
  description = "Something went wrong while retrieving records. Please try again.",
  onRetry
}) => {
  return (
    <div className="w-full flex flex-col items-center justify-center text-center p-8 border border-red-950/20 bg-red-950/5 rounded-3xl">
      <div className="mb-4 p-3 bg-red-950/30 rounded-xl border border-red-900/30 text-red-500">
        <AlertCircle className="w-8 h-8" />
      </div>
      <h3 className="text-base font-semibold text-white mb-1">{title}</h3>
      <p className="text-slate-400 text-sm max-w-sm mb-4">{description}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-200 hover:text-white text-xs font-medium rounded-xl transition-all duration-200 active:scale-[0.98] cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Try Again
        </button>
      )}
    </div>
  );
};

export default ErrorState;
