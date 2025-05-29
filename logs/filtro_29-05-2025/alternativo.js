import React, { useState, useEffect, useRef } from 'react';
import './estilosConfig.css';

const MultiLogProcessor = () => {
  const [archivos, setArchivos] = useState([]);
  const [error, setError] = useState(null);
  const [nuevaRuta, setNuevaRuta] = useState('');
  const [nuevoIntervalo, setNuevoIntervalo] = useState(5);
  const intervalosRef = useRef({});

  // Función optimizada para procesar un archivo individual
  const procesarArchivo = async (ruta) => {
    try {
      const formData = new FormData();
      formData.append('nombre_archivo', ruta);

      const response = await fetch('http://localhost:8000/procesar-log/', {
        method: 'POST',
        body: formData
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
    }
  };

  // Manejar inicio/detención con temporizadores independientes
  const toggleProcesamiento = (ruta, intervalo) => {
    setArchivos(prev => prev.map(a => 
      a.ruta === ruta ? { ...a, activo: !a.activo } : a
    ));

    if (!intervalosRef.current[ruta]) {
      // Ejecución inmediata
      procesarArchivo(ruta).catch(console.error);
      
      // Configurar intervalo
      intervalosRef.current[ruta] = setInterval(
        () => procesarArchivo(ruta).catch(console.error),
        intervalo * 60 * 1000
      );
    } else {
      clearInterval(intervalosRef.current[ruta]);
      delete intervalosRef.current[ruta];
    }
  };

  // Limpieza de intervalos al desmontar
  useEffect(() => {
    return () => {
      Object.values(intervalosRef.current).forEach(clearInterval);
    };
  }, []);

  // Agregar nuevo archivo
  const agregarArchivo = () => {
    if (!nuevaRuta.trim()) {
      setError('Ingrese una ruta válida');
      return;
    }

    if (archivos.some(a => a.ruta === nuevaRuta)) {
      setError('Esta ruta ya existe');
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
      <h2>Monitor de Servidores</h2>
      
      {/* Formulario */}
      <div className="agregar-archivo">
        <input
          type="text"
          value={nuevaRuta}
          onChange={(e) => setNuevaRuta(e.target.value)}
          placeholder="Ej: servidor1.log"
        />
        <input
          type="number"
          min="1"
          value={nuevoIntervalo}
          onChange={(e) => setNuevoIntervalo(Math.max(1, e.target.valueAsNumber || 5))}
        />
        <button onClick={agregarArchivo}>
          Agregar Servidor
        </button>
      </div>

      {/* Tabla de servidores */}
      <div className="lista-archivos">
        {archivos.length === 0 ? (
          <p>No hay servidores configurados</p>
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
              {archivos.map((archivo) => (
                <tr key={archivo.ruta}>
                  <td>{archivo.ruta}</td>
                  <td>
                    <input
                      type="number"
                      min="1"
                      value={archivo.intervalo}
                      onChange={(e) => {
                        const nuevoIntervalo = Math.max(1, e.target.valueAsNumber || 5);
                        setArchivos(prev => prev.map(a => 
                          a.ruta === archivo.ruta ? { ...a, intervalo: nuevoIntervalo } : a
                        ));
                      }}
                    />
                  </td>
                  <td>
                    <span className={`estado ${archivo.activo ? 'activo' : ''}`}>
                      {archivo.activo ? '▶ MONITOREANDO' : '⏸ DETENIDO'}
                    </span>
                  </td>
                  <td>
                    <button
                      onClick={() => toggleProcesamiento(archivo.ruta, archivo.intervalo)}
                      className={archivo.activo ? 'detener' : 'iniciar'}
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

      {error && (
        <div className="error" onClick={() => setError(null)}>
          ❌ {error}
        </div>
      )}
    </div>
  );
};

export default MultiLogProcessor;
