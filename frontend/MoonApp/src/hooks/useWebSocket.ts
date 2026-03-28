import { useState, useRef, useCallback, useEffect } from 'react';

type ConnectionState = 'DISCONNECTED' | 'CONNECTING' | 'CONNECTED';

interface UseWebSocketOptions {
  url: string;
  maxRetries?: number;
  onMessage?: (data: unknown) => void;
  onError?: (error: string) => void;
}

interface UseWebSocketReturn {
  connectionState: ConnectionState;
  send: (data: unknown) => void;
  connect: () => void;
  disconnect: () => void;
}

const MAX_RETRIES_DEFAULT = 3;

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const { url, maxRetries = MAX_RETRIES_DEFAULT, onMessage, onError } = options;
  const [connectionState, setConnectionState] = useState<ConnectionState>('DISCONNECTED');
  const wsRef = useRef<WebSocket | null>(null);
  const retryCount = useRef(0);
  const intentionalClose = useRef(false);

  const disconnect = useCallback(() => {
    intentionalClose.current = true;
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnectionState('DISCONNECTED');
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    intentionalClose.current = false;
    retryCount.current = 0;
    setConnectionState('CONNECTING');

    const createConnection = () => {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        retryCount.current = 0;
        setConnectionState('CONNECTED');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage?.(data);
        } catch {
          onMessage?.(event.data);
        }
      };

      ws.onerror = () => {
        onError?.('WebSocket 연결 오류');
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (!intentionalClose.current && retryCount.current < maxRetries) {
          retryCount.current += 1;
          setConnectionState('CONNECTING');
          setTimeout(createConnection, 1000 * retryCount.current);
        } else {
          setConnectionState('DISCONNECTED');
          if (!intentionalClose.current) {
            onError?.('WebSocket 재연결 실패');
          }
        }
      };

      wsRef.current = ws;
    };

    createConnection();
  }, [url, maxRetries, onMessage, onError]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    return () => {
      intentionalClose.current = true;
      wsRef.current?.close();
    };
  }, []);

  return { connectionState, send, connect, disconnect };
}
