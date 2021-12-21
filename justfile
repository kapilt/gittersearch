
_:
   @just -l


project := "cloud-custodian/cloud-custodian"


# run linters
lint:
   black hubhud
   flake8 hubhud

# run unit tests
test:
   pytest tests


sync db="sqlite:///data.db":
   python -m hubhud.cli sync gitter -f {{db}} -p {{project}}
#   python -m hubhud.cli sync github -f {{db}} -p {{project}}

