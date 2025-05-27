import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './estilos.css';

const LogsPage = () => {
  const [nombreArchivo, setNombreArchivo] = useState('');
  const [procesos, setProcesos] = useState([]);
  const [autoProcesamiento, setAutoProcesamiento] = useState(false);
  const [intervalo, setIntervalo] = useState(5);
  const [cargando, setCargando] = useState(false);
  const [procesoIniciadoPorUsuario, setProcesoIniciadoPorUsuario] = useState(false);
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  // 1. Cargar procesos desde la base de datos
  const cargarProcesos = async () => {
    setCargando(true);
    try {
      const response = await fetch('http://localhost:8000/api/logs-procesados/?idEmpresa=1');
      if (!response.ok) throw new Error('Error al cargar procesos');
      const data = await response.json();
      setProcesos(data.resultados);
    } catch (err) {
      console.error(err);
    } finally {
      setCargando(false);
    }
  };

  // 2. Procesar archivo de log
  const procesarLog = async () => {
    if (!nombreArchivo) return;
    
    try {
      const formData = new FormData();
      formData.append('nombre_archivo', nombreArchivo);

      const response = await fetch('http://localhost:8000/procesar-log/', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) throw new Error(`Error ${response.status}`);
      await cargarProcesos();
    } catch (err) {
      console.error("Error al procesar:", err);
    }
  };

  // 3. Cargar estado persistente del backend
  const cargarEstadoPersistente = async () => {
    try {
      const res = await fetch('http://localhost:8000/proceso-config/');
      const { activo, intervalo_minutos, archivo } = await res.json();
      
      if (activo && archivo) {
        setNombreArchivo(archivo);
        setIntervalo(intervalo_minutos);
        setAutoProcesamiento(true);
        setProcesoIniciadoPorUsuario(true);
      }
    } catch (err) {
      console.error("Error al cargar estado:", err);
    }
  };

  // Efecto 1: Cargar datos iniciales al montar el componente
  useEffect(() => {
    const cargarDatos = async () => {
      await cargarEstadoPersistente();
      await cargarProcesos();
    };
    cargarDatos();
  }, []);

  // Efecto 2: Manejar el auto-procesamiento
  useEffect(() => {
    let intervaloId;

    const iniciarProceso = async () => {
      if (!procesoIniciadoPorUsuario || !nombreArchivo) return;
      
      await fetch('http://localhost:8000/proceso-config/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          activo: true,
          intervalo_minutos: intervalo,
          archivo: nombreArchivo
        })
      });
      await procesarLog();
      intervaloId = setInterval(() => procesarLog(), intervalo * 60 * 1000);
    };

    const detenerProceso = async () => {
      await fetch('http://localhost:8000/proceso-detener/', {
        method: 'POST'
      });
      if (intervaloId) clearInterval(intervaloId);
    };

    if (autoProcesamiento) {
      iniciarProceso();
    } else {
      detenerProceso();
    }

    return () => {
      if (intervaloId) clearInterval(intervaloId);
    };
  }, [autoProcesamiento, intervalo, nombreArchivo, procesoIniciadoPorUsuario]);

  // Manejo de selección de archivo
  const handleFileSelect = (e) => {
    const archivo = e.target.files[0];
    if (archivo) {
      setNombreArchivo(archivo.name);
      setProcesoIniciadoPorUsuario(false); // Resetear bandera al cambiar archivo
    }
  };

  // Toggle para iniciar/detener el proceso
  const toggleProceso = () => {
    if (!nombreArchivo) return;
    setProcesoIniciadoPorUsuario(true);
    setAutoProcesamiento(!autoProcesamiento);
  };

  return (
    <div className="app-container">
      {/* Panel Izquierdo - Configuración */}
      <div className="config-panel">
        <h2 className="panel-title">Configuración de Procesamiento</h2>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          className="file-input"
          accept=".txt,.log"
          id="fileInput"
          hidden
        />
        <button 
          onClick={() => fileInputRef.current.click()}
          className="action-button"
        >
          {nombreArchivo || 'Seleccionar archivo de log'}
        </button>
        {nombreArchivo && (
          <>
            <button 
              onClick={procesarLog}
              className="action-button process-manual"
            >
              Procesar Manualmente
            </button>
            <div className="auto-process-panel">
              <h3>Procesamiento Automático</h3>
              <div className="interval-control">
                <label>
                  Intervalo (minutos):
                  <input
                    type="number"
                    min="1"
                    value={intervalo}
                    onChange={(e) => setIntervalo(Number(e.target.value))}
                    className="interval-input"
                  />
                </label>
              </div>
              <button
                onClick={toggleProceso}
                className={`toggle-button ${autoProcesamiento ? 'stop' : 'start'}`}
              >
                {autoProcesamiento ? '⏸ Detener' : '▶ Iniciar'} Auto-Proceso
              </button>
            </div>
          </>
        )}
      </div>

      {/* Panel Derecho - Resultados */}
      <div className="results-panel">
        <div className="panel-header">
          <h2 className="panel-title">Historial de Procesos</h2>
          <button 
            onClick={() => navigate('/logs-errores')}
            className="error-button"
          >
            Ver Errores
          </button>
        </div>
        {cargando ? (
          <p className="no-results">Cargando...</p>
        ) : procesos.length === 0 ? (
          <p className="no-results">No hay procesos registrados</p>
        ) : (
          <table className="results-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Archivo</th>
                <th>Logs</th>
                <th>Bytes</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {procesos.map((proceso) => (
                <tr key={proceso.id_auditoria}>
                  <td>{new Date(proceso.fecha_inicio).toLocaleString()}</td>
                  <td>{proceso.archivo.split('/').pop()}</td>
                  <td>{proceso.total_logs}</td>
                  <td>{proceso.rango_bytes}</td>
                  <td>
                    <span className={`status-badge ${proceso.estado === 'COMPLETADO' ? 'status-success' : 'status-warning'}`}>
                      {proceso.estado}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default LogsPage;
