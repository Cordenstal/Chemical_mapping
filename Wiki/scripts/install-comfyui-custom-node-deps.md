# ComfyUI Custom Node Dependency Installer

- Canonical source path: `C:\Users\Willaim\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable\install-comfyui-custom-node-deps.ps1`
- Source type: PowerShell automation
- Purpose: recursively scan the sibling `ComfyUI\custom_nodes` tree and install package dependencies for each node with progress logging.
- Usage:
  - Run the script from `C:\Users\Willaim\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable` or pass `-CustomNodesRoot` for a different layout.
  - Override `-PythonExe` when the portable Python executable is not auto-detected.
- Behavior:
  - Finds `requirements*.txt` files recursively and installs them with `python -m pip install -r`.
  - Runs any discovered `install.py` scripts from their own directories.
  - Writes a timestamped log file next to the script unless `-LogPath` is supplied.
- Debugging notes:
  - Each manifest is logged before and after execution.
  - Failures are collected and reported at the end so a single bad node does not hide later issues.
