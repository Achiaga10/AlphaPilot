import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  acknowledgeIncident,
  evaluateOperations,
  getNotificationPreferences,
  getNotifications,
  getNotificationStatus,
  getOperationsHealth,
  getResolvedIncidents,
  retryNotification,
  sendTestNotification,
  updateNotificationPreferences,
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
    notificationStatus: useQuery({
      queryKey: ['operations', 'notifications', 'status'],
      queryFn: ({ signal }) => getNotificationStatus(signal),
      refetchInterval: 60_000,
    }),
    notifications: useQuery({
      queryKey: ['operations', 'notifications', 'history'],
      queryFn: ({ signal }) => getNotifications(signal),
    }),
    notificationPreferences: useQuery({
      queryKey: ['operations', 'notifications', 'preferences'],
      queryFn: ({ signal }) => getNotificationPreferences(signal),
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
    saveNotificationPreferences: useMutation({
      mutationFn: updateNotificationPreferences,
      onSuccess: refresh,
    }),
    sendTestNotification: useMutation({
      mutationFn: sendTestNotification,
      onSuccess: refresh,
    }),
    retryNotification: useMutation({
      mutationFn: retryNotification,
      onSuccess: refresh,
    }),
  }
}
