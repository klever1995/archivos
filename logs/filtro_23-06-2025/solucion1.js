import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './estilosConfig.css';

const MultiLogProcessor = () => {
  const [servidores, setServidores] = useState([]);
  const [error, setError] = useState(null);
  const [nuevaRuta, setNuevaRuta] = useState('');
  const [nuevoIntervalo, setNuevoIntervalo] = useState(5);
  const [procesosActivos, setProcesosActivos] = useState([]);
  const intervalosRef = useRef({});
  const navigate = useNavigate();

  // Función segura para obtener procesos activos
  const fetchProcesosActivos = async () => {
    try {
      const response = await fetch('http://localhost:8000/proceso-estado/');
      const data = await response.json();
      return Array.isArray(data?.procesos_activos) ? data.procesos_activos : [];
    } catch (error) {
      console.error("Error fetching procesos activos:", error);
      return [];
    }
  };

  // Cargar servidores y estados activos al iniciar
  useEffect(() => {
    const cargarDatosIniciales = async () => {
      try {
        // Cargar servidores
        const responseServidores = await fetch('http://localhost:8000/api/servidores/?idEmpresa=1');
        if (!responseServidores.ok) throw new Error('Error al cargar servidores');
        const dataServidores = await responseServidores.json();
        
        // Cargar procesos activos (versión segura)
        const procesosActivos = await fetchProcesosActivos();
        
        setServidores(dataServidores.resultados.map(s => ({
          idServidor: s.id_servidor,
          ruta: s.ruta,
          intervalo: nuevoIntervalo,
          activo: procesosActivos.some(p => p.archivo === s.ruta),
          deshabilitado: false
        })));

        setProcesosActivos(procesosActivos);

      } catch (err) {
        setError(err.message);
      }
    };
    cargarDatosIniciales();
  }, [nuevoIntervalo]);

  // Procesar un servidor individual
  const procesarServidor = async (idServidor, ruta, intervaloMinutos = 5) => {
    try {
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
      throw err;
    }
  };

  // Detener un proceso
  const detenerProceso = async (idAuditoria) => {
    try {
      const response = await fetch('http://localhost:8000/proceso-detener/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idAuditoria })
      });
      
      if (!response.ok) throw new Error('Error al detener proceso');
      
      return await response.json();
    } catch (err) {
      console.error('Error deteniendo proceso:', err);
      throw err;
    }
  };

  const toggleProcesamiento = async (idServidor, ruta, intervalo) => {
    try {
      // 1. Deshabilitar botón y mostrar estado "cargando"
      setServidores(prev => prev.map(s => 
        s.idServidor === idServidor ? { 
          ...s, 
          deshabilitado: true,
          estadoTemporal: 'procesando' 
        } : s
      ));
  
      // 2. Verificar estado REAL en backend (nueva consulta)
      const procesosActuales = await fetchProcesosActivos();
      const estaActivo = procesosActuales.some(p => p.archivo === ruta);
  
      // 3. Acción basada en estado REAL
      if (!estaActivo) {
        // Iniciar proceso y ESPERAR confirmación
        const resultado = await procesarServidor(idServidor, ruta, intervalo);
        
        // Verificar si el backend confirmó el inicio
        if (resultado && resultado.id_auditoria) {
          if (intervalo > 0) {
            intervalosRef.current[idServidor] = setInterval(async () => {
              await procesarServidor(idServidor, ruta, intervalo);
            }, intervalo * 60 * 1000);
          }
        }
      } else {
        // Detener proceso
        const proceso = procesosActuales.find(p => p.archivo === ruta);
        if (proceso) await detenerProceso(proceso.idAuditoria);
        
        if (intervalosRef.current[idServidor]) {
          clearInterval(intervalosRef.current[idServidor]);
          delete intervalosRef.current[idServidor];
        }
      }
  
      // 4. Actualización INMEDIATA con nuevo estado
      const nuevosProcesos = await fetchProcesosActivos();
      setProcesosActivos(nuevosProcesos);
      setServidores(prev => prev.map(s => ({
        ...s,
        activo: nuevosProcesos.some(p => p.archivo === s.ruta),
        deshabilitado: false,
        estadoTemporal: null
      })));
  
    } catch (err) {
      console.error("Error en toggleProcesamiento:", err);
      setError(`Error: ${err.message}`);
      setServidores(prev => prev.map(s => 
        s.idServidor === idServidor ? { 
          ...s, 
          deshabilitado: false,
          estadoTemporal: null 
        } : s
      ));
    }
  };

  // Agregar nuevo servidor
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
        activo: false,
        estadoTemporal: null 
      }]);
      setNuevaRuta('');
    } catch (err) {
      setError(`Error al guardar: ${err.message}`);
    }
  };

  // Eliminar servidor
  const eliminarServidor = async (idServidor) => {
    if (!window.confirm("¿Estás seguro de borrar? Todos los procesos y logs asociados a este servidor también serán eliminados.")) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/servidores/${idServidor}`, {
        method: 'DELETE'
      });

      if (!response.ok) throw new Error('Error al eliminar servidor');

      // Limpiar intervalo si existe
      if (intervalosRef.current[idServidor]) {
        clearInterval(intervalosRef.current[idServidor]);
        delete intervalosRef.current[idServidor];
      }

      setServidores(prev => prev.filter(s => s.idServidor !== idServidor));
    } catch (err) {
      setError(`Error al eliminar servidor: ${err.message}`);
    }
  };

  // Limpieza al desmontar
  useEffect(() => {
    const intervalos = intervalosRef.current; // Copia de la referencia
    return () => {
      Object.values(intervalos).forEach(clearInterval);
    };
  }, []);

  // Sincronización periódica de estado
  useEffect(() => {
    const sincronizarEstado = async () => {
      const procesosActivos = await fetchProcesosActivos();
      setProcesosActivos(procesosActivos);
      setServidores(prev => prev.map(servidor => ({
        ...servidor,
        activo: procesosActivos.some(p => p.archivo === servidor.ruta)
      })));
    };

    const intervalo = setInterval(sincronizarEstado, 30000);
    sincronizarEstado(); // Ejecutar inmediatamente
    return () => clearInterval(intervalo);
  }, []);

  return (
    <div className="multi-log-container">
      <div className="header-con-boton">
        <h2>Monitor de Servidores</h2>
        <button 
          onClick={() => navigate('/tablero-logs')} 
          className="btn-ir-graficos"
        >
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
                      {servidor.estadoTemporal === 'procesando' ? '🔄 PROCESANDO...' : 
                      servidor.activo ? '▶ MONITOREANDO' : '⏸ DETENIDO'}
                    </span>
                      {estaProcesando && !servidor.activo && (
                        <span className="estado-procesando"> (PROCESANDO...)</span>
                      )}
                    </td>
                    <td>
                    <button
                        onClick={() => toggleProcesamiento(
                          servidor.idServidor,
                          servidor.ruta,
                          servidor.intervalo
                        )}
                        className={servidor.activo ? 'detener' : 'iniciar'}
                        disabled={servidor.deshabilitado || (estaProcesando && !servidor.activo)}
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
