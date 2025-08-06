{
  lib,
  python3Packages,
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

  pyprojectToPythonPackage =
    pyproject:
    let
      requires = map parseDependency pyproject.build-system.requires;
      dependencies = map parseDependency pyproject.project.dependencies;
      args =
        (lib.genAttrs (
          [ "buildPythonApplication" ] ++ (map ({ name, ... }: name) (requires ++ dependencies))
        ))
          (x: false);
    in
    lib.setFunctionArgs (
      python3Packages:
      let
        resolvePkgs =
          { name, extras }:
          let
            pkg = python3Packages.${name};
          in
          [ pkg ] ++ map (name: pkg.optional-dependencies.${name}) extras;
      in

      python3Packages.buildPythonApplication {
        name = pyproject.project.name;
        version = pyproject.project.version;
        src = ./.;
        pyproject = true;
        nativeBuildInputs = lib.flatten (map resolvePkgs requires);
        propagatedBuildInputs = lib.flatten (map resolvePkgs dependencies);
        passthru.pyproject = pyproject;
      }
    ) args;

in
python3Packages.callPackage (pyprojectToPythonPackage pyproject) { }
