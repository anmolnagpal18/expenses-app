import React from 'react';
import { Link } from 'react-router-dom';
import { useGroups } from '../api/hooks/useGroups';
import { useAuth } from '../api/hooks/useAuth';
import { Users, Plus, ArrowRight, Wallet, TrendingUp, Landmark } from 'lucide-react';
import LoadingPage from '../components/ui/LoadingPage';
import ErrorState from '../components/ui/ErrorState';

const Dashboard = () => {
  const { user } = useAuth();
  const { useGroupsQuery } = useGroups();
  const { data: groups, isLoading, isError, error, refetch } = useGroupsQuery();

  if (isLoading) return <LoadingPage />;
  if (isError) return <ErrorState message={error.message} onRetry={refetch} />;

  // Calculate some simple counts/aggregations
  const activeGroups = groups || [];
  
  return (
    <div className="space-y-8 select-none">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-purple-900/40 via-indigo-900/30 to-slate-900 border border-slate-800/80 p-8 md:p-10 shadow-lg shadow-purple-950/10">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl" />
        <div className="relative z-10 space-y-4 max-w-2xl">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-300 border border-purple-500/20">
            Split & Settle Made Easy
          </span>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-white">
            Hello, {user?.full_name || user?.username}!
          </h1>
          <p className="text-slate-400 text-sm md:text-base leading-relaxed">
            Welcome back to Antigravity. Keep track of your shared bills, see who owes who, and settle up balances instantly.
          </p>
        </div>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="glass-card p-6 flex items-center space-x-5">
          <div className="p-4 rounded-2xl bg-purple-500/10 text-purple-400 border border-purple-500/15">
            <Users size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Groups</p>
            <h3 className="text-2xl font-bold text-white mt-1">{activeGroups.length}</h3>
          </div>
        </div>

        <div className="glass-card p-6 flex items-center space-x-5">
          <div className="p-4 rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/15">
            <Wallet size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Base Currency</p>
            <h3 className="text-2xl font-bold text-white mt-1">INR (₹)</h3>
          </div>
        </div>

        <div className="glass-card p-6 flex items-center space-x-5">
          <div className="p-4 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/15">
            <Landmark size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Settlements</p>
            <h3 className="text-2xl font-bold text-white mt-1">Direct</h3>
          </div>
        </div>
      </div>

      {/* Main Section */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">Your Groups</h2>
            <p className="text-sm text-slate-500">Select a group to manage members, add expenses or settle balances</p>
          </div>
          <Link to="/groups" className="glass-btn-primary py-2 px-4 flex items-center space-x-2 text-sm">
            <Plus size={16} />
            <span>New Group</span>
          </Link>
        </div>

        {activeGroups.length === 0 ? (
          <div className="glass-card p-12 text-center max-w-xl mx-auto space-y-6">
            <div className="inline-flex p-4 rounded-3xl bg-slate-950/60 border border-slate-800 text-slate-400">
              <Users size={32} />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-bold text-white">No groups found</h3>
              <p className="text-sm text-slate-400 max-w-sm mx-auto">
                You haven't created or joined any expense groups yet. Create one now to start splitting bills.
              </p>
            </div>
            <Link to="/groups" className="glass-btn-primary inline-flex items-center space-x-2">
              <Plus size={18} />
              <span>Create First Group</span>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {activeGroups.map((group) => (
              <Link 
                key={group.id} 
                to={`/groups/${group.id}`}
                className="glass-card p-6 hover:border-purple-500/40 hover:bg-slate-900/80 transition-all duration-200 group flex flex-col justify-between h-48 border border-slate-800/80"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-950 text-slate-400 border border-slate-800">
                      {group.base_currency}
                    </span>
                    <span className="text-[11px] text-slate-500 font-medium">
                      {group.memberships?.length || 0} members
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-white mt-4 group-hover:text-purple-300 transition-colors">
                    {group.name}
                  </h3>
                </div>
                
                <div className="flex items-center justify-between pt-4 border-t border-slate-950/60">
                  <span className="text-xs text-slate-500">Created by {group.created_by?.username || 'System'}</span>
                  <div className="text-purple-400 group-hover:translate-x-1 transition-transform duration-200">
                    <ArrowRight size={18} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
