


resource "aws_kinesis_firehose_delivery_stream" "gitter_index" {
  name        = "gitter-s3-archive"
  destination = "elasticsearch"

  s3_configuration {
    prefix = "spool"
    role_arn = "${aws_iam_role.gitter_firehose.arn}"
    bucket_arn = "${aws_s3_bucket.gitter_archive.arn}"
    compression_format = "GZIP"
  }    
  
  elasticsearch_configuration {
    domain_arn = "${aws_elasticsearch_domain.gitter.arn}"
    role_arn   = "${aws_iam_role.gitter_firehose.arn}"
    index_name = "gitter"
    type_name  = "messages"
    s3_backup_mode = "AllDocuments"
  }


  # Wait until access has been granted before creating the firehose
  # delivery stream.
  depends_on = ["aws_iam_role_policy.firehose_role"]
}


resource "aws_iam_role_policy" "firehose_role" {
  role = "${aws_iam_role.gitter_firehose.name}"

  policy = <<EOF
{
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Resource": ["${aws_s3_bucket.gitter_archive.arn}", "${aws_s3_bucket.gitter_archive.arn}/*"]
    },
    {
      "Effect": "Allow",
      "Action": ["es:*"],
      "Resource": ["${aws_elasticsearch_domain.gitter.arn}", "${aws_elasticsearch_domain.gitter.arn}/*"]
    },
    {
      "Effect": "Allow",
      "Action": [
          "logs:PutLogEvents"
      ],
      "Resource": [
          "arn:aws:logs:*:*:log-group:*:log-stream:*"
      ]
    }
  ]
}
EOF
}

resource "aws_iam_role" "gitter_firehose" {
  name = "gitter-delivery"

  tags = var.resource_tags
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "firehose.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}
