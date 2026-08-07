param(
    [string]$ProjectPath = "C:\it-centre-rms\app",
    [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $ProjectPath
& "$ProjectPath\.venv\Scripts\waitress-serve.exe" --listen="127.0.0.1:$Port" it_centre_rms.wsgi:application
