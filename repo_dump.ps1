# Set output file
$outputFile = "repo_dump.txt"
if (Test-Path $outputFile) { Remove-Item $outputFile }

# Add header
Add-Content $outputFile "==== FILE TREE ===="
Add-Content $outputFile ""

# Generate file tree with file list
Get-ChildItem -Recurse -File | ForEach-Object {
    $relativePath = $_.FullName.Replace("$PWD\", "")
    Add-Content $outputFile $relativePath
}
Add-Content $outputFile "`n===================`n"

# Define extensions to include
$extensions = @("*.py", "*.yml", "*.yaml", "*.json", "*.bicep", "*.md")

# Skip large or unnecessary folders/files
$excludedPaths = @(
    "documentation/images",
    "src/frontend/wwwroot/assets",
    ".github/ISSUE_TEMPLATE",
    "src/backend/notebooks"
)

foreach ($ext in $extensions) {
    Get-ChildItem -Recurse -Filter $ext | Where-Object {
        $include = $true
        foreach ($path in $excludedPaths) {
            if ($_.FullName -like "*$path*") { $include = $false; break }
        }
        return $include
    } | ForEach-Object {
        $relativePath = $_.FullName.Replace("$PWD\", "")
        Add-Content $outputFile "`n----------------------------------------"
        Add-Content $outputFile "FILE: $relativePath"
        Add-Content $outputFile "----------------------------------------"
        Get-Content $_.FullName | Add-Content $outputFile
    }
}

Write-Host "✅ Dump complete. Output saved to $outputFile"
