# ps_screenshot.ps1 — PowerShell screen capture utility
# Captures the primary screen and outputs base64-encoded PNG to stdout.
# Usage: powershell -File ps_screenshot.ps1

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$screen   = [System.Windows.Forms.Screen]::PrimaryScreen
$bounds   = $screen.Bounds
$bitmap   = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)

$ms = New-Object System.IO.MemoryStream
$bitmap.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
$bytes = $ms.ToArray()

$graphics.Dispose()
$bitmap.Dispose()
$ms.Dispose()

[Convert]::ToBase64String($bytes)
