# Overnight driver, third revision.
#
# Changed from drive2: seven models truncated mid-thought at a 2,500-token
# budget — qwen3.5:9b on 63% of answers, gemma4:26b on 51% — so pinning now sets
# num_predict 8192 and those seven are re-run from scratch. Models that never
# hit the ceiling keep their results: under greedy decoding their output is
# identical at any budget they never reached.
#
# Order is chosen so the full canonical fleet exists as early as possible: re-run
# the truncating models, then every model's variants, THEN repeats for error bars.
#
# Same safety properties as before: Windows-side loop, one model/mode/repeat per
# wsl.exe call, completeness checked by row count before and after every unit,
# multi-pass, safe to re-run.
$ErrorActionPreference = "Continue"
$repo = "~/mission-control/projects/recall-or-reason"
$o    = "C:\Users\joyne\AppData\Local\Programs\Ollama\ollama.exe"

function Test-Complete([string]$m, [string]$k, [string]$r) {
  $a = "$m $k"; if ($r) { $a = "$a $r" }
  wsl.exe -d Ubuntu -- bash -lc "cd $repo && python3 have_complete.py $a" | Out-Null
  return ($LASTEXITCODE -eq 0)
}

function Invoke-Unit([string]$m, [string]$k, [string]$r) {
  $mode = "interval"; $extra = ""
  if ($k -eq "choice") { $mode = "choice"; if ($r) { $extra = "--tag $r" } }
  elseif ($k -eq "interval") { if ($r) { $extra = "--tag $r" } }
  else {
    $extra = "--items data/variants.jsonl --tag variants"
    if ($r) { $extra = "--items data/variants.jsonl --tag variants-$r" }
  }
  $cmd = "cd $repo && ./run.sh run_eval.py --mode $mode --model $m --timeout 600 $extra"
  $res = wsl.exe -d Ubuntu -- bash -lc $cmd
  "      " + (($res | Select-Object -Last 2) -join " | ")
}

$rerun  = @("gemma4-26b-t0","qwen3-6-35b-a3b-t0","qwen3-8b-t0","qwen3-5-9b-t0","gpt-oss-20b-t0","gemma4-31b-t0","qwen3-6-27b-t0")
$fast   = @("gemma3-4b-t0","llama3-1-8b-t0","gemma3-12b-t0","phi4-14b-t0","mistral-small-24b-t0","gemma3-27b-t0","devstral-small-2-t0","lfm2-t0")
$slowOk = @("qwen3-14b-t0","qwen3-32b-t0")
$all    = $fast + $slowOk + $rerun + @("llama3-2-1b-t0")

$q = New-Object System.Collections.ArrayList
function Add-Units($models, $kinds, [string]$rep) {
  foreach ($m in $models) { foreach ($k in $kinds) { [void]$q.Add(@($m, $k, $rep)) } }
}
# 1. re-run the seven truncating models at the new budget
Add-Units $rerun @("choice","interval") ""
# 2. every model's variants on the expanded set -> the full canonical fleet
Add-Units $all @("variants") ""
# 3-5. repeats for error bars, cheapest first
Add-Units $fast  @("choice","interval","variants") "r2"
Add-Units $rerun @("choice","interval","variants") "r2"
Add-Units $fast  @("choice","interval","variants") "r3"
# 6. the slowest models' repeats, only if time allows
Add-Units $slowOk @("choice","interval","variants") "r2"

"DRIVE3 START $(Get-Date -Format HH:mm:ss) - $($q.Count) units queued"
for ($pass = 1; $pass -le 20; $pass++) {
  "--- pass $pass $(Get-Date -Format HH:mm:ss): pinning at num_predict 8192"
  wsl.exe -d Ubuntu -- bash -lc "cd $repo && bash pin_models.sh" | Out-Null
  $listing = & $o list 2>$null
  $ran = 0; $waiting = 0; $failed = 0
  foreach ($u in $q) {
    $m = $u[0]; $k = $u[1]; $r = $u[2]
    $label = "$m $k"; if ($r) { $label = "$label $r" }
    if (Test-Complete $m $k $r) { continue }
    if (-not ($listing | Where-Object { $_ -match ("^" + [regex]::Escape($m) + ":latest\s") })) { $waiting++; continue }
    "RUN   $label  $(Get-Date -Format HH:mm:ss)"
    Invoke-Unit $m $k $r
    if (Test-Complete $m $k $r) { $ran++ } else { $failed++; "      !! $label still incomplete after running" }
  }
  "--- pass $pass done: ran $ran, failed $failed, not pulled $waiting"
  if ($ran -eq 0) { break }
}
"DRIVE3 COMPLETE $(Get-Date -Format HH:mm:ss)"
