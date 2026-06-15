import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useGroups } from '../api/hooks/useGroups';
import { useExpenses } from '../api/hooks/useExpenses';
import { useBalances } from '../api/hooks/useBalances';
import { useAuth } from '../api/hooks/useAuth';
import { 
  Users, 
  Plus, 
  Trash2, 
  DollarSign, 
  FileText, 
  Calendar,
  AlertCircle, 
  CheckCircle,
  HelpCircle,
  X,
  ArrowRight,
  TrendingDown
} from 'lucide-react';
import LoadingPage from '../components/ui/LoadingPage';
import ErrorState from '../components/ui/ErrorState';

const GroupDetail = () => {
  const { groupId } = useParams();
  const { user: currentUser } = useAuth();
  
  // Tab states: 'expenses' | 'settlements' | 'balances' | 'members'
  const [activeTab, setActiveTab] = useState('expenses');

  // Hooks
  const { useGroupDetailQuery, useAddMemberMutation } = useGroups();
  const { 
    useExpensesQuery, 
    useCreateExpenseMutation, 
    useDeleteExpenseMutation,
    useSettlementsQuery,
    useCreateSettlementMutation
  } = useExpenses();
  const { useBalancesQuery, useBalanceExplanationQuery } = useBalances();

  // Queries
  const { data: group, isLoading: groupLoading, isError: groupError, error: groupErr, refetch: refetchGroup } = useGroupDetailQuery(groupId);
  const { data: expenses, isLoading: expensesLoading, refetch: refetchExpenses } = useExpensesQuery(groupId);
  const { data: settlements, isLoading: settlementsLoading, refetch: refetchSettlements } = useSettlementsQuery(groupId);
  const { data: balances, isLoading: balancesLoading, refetch: refetchBalances } = useBalancesQuery(groupId);

  // Mutations
  const addMemberMutation = useAddMemberMutation(groupId);
  const createExpenseMutation = useCreateExpenseMutation(groupId);
  const deleteExpenseMutation = useDeleteExpenseMutation(groupId);
  const createSettlementMutation = useCreateSettlementMutation(groupId);

  // Modal / Form States
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [memberEmail, setMemberEmail] = useState('');
  const [memberRole, setMemberRole] = useState('MEMBER');
  const [memberJoinedAt, setMemberJoinedAt] = useState(new Date().toISOString().substring(0, 10));
  const [memberError, setMemberError] = useState('');

  const [expenseModalOpen, setExpenseModalOpen] = useState(false);
  const [expenseDesc, setExpenseDesc] = useState('');
  const [expenseAmount, setExpenseAmount] = useState('');
  const [expenseCurrency, setExpenseCurrency] = useState('INR');
  const [expenseDate, setExpenseDate] = useState(new Date().toISOString().substring(0, 16));
  const [expenseSplitType, setExpenseSplitType] = useState('EQUAL');
  const [expensePayers, setExpensePayers] = useState({}); // { user_id: amount }
  const [expenseParticipants, setExpenseParticipants] = useState({}); // { user_id: share_value }
  const [expenseError, setExpenseError] = useState('');

  const [settlementModalOpen, setSettlementModalOpen] = useState(false);
  const [settleFrom, setSettleFrom] = useState('');
  const [settleTo, setSettleTo] = useState('');
  const [settleAmount, setSettleAmount] = useState('');
  const [settleCurrency, setSettleCurrency] = useState('INR');
  const [settleDate, setSettleDate] = useState(new Date().toISOString().substring(0, 10));
  const [settleError, setSettleError] = useState('');

  // Balance Explanation Drawer State
  const [explainModalOpen, setExplainModalOpen] = useState(false);
  const [explainFrom, setExplainFrom] = useState(null); // { id, name }
  const [explainTo, setExplainTo] = useState(null); // { id, name }

  const { data: explanation, isLoading: explainLoading } = useBalanceExplanationQuery(
    groupId, 
    explainFrom?.id, 
    explainTo?.id
  );

  if (groupLoading) return <LoadingPage />;
  if (groupError) return <ErrorState message={groupErr.message} onRetry={refetchGroup} />;

  const membersList = group?.memberships || [];

  // Initialize Split/Payer inputs when opening Expense modal
  const openExpenseModal = () => {
    // Default: current user is the sole payer
    const initialPayers = {};
    if (currentUser) {
      initialPayers[currentUser.id] = '';
    }
    setExpensePayers(initialPayers);

    // Default: all members participate (value = 1)
    const initialParticipants = {};
    membersList.forEach(m => {
      initialParticipants[m.user.id] = '1';
    });
    setExpenseParticipants(initialParticipants);

    setExpenseDesc('');
    setExpenseAmount('');
    setExpenseCurrency(group.base_currency || 'INR');
    setExpenseSplitType('EQUAL');
    setExpenseError('');
    setExpenseModalOpen(true);
  };

  const openSettlementModal = () => {
    setSettleFrom('');
    setSettleTo('');
    setSettleAmount('');
    setSettleCurrency(group.base_currency || 'INR');
    setSettleError('');
    setSettlementModalOpen(true);
  };

  // Submissions
  const handleAddMember = (e) => {
    e.preventDefault();
    if (!memberEmail.trim()) return;
    setMemberError('');

    addMemberMutation.mutate(
      {
        email: memberEmail.trim(),
        role: memberRole,
        joined_at: new Date(memberJoinedAt).toISOString(),
      },
      {
        onSuccess: () => {
          setMemberEmail('');
          setMemberModalOpen(false);
          refetchGroup();
        },
        onError: (err) => {
          setMemberError(err.response?.data?.detail || 'Failed to add member.');
        }
      }
    );
  };

  const handleCreateExpense = (e) => {
    e.preventDefault();
    setExpenseError('');

    const parsedAmount = parseFloat(expenseAmount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setExpenseError('Total amount must be a positive number.');
      return;
    }

    // Assemble contributors list
    const contributors = [];
    let payersSum = 0;
    Object.entries(expensePayers).forEach(([userId, val]) => {
      const amt = parseFloat(val);
      if (!isNaN(amt) && amt > 0) {
        contributors.push({ user_id: userId, amount_paid: amt.toFixed(2) });
        payersSum += amt;
      }
    });

    if (contributors.length === 0) {
      setExpenseError('Please specify at least one contributor who paid.');
      return;
    }

    if (Math.abs(payersSum - parsedAmount) > 0.02) {
      setExpenseError(`Sum of payments (${payersSum.toFixed(2)}) must equal total amount (${parsedAmount.toFixed(2)}).`);
      return;
    }

    // Assemble participants list
    const participants = [];
    Object.entries(expenseParticipants).forEach(([userId, isSelected]) => {
      if (isSelected === true || isSelected === 'true' || parseFloat(isSelected) > 0) {
        let val = 1.0;
        if (expenseSplitType !== 'EQUAL') {
          val = parseFloat(isSelected) || 0;
        }
        participants.push({
          user_id: userId,
          split_input_value: val.toFixed(2)
        });
      }
    });

    if (participants.length === 0) {
      setExpenseError('Please check at least one participant.');
      return;
    }

    const payload = {
      group_id: groupId,
      description: expenseDesc.trim(),
      date: new Date(expenseDate).toISOString(),
      original_amount: parsedAmount.toFixed(2),
      currency: expenseCurrency,
      split_type: expenseSplitType.toLowerCase(),
      contributors,
      participants
    };

    createExpenseMutation.mutate(payload, {
      onSuccess: () => {
        setExpenseModalOpen(false);
        refetchExpenses();
        refetchBalances();
      },
      onError: (err) => {
        setExpenseError(err.response?.data?.detail || 'Failed to record expense.');
      }
    });
  };

  const handleCreateSettlement = (e) => {
    e.preventDefault();
    setSettleError('');

    if (!settleFrom || !settleTo) {
      setSettleError('Select payer and recipient.');
      return;
    }
    if (settleFrom === settleTo) {
      setSettleError('Payer and recipient must be different.');
      return;
    }

    const parsedAmount = parseFloat(settleAmount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setSettleError('Amount must be positive.');
      return;
    }

    createSettlementMutation.mutate({
      group_id: groupId,
      from_user_id: settleFrom,
      to_user_id: settleTo,
      amount: parsedAmount.toFixed(2),
      currency: settleCurrency,
      settlement_date: new Date(settleDate).toISOString().substring(0, 10)
    }, {
      onSuccess: () => {
        setSettlementModalOpen(false);
        refetchSettlements();
        refetchBalances();
      },
      onError: (err) => {
        setSettleError(err.response?.data?.detail || 'Failed to record settlement.');
      }
    });
  };

  const handleDeleteExpense = (expenseId) => {
    if (window.confirm('Are you sure you want to delete this expense?')) {
      deleteExpenseMutation.mutate(expenseId, {
        onSuccess: () => {
          refetchExpenses();
          refetchBalances();
        }
      });
    }
  };

  return (
    <div className="space-y-6 select-none relative">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-slate-900/80 pb-6 space-y-4 sm:space-y-0">
        <div>
          <span className="text-xs font-semibold text-purple-400 uppercase tracking-widest">Active Group</span>
          <h1 className="text-3xl font-extrabold text-white mt-1">{group.name}</h1>
          <p className="text-sm text-slate-500 mt-1">Base currency: <strong className="text-slate-300">{group.base_currency}</strong></p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={openExpenseModal}
            className="glass-btn-primary flex items-center justify-center space-x-2 py-2 px-4 text-sm"
          >
            <Plus size={16} />
            <span>Add Expense</span>
          </button>
          <button
            onClick={openSettlementModal}
            className="glass-btn-secondary flex items-center justify-center space-x-2 py-2 px-4 text-sm"
          >
            <DollarSign size={16} />
            <span>Settle Balance</span>
          </button>
        </div>
      </div>

      {/* Tabs Menu */}
      <div className="flex border-b border-slate-900/80 space-x-6 text-sm font-medium">
        {[
          { id: 'expenses', label: 'Expenses', count: expenses?.length },
          { id: 'settlements', label: 'Settlements', count: settlements?.length },
          { id: 'balances', label: 'Balances' },
          { id: 'members', label: 'Members', count: membersList.length }
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`pb-4 border-b-2 transition-all relative ${
              activeTab === t.id 
                ? 'border-purple-500 text-purple-400 font-semibold' 
                : 'border-transparent text-slate-500 hover:text-slate-300'
            }`}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="ml-1.5 px-1.5 py-0.5 text-[10px] rounded-full bg-slate-900 text-slate-400">
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* TAB CONTENTS */}

      {/* 1. EXPENSES */}
      {activeTab === 'expenses' && (
        <div className="space-y-4">
          {expensesLoading ? (
            <div className="p-12 text-center text-slate-500">Loading expenses...</div>
          ) : !expenses || expenses.length === 0 ? (
            <div className="glass-card p-12 text-center max-w-xl mx-auto space-y-4">
              <FileText size={32} className="mx-auto text-slate-500" />
              <h3 className="text-lg font-bold text-white">No expenses recorded</h3>
              <p className="text-sm text-slate-400">Add bills paid by members to see bilateral balance calculations.</p>
              <button onClick={openExpenseModal} className="glass-btn-primary py-2 px-4 text-sm">Add First Expense</button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {expenses.map(exp => (
                <div key={exp.id} className="glass-card p-5 flex flex-col md:flex-row md:items-center md:justify-between border border-slate-800/80 hover:border-slate-800 transition-colors">
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <h4 className="font-bold text-lg text-white">{exp.description}</h4>
                      <span className="px-2 py-0.5 text-[10px] font-semibold bg-purple-500/10 text-purple-300 border border-purple-500/10 rounded-full">
                        {exp.split_type}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span className="flex items-center"><Calendar size={12} className="mr-1" /> {new Date(exp.date).toLocaleString()}</span>
                      <span>Paid by: <strong className="text-slate-400">{exp.contributions.map(c => c.user.username).join(', ')}</strong></span>
                      <span>Spanned for: <strong className="text-slate-400">{exp.splits.map(s => s.user.username).join(', ')}</strong></span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-6 mt-4 md:mt-0 justify-between md:justify-end border-t md:border-t-0 border-slate-900/60 pt-4 md:pt-0">
                    <div className="text-right">
                      <p className="text-xs text-slate-500 uppercase tracking-widest font-semibold">Total Amount</p>
                      <h5 className="text-xl font-bold text-white mt-1">
                        {exp.currency} {parseFloat(exp.original_amount).toFixed(2)}
                      </h5>
                      {exp.currency !== group.base_currency && exp.converted_amount && (
                        <p className="text-[10px] text-slate-500">
                          &asymp; {group.base_currency} {parseFloat(exp.converted_amount).toFixed(2)}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => handleDeleteExpense(exp.id)}
                      className="p-2 rounded-xl text-rose-500 hover:bg-rose-500/10 hover:border-rose-500/20 border border-transparent transition-colors"
                      title="Delete Expense"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 2. SETTLEMENTS */}
      {activeTab === 'settlements' && (
        <div className="space-y-4">
          {settlementsLoading ? (
            <div className="p-12 text-center text-slate-500">Loading settlements...</div>
          ) : !settlements || settlements.length === 0 ? (
            <div className="glass-card p-12 text-center max-w-xl mx-auto space-y-4">
              <DollarSign size={32} className="mx-auto text-slate-500" />
              <h3 className="text-lg font-bold text-white">No settlements recorded</h3>
              <p className="text-sm text-slate-400">Record peer repayments to reduce outstanding group debts.</p>
              <button onClick={openSettlementModal} className="glass-btn-primary py-2 px-4 text-sm">Record A Settlement</button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {settlements.map(setl => (
                <div key={setl.id} className="glass-card p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between border border-slate-800/80">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/15">
                      <CheckCircle size={20} />
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <strong className="text-slate-200">{setl.payer?.username || 'Unknown'}</strong>
                        <ArrowRight size={14} className="text-slate-500" />
                        <strong className="text-slate-200">{setl.receiver?.username || 'Unknown'}</strong>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        Settled on {new Date(setl.settlement_date).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="text-right mt-4 sm:mt-0">
                    <p className="text-xs text-slate-500 uppercase tracking-widest font-semibold">Repaid</p>
                    <h5 className="text-lg font-bold text-white mt-1">
                      {setl.currency} {parseFloat(setl.original_amount).toFixed(2)}
                    </h5>
                    {setl.currency !== group.base_currency && setl.converted_amount && (
                      <p className="text-[10px] text-slate-500">
                        &asymp; {group.base_currency} {parseFloat(setl.converted_amount).toFixed(2)}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 3. BALANCES */}
      {activeTab === 'balances' && (
        <div className="space-y-4">
          {balancesLoading ? (
            <div className="p-12 text-center text-slate-500">Loading group balances...</div>
          ) : !balances || balances.length === 0 ? (
            <div className="glass-card p-8 text-center max-w-xl mx-auto text-slate-400">
              No active debts! Everyone is settled up.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {balances.map((bal, idx) => (
                <div key={idx} className="glass-card p-5 flex flex-col justify-between border border-slate-800/80">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center font-bold text-sm">
                        {bal.from_user.username.substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <strong className="text-white block">{bal.from_user.full_name || bal.from_user.username}</strong>
                        <span className="text-[10px] text-rose-400 uppercase tracking-widest font-semibold">Debtor</span>
                      </div>
                    </div>

                    <div className="text-slate-500 text-xs px-2 flex flex-col items-center">
                      <ArrowRight size={18} className="text-slate-400" />
                      <span className="text-[10px] font-semibold text-slate-500 mt-1">owes</span>
                    </div>

                    <div className="flex items-center space-x-3 text-right">
                      <div>
                        <strong className="text-white block">{bal.to_user.full_name || bal.to_user.username}</strong>
                        <span className="text-[10px] text-emerald-400 uppercase tracking-widest font-semibold">Creditor</span>
                      </div>
                      <div className="w-10 h-10 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold text-sm">
                        {bal.to_user.username.substring(0, 2).toUpperCase()}
                      </div>
                    </div>
                  </div>

                  <div className="mt-6 pt-4 border-t border-slate-950/60 flex items-center justify-between">
                    <div>
                      <span className="text-xs text-slate-500">Amount Owed</span>
                      <p className="text-xl font-extrabold text-white">
                        {group.base_currency} {parseFloat(bal.amount).toFixed(2)}
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setExplainFrom(bal.from_user);
                        setExplainTo(bal.to_user);
                        setExplainModalOpen(true);
                      }}
                      className="glass-btn-secondary py-1.5 px-3 flex items-center space-x-1.5 text-xs"
                    >
                      <HelpCircle size={14} />
                      <span>Explain Balance</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 4. MEMBERS */}
      {activeTab === 'members' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-bold text-white">Group Members</h3>
            <button
              onClick={() => setMemberModalOpen(true)}
              className="glass-btn-primary py-1.5 px-3 flex items-center space-x-1.5 text-xs"
            >
              <Plus size={14} />
              <span>Add Member</span>
            </button>
          </div>

          <div className="glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-950/60 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="p-4 font-semibold uppercase tracking-wider text-xs">Name</th>
                    <th className="p-4 font-semibold uppercase tracking-wider text-xs">Role</th>
                    <th className="p-4 font-semibold uppercase tracking-wider text-xs">Joined Date</th>
                    <th className="p-4 font-semibold uppercase tracking-wider text-xs">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                  {membersList.map(m => {
                    const isActive = !m.left_at;
                    return (
                      <tr key={m.id} className="hover:bg-slate-900/20">
                        <td className="p-4">
                          <div>
                            <p className="font-semibold text-slate-200">{m.user.full_name || m.user.username}</p>
                            <p className="text-xs text-slate-500">{m.user.email}</p>
                          </div>
                        </td>
                        <td className="p-4">
                          <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wider ${
                            m.role === 'OWNER' ? 'bg-purple-500/10 text-purple-300 border border-purple-500/10' :
                            m.role === 'ADMIN' ? 'bg-blue-500/10 text-blue-300 border border-blue-500/10' :
                            'bg-slate-800 text-slate-400'
                          }`}>
                            {m.role}
                          </span>
                        </td>
                        <td className="p-4 text-xs text-slate-400">
                          {new Date(m.joined_at).toLocaleDateString()}
                        </td>
                        <td className="p-4">
                          <span className={`inline-flex items-center text-xs font-semibold ${
                            isActive ? 'text-emerald-400' : 'text-slate-500'
                          }`}>
                            <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${isActive ? 'bg-emerald-400' : 'bg-slate-500'}`} />
                            {isActive ? 'Active' : 'Left'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* MEMBER MODAL */}
      {memberModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card w-full max-w-md p-6 relative">
            <button onClick={() => setMemberModalOpen(false)} className="absolute top-4 right-4 text-slate-500 hover:text-slate-300">
              <X size={20} />
            </button>
            <h2 className="text-xl font-bold text-white mb-6">Add Member to Group</h2>
            <form onSubmit={handleAddMember} className="space-y-4">
              {memberError && (
                <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/25 p-3 rounded-xl flex items-center space-x-2">
                  <AlertCircle size={16} />
                  <span>{memberError}</span>
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Member Email</label>
                <input
                  type="email"
                  placeholder="friend@email.com"
                  value={memberEmail}
                  onChange={(e) => setMemberEmail(e.target.value)}
                  className="glass-input"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Role</label>
                <select value={memberRole} onChange={(e) => setMemberRole(e.target.value)} className="glass-input bg-slate-950">
                  <option value="MEMBER">MEMBER</option>
                  <option value="ADMIN">ADMIN</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Join Date</label>
                <input
                  type="date"
                  value={memberJoinedAt}
                  onChange={(e) => setMemberJoinedAt(e.target.value)}
                  className="glass-input"
                  required
                />
              </div>
              <div className="flex space-x-3 pt-2">
                <button type="button" onClick={() => setMemberModalOpen(false)} className="w-1/2 glass-btn-secondary">Cancel</button>
                <button type="submit" disabled={addMemberMutation.isPending} className="w-1/2 glass-btn-primary flex justify-center">
                  {addMemberMutation.isPending ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Add'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EXPENSE MODAL */}
      {expenseModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="glass-card w-full max-w-lg p-6 relative my-8">
            <button onClick={() => setExpenseModalOpen(false)} className="absolute top-4 right-4 text-slate-500 hover:text-slate-300">
              <X size={20} />
            </button>
            <h2 className="text-xl font-bold text-white mb-6">Record Group Expense</h2>
            <form onSubmit={handleCreateExpense} className="space-y-4">
              {expenseError && (
                <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/25 p-3 rounded-xl flex items-center space-x-2">
                  <AlertCircle size={16} />
                  <span>{expenseError}</span>
                </div>
              )}
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase mb-1.5">Description</label>
                  <input type="text" placeholder="e.g. Dinner" value={expenseDesc} onChange={e => setExpenseDesc(e.target.value)} className="glass-input" required />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase mb-1.5">Total Amount</label>
                  <input type="number" step="0.01" placeholder="0.00" value={expenseAmount} onChange={e => setExpenseAmount(e.target.value)} className="glass-input" required />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase mb-1.5">Currency</label>
                  <select value={expenseCurrency} onChange={e => setExpenseCurrency(e.target.value)} className="glass-input bg-slate-950">
                    <option value="INR">INR (₹)</option>
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase mb-1.5">Date & Time</label>
                  <input type="datetime-local" value={expenseDate} onChange={e => setExpenseDate(e.target.value)} className="glass-input" required />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase mb-1.5">Split Strategy</label>
                <select value={expenseSplitType} onChange={e => setExpenseSplitType(e.target.value)} className="glass-input bg-slate-950">
                  <option value="EQUAL">EQUAL (Split equally)</option>
                  <option value="EXACT">EXACT (By exact amount)</option>
                  <option value="PERCENTAGE">PERCENTAGE (By percentage)</option>
                  <option value="SHARES">SHARES (By shares/ratio)</option>
                </select>
              </div>

              {/* PAYER(S) SECTION */}
              <div className="border-t border-slate-900/60 pt-4">
                <label className="block text-xs font-semibold text-slate-300 uppercase mb-2">Paid By (Who Paid?)</label>
                <div className="space-y-2 max-h-32 overflow-y-auto pr-1">
                  {membersList.filter(m => !m.left_at).map(m => {
                    const currentVal = expensePayers[m.user.id] || '';
                    return (
                      <div key={m.user.id} className="flex items-center justify-between space-x-4">
                        <span className="text-sm text-slate-400 truncate">{m.user.username}</span>
                        <input
                          type="number"
                          step="0.01"
                          placeholder="0.00"
                          value={currentVal}
                          onChange={(e) => {
                            setExpensePayers({
                              ...expensePayers,
                              [m.user.id]: e.target.value
                            });
                          }}
                          className="glass-input py-1.5 px-3 max-w-[120px] text-right"
                        />
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* PARTICIPANT(S) SECTION */}
              <div className="border-t border-slate-900/60 pt-4">
                <label className="block text-xs font-semibold text-slate-300 uppercase mb-2">
                  Participants ({expenseSplitType === 'EQUAL' ? 'Split Shares' : `Input Split Values in ${expenseSplitType}`})
                </label>
                <div className="space-y-2 max-h-36 overflow-y-auto pr-1">
                  {membersList.filter(m => !m.left_at).map(m => {
                    const isChecked = expenseParticipants[m.user.id] !== undefined && expenseParticipants[m.user.id] !== false;
                    const value = expenseParticipants[m.user.id] || '';

                    return (
                      <div key={m.user.id} className="flex items-center justify-between space-x-4">
                        <label className="flex items-center space-x-3 cursor-pointer text-sm text-slate-400">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              const newParticipants = { ...expenseParticipants };
                              if (e.target.checked) {
                                newParticipants[m.user.id] = expenseSplitType === 'EQUAL' ? true : '1';
                              } else {
                                delete newParticipants[m.user.id];
                              }
                              setExpenseParticipants(newParticipants);
                            }}
                            className="rounded bg-slate-950 border-slate-800 text-purple-600 focus:ring-purple-600/40"
                          />
                          <span>{m.user.username}</span>
                        </label>

                        {expenseSplitType !== 'EQUAL' && isChecked && (
                          <input
                            type="number"
                            step="0.01"
                            placeholder={expenseSplitType === 'PERCENTAGE' ? '%' : expenseSplitType === 'SHARES' ? 'shares' : 'amount'}
                            value={value}
                            onChange={(e) => {
                              setExpenseParticipants({
                                ...expenseParticipants,
                                [m.user.id]: e.target.value
                              });
                            }}
                            className="glass-input py-1.5 px-3 max-w-[100px] text-right"
                            required
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="flex space-x-3 pt-4 border-t border-slate-900/60">
                <button type="button" onClick={() => setExpenseModalOpen(false)} className="w-1/2 glass-btn-secondary">Cancel</button>
                <button type="submit" disabled={createExpenseMutation.isPending} className="w-1/2 glass-btn-primary flex justify-center">
                  {createExpenseMutation.isPending ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Record Expense'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SETTLEMENT MODAL */}
      {settlementModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card w-full max-w-md p-6 relative">
            <button onClick={() => setSettlementModalOpen(false)} className="absolute top-4 right-4 text-slate-500 hover:text-slate-300">
              <X size={20} />
            </button>
            <h2 className="text-xl font-bold text-white mb-6">Record A Settlement</h2>
            <form onSubmit={handleCreateSettlement} className="space-y-4">
              {settleError && (
                <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/25 p-3 rounded-xl flex items-center space-x-2">
                  <AlertCircle size={16} />
                  <span>{settleError}</span>
                </div>
              )}
              
              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Payer (Who Paid?)</label>
                <select value={settleFrom} onChange={e => setSettleFrom(e.target.value)} className="glass-input bg-slate-950" required>
                  <option value="">-- Select Member --</option>
                  {membersList.map(m => (
                    <option key={m.user.id} value={m.user.id}>{m.user.username}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Recipient (Who Received?)</label>
                <select value={settleTo} onChange={e => setSettleTo(e.target.value)} className="glass-input bg-slate-950" required>
                  <option value="">-- Select Member --</option>
                  {membersList.map(m => (
                    <option key={m.user.id} value={m.user.id}>{m.user.username}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Amount Paid</label>
                  <input type="number" step="0.01" placeholder="0.00" value={settleAmount} onChange={e => setSettleAmount(e.target.value)} className="glass-input" required />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Currency</label>
                  <select value={settleCurrency} onChange={e => setSettleCurrency(e.target.value)} className="glass-input bg-slate-950">
                    <option value="INR">INR (₹)</option>
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Settlement Date</label>
                <input type="date" value={settleDate} onChange={e => setSettleDate(e.target.value)} className="glass-input" required />
              </div>

              <div className="flex space-x-3 pt-2">
                <button type="button" onClick={() => setSettlementModalOpen(false)} className="w-1/2 glass-btn-secondary">Cancel</button>
                <button type="submit" disabled={createSettlementMutation.isPending} className="w-1/2 glass-btn-primary flex justify-center">
                  {createSettlementMutation.isPending ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Record Settlement'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* BALANCE EXPLANATION MODAL */}
      {explainModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card w-full max-w-2xl p-6 relative max-h-[85vh] flex flex-col">
            <button
              onClick={() => {
                setExplainModalOpen(false);
                setExplainFrom(null);
                setExplainTo(null);
              }}
              className="absolute top-4 right-4 text-slate-500 hover:text-slate-300"
            >
              <X size={20} />
            </button>

            <div className="mb-6">
              <span className="text-xs font-semibold text-purple-400 uppercase tracking-widest">Debtor Traceability Report</span>
              <h2 className="text-xl font-bold text-white mt-1">
                Balance Explanation
              </h2>
              <div className="flex items-center space-x-2 text-sm text-slate-400 mt-2">
                <span>Transactions showing why</span>
                <strong className="text-slate-200">{explainFrom?.username}</strong>
                <span>owes</span>
                <strong className="text-slate-200">{explainTo?.username}</strong>
              </div>
            </div>

            {explainLoading ? (
              <div className="flex-1 p-12 text-center text-slate-500">Retrieving ledger details...</div>
            ) : !explanation ? (
              <div className="flex-1 p-12 text-center text-slate-500">Failed to load explanation details.</div>
            ) : (
              <div className="flex-1 overflow-y-auto space-y-6 pr-1">
                {/* Net Debt Box */}
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-900 flex justify-between items-center">
                  <div>
                    <span className="text-xs text-slate-500 block uppercase font-medium">Bilateral Balance Position</span>
                    <strong className="text-lg text-white">
                      {explainFrom?.username} owes {explainTo?.username}
                    </strong>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-slate-500 block uppercase font-medium">Total Net Debt</span>
                    <strong className="text-xl text-purple-400">
                      {group.base_currency} {parseFloat(explanation.balance).toFixed(2)}
                    </strong>
                  </div>
                </div>

                {/* Expenses Breakdown */}
                <div className="space-y-3">
                  <h3 className="font-bold text-sm text-slate-300 uppercase tracking-wider">Underlying Shared Expenses</h3>
                  {explanation.expense_breakdown.length === 0 ? (
                    <p className="text-xs text-slate-500 italic p-3 bg-slate-900/30 rounded-lg">No shared expenses found.</p>
                  ) : (
                    <div className="space-y-2">
                      {explanation.expense_breakdown.map((item, idx) => (
                        <div key={idx} className="bg-slate-900/30 p-3 rounded-lg border border-slate-900/60 flex justify-between items-center text-xs">
                          <div>
                            <p className="font-semibold text-slate-200">{item.description}</p>
                            <span className="text-slate-500">{new Date(item.date).toLocaleDateString()} &middot; Total {item.currency} {parseFloat(item.original_amount).toFixed(2)}</span>
                          </div>
                          <div className="text-right font-medium">
                            <span className={parseFloat(item.amount) >= 0 ? "text-rose-400" : "text-emerald-400"}>
                              {parseFloat(item.amount) >= 0 ? '+' : ''}{parseFloat(item.amount).toFixed(2)} {group.base_currency}
                            </span>
                            <p className="text-[10px] text-slate-500">allocated share</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Settlements Breakdown */}
                <div className="space-y-3">
                  <h3 className="font-bold text-sm text-slate-300 uppercase tracking-wider">Direct Bilateral Settlements</h3>
                  {explanation.settlement_breakdown.length === 0 ? (
                    <p className="text-xs text-slate-500 italic p-3 bg-slate-900/30 rounded-lg">No settlements recorded between these users.</p>
                  ) : (
                    <div className="space-y-2">
                      {explanation.settlement_breakdown.map((item, idx) => (
                        <div key={idx} className="bg-slate-900/30 p-3 rounded-lg border border-slate-900/60 flex justify-between items-center text-xs">
                          <div>
                            <p className="font-semibold text-slate-200">
                              {item.from_user_id === explainFrom?.id ? 'Repayment sent' : 'Repayment received'}
                            </p>
                            <span className="text-slate-500">{new Date(item.date).toLocaleDateString()} &middot; {item.currency} {parseFloat(item.original_amount).toFixed(2)}</span>
                          </div>
                          <div className="text-right font-medium">
                            <span className={item.from_user_id === explainFrom?.id ? "text-emerald-400" : "text-rose-400"}>
                              {item.from_user_id === explainFrom?.id ? '-' : '+'}{parseFloat(item.amount).toFixed(2)} {group.base_currency}
                            </span>
                            <p className="text-[10px] text-slate-500">converted amount</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default GroupDetail;
