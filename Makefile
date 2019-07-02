


deploy:
	chalice package --pkg-format=terraform module
	cd module && terraform apply -auto-approve
