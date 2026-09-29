param(
    [switch]$ResetDatabase,
    [switch]$BackupFirst,
    [switch]$Include2026LiveData,
    [switch]$SkipLapIngestion,
    [switch]$SkipTraining
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PlatformDir = Join-Path $RepoRoot "f1-platform"
$BackupDir = Join-Path $PlatformDir "backups"
$CompletedSeasons = "2021 2022 2023 2024 2025"
$CompletedSeasonList = @(2021, 2022, 2023, 2024, 2025)

function Run-Step {
    param(
        [string]$Name,
        [string]$Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    Write-Host $Command -ForegroundColor DarkGray

    Invoke-Expression $Command

    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Name"
    }
}

if (-not (Test-Path $PlatformDir)) {
    throw "Could not find f1-platform directory at: $PlatformDir"
}

Set-Location $PlatformDir

if ($BackupFirst) {
    New-Item -ItemType Directory -Force $BackupDir | Out-Null
    $Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $BackupPath = Join-Path $BackupDir "f1_db_backup_$Timestamp.dump"
    # Write binary output inside the container to avoid PowerShell redirection
    # changing dump bytes. Use the running database's configured credentials.
    $ContainerBackupPath = "/tmp/f1_db_backup_$Timestamp.dump"
    $BackupCommand = 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$1"'
    & docker compose exec -T db sh -c $BackupCommand sh $ContainerBackupPath
    if ($LASTEXITCODE -ne 0) { throw "Database backup failed." }
    & docker compose cp "db:$ContainerBackupPath" $BackupPath
    if ($LASTEXITCODE -ne 0) { throw "Could not copy database backup to $BackupPath" }
    & docker compose exec -T db rm -- $ContainerBackupPath
    if ($LASTEXITCODE -ne 0) { throw "Could not remove temporary container backup." }
}

if ($ResetDatabase) {
    Run-Step "Stop containers and remove database volume" "docker compose down -v"
}

Run-Step "Build and start services" "docker compose up --build -d"
Run-Step "Run database migrations" "docker compose run --rm ingestion alembic upgrade head"

Run-Step "Ingest core data for completed seasons" "docker compose run --rm ingestion python ingestion/ingest_core.py --seasons $CompletedSeasons"

foreach ($Season in $CompletedSeasonList) {
    Run-Step "Ingest qualifying and race results for $Season" "docker compose run --rm -e JOLPICA_MAX_RETRIES=8 -e JOLPICA_RETRY_BASE_DELAY_SECONDS=10 ingestion python ingestion/ingest_results.py --seasons $Season"
    if ($Season -ne $CompletedSeasonList[-1]) {
        Write-Host "Waiting 30 seconds before the next results-ingestion season to reduce API rate limiting..." -ForegroundColor DarkGray
        Start-Sleep -Seconds 30
    }
}

if (-not $SkipLapIngestion) {
    Run-Step "Ingest laps and weather for completed seasons" "docker compose run --rm ingestion python ingestion/ingest_laps.py --seasons $CompletedSeasons --force"
}

# Feature engineering is DB-only (no F1 API calls). --force now deletes stale
# rows per race/context before upserting, so the snapshot matches the current data.
Run-Step "Build ML features for completed seasons" "docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --seasons $CompletedSeasons --force"

if (-not $SkipTraining) {
    # --min-train-seasons 1 yields the documented three-fold expanding design:
    # fold 1 = train 2021 -> validate 2022; fold 2 = train 2021-2022 -> validate 2023;
    # fold 3 = train 2021-2023 -> validate 2024. A new run gets a new experiment ID.
    Run-Step "Train thesis models with 2025 holdout" "docker compose run --rm ingestion python ml_pipeline/train_models.py --train-seasons 2021 2022 2023 2024 --evaluation-seasons 2025 --min-train-seasons 1 --context all --seed 42 --artifact-output-dir models_store --model-output-dir models_store --generate-plots"
    Run-Step "Reload deployed models in the API" "docker compose restart backend"
}

if ($Include2026LiveData) {
    Run-Step "Ingest 2026 core data for live display only" "docker compose run --rm ingestion python ingestion/ingest_core.py --seasons 2026"
    Run-Step "Refresh next-race qualifying for live display only" "docker compose run --rm ingestion python ingestion/ingest_weekend.py --next-race --qualifying-only --fallback-schedule"
}

Run-Step "Check container status" "docker compose ps"
Run-Step "Verify deployed models load" "docker compose exec -T backend python -c `"from app.ml.model_loader import load_all_models; load_all_models(); print('models load successfully')`""

Write-Host ""
Write-Host "Done. Historical data/features/models are rebuilt." -ForegroundColor Green
