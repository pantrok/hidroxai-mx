# Empaqueta lo mínimo para entrenar el LSTM en el LNS (local, Windows PowerShell 5.1 o 7).
#   código:   src/, scripts/xai_03_train_nets.py, scripts/xai_15_lstm_walk_forward.py,
#             pyproject.toml, hpc/lns/
#   insumos:  data/features/feature_table.parquet y data/processed/estaciones_hidrorivers.csv
#             (lo único que leen el entrenamiento y D.station_basins)
#   registro: PAQUETE.txt con el commit de git y el SHA-256 de cada archivo
# Salida: dist\lns\hidroxai_lns.tar.gz y hidroxai_lns.tar.gz.sha256 (formato de sha256sum -c).
# Uso, desde cualquier carpeta:  powershell -ExecutionPolicy Bypass -File hpc\lns\02_empaquetar.ps1

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$dist = Join-Path $repo "dist\lns"
$stage = Join-Path ([IO.Path]::GetTempPath()) "hidroxai_lns_stage"
$root = Join-Path $stage "hidroxai"
$utf8 = New-Object System.Text.UTF8Encoding $false

if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force $root, $dist | Out-Null

$items = @(
    @{ src = "src\hidroxai_mx"; dst = "src\hidroxai_mx" },
    @{ src = "scripts\xai_03_train_nets.py"; dst = "scripts\xai_03_train_nets.py" },
    @{ src = "scripts\xai_15_lstm_walk_forward.py"; dst = "scripts\xai_15_lstm_walk_forward.py" },
    @{ src = "pyproject.toml"; dst = "pyproject.toml" },
    @{ src = "hpc\lns"; dst = "hpc\lns" },
    @{ src = "data\features\feature_table.parquet"; dst = "data\features\feature_table.parquet" },
    @{ src = "data\processed\estaciones_hidrorivers.csv"; dst = "data\processed\estaciones_hidrorivers.csv" }
)
foreach ($it in $items) {
    $from = Join-Path $repo $it.src
    $to = Join-Path $root $it.dst
    if (-not (Test-Path $from)) { throw "No existe $from" }
    New-Item -ItemType Directory -Force (Split-Path $to) | Out-Null
    Copy-Item -Recurse -Force $from $to
}
Get-ChildItem -Recurse -Directory $root -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -File $root -Include "*.pyc" | Remove-Item -Force

# Fin de línea LF en los scripts de shell y de SLURM.
Get-ChildItem -Recurse -File (Join-Path $root "hpc\lns") -Include "*.sh", "*.sbatch", "*.def" | ForEach-Object {
    $text = [IO.File]::ReadAllText($_.FullName) -replace "`r`n", "`n"
    [IO.File]::WriteAllText($_.FullName, $text, $utf8)
}

# Registro del paquete: commit, archivos con cambios sin commit y SHA-256 por archivo.
Push-Location $repo
$commit = (git rev-parse HEAD).Trim()
$dirty = git status --porcelain -- src scripts/xai_03_train_nets.py scripts/xai_15_lstm_walk_forward.py pyproject.toml hpc/lns
Pop-Location
$lines = @("# Paquete hidroxai_lns · $(Get-Date -Format s)", "commit: $commit")
if ($dirty) { $lines += "AVISO: cambios sin commit en el código empaquetado:"; $lines += ($dirty | ForEach-Object { "  $_" }) }
else { $lines += "codigo_sin_cambios_respecto_al_commit: si" }
$lines += "sha256:"
Get-ChildItem -Recurse -File $root | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($root.Length + 1).Replace("\", "/")
    $lines += "  $((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower())  $rel"
}
[IO.File]::WriteAllText((Join-Path $root "PAQUETE.txt"), (($lines -join "`n") + "`n"), $utf8)

$tgz = Join-Path $dist "hidroxai_lns.tar.gz"
if (Test-Path $tgz) { Remove-Item -Force $tgz }
& tar -czf $tgz -C $stage hidroxai
if ($LASTEXITCODE -ne 0) { throw "tar falló" }
$hash = (Get-FileHash $tgz -Algorithm SHA256).Hash.ToLower()
[IO.File]::WriteAllText("$tgz.sha256", "$hash  hidroxai_lns.tar.gz`n", $utf8)
Remove-Item -Recurse -Force $stage

"Listo: $tgz  ($([math]::Round((Get-Item $tgz).Length / 1MB, 1)) MB)"
"sha256: $hash"
"commit: $commit"
if ($dirty) { "AVISO: el código empaquetado tiene cambios sin commit (ver PAQUETE.txt)." }
