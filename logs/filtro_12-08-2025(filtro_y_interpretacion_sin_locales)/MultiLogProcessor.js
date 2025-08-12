import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import './estilosConfig.css';
import ModalAccesos from './ModalAccesos'; 

const MultiLogProcessor = () => {
  const [servidores, setServidores] = useState([]);
  const [error, setError] = useState(null);
  const [nuevaRuta, setNuevaRuta] = useState('');
  const [nuevoIntervalo, setNuevoIntervalo] = useState(5);
  const [procesosActivos, setProcesosActivos] = useState([]);
  const wsRef = useRef(null);
  const navigate = useNavigate();
  const timersRef = useRef({});
  const [mostrarModalAccesos, setMostrarModalAccesos] = useState(false);
  const [idEmpresa] = useState(1);
  const [idAccesoSeleccionado, setIdAccesoSeleccionado] = useState('');
  const [accesosRemotos, setAccesosRemotos] = useState([]);

  const connectWebSocket = useCallback(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/${idEmpresa}`);
    
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

  const cargarProcesosActivos = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/interpretacion/procesos-activos');
      if (!res.ok) throw new Error('No se pudieron cargar procesos activos');
      const data = await res.json();
      setProcesosActivos(data);
    } catch (err) {
      console.error(err);
    }
  };

  const cargarDatosIniciales = async () => {
    try {
      const [servidoresRes, accesosRes] = await Promise.all([
        fetch('http://localhost:8000/api/servidores/?idEmpresa=1'),
        fetch('http://localhost:8000/api/accesos-remotos/?idEmpresa=1&activo=true')
      ]);

      if (!servidoresRes.ok) throw new Error('Error al cargar servidores');
      
      const dataServidores = await servidoresRes.json();
      const dataAccesos = await accesosRes.json();

      setServidores(dataServidores.resultados.map(s => ({
        idServidor: s.id_servidor,
        ruta: s.ruta,
        intervalo: s.intervalo ?? nuevoIntervalo,
        activo: false,
        idAccesoRemoto: s.id_acceso_remoto
      })));

      setAccesosRemotos(dataAccesos.data || []);

    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    connectWebSocket();
    cargarDatosIniciales();
    cargarProcesosActivos();
    
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
  
      const response = await fetch('http://localhost:8000/api/v1/interpretacion/iniciar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id_servidor: idServidor,
          batch_size: 100,
          intervalo_minutos: intervaloMinutos
        })
      });
  
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Error desconocido');
      }
      
      await cargarProcesosActivos();
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
      const url = `http://localhost:8000/api/v1/interpretacion/detener?id_servidor=${idServidor}`;
      const response = await fetch(url, {
        method: 'POST',
      });
  
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Error desconocido');
      }
  
      setServidores(prev => prev.map(s =>
        s.idServidor === idServidor ? { ...s, activo: false } : s
      ));
  
      if (timersRef.current[idServidor]) {
        clearTimeout(timersRef.current[idServidor]);
        delete timersRef.current[idServidor];
      }
  
      await cargarProcesosActivos();
      return await response.json();
    } catch (err) {
      console.error('Error deteniendo proceso:', err);
      setError(`Error al detener proceso: ${err.message}`);
      throw err;
    }
  };
  

  const toggleProcesamiento = async (idServidor, ruta, intervalo) => {
    const estaActivo = procesosActivos.some(p => p.id_servidor === idServidor);
    
    if (!estaActivo) {
      await procesarServidor(idServidor, ruta, intervalo);
    } else {
      await detenerProceso(idServidor);
    }
  };
  

  const agregarServidor = async () => {
    if (!nuevaRuta.trim()) return setError('Ruta requerida');
  
    if (!idAccesoSeleccionado) {
      return setError('Debe seleccionar un acceso remoto');
    }
  
    try {
      const response = await fetch('http://localhost:8000/api/servidores/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idEmpresa: 1,
          ruta: nuevaRuta,
          nombreServidor: nuevaRuta.split('/').pop(),
          activo: false,
          idAccesoRemoto: idAccesoSeleccionado,
        }),
      });
  
      if (!response.ok) throw new Error(await response.text());
  
      const nuevoServidor = await response.json();
      setServidores(prev => [...prev, {
        idServidor: nuevoServidor.id_servidor,
        ruta: nuevaRuta,
        intervalo: nuevoIntervalo,
        activo: false,
        idAccesoRemoto: idAccesoSeleccionado,
      }]);
      setNuevaRuta('');
      setIdAccesoSeleccionado('');
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
        <h2>Monitor de Servidores Remotos</h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            onClick={() => setMostrarModalAccesos(true)}
            className="btn-ir-graficos"
            style={{ backgroundColor: '#6a5acd' }}
          >
            Administrar Accesos
          </button>
          <button onClick={() => navigate('/tablero-logs')} className="btn-ir-graficos">
            Ver Dashboard
          </button>
        </div>
      </div>

      <div className="agregar-archivo">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="text"
            value={nuevaRuta}
            onChange={(e) => setNuevaRuta(e.target.value)}
            placeholder="Ej: /ruta/servidor.log"
            style={{ flexGrow: 1, minWidth: '180px' }}
          />
          <select
            className="dropdown-accesos"
            value={idAccesoSeleccionado || ''}
            onChange={(e) => setIdAccesoSeleccionado(e.target.value)}
            style={{ minWidth: '150px' }}
          >
            <option value="">Selecciona acceso remoto</option>
            {accesosRemotos.map((acceso) => (
              <option key={acceso.idAcceso} value={acceso.idAcceso}>
                {acceso.hostname}
              </option>
            ))}
          </select>
        </div>

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
                <th>Tipo</th>
                <th>Intervalo (min)</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {servidores.map((servidor) => {
                const estaActivo = procesosActivos.some(p => p.id_servidor === servidor.idServidor);
                return (
                  <tr key={servidor.idServidor}>
                    <td>{servidor.ruta}</td>
                    <td>☁️ Remoto</td>
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
                      <span className={`estado ${estaActivo ? 'activo' : ''}`}>
                        {estaActivo ? '▶ MONITOREANDO' : '⏸ DETENIDO'}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => toggleProcesamiento(servidor.idServidor, servidor.ruta, servidor.intervalo)}
                        className={estaActivo ? 'detener' : 'iniciar'}
                        disabled={false}
                      >
                        {estaActivo ? 'Detener' : 'Iniciar'}
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
      {mostrarModalAccesos && (
        <div className="modal-overlay">
          <div className="modal-contenido modal-grande">
            <ModalAccesos 
              idEmpresa={idEmpresa} 
              onClose={() => setMostrarModalAccesos(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default MultiLogProcessor;
