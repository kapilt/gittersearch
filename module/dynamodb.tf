resource "aws_dynamodb_table" "gitter" {
  name         = "Gitter"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ResourceId"

  attribute {
    name = "ResourceId"
    type = "S"
  }

}
