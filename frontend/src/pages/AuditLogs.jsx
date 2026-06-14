import React, { useState } from 'react';
import { 
  FileSpreadsheet, 
  Search, 
  Filter, 
  Calendar, 
  Info, 
  User, 
  DollarSign, 
  Settings, 
  Upload, 
  CheckCircle 
} from 'lucide-react';

const mockLogs = [
  {
    id: 'aud-1092',
    timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(), // 5 mins ago
    actor: 'admin@gmail.com',
    action: 'COMMIT_IMPORT_BATCH',
    category: 'IMPORT',
    description: 'Committed staging import batch for Flat 304 group. Migrated 14 expenses.',
    severity: 'INFO'
  },
  {
    id: 'aud-1091',
    timestamp: new Date(Date.now() - 1000 * 60 * 12).toISOString(), // 12 mins ago
    actor: 'admin@gmail.com',
    action: 'RESOLVE_ANOMALY',
    category: 'IMPORT',
    description: 'Resolved MISSING_MEMBER anomaly for row #4. Mapped "Aisha K" to "aisha@gmail.com".',
    severity: 'INFO'
  },
  {
    id: 'aud-1090',
    timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 mins ago
    actor: 'admin@gmail.com',
    action: 'UPLOAD_IMPORT_CSV',
    category: 'IMPORT',
    description: 'Uploaded staging CSV batch "history_messy.csv" for Flat 304 group.',
    severity: 'INFO'
  },
  {
    id: 'aud-1089',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(), // 2 hours ago
    actor: 'owner@gmail.com',
    action: 'RECORD_SETTLEMENT',
    category: 'SETTLEMENT',
    description: 'Recorded repayment: member@gmail.com paid owner@gmail.com INR 50.00.',
    severity: 'INFO'
  },
  {
    id: 'aud-1088',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 5).toISOString(), // 5 hours ago
    actor: 'owner@gmail.com',
    action: 'CREATE_EXPENSE',
    category: 'EXPENSE',
    description: 'Created expense: Dinner splitting INR 90.00 EQUAL among 3 members.',
    severity: 'INFO'
  },
  {
    id: 'aud-1087',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
    actor: 'owner@gmail.com',
    action: 'ADD_GROUP_MEMBER',
    category: 'GROUP',
    description: 'Added member@gmail.com to Flat 304 group with role MEMBER.',
    severity: 'INFO'
  },
  {
    id: 'aud-1086',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(), // 2 days ago
    actor: 'owner@gmail.com',
    action: 'CREATE_GROUP',
    category: 'GROUP',
    description: 'Created new expense group Flat 304 with base currency INR.',
    severity: 'INFO'
  },
  {
    id: 'aud-1085',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(), // 2 days ago
    actor: 'owner@gmail.com',
    action: 'USER_SIGNUP',
    category: 'AUTH',
    description: 'New user owner@gmail.com registered and verified profile.',
    severity: 'INFO'
  }
];

const AuditLogs = () => {
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');

  const filteredLogs = mockLogs.filter(log => {
    const matchesSearch = 
      log.description.toLowerCase().includes(search.toLowerCase()) || 
      log.actor.toLowerCase().includes(search.toLowerCase()) ||
      log.action.toLowerCase().includes(search.toLowerCase());
    
    const matchesCategory = categoryFilter === 'ALL' || log.category === categoryFilter;

    return matchesSearch && matchesCategory;
  });

  const getIcon = (category) => {
    switch (category) {
      case 'AUTH': return <User size={16} className="text-blue-400" />;
      case 'GROUP': return <Settings size={16} className="text-purple-400" />;
      case 'EXPENSE': return <DollarSign size={16} className="text-rose-400" />;
      case 'SETTLEMENT': return <CheckCircle size={16} className="text-emerald-400" />;
      case 'IMPORT': return <Upload size={16} className="text-amber-400" />;
      default: return <Info size={16} className="text-slate-400" />;
    }
  };

  return (
    <div className="space-y-6 select-none">
      <div>
        <h1 className="text-2xl font-extrabold text-white">System Audit Trail</h1>
        <p className="text-sm text-slate-500">Immutable ledger of group actions, settlements, and resolutions</p>
      </div>

      {/* Filters Bar */}
      <div className="glass-card p-4 flex flex-col md:flex-row gap-4 items-center justify-between border-slate-800/80">
        <div className="relative w-full md:max-w-md">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
            <Search size={16} />
          </div>
          <input
            type="text"
            placeholder="Search by action, actor, or details..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="glass-input pl-10 py-2 text-xs"
          />
        </div>

        <div className="flex items-center space-x-3 w-full md:w-auto">
          <div className="flex items-center text-slate-500 text-xs font-semibold uppercase space-x-1.5 whitespace-nowrap">
            <Filter size={14} />
            <span>Filter Category:</span>
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="glass-input py-2 px-3 text-xs bg-slate-950/80 max-w-[150px] appearance-none"
          >
            <option value="ALL">ALL CATEGORIES</option>
            <option value="AUTH">AUTHENTICATION</option>
            <option value="GROUP">GROUP SETUP</option>
            <option value="EXPENSE">EXPENSES</option>
            <option value="SETTLEMENT">SETTLEMENTS</option>
            <option value="IMPORT">CSV IMPORT</option>
          </select>
        </div>
      </div>

      {/* Logs Table / List */}
      <div className="glass-card overflow-hidden border border-slate-800/80">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="p-4 font-semibold uppercase tracking-wider text-xs w-28">Timestamp</th>
                <th className="p-4 font-semibold uppercase tracking-wider text-xs w-40">Actor</th>
                <th className="p-4 font-semibold uppercase tracking-wider text-xs w-36">Action</th>
                <th className="p-4 font-semibold uppercase tracking-wider text-xs">Description</th>
                <th className="p-4 font-semibold uppercase tracking-wider text-xs w-16 text-center">Cat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/40">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center text-slate-500 font-medium italic">
                    No logs found matching your filters.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-900/10">
                    <td className="p-4 text-slate-500 whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="p-4 text-slate-300 font-mono">
                      {log.actor}
                    </td>
                    <td className="p-4">
                      <span className="inline-flex px-2 py-0.5 rounded bg-slate-950 border border-slate-800 font-mono text-[10px] font-bold text-slate-400">
                        {log.action}
                      </span>
                    </td>
                    <td className="p-4 text-slate-300 font-medium">
                      {log.description}
                    </td>
                    <td className="p-4 text-center">
                      <div className="inline-flex p-1.5 rounded-lg bg-slate-950 border border-slate-900" title={log.category}>
                        {getIcon(log.category)}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default AuditLogs;
