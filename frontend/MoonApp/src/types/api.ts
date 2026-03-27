export interface ApiResponse<T> {
  status: 'SUCCESS' | 'ERROR';
  data?: T;
  error?: { code: string; message: string; timestamp: string };
}
