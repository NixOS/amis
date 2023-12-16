{ buildPythonApplication
, python3Packages
}:

let pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
in
buildPythonApplication {
  pname = pyproject.project.name;
  version = pyproject.project.version;
  src = ./.;
  pyproject = true;

  nativeBuildInputs =
    map (name: python3Packages.${name}) pyproject.build-system.requires;

  propagatedBuildInputs =
    map (name: python3Packages.${name}) pyproject.project.dependencies;

}
