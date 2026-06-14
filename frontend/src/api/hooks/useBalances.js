import { useQuery } from '@tanstack/react-query';
import client from '../client';

export const useBalances = () => {
  const useBalancesQuery = (groupId) => {
    return useQuery({
      queryKey: ['balances', groupId],
      queryFn: async () => {
        if (!groupId) return [];
        const res = await client.get(`/groups/${groupId}/balances/`);
        return res.data;
      },
      enabled: !!groupId,
    });
  };

  const useBalanceExplanationQuery = (groupId, fromUserId, toUserId) => {
    return useQuery({
      queryKey: ['balance-explanation', groupId, fromUserId, toUserId],
      queryFn: async () => {
        if (!groupId || !fromUserId || !toUserId) return null;
        const res = await client.get(`/groups/${groupId}/balances/explanation/`, {
          params: {
            from_user_id: fromUserId,
            to_user_id: toUserId,
          },
        });
        return res.data;
      },
      enabled: !!groupId && !!fromUserId && !!toUserId,
    });
  };

  return {
    useBalancesQuery,
    useBalanceExplanationQuery,
  };
};
