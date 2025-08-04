{pkgs, uv2nix, pyproject-nix, pyproject-build-systems}:

let
  lib = pkgs.lib;
  python = pkgs.python312;
  inherit (pkgs.callPackages pyproject-nix.build.util { }) mkApplication;

      # Load a uv workspace from a workspace root.
      # Uv2nix treats all uv projects as workspace projects.
  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      # Create package overlay from workspace.
      overlay = workspace.mkPyprojectOverlay {
        # Prefer prebuilt binary wheels as a package source.
        # Sdists are less likely to "just work" because of the metadata missing from uv.lock.
        # Binary wheels are more likely to, but may still require overrides for library dependencies.
        sourcePreference = "wheel"; # or sourcePreference = "sdist";
        # Optionally customise PEP 508 environment
        # environ = {
        #   platform_release = "5.10.65";
        # };
      };

      # Extend generated overlay with build fixups
      #
      # Uv2nix can only work with what it has, and uv.lock is missing essential metadata to perform some builds.
      # This is an additional overlay implementing build fixups.
      # See:
      # - https://pyproject-nix.github.io/uv2nix/FAQ.html
      pyprojectOverrides = _final: _prev: {
        # Implement build fixups here.
        # Note that uv2nix is _not_ using Nixpkgs buildPythonPackage.
        # It's using https://pyproject-nix.github.io/pyproject.nix/build.html
      };
  # Move the pythonSet definition here
  pythonSet = (pkgs.callPackage pyproject-nix.build.packages {
    inherit python;
  }).overrideScope (
    lib.composeManyExtensions [
      pyproject-build-systems.overlays.default
      overlay
      pyprojectOverrides
    ]
  );
  virtualenv = pythonSet.mkVirtualEnv "cc-proxy-env" workspace.deps.default;
in 
  {
    cc-proxy = mkApplication {
    venv = virtualenv;
    package = pythonSet.cc-proxy;
  };

  uv2nixShell = let
            editableOverlay = workspace.mkEditablePyprojectOverlay {
              root = "$REPO_ROOT";
            };

            editablePythonSet = pythonSet.overrideScope (
              lib.composeManyExtensions [
                editableOverlay
                (final: prev: {
                  hello-world = prev.hello-world.overrideAttrs (old: {
                    src = lib.fileset.toSource {
                      root = old.src;
                      fileset = lib.fileset.unions [
                        # # (old.src + "/pyproject.toml")
                        # (old.src + "/README.md") 
                      ];
                    };
                    nativeBuildInputs = old.nativeBuildInputs ++ final.resolveBuildSystem {
                      editables = [ ];
                    };
                  });
                })
              ]
            );
            virtualenv = editablePythonSet.mkVirtualEnv "cc-proxy-dev-env" workspace.deps.all;
          in pkgs.mkShell {
            packages = [ virtualenv pkgs.uv ];
            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            };
            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
            '';
          };
}

