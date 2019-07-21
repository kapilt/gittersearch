resource "aws_elasticsearch_domain" "gitter" {
  domain_name           = "gitter"
  elasticsearch_version = "6.7"

  cluster_config {
    instance_type = "t2.medium.elasticsearch"
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 10
  }
  
  snapshot_options {
    automated_snapshot_start_hour = 23
  }

  tags = var.resource_tags

}


resource "aws_elasticsearch_domain_policy" "gitter_access" {
  domain_name = "${aws_elasticsearch_domain.gitter.domain_name}"

  access_policies = <<POLICIES
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": "es:*",
            "Principal": {"AWS": "${aws_iam_role.default-role.arn}"},
            "Effect": "Allow",
            "Resource": "${aws_elasticsearch_domain.gitter.arn}/*"
        },
        {
            "Action": "es:*",
            "Principal": {"AWS": "${aws_iam_role.gitter_firehose.arn}"},
            "Effect": "Allow",
            "Resource": "${aws_elasticsearch_domain.gitter.arn}/*"
        },
        {
            "Action": "es:*",
            "Principal": {"AWS": "arn:aws:iam::619193117841:user/deputy"},
            "Effect": "Allow",
            "Resource": "${aws_elasticsearch_domain.gitter.arn}/*"
        },
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "*"
      },
      "Action": [
        "es:*"
      ],
      "Condition": {
        "IpAddress": {
          "aws:SourceIp": [
            "173.79.14.27"
          ]
        }
      },
      "Resource": "${aws_elasticsearch_domain.gitter.arn}/*"
    }
    ]
}
POLICIES
}
