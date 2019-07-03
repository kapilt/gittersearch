resource "aws_iam_role_policy" "app_role" {
  role = "${aws_iam_role.default-role.name}"

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
      "Action": ["kms:Decrypt"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["ssm:GetParameter"],
      "Resource": ["${aws_ssm_parameter.gitter_token.arn}"]
    },
    {
      "Effect": "Allow",
      "Action": ["lambda:*"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:*"],
      "Resource": ["${aws_dynamodb_table.gitter.arn}"]
    },
    {
      "Effect": "Allow",
      "Action": [
          "logs:CreateLogGroup",
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
