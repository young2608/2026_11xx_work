# =====================================================================
#  yMp3Player 릴리즈 빌드 실행기 (build_all.cmd 가 호출)
#
#  MSYS2 bash 의 출력이 Windows 콘솔(Windows Terminal)에 안 보이는 경우가 있어,
#  bash 는 화면 없이 로그 파일에만 쓰고(BUILD_QUIET=1), 이 스크립트가 로그를 실시간으로 읽어 화면에 보여 줌.
#    로그: dist\build_<명령>_<날짜_시각>.log
#  사용: powershell -ExecutionPolicy Bypass -File build_all.ps1 [all|exe|apk|deps|clean|test ...]
#  (이 파일은 UTF-8 BOM 으로 저장해야 Windows PowerShell 5.1 에서 한글이 깨지지 않음)
# =====================================================================
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$BuildArgs)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$root = $PSScriptRoot
$msys = if ($env:MSYS2_ROOT) { $env:MSYS2_ROOT } else { 'C:\msys64' }
$bash = [IO.Path]::Combine($msys, 'usr', 'bin', 'bash.exe')
if ($env:YMP_BASH) { $bash = $env:YMP_BASH }          # 테스트용
if (-not (Test-Path $bash)) {
    Write-Host "[오류] MSYS2 bash 를 찾을 수 없습니다: $bash" -ForegroundColor Red
    Write-Host "       MSYS2 설치 후 다시 실행하거나, set MSYS2_ROOT=D:\msys64 처럼 위치를 지정하세요."
    exit 1
}

if (-not $BuildArgs -or $BuildArgs.Count -eq 0) { $BuildArgs = @('all') }
$cmdName = $BuildArgs[0]
$argStr = ($BuildArgs | ForEach-Object { if ($_ -match '^[\w.\-+]+$') { $_ } else { "'" + ($_ -replace "'", '') + "'" } }) -join ' '
$dist = Join-Path $root 'dist'
New-Item -ItemType Directory -Force -Path $dist | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $dist ("build_{0}_{1}.log" -f $cmdName, $stamp)

Write-Host ''
Write-Host ("yMp3Player 빌드 시작: build.sh {0}   ({1})" -f $argStr, (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -ForegroundColor Cyan
Write-Host ("로그 파일: {0}" -f $log)
Write-Host 'MSYS2 bash 시작 중…'

$env:MSYSTEM = 'UCRT64'
$env:CHERE_INVOKING = '1'
$env:MSYS2_PATH_TYPE = 'inherit'
$env:BUILD_LOG = ($log -replace '\\', '/')          # bash 쪽 cygpath 가 D:/... 를 변환
$env:BUILD_QUIET = '1'

$sw = [Diagnostics.Stopwatch]::StartNew()
# ArgumentList 는 한 문자열로 (PowerShell 5.1 은 배열을 따옴표 없이 이어 붙임)
$p = Start-Process -FilePath $bash -ArgumentList ('-lc "./build.sh {0}"' -f $argStr) `
        -WorkingDirectory $root -NoNewWindow -PassThru
$null = $p.Handle                                      # PS 5.1: ExitCode 를 받으려면 핸들을 먼저 잡아야 함

$script:pos = 0
$script:rest = New-Object System.Collections.Generic.List[byte]
$script:result = ''
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Show-Line([string]$line) {
    $txt = $line
    if ($txt -match '^\[\d\d:\d\d:\d\d\] (.*)$') { $body = $Matches[1] } else { $body = $txt }
    if ($body -like 'BUILD_RESULT*') { $script:result = $body }
    $color = $null
    if ($body -match '^==== .* ====$' -or $body -like '---- *') { $color = 'Cyan' }
    elseif ($body -match '^OK  |passed in|BUILD SUCCESSFUL|BUILD_RESULT 성공') { $color = 'Green' }
    elseif ($body -match '실패|FAILED|BUILD FAILED|error:|Error:|Traceback|오류') { $color = 'Red' }
    elseif ($body -like '  … 진행 중*') { $color = 'DarkGray' }
    if ($color) { Write-Host $txt -ForegroundColor $color } else { Write-Host $txt }
}

function Read-New {
    if (-not (Test-Path $log)) { return }
    try {
        $fs = New-Object IO.FileStream($log, [IO.FileMode]::Open, [IO.FileAccess]::Read,
                                       ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    } catch { return }
    try {
        if ($fs.Length -le $script:pos) { return }
        $null = $fs.Seek($script:pos, [IO.SeekOrigin]::Begin)
        $buf = New-Object byte[] ($fs.Length - $script:pos)
        $n = $fs.Read($buf, 0, $buf.Length)
        $script:pos += $n
        for ($i = 0; $i -lt $n; $i++) { $script:rest.Add($buf[$i]) }
    } finally { $fs.Dispose() }
    # 마지막 줄바꿈까지만 출력 (UTF-8 글자가 중간에 잘리지 않게)
    $arr = $script:rest.ToArray()
    $last = [Array]::LastIndexOf($arr, [byte]10)
    if ($last -lt 0) { return }
    $text = $utf8.GetString($arr, 0, $last + 1)
    $script:rest = New-Object System.Collections.Generic.List[byte]
    for ($i = $last + 1; $i -lt $arr.Length; $i++) { $script:rest.Add($arr[$i]) }
    $text = $text.Substring(0, $text.Length - 1)          # 끝 줄바꿈 제거 후 줄 단위로
    foreach ($ln in ($text -split "`n")) { Show-Line ($ln.TrimEnd("`r")) }
}

$warned = $false
while (-not $p.HasExited) {
    Read-New
    if (-not $warned -and -not (Test-Path $log) -and $sw.Elapsed.TotalSeconds -gt 30) {
        Write-Host '  … bash 시작을 기다리는 중 (MSYS2 첫 실행·백신 검사면 시간이 걸릴 수 있음)' -ForegroundColor DarkGray
        $warned = $true
    }
    Start-Sleep -Milliseconds 300
}
Start-Sleep -Milliseconds 300
Read-New
if ($script:rest.Count -gt 0) { Show-Line ($utf8.GetString($script:rest.ToArray())); $script:rest.Clear() }

$rc = $p.ExitCode
if ($null -eq $rc) { $rc = if ($script:result -like '*성공*') { 0 } else { 1 } }
$el = $sw.Elapsed
Write-Host ''
if (-not (Test-Path $log)) {
    Write-Host '[오류] 로그 파일이 만들어지지 않았습니다 — bash 가 build.sh 를 시작하지 못했습니다.' -ForegroundColor Red
    Write-Host '       MSYS2 UCRT64 터미널에서 이 폴더로 이동해 ./build.sh all 을 직접 실행해 보세요.'
    if ($rc -eq 0) { $rc = 1 }
}
$msg = if ($rc -eq 0) { '빌드 성공' } else { "빌드 실패 (rc=$rc)" }
$col = if ($rc -eq 0) { 'Green' } else { 'Red' }
Write-Host ("{0}   소요 {1:hh\:mm\:ss}" -f $msg, $el) -ForegroundColor $col
Write-Host ("로그: {0}" -f $log)
exit $rc
