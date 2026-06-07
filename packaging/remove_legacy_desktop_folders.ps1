# Remove pre-merge Desktop folders (run only after verifying project_rbGyanx build).
$ErrorActionPreference = "Stop"
$Legacy = @(
    "C:\Users\Sampa\OneDrive\Desktop\rbgyanx_dual",
    "C:\Users\Sampa\OneDrive\Desktop\rbGyanX_cdss",
    "C:\Users\Sampa\OneDrive\Desktop\py_tcpx"
)
foreach ($path in $Legacy) {
    if (Test-Path $path) {
        Write-Host "Removing $path ..."
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}
Write-Host "Legacy folders removed. Keep only: C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx"
