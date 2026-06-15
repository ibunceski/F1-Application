import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query';
import { showToast } from '../components/ui/toastStore';
import { ApiError } from './api';

function handleQueryError(error: Error) {
  if (import.meta.env.DEV) {
    console.error('[query-error]', error);
  }
  if (error instanceof ApiError && error.status === 0) {
    showToast('Network error. Check that the backend is running.', 'error');
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: handleQueryError,
  }),
  mutationCache: new MutationCache({
    onError: handleQueryError,
  }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});
