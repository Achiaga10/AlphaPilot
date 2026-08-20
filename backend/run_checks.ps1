Write-Host ""
Write-Host "===================================" -ForegroundColor Cyan
Write-Host " AlphaPilot Quality Checks"
Write-Host " uv run ruff check ."
Write-Host " uv run mypy src"
Write-Host " uv run pytest"
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Ruff..." -ForegroundColor Yellow
uv run ruff check . --fix
uv run ruff format .
uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[2/3] MyPy..." -ForegroundColor Yellow
uv run mypy src
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "[3/3] Pytest..." -ForegroundColor Yellow
uv run pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "===================================" -ForegroundColor Green
Write-Host " All checks passed!"
Write-Host "===================================" -ForegroundColor Green


