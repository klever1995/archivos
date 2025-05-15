import os
import sys

# Script de prueba para el agente de OpenAI (análisis de logs de error)
os.environ['NO_PROXY'] = 'recursoazureopenaimupi.openai.azure.com'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from consumos.consulta_ia_openai import Consulta_ia_openai

consulta = Consulta_ia_openai()

log_error = """
ERROR [org.jboss.as.ejb3] (ajp-/150.150.1.192:8009-46) JBAS014268: Fallo en la transacción de llamado.: javax.ejb.EJBTransactionRolledbackException: result returns more than one elements
	at org.jboss.as.ejb3.tx.CMTTxInterceptor.handleInCallerTx(CMTTxInterceptor.java:161) [jboss-as-ejb3.jar:7.5.19.Final-redhat-2]
	at org.jboss.as.ejb3.tx.CMTTxInterceptor.invokeInCallerTx(CMTTxInterceptor.java:260) [jboss-as-ejb3.jar:7.5.19.Final-redhat-2]
	at org.jboss.as.ejb3.tx.CMTTxInterceptor.required(CMTTxInterceptor.java:333) [jboss-as-ejb3.jar:7.5.19.Final-redhat-2]
	at org.jboss.as.ejb3.tx.CMTTxInterceptor.processInvocation(CMTTxInterceptor.java:243) [jboss-as-ejb3.jar:7.5.19.Final-redhat-2]
	at org.jboss.invocation.InterceptorContext.proceed(InterceptorContext.java:288) [jboss-invocation.jar:1.1.3.Final-redhat-1]
	at org.jboss.as.ejb3.component.interceptors.CurrentInvocationContextInterceptor.processInvocation(CurrentInvocationContextInterceptor.java:41) [jboss-as-ejb3.jar:7.5.19.Final-redhat-...
"""

respuesta = consulta.interpretar_logs(log_error)
print(respuesta)
