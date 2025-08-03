{
  buildPythonApplication,
  python,
  awscli2,
  opentofu,
  mypy,
  black,
  lib,
}:

let
  pyproject = builtins.fromTOML (builtins.readFile ./pyproject.toml);
  # str -> { name: str, extras: [str] }
  parseDependency =
    dep:
    let
      parts = lib.splitString "[" dep;
      name = lib.head parts;
      extras = lib.optionals (lib.length parts > 1) (
        lib.splitString "," (lib.removeSuffix "]" (builtins.elemAt parts 1))
      );
    in
    {
      name = name;
      extras = extras;
    };

  # { name: str, extras: [str] } -> [package]
  resolvePackages =
    dep:
    let
      inherit (parseDependency dep) name extras;
      package = python.pkgs.${name};
      optionalPackages = lib.flatten (map (name: package.optional-dependencies.${name}) extras);
    in
    [ package ] ++ optionalPackages;

in
buildPythonApplication {
  pname = pyproject.project.name;
  version = pyproject.project.version;
  src = ./.;
  pyproject = true;
  nativeBuildInputs = map (name: python.pkgs.${name}) pyproject.build-system.requires ++ [
    opentofu
    awscli2
    mypy
    black
  ];

  propagatedBuildInputs = lib.flatten (map resolvePackages pyproject.project.dependencies);

  checkPhase = ''
    mypy src
    black --check src
  '';

  passthru.pyproject = pyproject;
  passthru.parseDependency = parseDependency;
  passthru.resolvePackages = resolvePackages;

}
