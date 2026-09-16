import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  acknowledgeIncident,
  evaluateOperations,
  getOperationsHealth,
  getResolvedIncidents,
} from '../api/operations'

export function useOperationsCenter() {
  const client = useQueryClient()
  const refresh = () => client.invalidateQueries({ queryKey: ['operations'] })
  return {
    health: useQuery({
      queryKey: ['operations', 'health'],
      queryFn: ({ signal }) => getOperationsHealth(signal),
      refetchInterval: 60_000,
    }),
    resolved: useQuery({
      queryKey: ['operations', 'incidents', 'resolved'],
      queryFn: ({ signal }) => getResolvedIncidents(signal),
    }),
    acknowledge: useMutation({
      mutationFn: ({ id, reason }: { id: string; reason: string }) =>
        acknowledgeIncident(id, reason),
      onSuccess: refresh,
    }),
    evaluate: useMutation({
      mutationFn: evaluateOperations,
      onSuccess: refresh,
    }),
  }
}
