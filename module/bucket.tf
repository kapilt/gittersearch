resource "aws_s3_bucket" "gitter_archive" {
  bucket = "gitter-archive"
  acl    = "private"
}
