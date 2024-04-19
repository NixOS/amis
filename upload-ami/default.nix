{ buildPythonApplication
, python3Packages
, lib
}:

let pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
in
buildPythonApplication {
  pname = pyproject.project.name;
  version = pyproject.project.version;
  src = ./.;
  pyproject = true;
  nativeBuildInputs =
    map (name: python3Packages.${name}) pyproject.build-system.requires ++ [
      python3Packages.mypy
      python3Packages.black
    ];

  propagatedBuildInputs =
    map (name: python3Packages.${name}) pyproject.project.dependencies;

  passthru.pyproject = pyproject;
}
