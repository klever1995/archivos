import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from flask import Flask
from config import db, init_app
from modelo.loDepartamentos import loDepartamentos
from modelo.loServidores import loServidores
from modelo.asEmpresa import asEmpresa

app = Flask(__name__)
init_app(app)  # <-- inicializa la app con la configuración de SQLAlchemy

with app.app_context():
    # Suponiendo que ya existe la empresa con idEmpresa=1
    # Crear un departamento
    depto = loDepartamentos(nombre="Contabilidad2r", idEmpresa=1)
    db.session.add(depto)
    db.session.commit()  # commit para obtener depto.idDepartamento

    # Crear un servidor asociado al departamento
    servidor = loServidores(
        nombreServidor="Server1",
        idEmpresa=1,
        idDepartamento=depto.idDepartamento,
        ruta="C:/ruta/del/servidor425er",  # <-- obligatorio
        activo=0,
        idAccesoRemoto=None
    )
    db.session.add(servidor)
    db.session.commit()  # commit para guardar el servidor

    # Verificar relaciones
    print("Servidor pertenece al departamento:", servidor.departamentoAsociado.nombre)


