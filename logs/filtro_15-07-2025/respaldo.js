import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import './estilosConfig.css';

const MultiLogProcessor = () => {
  const [servidores, setServidores] = useState([]);
  const [error, setError] = useState(null);
  const [nuevaRuta, setNuevaRuta] = useState('');
  const [nuevoIntervalo, setNuevoIntervalo] = useState(5);
  const [procesosActivos, setProcesosActivos] = useState([]);
  const wsRef = useRef(null);
  const navigate = useNavigate();
  const timersRef = useRef({});
  

  const connectWebSocket = useCallback(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/1');
    
    ws.onopen = () => {
      console.log('WebSocket conectado');
    };
    
    ws.onmessage = (event) => {
      if (event.data.startsWith('proceso_completado:')) {
        const idProceso = event.data.split(':')[1];
        console.log('Proceso completado:', idProceso);
        
        setServidores(prev => prev.map(servidor => {
          if (servidor.activo) {
            if (timersRef.current[servidor.idServidor]) {
              clearTimeout(timersRef.current[servidor.idServidor]);
            }
            
            timersRef.current[servidor.idServidor] = setTimeout(() => {
              procesarServidor(servidor.idServidor, servidor.ruta, servidor.intervalo);
            }, servidor.intervalo * 60 * 1000);
            
            return servidor;
          }
          return servidor;
        }));
      }
    };
    
    ws.onclose = () => {
      console.log('WebSocket desconectado, reconectando...');
      setTimeout(connectWebSocket, 5000);
    };
    
    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
      ws.close();
    };
    
    wsRef.current = ws;
  }, []);

  const cargarDatosIniciales = async () => {
    try {
      const responseServidores = await fetch('http://localhost:8000/api/servidores/?idEmpresa=1');
      if (!responseServidores.ok) throw new Error('Error al cargar servidores');
      const dataServidores = await responseServidores.json();

      const responseProcesos = await fetch('http://localhost:8000/proceso-config/');
      const dataProcesos = await responseProcesos.json();

      setServidores(dataServidores.resultados.map(s => ({
        idServidor: s.id_servidor,
        ruta: s.ruta,
        intervalo: nuevoIntervalo,
        activo: dataProcesos.activo && dataProcesos.archivo === s.ruta
      })));

    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    connectWebSocket();
    cargarDatosIniciales();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      Object.values(timersRef.current).forEach(timer => clearTimeout(timer));
    };
  }, [connectWebSocket]);

  const procesarServidor = async (idServidor, ruta, intervaloMinutos = 5) => {
    try {
      setServidores(prev => prev.map(s => 
        s.idServidor === idServidor ? { ...s, activo: true } : s
      ));

      const formData = new FormData();
      formData.append('nombre_archivo', ruta);
      formData.append('idServidor', idServidor);
      formData.append('intervalo_minutos', intervaloMinutos);

      const response = await fetch('http://localhost:8000/procesar-log/', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Error desconocido');
      }

      return await response.json();
    } catch (err) {
      console.error(`Error procesando ${ruta}:`, err);
      setError(`Error en ${ruta}: ${err.message}`);
      setServidores(prev => prev.map(s => 
        s.idServidor === idServidor ? { ...s, activo: false } : s
      ));
      throw err;
    }
  };

  const detenerProceso = async (idServidor) => {
    try {
      const response = await fetch('http://localhost:8000/proceso-detener/', {
        method: 'POST'
      });

      if (!response.ok) throw new Error('Error al detener proceso');
      
      setServidores(prev => prev.map(s => 
        s.idServidor === idServidor ? { ...s, activo: false } : s
      ));
      
      if (timersRef.current[idServidor]) {
        clearTimeout(timersRef.current[idServidor]);
        delete timersRef.current[idServidor];
      }
      
      return await response.json();
    } catch (err) {
      console.error('Error deteniendo proceso:', err);
      throw err;
    }
  };

  const toggleProcesamiento = async (idServidor, ruta, intervalo) => {
    const servidor = servidores.find(s => s.idServidor === idServidor);
    
    if (!servidor.activo) {
      await procesarServidor(idServidor, ruta, intervalo);
    } else {
      await detenerProceso(idServidor);
    }
  };

  const agregarServidor = async () => {
    if (!nuevaRuta.trim()) return setError('Ruta requerida');

    try {
      const response = await fetch('http://localhost:8000/api/servidores/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idEmpresa: 1,
          ruta: nuevaRuta,
          nombreServidor: nuevaRuta.split('/').pop(),
          activo: false
        })
      });

      if (!response.ok) throw new Error(await response.text());

      const nuevoServidor = await response.json();
      setServidores(prev => [...prev, {
        idServidor: nuevoServidor.id_servidor,
        ruta: nuevaRuta,
        intervalo: nuevoIntervalo,
        activo: false
      }]);
      setNuevaRuta('');
    } catch (err) {
      setError(`Error al guardar: ${err.message}`);
    }
  };

  const eliminarServidor = async (idServidor) => {
    if (!window.confirm("¿Estás seguro de borrar? Todos los procesos y logs asociados serán eliminados.")) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/servidores/${idServidor}`, {
        method: 'DELETE'
      });

      if (!response.ok) throw new Error('Error al eliminar servidor');

      if (timersRef.current[idServidor]) {
        clearTimeout(timersRef.current[idServidor]);
        delete timersRef.current[idServidor];
      }

      setServidores(prev => prev.filter(s => s.idServidor !== idServidor));
    } catch (err) {
      setError(`Error al eliminar servidor: ${err.message}`);
    }
  };

  return (
    <div className="multi-log-container">
      <div className="header-con-boton">
        <h2>Monitor de Servidores</h2>
        <button onClick={() => navigate('/tablero-logs')} className="btn-ir-graficos">
          Ver Dashboard de Métricas
        </button>
      </div>

      <div className="agregar-archivo">
        <input
          type="text"
          value={nuevaRuta}
          onChange={(e) => setNuevaRuta(e.target.value)}
          placeholder="Ej: /ruta/servidor.log"
        />
        <input
          type="number"
          min="1"
          value={nuevoIntervalo}
          onChange={(e) => setNuevoIntervalo(Math.max(1, e.target.valueAsNumber || 5))}
        />
        <button onClick={agregarServidor}>Agregar Servidor</button>
      </div>

      <div className="lista-archivos">
        {servidores.length === 0 ? (
          <p>No hay servidores registrados</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Servidor</th>
                <th>Intervalo (min)</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {servidores.map((servidor) => {
                const estaProcesando = procesosActivos.some(p => p.archivo === servidor.ruta);
                return (
                  <tr key={servidor.idServidor}>
                    <td>{servidor.ruta}</td>
                    <td>
                      <input
                        type="number"
                        min="1"
                        value={servidor.intervalo}
                        onChange={(e) => {
                          const intervalo = Math.max(1, e.target.valueAsNumber || 5);
                          setServidores(prev => prev.map(s =>
                            s.idServidor === servidor.idServidor ? { ...s, intervalo } : s
                          ));
                        }}
                      />
                    </td>
                    <td>
                    <span className={`estado ${servidor.activo ? 'activo' : ''}`}>
                      {servidor.activo ? '▶ MONITOREANDO' : '⏸ DETENIDO'}
                    </span>
                    </td>
                    <td>
                      <button
                        onClick={() => toggleProcesamiento(
                          servidor.idServidor,
                          servidor.ruta,
                          servidor.intervalo
                        )}
                        className={servidor.activo ? 'detener' : 'iniciar'}
                        disabled={estaProcesando && !servidor.activo}
                      >
                        {servidor.activo ? 'Detener' : 'Iniciar'}
                      </button>
                      <button
                        onClick={() => eliminarServidor(servidor.idServidor)}
                        className="eliminar"
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {error && (
        <div className="error" onClick={() => setError(null)}>
          ❌ {error}
        </div>
      )}
    </div>
  );
};

export default MultiLogProcessor;
