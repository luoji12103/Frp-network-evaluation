$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
& $python -m controller.webui --host 127.0.0.1 --port 8765 --open-browser @args
