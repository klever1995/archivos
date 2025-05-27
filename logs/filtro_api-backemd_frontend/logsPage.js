import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './estilos.css'; // Tus estilos actuales

const LogsPage = () => {
  const [nombreArchivo, setNombreArchivo] = useState('');
  const [procesos, setProcesos] = useState([]);
  const [autoProcesamiento, setAutoProcesamiento] = useState(false);
  const [intervalo, setIntervalo] = useState(5);
  const [cargando, setCargando] = useState(false);
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  // Cargar procesos desde la base de datos
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

  // Procesar nuevo archivo (igual que antes)
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
      
      // Recargar la lista de procesos después de procesar
      await cargarProcesos();
    } catch (err) {
      console.error("Error al procesar:", err);
    }
  };

  // Efectos (igual que antes)
  useEffect(() => {
    cargarProcesos();
  }, []);

  useEffect(() => {
    let intervaloId;
    if (autoProcesamiento) {
      procesarLog();
      intervaloId = setInterval(() => {
        procesarLog();
      }, intervalo * 60 * 1000);
    }
    return () => clearInterval(intervaloId);
  }, [autoProcesamiento, intervalo, nombreArchivo]);

  const handleFileSelect = (e) => {
    const archivo = e.target.files[0];
    if (archivo) setNombreArchivo(archivo.name);
  };

  return (
    <div className="app-container">
      {/* Panel Izquierdo - Configuración (IDÉNTICO A ANTES) */}
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
                onClick={() => setAutoProcesamiento(!autoProcesamiento)}
                className={`toggle-button ${autoProcesamiento ? 'stop' : 'start'}`}
              >
                {autoProcesamiento ? '⏸ Detener' : '▶ Iniciar'} Auto-Proceso
              </button>
            </div>
          </>
        )}
      </div>

      {/* Panel Derecho - Resultados (MISMO ESTILO, NUEVOS DATOS) */}
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

