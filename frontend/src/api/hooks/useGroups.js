import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../client';

export const useGroups = () => {
  const queryClient = useQueryClient();

  const useGroupsQuery = () => {
    return useQuery({
      queryKey: ['groups'],
      queryFn: async () => {
        const res = await client.get('/groups/');
        return res.data;
      },
    });
  };

  const useGroupDetailQuery = (groupId) => {
    return useQuery({
      queryKey: ['group', groupId],
      queryFn: async () => {
        if (!groupId) return null;
        const res = await client.get(`/groups/${groupId}/`);
        return res.data;
      },
      enabled: !!groupId,
    });
  };

  const useCreateGroupMutation = () => {
    return useMutation({
      mutationFn: async (payload) => {
        // payload: { name, base_currency }
        const res = await client.post('/groups/', payload);
        return res.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['groups'] });
      },
    });
  };

  const useAddMemberMutation = (groupId) => {
    return useMutation({
      mutationFn: async (payload) => {
        // payload: { email, joined_at }
        const res = await client.post(`/groups/${groupId}/members/`, payload);
        return res.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['group', groupId] });
      },
    });
  };

  const useUpdateMemberMutation = (groupId) => {
    return useMutation({
      mutationFn: async ({ membershipId, payload }) => {
        // payload: { role, left_at }
        const res = await client.put(`/groups/${groupId}/members/${membershipId}/`, payload);
        return res.data;
      },
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['group', groupId] });
      },
    });
  };

  return {
    useGroupsQuery,
    useGroupDetailQuery,
    useCreateGroupMutation,
    useAddMemberMutation,
    useUpdateMemberMutation,
  };
};
