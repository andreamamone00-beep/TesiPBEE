# Script PowerShell per creare collegamento sul desktop
$desktop = [System.Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Ab-Ag PBEE - SAbDab.lnk'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = 'C:\dev\ab_ag_pbee\start_sabdab_app.bat'
$shortcut.WorkingDirectory = 'C:\dev\ab_ag_pbee'
$shortcut.Description = 'Ab/Ag PBEE Dashboard with SAbDab Real Data'
$shortcut.Save()

Write-Host "Collegamento creato sul desktop: $shortcutPath"
