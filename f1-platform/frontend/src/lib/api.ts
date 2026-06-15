import axios, { AxiosError, type AxiosInstance } from 'axios';

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  timeout: 15000,
});

apiClient.interceptors.request.use((config) => {
  if (import.meta.env.DEV) {
    console.info('[api]', config.method?.toUpperCase(), config.url);
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (!error.response) {
      throw new ApiError('Network error', 0);
    }
    if (error.response.status === 404) {
      throw new ApiError('Not found', 404);
    }
    if (error.response.status >= 500) {
      throw new ApiError('Server error', 500);
    }
    const payload = error.response.data as { detail?: string; message?: string } | undefined;
    throw new ApiError(payload?.message || payload?.detail || error.message, error.response.status);
  },
);
