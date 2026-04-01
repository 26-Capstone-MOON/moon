const ERROR_MESSAGES: Record<string, string> = {
  ROUTE_NOT_FOUND: '경로를 찾을 수 없어요',
  PIPELINE_SERVICE_ERROR: '경로 생성 중 문제가 생겼어요',
  SERVICE_TIMEOUT: '서버 응답이 오래 걸려요',
  INVALID_REQUEST: '잘못된 요청이에요',
  INTERNAL_SERVER_ERROR: '서버에 문제가 생겼어요',
};

export function getErrorMessage(code: string): string {
  return ERROR_MESSAGES[code] ?? '알 수 없는 오류가 발생했어요';
}

export function extractErrorMessage(err: unknown): string {
  if (err instanceof Error && err.message === 'Network request failed') {
    return '인터넷 연결을 확인해주세요';
  }

  const response = (err as any)?.response?.data ?? (err as any)?.data;
  if (response?.error?.code) {
    return getErrorMessage(response.error.code);
  }

  if (err instanceof Error) {
    return err.message;
  }

  return '알 수 없는 오류가 발생했어요';
}
