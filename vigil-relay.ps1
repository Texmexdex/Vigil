# Vigil home relay
# Starts the relay on this computer, opens a Cloudflare quick tunnel to it, and tells the
# Vigil Worker the tunnel's current address. Close this window (or reboot) to stop it.
# Usage:  powershell -ExecutionPolicy Bypass -File vigil-relay.ps1

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 5600
$log  = Join-Path $env:TEMP 'vigil-tunnel.log'
$out  = Join-Path $env:TEMP 'vigil-relay.log'
"$(Get-Date -Format s) starting" | Set-Content $out

# 1. the relay, answering /relay only
Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
$relay = Start-Process -PassThru -WindowStyle Hidden python -ArgumentList "`"$here\serve.py`"", $port, '--relay-only'

# 2. the tunnel
Remove-Item $log -ErrorAction SilentlyContinue
$tunnel = Start-Process -PassThru -WindowStyle Hidden cloudflared -ArgumentList 'tunnel', '--no-autoupdate', '--url', "http://127.0.0.1:$port", '--logfile', $log

# 3. wait for its address
$url = $null
for ($i = 0; $i -lt 60 -and -not $url; $i++) {
  Start-Sleep 1
  if (Test-Path $log) { $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1; if ($m) { $url = $m.Matches[0].Value } }
}
if (-not $url) { "$(Get-Date -Format s) tunnel did not start" | Add-Content $out; exit 1 }

# 4. tell the Worker (key kept in .relay-key beside this script, never committed)
$key = (Get-Content -Raw (Join-Path $here '.relay-key')).Trim()
$ok = $false
for ($try = 1; $try -le 8 -and -not $ok; $try++) {   # right after sign-in the network can take a moment
  try { $r = Invoke-RestMethod -Method Post -Uri 'https://vigil.texmexdex11.workers.dev/register' -Headers @{ 'x-vigil-key' = $key } -Body $url -TimeoutSec 20; "$r" | Add-Content $out; $ok = $true }
  catch { "$(Get-Date -Format s) register attempt $try failed: $($_.Exception.Message)" | Add-Content $out; Start-Sleep 15 }
}
"$(Get-Date -Format s) tunnel $url  registered=$ok" | Add-Content $out
Write-Host "Vigil home relay is live at $url"
Write-Host 'Leave this running. Helicopters stop updating if it is closed.'
Wait-Process -Id $tunnel.Id
Stop-Process -Id $relay.Id -ErrorAction SilentlyContinue
