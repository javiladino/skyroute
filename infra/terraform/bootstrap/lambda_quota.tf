# La cuota "Concurrent executions" de Lambda en eu-west-3 vale 10 y AWS exige
# dejar 10 sin reservar, por lo que no se puede fijar
# reserved_concurrent_executions = 1 (Ruling Implement decisions, topic
# generator-landing). Se pide subirla a 1000.
#
# AWS aprueba la petición de forma asíncrona: puede tardar o ser rechazada, y
# el apply no espera a la aprobación. Bajar el valor no es posible por API.
resource "aws_servicequotas_service_quota" "lambda_concurrent_executions" {
  service_code = "lambda"
  quota_code   = "L-B99A9384"
  value        = 1000
}
