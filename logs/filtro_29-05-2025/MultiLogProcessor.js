import React, { useState, useEffect } from 'react';
import './estilosConfig.css';

const MultiLogProcessor = () => {
  const [archivos, setArchivos] = useState([]);
  const [intervalosActivos, setIntervalosActivos] = useState({});
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);
  const [nuevaRuta, setNuevaRuta] = useState('');
  const [nuevoIntervalo, setNuevoIntervalo] = useState(5);

  // Función para procesar un archivo individual (CORREGIDO)
  const procesarArchivo = async (ruta) => {
    setCargando(true);
    try {
      const formData = new FormData();
      formData.append('nombre_archivo', ruta);  // Nombre exacto que espera el backend

      const response = await fetch('http://localhost:8000/procesar-log/', {
        method: 'POST',
        body: formData  // Sin headers Content-Type para FormData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Error ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      console.error(`Error al procesar ${ruta}:`, err);
      setError(`Fallo en ${ruta}: ${err.message}`);
      throw err;
    } finally {
      setCargando(false);
    }
  };

  // Manejar inicio/detención de un archivo (OPTIMIZADO)
  const toggleProcesamiento = async (ruta, intervalo) => {
    try {
      const archivoIndex = archivos.findIndex(a => a.ruta === ruta);
      const nuevoEstado = !archivos[archivoIndex].activo;

      // Actualizar estado UI primero para feedback inmediato
      setArchivos(prev => prev.map(a => 
        a.ruta === ruta ? { ...a, activo: nuevoEstado } : a
      ));

      if (nuevoEstado) {
        await procesarArchivo(ruta);  // Ejecución inicial
        const intervalId = setInterval(
          () => procesarArchivo(ruta), 
          intervalo * 60 * 1000
        );
        setIntervalosActivos(prev => ({ ...prev, [ruta]: intervalId }));
      } else {
        clearInterval(intervalosActivos[ruta]);
        setIntervalosActivos(prev => {
          const nuevos = { ...prev };
          delete nuevos[ruta];
          return nuevos;
        });
      }
    } catch (err) {
      // Revertir estado si falla
      setArchivos(prev => prev.map(a => 
        a.ruta === ruta ? { ...a, activo: false } : a
      ));
    }
  };

  // Limpieza de intervalos (MEJORADO)
  useEffect(() => {
    return () => {
      Object.values(intervalosActivos).forEach(clearInterval);
    };
  }, [intervalosActivos]);

  // Agregar archivo (SIMPLIFICADO)
  const agregarArchivo = () => {
    if (!nuevaRuta) return;
    
    // Validar ruta única
    if (archivos.some(a => a.ruta === nuevaRuta)) {
      setError(`La ruta ${nuevaRuta} ya existe`);
      return;
    }

    setArchivos([...archivos, { 
      ruta: nuevaRuta, 
      intervalo: nuevoIntervalo, 
      activo: false 
    }]);
    setNuevaRuta('');
  };

  return (
    <div className="multi-log-container">
      <h2>Procesador Multi-Archivo</h2>
      
      {/* Formulario mejorado */}
      <div className="agregar-archivo">
        <input
          type="text"
          value={nuevaRuta}
          onChange={(e) => setNuevaRuta(e.target.value)}
          placeholder="Ruta absoluta (ej: C:/logs/servidor1.log)"
        />
        <input
          type="number"
          min="1"
          value={nuevoIntervalo}
          onChange={(e) => setNuevoIntervalo(parseInt(e.target.value) || 5)}
          placeholder="Intervalo (min)"
        />
        <button onClick={agregarArchivo}>
          Agregar Archivo
        </button>
      </div>

      {/* Tabla optimizada */}
      <div className="lista-archivos">
        {archivos.length === 0 ? (
          <p className="no-archivos">No hay archivos configurados</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Archivo</th>
                <th>Intervalo (min)</th>
                <th>Estado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {archivos.map((archivo) => (
                <tr key={archivo.ruta}>
                  <td className="ruta-cell">{archivo.ruta}</td>
                  <td>
                    <input
                      type="number"
                      min="1"
                      value={archivo.intervalo}
                      onChange={(e) => {
                        const nuevoIntervalo = parseInt(e.target.value) || 5;
                        setArchivos(prev => prev.map(a => 
                          a.ruta === archivo.ruta 
                            ? { ...a, intervalo: nuevoIntervalo } 
                            : a
                        ));
                      }}
                    />
                  </td>
                  <td>
                    <span className={`estado ${archivo.activo ? 'activo' : 'inactivo'}`}>
                      {archivo.activo ? '▶ ACTIVO' : '⏸ INACTIVO'}
                    </span>
                  </td>
                  <td>
                    <button
                      onClick={() => toggleProcesamiento(archivo.ruta, archivo.intervalo)}
                      disabled={cargando}
                      className={`accion-btn ${archivo.activo ? 'detener' : 'iniciar'}`}
                    >
                      {archivo.activo ? 'Detener' : 'Iniciar'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Mensajes de estado */}
      {error && (
        <div className="error" onClick={() => setError(null)}>
          ❌ {error} (click para cerrar)
        </div>
      )}
      {cargando && <div className="cargando">🔄 Procesando...</div>}
    </div>
  );
};

export default MultiLogProcessor;
