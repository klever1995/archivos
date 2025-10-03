import React, { useEffect, useState } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import MultiLogProcessor from './MultiLogProcessor';
import TableroLogs from "./TableroLogs";
import { LogsProvider } from "./LogsContext"; 
import { WebSocketProvider } from "./WebsocketContext"; 
import { ModalLogsCacheProvider } from "./ModalLogsContext"; 
import "./App.css";

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Si ya está marcado como "desde menú", no verificar de nuevo
    const fromMenu = sessionStorage.getItem("fromMenu");
    if (fromMenu === "true") {
      setUser({}); // asumimos usuario logueado, puedes guardar info mínima
      setLoading(false);
      return;
    }

    // Verifica sesión con el backend del filtro solo si no viene del menú
    fetch("http://localhost:8001/api/auth/check", {
      credentials: "include", // envía cookies
    })
      .then(async (res) => {
        if (res.redirected) {
          window.location.href = res.url;
          return;
        }
        const data = await res.json();
        setUser(data);
        // Marcar que ya pasó verificación para próximas visitas en la misma sesión
        sessionStorage.setItem("fromMenu", "true");
      })
      .catch((err) => {
        console.error("Error al verificar sesión:", err);
        window.location.href = "http://localhost:8000/api/auth/login?redirect=http://localhost:3001";
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div>Cargando...</div>;
  }

  return (
    <Router>
      <WebSocketProvider idEmpresa={1}>
        <ModalLogsCacheProvider> 
          <LogsProvider>
            <Routes>
              <Route path="/tablero-logs" element={<TableroLogs />} />
              <Route path="/" element={<MultiLogProcessor />} />
            </Routes>
          </LogsProvider>
        </ModalLogsCacheProvider> 
      </WebSocketProvider>
    </Router>
  );
}

export default App;
