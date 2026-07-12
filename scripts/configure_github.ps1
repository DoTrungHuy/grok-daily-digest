# Configure GitHub Pages + print required secrets checklist.
# Requires: GitHub CLI (gh) logged in: gh auth login

$ErrorActionPreference = "Stop"
$Repo = "DoTrungHuy/grok-daily-digest"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "gh CLI not found. Install: winget install GitHub.cli"
    Write-Host "Then: gh auth login"
    exit 1
}

gh auth status
if ($LASTEXITCODE -ne 0) {
    Write-Host "Run: gh auth login"
    exit 1
}

# Enable Pages from /docs on main
Write-Host "Enabling GitHub Pages (main / docs)..."
gh api -X POST "repos/$Repo/pages" -f build_type=legacy -f source[branch]=main -f source[path]=/docs 2>$null
if ($LASTEXITCODE -ne 0) {
    # update existing
    gh api -X PUT "repos/$Repo/pages" -f build_type=legacy -f source[branch]=main -f source[path]=/docs
}

Write-Host ""
Write-Host "Pages config:"
gh api "repos/$Repo/pages" --jq "{url: html_url, status: status, source: source}"

Write-Host ""
Write-Host "Required secrets (set with):"
Write-Host "  gh secret set DEEPSEEK_API_KEY --repo $Repo"
Write-Host "  gh secret set TWITTER_AUTH_TOKEN --repo $Repo"
Write-Host "  gh secret set TWITTER_CT0 --repo $Repo"
Write-Host ""
Write-Host "Optional proxy after A1 fails:"
Write-Host "  gh secret set HTTPS_PROXY --repo $Repo"
Write-Host ""
Write-Host "Trigger workflow:"
Write-Host "  gh workflow run daily.yml --repo $Repo"
