resource "aws_ssm_parameter" "gitter_token" {
  name  = "/gittersearch/token"
  type  = "SecureString"
  value = var.gitter_token
}
