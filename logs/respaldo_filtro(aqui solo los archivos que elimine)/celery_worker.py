import os
import sys
import socket
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config import db, init_app
from flask import Flask
from modelo.loAccesosremotos import loAccesosremotos
from modelo.asEmpresa import asEmpresa
from modelo.loServidores import loServidores  # Importa el modelo correcto

flask_app = Flask(__name__)
init_app(flask_app)

def main():
    try:
        hostname_actual = socket.gethostname()  # <-- Aquí el hostname automático
        print(f"🖥️ Hostname detectado: {hostname_actual}")

        with flask_app.app_context():
            # Buscar el acceso remoto con ese hostname (activo)
            acceso = (
                db.session.query(loAccesosremotos)
                .filter(loAccesosremotos.hostname == hostname_actual)
                .filter(loAccesosremotos.activo == 1)
                .first()
            )

            if not acceso:
                print("❌ No hay configuración para este host en la BD o no está activo")
                return

            # Contar servidores asociados a ese acceso remoto
            total_servidores = (
                db.session.query(loServidores)
                .filter(loServidores.idAccesoRemoto == acceso.idAcceso)
                .count()
            )

            print(f"🔢 Número de servidores asociados a {hostname_actual}: {total_servidores}")

            # Mostrar info adicional del acceso
            print(f"✅ Acceso configurado encontrado (Ruta: {acceso.rutaRemota})")
            if acceso.empresa:
                print(f"📄 Empresa asociada: {acceso.empresa.nombre}")
            else:
                print("⚠️ No se encontró información de empresa asociada")

    except Exception as e:
        print(f"🔥 Error crítico: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
