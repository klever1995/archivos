import React, { createContext, useContext, useRef, useEffect, useState } from 'react';

// Contexto para mantener la conexión del Websocket
const WebSocketContext = createContext(null);

//Acceso al contexto Websocket
export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket debe ser usado dentro de WebSocketProvider');
  }
  return context;
};

//Conexión persistente y notificaciones en tiempo real
export const WebSocketProvider = ({ children, idEmpresa = 1 }) => {
  const wsRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const messageHandlersRef = useRef(new Set());

//Reconexión automática
  const connectWebSocket = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const ws = new WebSocket(`ws://localhost:8000/ws/${idEmpresa}`);
    
    ws.onopen = () => {
      console.log('WebSocket conectado globalmente');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        messageHandlersRef.current.forEach(handler => {
          try {
            handler(message);
          } catch (error) {
            console.error('Error en handler de WebSocket:', error);
          }
        });
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onclose = () => {
      console.log('WebSocket desconectado, reconectando...');
      setIsConnected(false);
      setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      ws.close();
    };

    wsRef.current = ws;
  };

// Registro de handlers para procesar mensajes entrantes
  const addMessageHandler = (handler) => {
    messageHandlersRef.current.add(handler);
    return () => messageHandlersRef.current.delete(handler);
  };

// Envía mensajes a través del WebSocket
  const sendMessage = (message) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  };

//Inicia la conexión
  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [idEmpresa]);

  const value = {
    isConnected,
    sendMessage,
    addMessageHandler,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};
