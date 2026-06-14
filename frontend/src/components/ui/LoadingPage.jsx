import React from 'react';
import { Loader2 } from 'lucide-react';

export const LoadingPage = () => {
  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-100">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="w-10 h-10 text-purple-500 animate-spin" />
        <p className="text-slate-400 text-sm font-medium animate-pulse">
          Loading system resources...
        </p>
      </div>
    </div>
  );
};

export default LoadingPage;
