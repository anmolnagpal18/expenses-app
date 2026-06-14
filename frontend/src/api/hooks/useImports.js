import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../client';

export const useImports = () => {
  const queryClient = useQueryClient();

  const useUploadMutation = () => {
    return useMutation({
      mutationFn: async ({ file, groupId }) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('group_id', groupId);

        const res = await client.post('/imports/upload/', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });
        return res.data;
      },
    });
  };

  const useDetectMutation = () => {
    return useMutation({
      mutationFn: async (batchId) => {
        const res = await client.post(`/imports/${batchId}/detect/`);
        return res.data;
      },
      onSuccess: (data, batchId) => {
        queryClient.invalidateQueries({ queryKey: ['import-batch', batchId] });
      },
    });
  };

  const useBatchDetailQuery = (batchId) => {
    return useQuery({
      queryKey: ['import-batch', batchId],
      queryFn: async () => {
        if (!batchId) return null;
        const res = await client.get(`/imports/batches/${batchId}/`);
        return res.data;
      },
      enabled: !!batchId,
    });
  };

  const useResolveAnomalyMutation = (batchId) => {
    return useMutation({
      mutationFn: async ({ rowId, payload }) => {
        // payload: { anomaly_id, action_taken, notes, resolution_details }
        const res = await client.post(`/imports/rows/${rowId}/resolve/`, payload);
        return res.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['import-batch', batchId] });
      },
    });
  };

  const useCommitMutation = () => {
    return useMutation({
      mutationFn: async (batchId) => {
        const res = await client.post(`/imports/batches/${batchId}/commit/`);
        return res.data;
      },
      onSuccess: (data, batchId) => {
        queryClient.invalidateQueries({ queryKey: ['import-batch', batchId] });
        // Also invalidate groups and expenses since they will have new data
        queryClient.invalidateQueries({ queryKey: ['groups'] });
        queryClient.invalidateQueries({ queryKey: ['expenses'] });
        queryClient.invalidateQueries({ queryKey: ['balances'] });
      },
    });
  };

  return {
    useUploadMutation,
    useDetectMutation,
    useBatchDetailQuery,
    useResolveAnomalyMutation,
    useCommitMutation,
  };
};
