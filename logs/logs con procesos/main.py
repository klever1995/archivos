-------------------------prueba del agente de openai--------------archivo main.py
import os
import sys

# Script de prueba para el agente de OpenAI (análisis de logs de error)
os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from consumos.consulta_ia_openai import Consulta_ia_openai

consulta = Consulta_ia_openai()

log_error = """
2023-11-15 14:30:22 [ERROR] [nginx] 502 Bad Gateway
upstream prematurely closed connection while reading response header
"""

respuesta = consulta.interpretar_logs(log_error)
print(respuesta)
