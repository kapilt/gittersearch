variable "resource_tags" {
  type = "map"
  default = {
    "App" = "GitterSearch"
  }
}

variable "gitter_token" {
  type = "string"
}
