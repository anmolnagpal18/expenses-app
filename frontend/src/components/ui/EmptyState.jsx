import React from 'react';
import { Inbox } from 'lucide-react';

export const EmptyState = ({
  title = "No data found",
  description = "There are no records to display here at the moment.",
  icon = <Inbox className="w-12 h-12 text-slate-600" />,
  action
}) => {
  return (
    <div className="w-full flex flex-col items-center justify-center text-center p-12 border border-dashed border-slate-800 bg-slate-900/10 rounded-3xl">
      <div className="mb-4 p-4 bg-slate-900/50 rounded-2xl border border-slate-800/80">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>
      <p className="text-slate-400 text-sm max-w-sm mb-6 leading-relaxed">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
};
