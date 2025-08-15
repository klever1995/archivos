import React, { useState } from 'react';
import './ModalLogs.css';

const ModalLogs = ({ nivel, logs, onClose, servidorNombre }) => {
  const [filtros, setFiltros] = useState({
    componente: '',
    desdeFecha: '',
    hastaFecha: ''
  });
  const [expandedRow, setExpandedRow] = useState(null);

  if (!logs || !Array.isArray(logs)) return null;

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

  const logsFiltrados = filtrarLogs();

  // Ordenar por nivel de criticidad (FATAL primero, luego ERROR, luego WARN)
  const logsOrdenados = [...logsFiltrados].sort((a, b) => {
    const prioridad = { FATAL: 0, ERROR: 1, WARN: 2 }; // FATAL primero
    return (prioridad[a.nivel] || 3) - (prioridad[b.nivel] || 3);
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
        <h3 className={`${nivel.toLowerCase()}-header`}> {/* Usará .fatal-header en CSS */}
          {nivel === 'FATAL' } {/* Icono distinto */}
          Logs de {nivel} - {servidorNombre}
        </h3>
          <button onClick={onClose} className="close-button">
            &times;
          </button>
        </div>
        
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
