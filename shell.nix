let
  pkgs = import <nixpkgs> { };
  pythonEnv = pkgs.python3.withPackages(ps: [ ps.requests ]);
in pkgs.mkShell {
  packages = with pkgs; [
    remarshal
    nodejs-slim_20
    pyright
    pythonEnv
  ];
}
