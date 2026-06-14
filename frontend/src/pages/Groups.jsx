import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useGroups } from '../api/hooks/useGroups';
import { Plus, Users, Globe, X, AlertCircle } from 'lucide-react';
import LoadingPage from '../components/ui/LoadingPage';
import ErrorState from '../components/ui/ErrorState';

const Groups = () => {
  const { useGroupsQuery, useCreateGroupMutation } = useGroups();
  const { data: groups, isLoading, isError, error, refetch } = useGroupsQuery();
  const createGroupMutation = useCreateGroupMutation();

  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [baseCurrency, setBaseCurrency] = useState('INR');
  const [formError, setFormError] = useState('');

  if (isLoading) return <LoadingPage />;
  if (isError) return <ErrorState message={error.message} onRetry={refetch} />;

  const handleCreateGroup = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setFormError('Group name is required');
      return;
    }

    setFormError('');
    createGroupMutation.mutate(
      { name: name.trim(), base_currency: baseCurrency },
      {
        onSuccess: () => {
          setName('');
          setBaseCurrency('INR');
          setModalOpen(false);
        },
        onError: (err) => {
          console.error(err);
          const detail = err.response?.data?.detail || err.response?.data?.base_currency?.[0] || 'Failed to create group.';
          setFormError(detail);
        },
      }
    );
  };

  return (
    <div className="space-y-6 select-none relative">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-4 sm:space-y-0">
        <div>
          <h1 className="text-2xl font-extrabold text-white">Expense Groups</h1>
          <p className="text-sm text-slate-500">Create and manage your shared expense accounts</p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="glass-btn-primary flex items-center justify-center space-x-2 py-2.5 px-4"
        >
          <Plus size={18} />
          <span>Create Group</span>
        </button>
      </div>

      {/* Groups Grid */}
      {groups.length === 0 ? (
        <div className="glass-card p-12 text-center max-w-xl mx-auto space-y-6">
          <div className="inline-flex p-4 rounded-3xl bg-slate-950/60 border border-slate-800 text-slate-400">
            <Users size={32} />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-bold text-white">No groups yet</h3>
            <p className="text-sm text-slate-400 max-w-sm mx-auto">
              Start by creating a group for your flatmates, trip companions, or family bills.
            </p>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="glass-btn-primary inline-flex items-center space-x-2"
          >
            <Plus size={18} />
            <span>Create First Group</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {groups.map((group) => (
            <div
              key={group.id}
              className="glass-card p-6 flex flex-col justify-between border border-slate-800/80 hover:border-purple-500/30 transition-all duration-200"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 uppercase tracking-widest font-semibold">
                    Group ID: {group.id.substring(0, 8)}...
                  </span>
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-300 border border-purple-500/10">
                    {group.base_currency}
                  </span>
                </div>
                <h3 className="text-xl font-bold text-white mt-4">{group.name}</h3>
                <p className="text-xs text-slate-400 mt-2">
                  Created by {group.created_by?.username}
                </p>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-950/60 flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  {group.memberships?.length || 0} Members active
                </span>
                <Link
                  to={`/groups/${group.id}`}
                  className="text-purple-400 hover:text-purple-300 font-semibold text-sm transition-colors"
                >
                  View Details &rarr;
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Creation Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card w-full max-w-md p-6 relative">
            <button
              onClick={() => {
                setModalOpen(false);
                setFormError('');
              }}
              className="absolute top-4 right-4 text-slate-500 hover:text-slate-300 transition-colors"
            >
              <X size={20} />
            </button>

            <h2 className="text-xl font-bold text-white mb-6">Create New Group</h2>

            <form onSubmit={handleCreateGroup} className="space-y-5">
              {formError && (
                <div className="flex items-center space-x-2 text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 p-3 rounded-xl">
                  <AlertCircle size={16} className="flex-shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Group Name
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                    <Users size={16} />
                  </div>
                  <input
                    type="text"
                    placeholder="e.g. Flat 304, Euro Trip"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="glass-input pl-10"
                    maxLength={100}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Base Currency
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                    <Globe size={16} />
                  </div>
                  <select
                    value={baseCurrency}
                    onChange={(e) => setBaseCurrency(e.target.value)}
                    className="glass-input pl-10 appearance-none bg-slate-950"
                  >
                    <option value="INR">INR (₹)</option>
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                  </select>
                </div>
                <p className="text-[10px] text-slate-500 mt-1.5">
                  All expenses added in other currencies will be converted to this base currency.
                </p>
              </div>

              <div className="flex space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setModalOpen(false);
                    setFormError('');
                  }}
                  className="w-1/2 glass-btn-secondary py-2.5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createGroupMutation.isPending}
                  className="w-1/2 glass-btn-primary py-2.5 flex justify-center items-center"
                >
                  {createGroupMutation.isPending ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    'Create Group'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Groups;
