import React, { useState, useEffect } from 'react';
import './ModalLogs.css';

// Modal para visualizar logs filtrados por nivel
const ModalLogs = ({ nivel, logs, onClose, servidorNombre, fechaDesde, fechaHasta, cargando }) => {
  const [filtros, setFiltros] = useState({
    componente: '',
    desdeFecha: fechaDesde || new Date().toISOString().split('T')[0],
    hastaFecha: fechaHasta || new Date().toISOString().split('T')[0]  
  });
  const [expandedRow, setExpandedRow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Actualizar filtros cuando las fechas del padre cambien
    setFiltros(prev => ({
      ...prev,
      desdeFecha: fechaDesde || new Date().toISOString().split('T')[0],
      hastaFecha: fechaHasta || new Date().toISOString().split('T')[0]
    }));
  }, [fechaDesde, fechaHasta]);

  useEffect(() => {
    // Si recibimos el prop cargando, usarlo directamente
    if (cargando !== undefined) {
      setLoading(cargando);
      return;
    }
  
    // Lógica original solo si no recibimos el prop cargando
    const timer = setTimeout(() => {
      if (!logs || !Array.isArray(logs)) {
        setError('No se pudieron cargar los logs o el formato es incorrecto');
      } else {
        setError(null);
      }
      setLoading(false);
    }, 500);
  
    return () => clearTimeout(timer);
  }, [logs, nivel, cargando]); 

  // Estados de carga y error - DEBEN IR PRIMERO
  if (loading) return (
    <div className="modal-overlay" >
      <div className="modal-container" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Cargando logs {nivel}...</h3>
        </div>
        <div className="cargando">Cargando logs...</div>
      </div>
    </div>
  );

  if (error) return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className={`${nivel.toLowerCase()}-header`}>
            Error - {servidorNombre}
          </h3>
          <button onClick={onClose} className="close-button">
            &times;
          </button>
        </div>
        <div className="error-modal">
          <p>{error}</p>
          <button onClick={onClose} className="btn btn-primario">
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );

  // Filtra logs por componente y rango de fechas
  const filtrarLogs = () => {
    return logs.filter(log => {
      const cumpleComponente = filtros.componente === '' || 
        (log.componente && log.componente.toLowerCase().includes(filtros.componente.toLowerCase()));
      
      const fechaLog = new Date(log.fecha_creacion);
      const cumpleDesde = !filtros.desdeFecha || fechaLog >= new Date(filtros.desdeFecha);
      const cumpleHasta = !filtros.hastaFecha || fechaLog <= new Date(filtros.hastaFecha + 'T23:59:59');
      
      return cumpleComponente && cumpleDesde && cumpleHasta;
    });
  };

  // Ordena logs por prioridad 
  const logsFiltrados = filtrarLogs();
  const logsOrdenados = [...logsFiltrados].sort((a, b) => {
    const prioridad = { FATAL: 0, ERROR: 1, WARN: 2 }; 
    return (prioridad[a.nivel] || 3) - (prioridad[b.nivel] || 3);
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className={`${nivel.toLowerCase()}-header`}> 
            {nivel === 'FATAL' }
            Logs de {nivel} - {servidorNombre}
          </h3>
          <button onClick={onClose} className="close-button">
            &times;
          </button>
        </div>
        {/* Sección de filtros */}
        <div className="modal-filtros">
          <input
            type="text"
            placeholder="Filtrar por componente"
            value={filtros.componente}
            onChange={(e) => setFiltros({...filtros, componente: e.target.value})}
          />
          <div className="fecha-filtros">
            <input
              type="date"
              placeholder="Desde"
              value={filtros.desdeFecha}
              onChange={(e) => setFiltros({...filtros, desdeFecha: e.target.value})}
            />
            <input
              type="date"
              placeholder="Hasta"
              value={filtros.hastaFecha}
              onChange={(e) => setFiltros({...filtros, hastaFecha: e.target.value})}
            />
          </div>
        </div>
        {/* Tabla de resultados */}
        <div className="tabla-contenedor">
          <table className="tabla-logs">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Componente</th>
                <th>Mensaje</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {logsOrdenados.length === 0 ? (
                <tr>
                  <td colSpan="4" className="sin-resultados">
                    No se encontraron logs con los filtros actuales
                  </td>
                </tr>
              ) : (
                logsOrdenados.map((log, index) => (
                  <React.Fragment key={log.id_log || index}>
                    <tr className={`fila-log ${log.nivel.toLowerCase()}`}>
                      <td>{new Date(log.fecha_creacion).toLocaleString()}</td>
                      <td>{log.componente || 'N/A'}</td>
                      <td className="mensaje-celda">
                        {log.mensaje.split('\n')[0].substring(0, 80)}...
                      </td>
                      <td className="acciones-celda">
                        <button 
                          className="btn-detalle"
                          onClick={() => setExpandedRow(expandedRow === index ? null : index)}
                        >
                          {expandedRow === index ? '▲ Ocultar' : '▼ Detalle'}
                        </button>
                      </td>
                    </tr>
                    {/* Fila expandida con detalles */}
                    {expandedRow === index && (
                      <tr className="fila-expandida">
                        <td colSpan="4">
                          <div className="detalle-expandido">
                            <div className="mensaje-completo">
                              <strong>Mensaje completo:</strong>
                              <pre>{log.mensaje}</pre>
                            </div>
                            {log.lineas && log.lineas.length > 0 && (
                              <div className="lineas-afectadas">
                                <strong>Líneas afectadas:</strong> {log.lineas.join(', ')}
                              </div>
                            )}
                            {log.respuestaOpenai && (
                              <div className="solucion-ia">
                                <strong>Solución sugerida:</strong>
                                <div className="solucion-contenido">
                                  {log.respuestaOpenai}
                                </div>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ModalLogs;
