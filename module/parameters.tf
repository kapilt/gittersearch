resource "aws_ssm_parameter" "gitter_token" {
  name  = "/gittersearch/token"
  type  = "String"
  value = var.gitter_token
}
