import React, { useState, useEffect, useRef } from 'react';
import './estilosConfig.css';

const MultiLogProcessor = () => {
  const [servidores, setServidores] = useState([]);
  const [error, setError] = useState(null);
  const [nuevaRuta, setNuevaRuta] = useState('');
  const [nuevoIntervalo, setNuevoIntervalo] = useState(5);
  const intervalosRef = useRef({});

  // Cargar servidores al iniciar con persistencia de estado
  useEffect(() => {
    const cargarServidores = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/servidores/?idEmpresa=1');
        if (!response.ok) throw new Error('Error al cargar servidores');
        const data = await response.json();
        
        // Recuperar estados activos desde localStorage
        const servidoresGuardados = JSON.parse(localStorage.getItem('servidoresConfig')) || {};
        
        setServidores(data.resultados.map(s => ({
          idServidor: s.id_servidor,
          ruta: s.ruta,
          intervalo: servidoresGuardados[s.id_servidor]?.intervalo || nuevoIntervalo,
          activo: servidoresGuardados[s.id_servidor]?.activo || false
        })));

        // Reiniciar intervalos para los servidores que estaban activos
        data.resultados.forEach(s => {
          const config = servidoresGuardados[s.id_servidor];
          if (config?.activo) {
            intervalosRef.current[s.id_servidor] = setInterval(
              () => procesarServidor(s.id_servidor, s.ruta),
              config.intervalo * 60 * 1000
            );
          }
        });
      } catch (err) {
        setError(err.message);
      }
    };
    cargarServidores();
  }, []);

  // Guardar configuración cuando cambia
  useEffect(() => {
    if (servidores.length > 0) {
      const configToSave = servidores.reduce((acc, s) => {
        acc[s.idServidor] = { intervalo: s.intervalo, activo: s.activo };
        return acc;
      }, {});
      localStorage.setItem('servidoresConfig', JSON.stringify(configToSave));
    }
  }, [servidores]);

  // Procesar un servidor individual (sin cambios)
  const procesarServidor = async (idServidor, ruta) => {
    try {
      const formData = new FormData();
      formData.append('nombre_archivo', ruta);
      formData.append('idServidor', idServidor);

      const response = await fetch('http://localhost:8000/procesar-log/', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error(await response.text());
      return await response.json();
    } catch (err) {
      console.error(`Error en ${ruta}:`, err);
      setError(`Fallo en ${ruta}: ${err.message}`);
      throw err;
    }
  };

  // Toggle procesamiento con persistencia
  const toggleProcesamiento = async (idServidor, ruta, intervalo) => {
    const estaActivo = intervalosRef.current[idServidor];
    
    if (!estaActivo) {
      try {
        await procesarServidor(idServidor, ruta);
        intervalosRef.current[idServidor] = setInterval(
          () => procesarServidor(idServidor, ruta),
          intervalo * 60 * 1000
        );
      } catch (err) {
        return; // No cambiamos el estado si falla
      }
    } else {
      clearInterval(intervalosRef.current[idServidor]);
      delete intervalosRef.current[idServidor];
    }

    setServidores(prev => prev.map(s => 
      s.idServidor === idServidor ? { ...s, activo: !estaActivo } : s
    ));
  };

  // Agregar nuevo servidor con persistencia
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

  // Limpieza al desmontar
  useEffect(() => {
    return () => {
      Object.values(intervalosRef.current).forEach(clearInterval);
    };
  }, []);

  return (
    <div className="multi-log-container">
      <h2>Monitor de Servidores</h2>
      
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
                  </td>
                  <td>
                    <button
                      onClick={() => toggleProcesamiento(
                        servidor.idServidor,
                        servidor.ruta,
                        servidor.intervalo
                      )}
                      className={servidor.activo ? 'detener' : 'iniciar'}
                    >
                      {servidor.activo ? 'Detener' : 'Iniciar'}
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
