import React, { useState } from 'react';
import { useGroups } from '../api/hooks/useGroups';
import { useImports } from '../api/hooks/useImports';
import { 
  Upload, 
  FileText, 
  CheckCircle, 
  AlertTriangle, 
  AlertCircle,
  HelpCircle,
  Play,
  RotateCcw,
  Sparkles,
  ChevronRight,
  ArrowRight,
  UserPlus,
  Link2,
  Trash
} from 'lucide-react';
import LoadingPage from '../components/ui/LoadingPage';
import ErrorState from '../components/ui/ErrorState';

const CSVImport = () => {
  const { useGroupsQuery } = useGroups();
  const { data: groups, isLoading: groupsLoading } = useGroupsQuery();

  const { 
    useUploadMutation, 
    useDetectMutation, 
    useBatchDetailQuery, 
    useResolveAnomalyMutation, 
    useCommitMutation 
  } = useImports();

  const uploadMutation = useUploadMutation();
  const detectMutation = useDetectMutation();
  const commitMutation = useCommitMutation();

  // Staging state
  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [activeBatchId, setActiveBatchId] = useState(null);
  const [uploadError, setUploadError] = useState('');

  // Fetch active batch details
  const { data: batch, isLoading: batchLoading, refetch: refetchBatch } = useBatchDetailQuery(activeBatchId);
  const resolveAnomalyMutation = useResolveAnomalyMutation(activeBatchId);

  // Resolution Modal State
  const [resolutionModalOpen, setResolutionModalOpen] = useState(false);
  const [activeRow, setActiveRow] = useState(null);
  const [activeAnomaly, setActiveAnomaly] = useState(null);
  
  const [resolutionAction, setResolutionAction] = useState('MAP_USER'); // 'MAP_USER' | 'CREATE_USER' | 'SKIP' | 'KEEP'
  const [mappedUserId, setMappedUserId] = useState('');
  const [newUsername, setNewUsername] = useState('');
  const [newFullName, setNewFullName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [resError, setResError] = useState('');

  // Commit Report Summary State
  const [commitSummary, setCommitSummary] = useState(null);

  if (groupsLoading) return <LoadingPage />;

  const handleFileChange = (e) => {
    setSelectedFile(e.target.files[0]);
    setUploadError('');
  };

  const handleUpload = (e) => {
    e.preventDefault();
    if (!selectedGroupId) {
      setUploadError('Please select a group.');
      return;
    }
    if (!selectedFile) {
      setUploadError('Please choose a CSV file.');
      return;
    }

    setUploadError('');
    setCommitSummary(null);

    uploadMutation.mutate({
      file: selectedFile,
      groupId: selectedGroupId
    }, {
      onSuccess: (data) => {
        setActiveBatchId(data.batch_id);
        setSelectedFile(null);
      },
      onError: (err) => {
        setUploadError(err.response?.data?.detail || 'Failed to upload CSV file.');
      }
    });
  };

  const handleDetect = () => {
    if (!activeBatchId) return;
    detectMutation.mutate(activeBatchId);
  };

  const openResolutionModal = (row, anomaly) => {
    setActiveRow(row);
    setActiveAnomaly(anomaly);
    setResError('');

    // Pre-populate resolution options
    if (anomaly.anomaly_type === 'MISSING_MEMBER' || anomaly.anomaly_type === 'UNKNOWN_MEMBER') {
      setResolutionAction('MAP_USER');
      setNewUsername((anomaly.metadata?.missing_member || '').toLowerCase().replace(/\s+/g, ''));
      setNewFullName(anomaly.metadata?.missing_member || '');
      setNewEmail('');
    } else if (anomaly.anomaly_type === 'DUPLICATE_ROW' || anomaly.anomaly_type === 'DUPLICATE_EXPENSE') {
      setResolutionAction('SKIP');
    } else {
      setResolutionAction('KEEP');
    }

    setResolutionModalOpen(true);
  };

  const handleResolve = (e) => {
    e.preventDefault();
    setResError('');

    let details = {};
    if (resolutionAction === 'MAP_USER') {
      if (!mappedUserId) {
        setResError('Please select a group member to map to.');
        return;
      }
      details = { user_id: mappedUserId };
    } else if (resolutionAction === 'CREATE_USER') {
      if (!newUsername || !newEmail || !newFullName) {
        setResError('Please fill in username, email, and full name.');
        return;
      }
      details = {
        username: newUsername,
        email: newEmail,
        full_name: newFullName
      };
    }

    let finalAction = resolutionAction;
    if (resolutionAction === 'SKIP') finalAction = 'IGNORE';
    if (resolutionAction === 'KEEP') finalAction = 'KEEP_BOTH';

    resolveAnomalyMutation.mutate({
      rowId: activeRow.id,
      payload: {
        anomaly_id: activeAnomaly.id,
        action_taken: finalAction,
        notes: `Resolved ${activeAnomaly.anomaly_type} by choosing ${finalAction}`,
        resolution_details: details
      }
    }, {
      onSuccess: () => {
        setResolutionModalOpen(false);
        setActiveRow(null);
        setActiveAnomaly(null);
        refetchBatch();
      },
      onError: (err) => {
        setResError(err.response?.data?.detail || 'Failed to resolve anomaly.');
      }
    });
  };

  const handleCommit = () => {
    if (!activeBatchId) return;
    if (window.confirm('Commit staging rows to production expenses? Only APPROVED rows will be migrated.')) {
      commitMutation.mutate(activeBatchId, {
        onSuccess: (data) => {
          setCommitSummary(data.import_summary);
          setActiveBatchId(null);
        },
        onError: (err) => {
          alert(err.response?.data?.detail || 'Failed to commit batch.');
        }
      });
    }
  };

  return (
    <div className="space-y-8 select-none relative">
      <div>
        <h1 className="text-2xl font-extrabold text-white">CSV Staging & Imports</h1>
        <p className="text-sm text-slate-500">Upload, parse, resolve anomalies, and review batches before committing to production</p>
      </div>

      {/* Commit Report Summary */}
      {commitSummary && (
        <div className="glass-card p-6 border-emerald-500/20 bg-emerald-950/10">
          <div className="flex items-center space-x-3 mb-4 text-emerald-400">
            <CheckCircle size={24} />
            <h3 className="text-lg font-bold">Staging Committed Successfully</h3>
          </div>
          <p className="text-sm text-slate-300 mb-6">
            The CSV batch has been successfully processed, and its transactions have been migrated. Below is the import summary report:
          </p>
          
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-900">
              <span className="text-[10px] text-slate-500 font-semibold uppercase block">Expenses Created</span>
              <span className="text-2xl font-extrabold text-white">{commitSummary.expenses_created || 0}</span>
            </div>
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-900">
              <span className="text-[10px] text-slate-500 font-semibold uppercase block">Settlements Created</span>
              <span className="text-2xl font-extrabold text-white">{commitSummary.settlements_created || 0}</span>
            </div>
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-900">
              <span className="text-[10px] text-slate-500 font-semibold uppercase block">Users Auto-Created</span>
              <span className="text-2xl font-extrabold text-white">{commitSummary.users_created || 0}</span>
            </div>
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-900">
              <span className="text-[10px] text-slate-500 font-semibold uppercase block">Rows Skipped</span>
              <span className="text-2xl font-extrabold text-white">{commitSummary.rows_skipped || 0}</span>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 1: UPLOAD FORM (Only if no batch is active) */}
      {!activeBatchId && (
        <div className="glass-card p-8 max-w-xl mx-auto">
          <form onSubmit={handleUpload} className="space-y-6">
            <h2 className="text-xl font-bold text-white mb-4">Start New Import</h2>

            {uploadError && (
              <div className="flex items-center space-x-2 text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 p-3.5 rounded-xl">
                <AlertCircle size={18} className="flex-shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Target Group
              </label>
              <select
                value={selectedGroupId}
                onChange={(e) => setSelectedGroupId(e.target.value)}
                className="glass-input bg-slate-950"
                required
              >
                <option value="">-- Choose Expense Group --</option>
                {groups?.map(g => (
                  <option key={g.id} value={g.id}>{g.name} ({g.base_currency})</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Upload CSV File
              </label>
              <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-slate-800 border-dashed rounded-xl hover:border-purple-500/40 transition-colors">
                <div className="space-y-1 text-center">
                  <Upload className="mx-auto h-12 w-12 text-slate-500" />
                  <div className="flex text-sm text-slate-400 justify-center">
                    <label className="relative cursor-pointer bg-transparent rounded-md font-semibold text-purple-400 hover:text-purple-300 focus-within:outline-none">
                      <span>Upload a file</span>
                      <input
                        type="file"
                        accept=".csv"
                        onChange={handleFileChange}
                        className="sr-only"
                        required
                      />
                    </label>
                  </div>
                  <p className="text-xs text-slate-500">CSV only up to 2MB</p>
                  {selectedFile && (
                    <div className="text-xs font-semibold text-purple-300 bg-purple-500/10 px-3 py-1 rounded-full border border-purple-500/20 inline-block mt-2">
                      Selected: {selectedFile.name}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={uploadMutation.isPending}
              className="w-full glass-btn-primary py-3 flex justify-center items-center"
            >
              {uploadMutation.isPending ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                'Upload & Parse Staging'
              )}
            </button>
          </form>
        </div>
      )}

      {/* SECTION 2: BATCH REVIEW BOARD */}
      {activeBatchId && batch && (
        <div className="space-y-6">
          {/* Staging Status Summary */}
          <div className="glass-card p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border-slate-800/80">
            <div>
              <span className="text-xs font-semibold text-purple-400 uppercase tracking-widest">Active Batch: {batch.id.substring(0, 8)}</span>
              <h3 className="text-xl font-bold text-white mt-1">Review Staging Row Data</h3>
              <div className="flex flex-wrap gap-4 text-xs text-slate-500 mt-2">
                <span>Group: <strong className="text-slate-400">{batch.group?.name}</strong></span>
                <span>Uploaded by: <strong className="text-slate-400">{batch.uploaded_by?.username}</strong></span>
                <span>File: <strong className="text-slate-400">{batch.filename}</strong></span>
                <span>Status: <strong className="text-purple-300 font-bold uppercase">{batch.status}</strong></span>
              </div>
            </div>

            <div className="flex space-x-3 w-full md:w-auto">
              <button
                onClick={handleDetect}
                disabled={detectMutation.isPending}
                className="w-1/2 md:w-auto glass-btn-secondary py-2 px-4 text-sm flex items-center justify-center space-x-2"
              >
                <Sparkles size={16} />
                <span>{detectMutation.isPending ? 'Detecting...' : 'Run Diagnostics'}</span>
              </button>
              <button
                onClick={handleCommit}
                disabled={commitMutation.isPending}
                className="w-1/2 md:w-auto glass-btn-primary py-2 px-4 text-sm flex items-center justify-center space-x-2"
              >
                <Play size={16} />
                <span>{commitMutation.isPending ? 'Committing...' : 'Commit Batch'}</span>
              </button>
              <button
                onClick={() => setActiveBatchId(null)}
                className="p-2 border border-slate-800 hover:bg-slate-800 rounded-xl text-slate-400 hover:text-slate-200 transition-colors"
                title="Cancel Import"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Staging Rows Listing */}
          <div className="glass-card overflow-hidden border border-slate-800/80">
            <div className="p-4 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between">
              <h4 className="font-bold text-sm text-slate-300 uppercase tracking-wider">CSV Rows Staging Area</h4>
              <span className="text-xs text-slate-500">Only rows with status <strong className="text-emerald-400">APPROVED</strong> will be migrated.</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/40 text-slate-400 border-b border-slate-900">
                  <tr>
                    <th className="p-3 font-semibold uppercase tracking-wider">#</th>
                    <th className="p-3 font-semibold uppercase tracking-wider">Type</th>
                    <th className="p-3 font-semibold uppercase tracking-wider">Date</th>
                    <th className="p-3 font-semibold uppercase tracking-wider">Description</th>
                    <th className="p-3 font-semibold uppercase tracking-wider">Payer(s)</th>
                    <th className="p-3 font-semibold uppercase tracking-wider">Splits</th>
                    <th className="p-3 font-semibold uppercase tracking-wider">Amount</th>
                    <th className="p-3 font-semibold uppercase tracking-wider text-center">Status</th>
                    <th className="p-3 font-semibold uppercase tracking-wider text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                  {batch.rows?.map((row) => {
                    const rowAnomalies = row.anomalies || [];
                    const hasUnresolved = rowAnomalies.some(a => !a.resolution);
                    
                    return (
                      <tr key={row.id} className={`hover:bg-slate-900/20 ${hasUnresolved ? 'bg-rose-500/5' : ''}`}>
                        <td className="p-3 font-semibold text-slate-300">
                          {row.raw_data?.split_type || row.raw_data?.['split type'] || row.raw_data?.type || 'equal'}
                        </td>
                        <td className="p-3 text-slate-500 whitespace-nowrap">
                          {(() => {
                            const dateVal = row.raw_data?.date || row.raw_data?.expense_date || '';
                            if (!dateVal) return 'Unknown';
                            const d = new Date(dateVal);
                            return isNaN(d.getTime()) ? dateVal : d.toLocaleDateString();
                          })()}
                        </td>
                        <td className="p-3 text-slate-300 max-w-[150px] truncate" title={row.raw_data?.description || row.raw_data?.expense || row.raw_data?.title || ''}>
                          {row.raw_data?.description || row.raw_data?.expense || row.raw_data?.title || ''}
                        </td>
                        <td className="p-3 text-slate-400 max-w-[120px] truncate" title={row.raw_data?.paid_by || row.raw_data?.['paid by'] || row.raw_data?.payer || ''}>
                          {row.raw_data?.paid_by || row.raw_data?.['paid by'] || row.raw_data?.payer || ''}
                        </td>
                        <td className="p-3 text-slate-400 max-w-[120px] truncate" title={row.raw_data?.participants || row.raw_data?.split_between || ''}>
                          {row.raw_data?.participants || row.raw_data?.split_between || ''}
                        </td>
                        <td className="p-3 font-bold text-slate-200">
                          {row.raw_data?.currency || 'INR'} {row.raw_data?.amount || row.raw_data?.value || '0.00'}
                        </td>
                        <td className="p-3 text-center">
                          <span className={`inline-flex px-2 py-0.5 rounded-full font-semibold text-[10px] ${
                            row.status === 'APPROVED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/15' :
                            row.status === 'SKIPPED' ? 'bg-slate-800 text-slate-400' :
                            'bg-amber-500/10 text-amber-400 border border-amber-500/15'
                          }`}>
                            {row.status}
                          </span>
                        </td>
                        <td className="p-3 text-right whitespace-nowrap">
                          {rowAnomalies.length > 0 ? (
                            <div className="flex items-center justify-end space-x-2">
                              {rowAnomalies.map((anom) => {
                                const isResolved = !!anom.resolution;
                                return (
                                  <button
                                    key={anom.id}
                                    onClick={() => !isResolved && openResolutionModal(row, anom)}
                                    className={`px-2 py-1 rounded text-[10px] font-bold flex items-center space-x-1 ${
                                      isResolved
                                        ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                                        : 'bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20'
                                    }`}
                                    title={anom.description}
                                    disabled={isResolved}
                                  >
                                    <AlertTriangle size={10} />
                                    <span>{anom.anomaly_type.substring(0, 7)} {isResolved ? '(Ok)' : ''}</span>
                                  </button>
                                );
                              })}
                            </div>
                          ) : (
                            <span className="text-slate-500 font-semibold text-[10px]">No issues</span>
                          )}
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

      {/* RESOLUTION MODAL */}
      {resolutionModalOpen && activeRow && activeAnomaly && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card w-full max-w-md p-6 relative">
            <button onClick={() => setResolutionModalOpen(false)} className="absolute top-4 right-4 text-slate-500 hover:text-slate-300">
              <X size={20} />
            </button>

            <div className="flex items-center space-x-2 text-rose-400 mb-2">
              <AlertTriangle size={20} />
              <h3 className="text-lg font-bold">Resolve Row Anomaly</h3>
            </div>
            <p className="text-xs text-slate-400 mb-6">
              Row #{activeRow.row_number}: <strong className="text-slate-300">{activeAnomaly.description}</strong>
            </p>

            <form onSubmit={handleResolve} className="space-y-4">
              {resError && (
                <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/25 p-3 rounded-xl flex items-center space-x-2">
                  <AlertCircle size={16} className="flex-shrink-0" />
                  <span>{resError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Choose Resolution Action</label>
                <select 
                  value={resolutionAction} 
                  onChange={e => setResolutionAction(e.target.value)} 
                  className="glass-input bg-slate-950"
                >
                  {(activeAnomaly.anomaly_type === 'MISSING_MEMBER' || activeAnomaly.anomaly_type === 'UNKNOWN_MEMBER') && (
                    <>
                      <option value="MAP_USER">MAP USER (Link to existing group user)</option>
                      <option value="CREATE_USER">CREATE USER (Add new user & member)</option>
                    </>
                  )}
                  {(activeAnomaly.anomaly_type === 'DUPLICATE_ROW' || activeAnomaly.anomaly_type === 'DUPLICATE_EXPENSE') && (
                    <>
                      <option value="SKIP">SKIP ROW (Exclude from import)</option>
                      <option value="KEEP">KEEP ROW (Import anyway)</option>
                    </>
                  )}
                  {activeAnomaly.anomaly_type !== 'MISSING_MEMBER' && activeAnomaly.anomaly_type !== 'UNKNOWN_MEMBER' && activeAnomaly.anomaly_type !== 'DUPLICATE_ROW' && activeAnomaly.anomaly_type !== 'DUPLICATE_EXPENSE' && (
                    <>
                      <option value="KEEP">FORCE APPROVE (Import anyway)</option>
                      <option value="SKIP">SKIP ROW (Ignore this row)</option>
                    </>
                  )}
                </select>
              </div>

              {/* MAP USER FIELDS */}
              {resolutionAction === 'MAP_USER' && (
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase mb-2">Map to Group Member</label>
                  <select 
                    value={mappedUserId} 
                    onChange={e => setMappedUserId(e.target.value)} 
                    className="glass-input bg-slate-950"
                    required
                  >
                    <option value="">-- Select Member --</option>
                    {batch.group?.memberships?.map(m => (
                      <option key={m.user.id} value={m.user.id}>{m.user.username} ({m.user.email})</option>
                    ))}
                  </select>
                </div>
              )}

              {/* CREATE USER FIELDS */}
              {resolutionAction === 'CREATE_USER' && (
                <div className="space-y-3 pt-2 border-t border-slate-900">
                  <p className="text-[10px] text-slate-500 leading-normal">
                    This will create a new user profile and join them to this group. Their membership join-date will be set to the transaction date ({(() => {
                      const dateVal = activeRow.raw_data?.date || activeRow.raw_data?.expense_date || '';
                      if (!dateVal) return 'Unknown';
                      const d = new Date(dateVal);
                      return isNaN(d.getTime()) ? dateVal : d.toLocaleDateString();
                    })()}) to ensure integrity.
                  </p>
                  <div>
                    <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Username</label>
                    <input type="text" placeholder="e.g. aishak" value={newUsername} onChange={e => setNewUsername(e.target.value)} className="glass-input py-1.5 px-3" required />
                  </div>
                  <div>
                    <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Full Name</label>
                    <input type="text" placeholder="e.g. Aisha Kapoor" value={newFullName} onChange={e => setNewFullName(e.target.value)} className="glass-input py-1.5 px-3" required />
                  </div>
                  <div>
                    <label className="block text-[10px] font-semibold text-slate-400 uppercase mb-1">Email</label>
                    <input type="email" placeholder="e.g. aisha@gmail.com" value={newEmail} onChange={e => setNewEmail(e.target.value)} className="glass-input py-1.5 px-3" required />
                  </div>
                </div>
              )}

              <div className="flex space-x-3 pt-4 border-t border-slate-900/60">
                <button type="button" onClick={() => setResolutionModalOpen(false)} className="w-1/2 glass-btn-secondary">Cancel</button>
                <button type="submit" disabled={resolveAnomalyMutation.isPending} className="w-1/2 glass-btn-primary flex justify-center">
                  {resolveAnomalyMutation.isPending ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : 'Apply Resolution'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CSVImport;
