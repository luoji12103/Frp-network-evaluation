$ErrorActionPreference = "Stop"

$python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
& $python -m controller.quickstart --mode client-windows @args
