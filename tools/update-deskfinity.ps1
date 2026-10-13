# Replace Deskfinity.exe in this folder with the latest build and restart it.
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $dir 'Deskfinity.exe'
$new = "$exe.new"
$url = 'https://github.com/Zeghreit/Deskfinity/releases/download/dev/Deskfinity.exe'

Write-Host "Downloading the latest Deskfinity build..."
Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $new

# Stop only the copy running from this folder, by PID (a one-file exe runs
# as two processes with the same path).
$running = Get-CimInstance Win32_Process -Filter "Name='Deskfinity.exe'" |
    Where-Object { $_.ExecutablePath -and ($_.ExecutablePath -ieq $exe) }
foreach ($p in $running) {
    Write-Host "Stopping Deskfinity (PID $($p.ProcessId))"
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

for ($i = 0; $i -lt 20; $i++) {       # wait until Windows lets go of the file
    try {
        if (Test-Path $exe) { Move-Item -Force $exe "$exe.old" }
        break
    } catch { Start-Sleep -Milliseconds 300 }
}
Move-Item -Force $new $exe
Start-Process -FilePath $exe
Write-Host "Updated and restarted. Previous version kept as Deskfinity.exe.old"
Start-Sleep -Seconds 2
