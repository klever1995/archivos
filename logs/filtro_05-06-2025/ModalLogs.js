import React from 'react';
import './ModalLogs.css'; // Crearemos este CSS después

const ModalLogs = ({ nivel, logs, onClose }) => {
  if (!logs) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-container">
        <div className="modal-header">
          <h3>Logs de {nivel}</h3>
          <button onClick={onClose} className="close-button">
            &times;
          </button>
        </div>
        
        <div className="modal-content">
          <div className="logs-list">
            {logs.map((log, index) => (
              <div key={index} className={`log-item ${log.nivel.toLowerCase()}`}>
                <div className="log-meta">
                  <span className="log-fecha">{log.fecha_creacion}</span>
                  <span className="log-componente">{log.componente || 'Sin componente'}</span>
                </div>
                <div className="log-mensaje">{log.mensaje}</div>
                {log.lineas && (
                  <div className="log-lineas">
                    <pre>{JSON.stringify(log.lineas, null, 2)}</pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ModalLogs;
