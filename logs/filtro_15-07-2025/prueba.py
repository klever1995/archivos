import os
from smbclient import open_file, register_session

# Autenticación
register_session("150.150.1.228", username="userlogs", password="P4ssw0rd")

ruta_archivo = r'\\150.150.1.228\logs\INTERNET\srv-jbx-liferay1\server.log'

try:
    # Lee y filtra líneas con ERROR (muestra las 5 primeras para prueba)
    with open_file(ruta_archivo, mode='r', encoding='utf-8') as f:
        errores = [linea.strip() for linea in f if 'ERROR' in linea]
    
    print(f"✅ Archivo accesible | {len(errores)} errores encontrados")
    print("\n".join(errores[:5]))  # Muestra solo 5 errores como prueba

except Exception as e:
    print(f"❌ Falló: {str(e)}")
