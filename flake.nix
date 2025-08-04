{
  description = "Hello world flake using uv2nix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/release-25.05";
    #nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    flake-utils.url = "github:numtide/flake-utils";

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      flake-utils,
      ...
    }:
    let
      inherit (nixpkgs) lib;

    in
      # Import flake-utils in inputs first
      

      flake-utils.lib.eachSystem flake-utils.lib.allSystems (system: 
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;

        # Move the pythonSet definition here
        cc-proxy-module = pkgs.callPackage ./cc-proxy.nix {
          inherit pkgs;
          inherit uv2nix;
          inherit pyproject-nix;
          inherit pyproject-build-systems;
        };
      in {
        packages.default = cc-proxy-module.cc-proxy; 

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/cc-proxy";
        };

        formatter = pkgs.nixpkgs-fmt;

        devShells = {
          impure = pkgs.mkShell {
            packages = [
              python
              pkgs.uv
            ];
            env = {
              UV_PYTHON_DOWNLOADS = "never";
              UV_PYTHON = python.interpreter;
            } // lib.optionalAttrs pkgs.stdenv.isLinux {
              LD_LIBRARY_PATH = lib.makeLibraryPath pkgs.pythonManylinuxPackages.manylinux1;
            };
            shellHook = ''
              unset PYTHONPATH
            '';
          };
          nv2nix = cc-proxy-module.uv2nixShell;

        };
      });
}
