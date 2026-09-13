# Remove pre-merge Desktop folders (run only after verifying project_rbGyanx build).
$ErrorActionPreference = "Stop"
$Legacy = @(
    # Legacy checkouts to remove. These were absolute paths into one machine's Desktop; pass
    # your own with -Folders, or set RBGYANX_LEGACY_FOLDERS (semicolon-separated).
    "./rbgyanx_dual",
    "./rbGyanX_cdss",
    "./py_tcpx"
)
foreach ($path in $Legacy) {
    if (Test-Path $path) {
        Write-Host "Removing $path ..."
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}
Write-Host "Legacy folders removed. Keep only the current rbGyanX checkout."
