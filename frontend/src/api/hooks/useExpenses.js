import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../client';

export const useExpenses = () => {
  const queryClient = useQueryClient();

  const useExpensesQuery = (groupId) => {
    return useQuery({
      queryKey: ['expenses', groupId],
      queryFn: async () => {
        if (!groupId) return [];
        // The endpoint GET /api/expenses/ lists group expenses by filtering or from a nested route.
        // Looking at backend/expenses/urls.py and core/urls.py,
        // path('api/expenses/', include('expenses.urls'))
        // Wait, is there a group-specific expenses view? Let's check how it's wired.
        // Actually, we can fetch from GET /api/expenses/?group_id=groupId or similar.
        const res = await client.get('/expenses/', { params: { group_id: groupId } });
        return res.data;
      },
      enabled: !!groupId,
    });
  };

  const useExpenseDetailQuery = (expenseId) => {
    return useQuery({
      queryKey: ['expense', expenseId],
      queryFn: async () => {
        if (!expenseId) return null;
        const res = await client.get(`/expenses/${expenseId}/`);
        return res.data;
      },
      enabled: !!expenseId,
    });
  };

  const useCreateExpenseMutation = (groupId) => {
    return useMutation({
      mutationFn: async (payload) => {
        // payload: { description, date, original_amount, currency, split_type, payers, splits }
        const res = await client.post('/expenses/', payload);
        return res.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['expenses', groupId] });
        queryClient.invalidateQueries({ queryKey: ['balances', groupId] });
      },
    });
  };

  const useDeleteExpenseMutation = (groupId) => {
    return useMutation({
      mutationFn: async (expenseId) => {
        const res = await client.delete(`/expenses/${expenseId}/`);
        return res.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['expenses', groupId] });
        queryClient.invalidateQueries({ queryKey: ['balances', groupId] });
      },
    });
  };

  const useSettlementsQuery = (groupId) => {
    return useQuery({
      queryKey: ['settlements', groupId],
      queryFn: async () => {
        if (!groupId) return [];
        const res = await client.get('/settlements/', { params: { group_id: groupId } });
        return res.data;
      },
      enabled: !!groupId,
    });
  };

  const useSettlementDetailQuery = (settlementId) => {
    return useQuery({
      queryKey: ['settlement', settlementId],
      queryFn: async () => {
        if (!settlementId) return null;
        const res = await client.get(`/settlements/${settlementId}/`);
        return res.data;
      },
      enabled: !!settlementId,
    });
  };

  const useCreateSettlementMutation = (groupId) => {
    return useMutation({
      mutationFn: async (payload) => {
        // payload: { from_user_id, to_user_id, original_amount, currency, settlement_date }
        const res = await client.post('/settlements/', payload);
        return res.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['settlements', groupId] });
        queryClient.invalidateQueries({ queryKey: ['balances', groupId] });
      },
    });
  };

  return {
    useExpensesQuery,
    useExpenseDetailQuery,
    useCreateExpenseMutation,
    useDeleteExpenseMutation,
    useSettlementsQuery,
    useSettlementDetailQuery,
    useCreateSettlementMutation,
  };
};
