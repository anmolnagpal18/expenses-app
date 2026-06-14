import React from 'react';
import { Loader2 } from 'lucide-react';

export const LoadingCard = ({ message = "Fetching data..." }) => {
  return (
    <div className="w-full min-h-[200px] flex flex-col items-center justify-center border border-slate-800 bg-slate-900/40 rounded-2xl p-6">
      <Loader2 className="w-8 h-8 text-purple-500 animate-spin mb-3" />
      <p className="text-slate-400 text-sm">{message}</p>
    </div>
  );
};
