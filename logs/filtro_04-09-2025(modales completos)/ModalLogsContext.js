import React, { createContext, useContext, useState } from 'react';

const ModalLogsCacheContext = createContext();

export const ModalLogsCacheProvider = ({ children }) => {
  const [logsCache, setLogsCache] = useState({});

  const agregarAlCache = (clave, datos) => {
    setLogsCache(prev => ({
      ...prev,
      [clave]: {
        datos,
        timestamp: Date.now()
      }
    }));
  };

  const obtenerDelCache = (clave) => {
    const cached = logsCache[clave];
    // Cache válido por 5 minutos
    if (cached && (Date.now() - cached.timestamp < 300000)) {
      return cached.datos;
    }
    return null;
  };

  const value = {
    logsCache,
    agregarAlCache,
    obtenerDelCache
  };

  return (
    <ModalLogsCacheContext.Provider value={value}>
      {children}
    </ModalLogsCacheContext.Provider>
  );
};

export const useModalLogsCache = () => {
  const context = useContext(ModalLogsCacheContext);
  if (!context) {
    throw new Error('useModalLogsCache debe usarse dentro de ModalLogsCacheProvider');
  }
  return context;
};
