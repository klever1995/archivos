import React, { useState, useEffect } from 'react';
import './ModalEstilos.css'; 

const ModalAccesos = ({ idEmpresa, onClose }) => {
  const [accesos, setAccesos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [modoEdicion, setModoEdicion] = useState(false);
  const [accesoActual, setAccesoActual] = useState({
    idAcceso: null,
    usuario: '',
    contrasena: '',
    hostname: ''
  });
  const [servidoresVinculados, setServidoresVinculados] = useState({});

// Obtener los accesos remotos:
  const fetchAccesos = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/accesos-remotos/?idEmpresa=${idEmpresa}`);
      if (!response.ok) throw new Error('Error al obtener accesos');
      const data = await response.json();
      setAccesos(data.data);
      
// Cuenta los servidores vinculados
      const conteoServidores = {};
      for (const acceso of data.data) {
        const res = await fetch(`http://localhost:8000/api/accesos-remotos/contar-servidores?idAccesoRemoto=${acceso.idAcceso}`);
        const countData = await res.json();
        conteoServidores[acceso.idAcceso] = countData.total;
      }
      setServidoresVinculados(conteoServidores);
      
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setAccesoActual(prev => ({ ...prev, [name]: value }));
  };

// Crea nuevo acceso
  const handleCrear = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('http://localhost:8000/api/accesos-remotos/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...accesoActual,
          idEmpresa
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Error al crear acceso');
      }

      await fetchAccesos();
      setShowForm(false);
      setAccesoActual({
        idAcceso: null,
        usuario: '',
        contrasena: '',
        hostname: ''
      });
    } catch (err) {
      setError(err.message);
    }
  };

// Actualizar acceso existente
  const handleActualizar = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch(`http://localhost:8000/api/accesos-remotos/${accesoActual.idAcceso}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          usuario: accesoActual.usuario,
          hostname: accesoActual.hostname,
          contrasena: accesoActual.contrasena || undefined 
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al actualizar acceso');
      }

      await fetchAccesos();
      setShowForm(false);
      setModoEdicion(false);
      setAccesoActual({
        idAcceso: null,
        usuario: '',
        contrasena: '',
        hostname: ''
      });
    } catch (err) {
      setError(err.message);
    }
  };

// Elimina un acceso remoto
  const handleEliminarAcceso = async (idAcceso) => {
    const count = servidoresVinculados[idAcceso] || 0;
    
    if (!window.confirm(
      `¿Estás seguro de eliminar este acceso? ${count > 0 ? 
      `\n\nADVERTENCIA: Esto eliminará también los ${count} servidores vinculados y todos sus logs asociados.` : ''}`
    )) return;

    try {
      const response = await fetch(`http://localhost:8000/api/accesos-remotos/${idAcceso}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Error al eliminar acceso');
      }

      await fetchAccesos();
    } catch (err) {
      setError(err.message);
    }
  };

// Abrir formulario para editar
  const handleEditar = (acceso) => {
    setAccesoActual({
      idAcceso: acceso.idAcceso,
      usuario: acceso.usuario,
      contrasena: '',
      hostname: acceso.hostname
    });
    setModoEdicion(true);
    setShowForm(true);
  };

// Cancelar edición/creación
  const handleCancelar = () => {
    setShowForm(false);
    setModoEdicion(false);
    setAccesoActual({
      idAcceso: null,
      usuario: '',
      contrasena: '',
      hostname: ''
    });
  };

  useEffect(() => {
    fetchAccesos();
  }, [idEmpresa]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-contenedor" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Lista de Accesos Remotos</h2>
          <div className="modal-header-actions">
            <button 
              className="btn btn-primario" 
              onClick={() => setShowForm(true)}
              disabled={showForm}
            >
              + Nuevo Acceso
            </button>
            <button className="modal-cerrar" onClick={onClose}>×</button>
          </div>
        </div>
        
        {/* Formulario para agregar/editar accesos */}
        {showForm && (
          <div className="modal-formulario">
            <h3>{modoEdicion ? 'Editar Acceso' : 'Nuevo Acceso'}</h3>
            <form onSubmit={modoEdicion ? handleActualizar : handleCrear}>
              <div className="modal-form-group">
                <label>Usuario:</label>
                <input
                  type="text"
                  name="usuario"
                  value={accesoActual.usuario}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="modal-form-group">
                <label>Contraseña:</label>
                <input
                  type="password"
                  name="contrasena"
                  value={accesoActual.contrasena}
                  onChange={handleInputChange}
                  placeholder={modoEdicion ? "Dejar vacío para mantener la actual" : ""}
                  required={!modoEdicion}
                />
              </div>
              <div className="modal-form-group">
                <label>Hostname:</label>
                <input
                  type="text"
                  name="hostname"
                  value={accesoActual.hostname}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="modal-form-buttons">
                <button type="submit" className="btn btn-primario">
                  {modoEdicion ? 'Actualizar' : 'Guardar'}
                </button>
                <button type="button" className="btn btn-secundario" onClick={handleCancelar}>
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        )}
        
        {/* Tabla de accesos existentes */}
        <div className="modal-contenido">
          <div className="modal-tabla-contenedor">
            <table className="modal-tabla">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Usuario</th>
                  <th>Contraseña</th>
                  <th>Hostname</th>
                  <th>Fecha Registro</th>
                  <th>Servidores</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {accesos.map((acceso) => (
                  <tr key={acceso.idAcceso}>
                    <td>{acceso.idAcceso}</td>
                    <td>{acceso.usuario}</td>
                    <td>••••••••</td>
                    <td>{acceso.hostname}</td>
                    <td>
                      {new Date(acceso.fechaRegistro).toLocaleString('es-ES', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </td>
                    <td>{servidoresVinculados[acceso.idAcceso] || 0}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button 
                          onClick={() => handleEditar(acceso)}
                          className="btn btn-secundario"
                        >
                          Editar
                        </button>
                        <button 
                          onClick={() => handleEliminarAcceso(acceso.idAcceso)}
                          className="btn btn-peligro"
                        >
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ModalAccesos;
