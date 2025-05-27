import React, { useState, useEffect } from 'react';
import './estilosErrores.css';

const LogsErrores = () => {
  const [logs, setLogs] = useState([]);
  const [filtros, setFiltros] = useState({
    idEmpresa: 1,
    dias_atras: 7,
    nivel: null,
    estado: null,
    componente: null,
    limite: 100
  });
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);

  const cargarErrores = async () => {
    setCargando(true);
    setError(null);
    try {
      // Construir parámetros de consulta
      const params = new URLSearchParams();
      Object.keys(filtros).forEach(key => {
        if (filtros[key] !== null && filtros[key] !== undefined) {
          params.append(key, filtros[key]);
        }
      });

      const url = `http://localhost:8000/api/logs-aplicacion/?${params.toString()}`;
      console.log('Solicitando datos desde:', url);

      const response = await fetch(url, {
        headers: {
          'Accept': 'application/json',
        }
      });

      if (!response.ok) {
        throw new Error(`Error HTTP: ${response.status}`);
      }

      const data = await response.json();
      console.log('Datos recibidos:', data);
      setLogs(data.resultados);
    } catch (err) {
      console.error('Error al cargar logs:', err);
      setError(err.message);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarErrores();
  }, [filtros]);

  const manejarCambioFiltro = (e) => {
    const { name, value } = e.target;
    setFiltros(prev => ({
      ...prev,
      [name]: value === '' ? null : value
    }));
  };

  return (
    <div className="contenedor-errores">
      <h2>Logs de Errores</h2>
      
      {/* Filtros */}
      <div className="filtros">
        <select 
          name="nivel"
          value={filtros.nivel || ''}
          onChange={manejarCambioFiltro}
        >
          <option value="">Todos los niveles</option>
          <option value="ERROR">ERROR</option>
          <option value="WARN">WARN</option>
          <option value="INFO">INFO</option>
        </select>

        <input
          type="number"
          name="dias_atras"
          value={filtros.dias_atras}
          onChange={manejarCambioFiltro}
          min="1"
          placeholder="Días atrás"
        />
      </div>

      {/* Mensajes de estado */}
      {error && <div className="error-mensaje">Error: {error}</div>}
      {cargando && <div className="cargando-mensaje">Cargando...</div>}

      {/* Tabla de resultados */}
      {!cargando && !error && (
        <div className="tabla-contenedor">
          {logs.length === 0 ? (
            <p>No se encontraron registros con los filtros actuales</p>
          ) : (
            <table className="tabla-errores">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Nivel</th>
                  <th>Componente</th>
                  <th>Mensaje</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id_log} className={`fila-nivel-${log.nivel.toLowerCase()}`}>
                    <td>{new Date(log.fecha_creacion).toLocaleString()}</td>
                    <td>
                      <span className={`badge-nivel-${log.nivel.toLowerCase()}`}>
                        {log.nivel}
                      </span>
                    </td>
                    <td>{log.componente}</td>
                    <td className="mensaje-celda">
                      <div className="mensaje-resumido">
                        {log.mensaje.split('\r')[0].substring(0, 100)}...
                      </div>
                      <div className="mensaje-completo" style={{display: 'none'}}>
                        {log.mensaje}
                      </div>
                      <button 
                        className="btn-expandir"
                        onClick={(e) => {
                          const divCompleto = e.target.previousElementSibling;
                          divCompleto.style.display = divCompleto.style.display === 'none' ? 'block' : 'none';
                        }}
                      >
                        ▼
                      </button>
                    </td>
                    <td>
                      {log.respuesta_ia && (
                        <button 
                          className="btn-solucion"
                          onClick={() => alert(log.respuesta_ia)}
                        >
                          Ver solución
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};

export default LogsErrores;
