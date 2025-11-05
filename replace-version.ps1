$originalLocation = Get-Location
try {
    Set-Location ./versioning
    
    # Use python3 on Linux/Mac, python on Windows
    $pythonCmd = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
    $ActualVersion = & $pythonCmd -m setuptools_git_versioning
    
    Write-Output $ActualVersion
} finally {
    Set-Location $originalLocation
}