import React, { useState, useEffect } from 'react';
import './ModalEstilos.css'; 

const ModalDepartamentos = ({ idEmpresa, onClose }) => {
  const [departamentos, setDepartamentos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [modoEdicion, setModoEdicion] = useState(false);
  const [departamentoActual, setDepartamentoActual] = useState({
    idDepartamento: null,
    nombre: ''
  });

// Obtener departamentos
  const fetchDepartamentos = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/departamentos/?idEmpresa=${idEmpresa}`);
      if (!response.ok) throw new Error('Error al obtener departamentos');
      const data = await response.json();
      setDepartamentos(data.data);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { value } = e.target;
    setDepartamentoActual(prev => ({ ...prev, nombre: value }));
  };

// Crear nuevo departamento
  const handleCrear = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('http://localhost:8000/api/departamentos/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          nombre: departamentoActual.nombre,
          idEmpresa
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al crear departamento');
      }

      await fetchDepartamentos();
      setShowForm(false);
      setDepartamentoActual({
        idDepartamento: null,
        nombre: ''
      });
    } catch (err) {
      setError(err.message);
    }
  };

// Actualizar departamento
  const handleActualizar = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch(`http://localhost:8000/api/departamentos/${departamentoActual.idDepartamento}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          nombre: departamentoActual.nombre
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al actualizar departamento');
      }

      await fetchDepartamentos();
      setShowForm(false);
      setModoEdicion(false);
      setDepartamentoActual({
        idDepartamento: null,
        nombre: ''
      });
    } catch (err) {
      setError(err.message);
    }
  };

// Eliminar departamento
  const handleEliminar = async (idDepartamento) => {

    const departamento = departamentos.find(d => d.idDepartamento === idDepartamento);

    if (departamento && departamento.totalServidores > 0) {
      alert("No se puede eliminar: tiene servidores asignados");
      return;
    }
  
    if (!window.confirm('¿Estás seguro de eliminar este departamento?')) return;
  
    try {
      const response = await fetch(`http://localhost:8000/api/departamentos/${idDepartamento}`, {
        method: 'DELETE',
      });
  
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al eliminar departamento');
      }
  
      await fetchDepartamentos();
    } catch (err) {
      setError(err.message);
    }
  };

// Abrir formulario para editar
  const handleEditar = (departamento) => {
    setDepartamentoActual({
      idDepartamento: departamento.idDepartamento,
      nombre: departamento.nombre
    });
    setModoEdicion(true);
    setShowForm(true);
  };

// Cancelar edición/creación
  const handleCancelar = () => {
    setShowForm(false);
    setModoEdicion(false);
    setDepartamentoActual({
      idDepartamento: null,
      nombre: ''
    });
  };

  useEffect(() => {
    fetchDepartamentos();
  }, [idEmpresa]);

  if (loading) return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-contenedor" onClick={e => e.stopPropagation()}>
        <button className="modal-cerrar" onClick={onClose}>×</button>
        <div className="cargando">Cargando departamentos...</div>
      </div>
    </div>
  );

  if (error) return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-contenedor" onClick={e => e.stopPropagation()}>
        <button className="modal-cerrar" onClick={onClose}>×</button>
        <div className="error-modal">Error: {error}</div>
      </div>
    </div>
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-contenedor" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Gestión de Departamentos</h2>
          <div className="modal-header-actions">
            <button 
              className="btn btn-primario" 
              onClick={() => setShowForm(true)}
              disabled={showForm}
            >
              + Nuevo Departamento
            </button>
            <button className="modal-cerrar" onClick={onClose}>×</button>
          </div>
        </div>

        {showForm && (
          <div className="modal-formulario">
            <h3>{modoEdicion ? 'Editar Departamento' : 'Nuevo Departamento'}</h3>
            <form onSubmit={modoEdicion ? handleActualizar : handleCrear}>
              <div className="modal-form-group">
                <label>Nombre del Departamento:</label>
                <input
                  type="text"
                  value={departamentoActual.nombre}
                  onChange={handleInputChange}
                  required
                  placeholder="Ej: TI, Finanzas, Logística"
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

        <div className="modal-contenido">
          <div className="modal-tabla-contenedor">
            <table className="modal-tabla">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nombre</th>
                  <th>Fecha Registro</th>
                  <th>Total Servidores</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {departamentos.map((departamento) => (
                  <tr key={departamento.idDepartamento}>
                    <td>{departamento.idDepartamento}</td>
                    <td>{departamento.nombre}</td>
                    <td>
                      {new Date(departamento.fechaRegistro).toLocaleString('es-ES', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </td>
                    <td>{departamento.totalServidores || 0}</td>
                    <td>
                      <button 
                        onClick={() => handleEditar(departamento)}
                        className="btn btn-secundario"
                        style={{marginRight: '8px'}}
                      >
                        Editar
                      </button>
                      <button 
                        onClick={() => handleEliminar(departamento.idDepartamento)}
                        className="btn btn-peligro"
                        disabled={departamento.totalServidores > 0}
                        title={departamento.totalServidores > 0 ? 
                          'No se puede eliminar: tiene servidores asignados' : 'Eliminar departamento'}
                      >
                        Eliminar
                      </button>
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

export default ModalDepartamentos;
