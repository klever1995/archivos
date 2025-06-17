import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './estilosConfig.css';

const MultiLogProcessor = () => {
  const [servidores, setServidores] = useState([]);
  const [error, setError] = useState(null);
  const [nuevaRuta, setNuevaRuta] = useState('');
  const [nuevoIntervalo, setNuevoIntervalo] = useState(5);
  const [procesosActivos, setProcesosActivos] = useState({}); // Nuevo estado para rastrear procesos
  const intervalosRef = useRef({});
  const navigate = useNavigate();

  // Cargar servidores y estados activos al iniciar
  useEffect(() => {
    const cargarDatosIniciales = async () => {
      try {
        // Cargar servidores
        const responseServidores = await fetch('http://localhost:8000/api/servidores/?idEmpresa=1');
        if (!responseServidores.ok) throw new Error('Error al cargar servidores');
        const dataServidores = await responseServidores.json();
        
        // Cargar estado actual de procesos
        const responseProcesos = await fetch('http://localhost:8000/proceso-estado/');
        const dataProcesos = await responseProcesos.json();
        
        setServidores(dataServidores.resultados.map(s => ({
          idServidor: s.id_servidor,
          ruta: s.ruta,
          intervalo: nuevoIntervalo,
          activo: dataProcesos.archivos_procesando?.includes(s.ruta) || false
        })));

        setProcesosActivos(dataProcesos.archivos_procesando || []);

      } catch (err) {
        setError(err.message);
      }
    };
    cargarDatosIniciales();
  }, []);

  // Procesar un servidor individual con manejo de errores mejorado
  const procesarServidor = async (idServidor, ruta) => {
    try {
      // Verificar si ya está en proceso
      if (procesosActivos.includes(ruta)) {
        throw new Error(`El archivo ${ruta} ya está siendo procesado`);
      }

      const formData = new FormData();
      formData.append('nombre_archivo', ruta);
      formData.append('idServidor', idServidor);

      const response = await fetch('http://localhost:8000/procesar-log/', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Error desconocido');
      }

      const resultado = await response.json();
      return resultado;

    } catch (err) {
      console.error(`Error procesando ${ruta}:`, err);
      setError(`Error en ${ruta}: ${err.message}`);
      throw err;
    }
  };

  // Toggle procesamiento mejorado con verificación de estado
  const toggleProcesamiento = async (idServidor, ruta, intervalo) => {
    const estaActivo = intervalosRef.current[idServidor];
    
    try {
      if (!estaActivo) {
        // Ejecución inmediata
        await procesarServidor(idServidor, ruta);
        
        // Configurar intervalo solo si la ejecución fue exitosa
        intervalosRef.current[idServidor] = setInterval(async () => {
          try {
            await procesarServidor(idServidor, ruta);
          } catch (err) {
            // En caso de error, detener el intervalo
            clearInterval(intervalosRef.current[idServidor]);
            delete intervalosRef.current[idServidor];
            setServidores(prev => prev.map(s => 
              s.idServidor === idServidor ? { ...s, activo: false } : s
            ));
          }
        }, intervalo * 60 * 1000);

      } else {
        // Detener el intervalo
        clearInterval(intervalosRef.current[idServidor]);
        delete intervalosRef.current[idServidor];
      }

      // Actualizar estado UI
      setServidores(prev => prev.map(s => 
        s.idServidor === idServidor ? { ...s, activo: !estaActivo } : s
      ));

    } catch (err) {
      // No cambiar el estado si hubo error
      console.error("Error en toggleProcesamiento:", err);
    }
  };

  // Agregar nuevo servidor (sin cambios)
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

  // Eliminar servidor (sin cambios)
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
    return () => {
      Object.values(intervalosRef.current).forEach(clearInterval);
    };
  }, []);

  // Sincronización periódica de estado
  useEffect(() => {
    const sincronizarEstado = async () => {
      try {
        const response = await fetch('http://localhost:8000/proceso-estado/');
        const data = await response.json();
        setProcesosActivos(data.archivos_procesando || []);
      } catch (err) {
        console.error("Error sincronizando estado:", err);
      }
    };

    const intervalo = setInterval(sincronizarEstado, 30000); // Sincronizar cada 30 segundos
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
              {servidores.map((servidor) => (
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
                    {procesosActivos.includes(servidor.ruta) && !servidor.activo && (
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
                      disabled={procesosActivos.includes(servidor.ruta) && !servidor.activo}
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
              ))}
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
