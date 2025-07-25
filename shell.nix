let
  pkgs = import <nixpkgs> { };
  pythonEnv = pkgs.python3.withPackages(ps: [ ps.requests ]);
in pkgs.mkShell {
  packages = [
    pkgs.remarshal
    pythonEnv
  ];
}
