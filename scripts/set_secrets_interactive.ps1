# Interactive: set GitHub Actions secrets for this repo.
# Prerequisites: gh auth login

$ErrorActionPreference = "Stop"
$env:Path = "C:\Program Files\GitHub CLI;" + $env:Path
$Repo = "DoTrungHuy/grok-daily-digest"

gh auth status
if ($LASTEXITCODE -ne 0) { throw "请先运行: gh auth login" }

Write-Host ""
Write-Host "将配置仓库 Secrets: $Repo"
Write-Host "（输入时不会回显，粘贴后回车）"
Write-Host ""

function Set-Secret($name) {
    Write-Host ">>> 粘贴 $name 后回车:"
    $val = Read-Host -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($val)
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    if (-not $plain) {
        Write-Host "跳过空值: $name"
        return
    }
    $plain | gh secret set $name --repo $Repo
    Write-Host "OK: $name"
}

Set-Secret "DEEPSEEK_API_KEY"
Set-Secret "TWITTER_AUTH_TOKEN"
Set-Secret "TWITTER_CT0"

Write-Host ""
Write-Host "可选: 设置代理? (A1先测一般不需要) y/N"
$ans = Read-Host
if ($ans -eq "y" -or $ans -eq "Y") {
    Set-Secret "HTTPS_PROXY"
}

Write-Host ""
Write-Host "当前 Secrets 列表:"
gh secret list --repo $Repo

Write-Host ""
Write-Host "触发一次 workflow:"
gh workflow run daily.yml --repo $Repo
Write-Host "查看: https://github.com/$Repo/actions"
