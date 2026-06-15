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
  Trash,
  X
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

  const [autoResolving, setAutoResolving] = useState(false);
  const [autoResolveMessage, setAutoResolveMessage] = useState('');

  const downloadUpdatedCSV = () => {
    if (!batch?.rows) return;
    const headers = ["RowNumber", "SplitType", "Date", "Description", "PaidBy", "Participants", "Amount", "Currency", "Status"];
    const csvRows = [headers.join(",")];
    batch.rows.forEach(row => {
      const rowNum = row.row_number;
      const type = row.raw_data?.split_type || row.raw_data?.type || 'equal';
      const dateVal = row.raw_data?.date || row.raw_data?.expense_date || '';
      const desc = `"${(row.raw_data?.description || '').replace(/"/g, '""')}"`;
      const payer = `"${(row.raw_data?.paid_by || '').replace(/"/g, '""')}"`;
      const parts = `"${(row.raw_data?.participants || '').replace(/"/g, '""')}"`;
      const amount = row.raw_data?.amount || row.raw_data?.value || '0.00';
      const curr = row.raw_data?.currency || 'INR';
      const status = row.status;
      csvRows.push([rowNum, type, dateVal, desc, payer, parts, amount, curr, status].join(","));
    });
    
    const csvContent = "data:text/csv;charset=utf-8," + csvRows.join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `updated_staging_${batch.id.substring(0, 8)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const downloadErrorReportPDF = () => {
    if (!batch) return;
    const printWindow = window.open('', '_blank');
    const anomaliesList = [];
    batch.rows?.forEach(row => {
      row.anomalies?.forEach(anom => {
        anomaliesList.push({
          rowNumber: row.row_number,
          type: anom.anomaly_type,
          severity: anom.severity,
          description: anom.description,
          resolved: anom.is_resolved,
          resolutionAction: anom.resolution?.action_taken || (anom.is_resolved ? 'Auto-Resolved' : '')
        });
      });
    });
    
    const html = `
      <html>
        <head>
          <title>CSV Import Error Report - Batch ${batch.id.substring(0, 8)}</title>
          <style>
            body { font-family: 'Inter', sans-serif; color: #1e293b; padding: 40px; margin: 0; }
            h1 { font-size: 24px; font-weight: 800; color: #0f172a; margin-bottom: 5px; }
            p { font-size: 14px; color: #64748b; margin-top: 0; }
            .meta-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 30px 0; padding: 20px; background: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0; }
            .meta-item { font-size: 12px; }
            .meta-item strong { color: #334155; }
            .summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-bottom: 40px; }
            .summary-card { padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; text-align: center; }
            .summary-card.error { border-color: #fca5a5; background: #fef2f2; }
            .summary-val { font-size: 20px; font-weight: 700; color: #0f172a; }
            .summary-label { font-size: 10px; text-transform: uppercase; tracking-wider; color: #64748b; margin-top: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th { background: #f1f5f9; font-weight: 600; text-align: left; padding: 12px; font-size: 11px; text-transform: uppercase; color: #475569; border-bottom: 2px solid #cbd5e1; }
            td { padding: 12px; font-size: 12px; border-bottom: 1px solid #e2e8f0; }
            .badge { display: inline-block; padding: 2px 6px; font-size: 9px; font-weight: 700; border-radius: 4px; text-transform: uppercase; }
            .badge.error { background: #fee2e2; color: #ef4444; }
            .badge.warning { background: #fef3c7; color: #d97706; }
            .badge.resolved { background: #ecfdf5; color: #10b981; }
          </style>
        </head>
        <body>
          <h1>CSV Import Diagnostics Report</h1>
          <p>Audit trail and detected anomalies for batch file: ${batch.filename || 'Unknown'}</p>
          
          <div class="meta-grid">
             <div class="meta-item"><strong>Batch ID:</strong> ${batch.id}</div>
             <div class="meta-item"><strong>Group Name:</strong> ${batch.group_name || 'Unknown'}</div>
             <div class="meta-item"><strong>Uploaded By:</strong> ${batch.uploaded_by_username || 'Unknown'}</div>
             <div class="meta-item"><strong>Uploaded At:</strong> ${new Date(batch.uploaded_at).toLocaleString()}</div>
          </div>
          
          <div class="summary-grid">
            <div class="summary-card">
              <div class="summary-val">${batch.total_rows}</div>
              <div class="summary-label">Total Rows</div>
            </div>
            <div class="summary-card">
              <div class="summary-val">${batch.rows?.filter(r => r.status === 'APPROVED').length || 0}</div>
              <div class="summary-label">Approved Rows</div>
            </div>
            <div class="summary-card">
              <div class="summary-val">${batch.rows?.filter(r => r.status === 'FLAGGED').length || 0}</div>
              <div class="summary-label">Flagged Rows</div>
            </div>
            <div class="summary-card">
              <div class="summary-val">${batch.rows?.filter(r => r.status === 'REJECTED').length || 0}</div>
              <div class="summary-label">Rejected Rows</div>
            </div>
            <div class="summary-card error">
              <div class="summary-val">${anomaliesList.filter(a => !a.resolved).length}</div>
              <div class="summary-label">Unresolved Issues</div>
            </div>
          </div>
          
          <h2>Anomaly Details</h2>
          <table>
            <thead>
              <tr>
                <th style="width: 8%">Row</th>
                <th style="width: 20%">Anomaly Type</th>
                <th style="width: 12%">Severity</th>
                <th style="width: 45%">Description</th>
                <th style="width: 15%">Status</th>
              </tr>
            </thead>
            <tbody>
              ${anomaliesList.map(a => `
                <tr>
                  <td>#${a.rowNumber}</td>
                  <td><strong>${a.type}</strong></td>
                  <td>
                    <span class="badge ${a.severity === 'ERROR' ? 'error' : 'warning'}">${a.severity}</span>
                  </td>
                  <td>${a.description}</td>
                  <td>
                    <span class="badge ${a.resolved ? 'resolved' : 'error'}">
                      ${a.resolved ? `Resolved (${a.resolutionAction})` : 'Unresolved'}
                    </span>
                  </td>
                </tr>
              `).join('')}
              ${anomaliesList.length === 0 ? '<tr><td colspan="5" style="text-align: center; color: #64748b;">No anomalies detected in this batch.</td></tr>' : ''}
            </tbody>
          </table>
          
          <script>
            window.onload = function() {
              window.print();
              setTimeout(function() { window.close(); }, 500);
            };
          </script>
        </body>
      </html>
    `;
    
    printWindow.document.write(html);
    printWindow.document.close();
  };

  const handleAutoResolve = async () => {
    if (!batch?.rows) return;
    
    const currentGroup = groups?.find(g => g.id === batch.group);
    const groupMembers = currentGroup?.memberships?.map(m => m.user) || [];
    
    setAutoResolving(true);
    setAutoResolveMessage('Analyzing and resolving staging anomalies...');
    
    let resolvedCount = 0;
    
    try {
      const unresolvedAnomalies = [];
      batch.rows.forEach(row => {
        row.anomalies?.forEach(anom => {
          if (!anom.is_resolved) {
            unresolvedAnomalies.push({ row, anom });
          }
        });
      });
      
      if (unresolvedAnomalies.length === 0) {
        setAutoResolveMessage('All anomalies are already resolved! Ready to commit.');
        setTimeout(() => setAutoResolveMessage(''), 3000);
        setAutoResolving(false);
        return;
      }
      
      for (const { row, anom } of unresolvedAnomalies) {
        let action = 'KEEP_BOTH';
        let details = {};
        
        if (anom.anomaly_type === 'UNKNOWN_MEMBER' || anom.anomaly_type === 'MISSING_MEMBER') {
          const missingName = anom.metadata?.missing_member || '';
          const possible = anom.metadata?.possible_matches || [];
          
          let mappedUser = null;
          if (possible.length > 0) {
            mappedUser = groupMembers.find(member => member.email === possible[0]);
          }
          
          if (mappedUser) {
            action = 'MAP_USER';
            details = { user_id: mappedUser.id };
          } else {
            action = 'CREATE_USER';
            const username = missingName.toLowerCase().replace(/[^a-z0-9]/g, '') || 'user';
            details = {
              username: `${username}_auto`,
              full_name: missingName,
              email: `${username}_auto@splitsmart.com`
            };
          }
        } else if (anom.anomaly_type === 'DUPLICATE_EXPENSE' || anom.anomaly_type === 'CONFLICTING_DUPLICATE') {
          action = 'IGNORE';
        }
        
        await resolveAnomalyMutation.mutateAsync({
          rowId: row.id,
          payload: {
            anomaly_id: anom.id,
            action_taken: action,
            notes: 'Auto-resolved by Splitsmart Diagnostic engine.',
            resolution_details: details
          }
        });
        resolvedCount++;
      }
      
      setAutoResolveMessage(`Successfully corrected ${resolvedCount} anomalies! Please recheck and verify.`);
      setTimeout(() => setAutoResolveMessage(''), 5000);
      refetchBatch();
    } catch (err) {
      console.error(err);
      setAutoResolveMessage('Failed during auto-resolution.');
    } finally {
      setAutoResolving(false);
    }
  };

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
            <h3 className="text-lg font-bold">Import Summary Report</h3>
          </div>
          <p className="text-sm text-slate-300 mb-6">
            The CSV batch has been successfully committed. Below is the transaction migration summary:
          </p>
          
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-900">
              <span className="text-[10px] text-slate-500 font-semibold uppercase block">Total Rows</span>
              <span className="text-2xl font-extrabold text-white">{commitSummary.rows_total || 0}</span>
            </div>
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-900">
              <span className="text-[10px] text-slate-500 font-semibold uppercase block">Approved Rows</span>
              <span className="text-2xl font-extrabold text-white">{commitSummary.rows_imported || 0}</span>
            </div>
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-900">
              <span className="text-[10px] text-slate-500 font-semibold uppercase block">Rejected Rows</span>
              <span className="text-2xl font-extrabold text-white">{commitSummary.rows_rejected || 0}</span>
            </div>
            <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-900">
              <span className="text-[10px] text-slate-500 font-semibold uppercase block">Transactions Imported</span>
              <span className="text-2xl font-extrabold text-emerald-400">{commitSummary.rows_imported || 0}</span>
            </div>
          </div>

          <div className="bg-slate-950/40 p-4 rounded-xl border border-slate-900/60 space-y-3">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">CSV Cleaning Report</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-300">
              <div className="flex justify-between p-2 bg-slate-900/40 rounded-lg">
                <span>Duplicate Expenses Removed:</span>
                <strong className="text-slate-100">{commitSummary.duplicates_removed || 0}</strong>
              </div>
              <div className="flex justify-between p-2 bg-slate-900/40 rounded-lg">
                <span>Negative Amounts Excluded:</span>
                <strong className="text-slate-100">{commitSummary.negative_amount_removed || 0}</strong>
              </div>
              <div className="flex justify-between p-2 bg-slate-900/40 rounded-lg">
                <span>Zero Amounts Excluded:</span>
                <strong className="text-slate-100">{commitSummary.zero_amount_removed || 0}</strong>
              </div>
              <div className="flex justify-between p-2 bg-slate-900/40 rounded-lg">
                <span>Invalid Splits Excluded:</span>
                <strong className="text-slate-100">{commitSummary.invalid_split_removed || 0}</strong>
              </div>
              <div className="flex justify-between p-2 bg-slate-900/40 rounded-lg">
                <span>Unknown Members Resolved:</span>
                <strong className="text-purple-300">{commitSummary.unknown_members_resolved || 0}</strong>
              </div>
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
          <div className="glass-card p-6 border border-slate-800/80 space-y-4">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
              <div>
                <span className="text-xs font-semibold text-purple-400 uppercase tracking-widest">Active Batch: {batch.id.substring(0, 8)}</span>
                <h3 className="text-xl font-bold text-white mt-1">Review Staging Row Data</h3>
                <div className="flex flex-wrap gap-4 text-xs text-slate-500 mt-2">
                  <span>Group: <strong className="text-slate-400">{batch.group_name || 'Unknown'}</strong></span>
                  <span>Uploaded by: <strong className="text-slate-400">{batch.uploaded_by_username || 'Unknown'}</strong></span>
                  <span>File: <strong className="text-slate-400">{batch.filename || 'Unknown'}</strong></span>
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

            {/* Diagnostic & Export Actions Toolbar */}
            <div className="pt-4 border-t border-slate-800/60 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={handleAutoResolve}
                  disabled={autoResolving}
                  className="glass-btn-primary bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 py-1.5 px-4 text-xs flex items-center space-x-2"
                  title="Correct unknown members and duplicate items automatically"
                >
                  <Sparkles size={14} className={autoResolving ? "animate-spin" : ""} />
                  <span>{autoResolving ? 'Auto-Correcting...' : 'Auto-Resolve & Correct'}</span>
                </button>

                <button
                  onClick={downloadUpdatedCSV}
                  className="glass-btn-secondary py-1.5 px-4 text-xs flex items-center space-x-2"
                  title="Download CSV representing current staging details"
                >
                  <FileText size={14} />
                  <span>Export Corrected CSV</span>
                </button>

                <button
                  onClick={downloadErrorReportPDF}
                  className="glass-btn-secondary py-1.5 px-4 text-xs flex items-center space-x-2 text-rose-400 border-rose-500/20 hover:bg-rose-500/5"
                  title="Generate print-friendly PDF report of batch errors"
                >
                  <AlertCircle size={14} />
                  <span>PDF Diagnostics Report</span>
                </button>
              </div>

              {autoResolveMessage && (
                <span className="text-xs text-purple-300 font-semibold animate-pulse">{autoResolveMessage}</span>
              )}
            </div>
          </div>

          {batch.anomalies?.filter(a => !a.row).map(anom => (
            <div key={anom.id} className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl flex items-start space-x-3 text-sm">
              <AlertCircle size={20} className="mt-0.5 flex-shrink-0 text-rose-400" />
              <div>
                <h4 className="font-bold uppercase tracking-wider text-xs">Batch Anomaly: {anom.anomaly_type}</h4>
                <p className="mt-1 text-slate-300">{anom.description}</p>
              </div>
            </div>
          ))}

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
                    const hasUnresolved = rowAnomalies.some(a => !a.is_resolved);
                    
                    return (
                      <tr key={row.id} className={`hover:bg-slate-900/20 ${hasUnresolved ? 'bg-rose-500/5' : ''}`}>
                        <td className="p-3 font-semibold text-slate-500">
                          {row.row_number}
                        </td>
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
                            row.status === 'REJECTED' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/15' :
                            'bg-amber-500/10 text-amber-400 border border-amber-500/15'
                          }`}>
                            {row.status}
                          </span>
                        </td>
                        <td className="p-3 text-right whitespace-nowrap">
                          {rowAnomalies.length > 0 ? (
                            <div className="flex items-center justify-end space-x-2">
                              {rowAnomalies.map((anom) => {
                                const isResolved = anom.is_resolved;
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
