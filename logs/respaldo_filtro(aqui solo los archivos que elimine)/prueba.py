import os
import sys
from datetime import datetime

# Configuración de entorno
os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from consumos.consulta_ia_openai import Consulta_ia_openai

def analizar_error(log_error: str):
    try:
        consulta = Consulta_ia_openai()
        
        # Medir tiempo de respuesta
        inicio = datetime.now()
        respuesta = consulta.interpretar_logs(log_error)
        tiempo_respuesta = (datetime.now() - inicio).total_seconds()
        
        # Formatear salida
        print("\n🔍 Análisis de OpenAI:")
        print(respuesta)
        print(f"\n⏱️ Tiempo de respuesta: {tiempo_respuesta:.2f} segundos")
        
        return respuesta
        
    except Exception as e:
        print(f"\n❌ Error al consultar OpenAI: {str(e)}")
        return None

if __name__ == "__main__":
    log_ejemplo = """
    2023-11-15 14:30:22 [ERROR] [nginx] 502 Bad Gateway
    upstream prematurely closed connection while reading response header
    """
    
    analizar_error(log_ejemplo)
