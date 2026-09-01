# Restrict the USIS CRM Entra app so Graph Mail.Send / Mail.ReadWrite
# can only access @gousis.com mailboxes plus noreply@gousis.com.
#
# Do not paste this into a normal Windows PowerShell window. Connect first:
#   Install-Module ExchangeOnlineManagement -Scope CurrentUser
#   Connect-ExchangeOnline
#   Set-Location E:\programs\CM_Deploy
#   .\docs\exchange-application-access-policy.ps1
#
# Connect-ExchangeOnline opens a browser sign-in. Use a Microsoft 365
# account that can manage Exchange (Global admin or Exchange admin).

if (-not (Get-Command Get-DistributionGroup -ErrorAction SilentlyContinue)) {
    Write-Host @"
Exchange Online cmdlets are not loaded.

In this same PowerShell window run:

  Install-Module ExchangeOnlineManagement -Scope CurrentUser
  Connect-ExchangeOnline

Sign in when the browser opens, then run this script again:
  Set-Location E:\programs\CM_Deploy
  .\docs\exchange-application-access-policy.ps1
"@
    exit 1
}

$AppId = "738dce41-ed61-4475-82ae-5800963231c0"
$GroupName = "USIS Graph mail mailboxes"
$Noreply = "noreply@gousis.com"
$Quotes = "quotes@gousis.com"
$Invoices = "invoices@gousis.com"

$group = Get-DistributionGroup -Identity $GroupName -ErrorAction SilentlyContinue
if (-not $group) {
    $group = New-DistributionGroup -Name $GroupName -Type Security -Notes "Mailboxes the USIS CRM Graph app may access"
}

# Add every licensed gousis.com mailbox + shared system mailboxes.
Get-Mailbox -ResultSize Unlimited | Where-Object {
    $_.PrimarySmtpAddress -like "*@gousis.com"
} | ForEach-Object {
    Add-DistributionGroupMember -Identity $GroupName -Member $_.PrimarySmtpAddress -BypassSecurityGroupManagerCheck -ErrorAction SilentlyContinue
}
Add-DistributionGroupMember -Identity $GroupName -Member $Noreply -BypassSecurityGroupManagerCheck -ErrorAction SilentlyContinue
Add-DistributionGroupMember -Identity $GroupName -Member $Quotes -BypassSecurityGroupManagerCheck -ErrorAction SilentlyContinue
Add-DistributionGroupMember -Identity $GroupName -Member $Invoices -BypassSecurityGroupManagerCheck -ErrorAction SilentlyContinue

$Description = "USIS CRM may only send/read mail for gousis.com + noreply/quotes/invoices"

# Get-ApplicationAccessPolicy with no Identity searches '*', which Exchange
# Hosted sometimes fails to resolve (OU=...onmicrosoft.com\*) even when
# policies exist. Treat that as "none found" and create-or-update below.
$existing = $null
try {
    $existing = @(Get-ApplicationAccessPolicy -ErrorAction Stop) |
        Where-Object { $_.AppId -eq $AppId } |
        Select-Object -First 1
} catch {
    if ($_.Exception.Message -notmatch "couldn't be found") {
        throw
    }
}

if ($existing) {
    # Set-ApplicationAccessPolicy can only change Description, not the scope group.
    # Adding members to the existing mail-enabled security group is enough.
    Set-ApplicationAccessPolicy -Identity $existing.Identity -Description $Description
    Write-Host "Updated description on existing application access policy."
} else {
    try {
        New-ApplicationAccessPolicy `
            -AppId $AppId `
            -PolicyScopeGroupId $group.PrimarySmtpAddress `
            -AccessRight RestrictAccess `
            -Description $Description
        Write-Host "Created application access policy."
    } catch {
        if ($_.Exception.Message -notmatch "already exists") {
            throw
        }
        Write-Host "Application access policy already exists."
    }
}

Write-Host "Policy is scoped to group '$GroupName'. Checking shared mailboxes:"
$needed = @($Noreply, $Quotes, $Invoices)
$members = @(Get-DistributionGroupMember -Identity $GroupName -ResultSize Unlimited)
foreach ($addr in $needed) {
    $hit = $members | Where-Object {
        $_.PrimarySmtpAddress -and ($_.PrimarySmtpAddress.ToString() -ieq $addr)
    }
    if ($hit) {
        Write-Host "  OK  $addr is in the group"
    } else {
        Write-Host "  MISSING  $addr is not in the group"
    }
    try {
        $test = Test-ApplicationAccessPolicy -AppId $AppId -Identity $addr
        Write-Host ("        Test-ApplicationAccessPolicy: {0}" -f $test.AccessCheckResult)
    } catch {
        Write-Host ("        Test-ApplicationAccessPolicy failed: {0}" -f $_.Exception.Message)
    }
}

Write-Host "Done. Graph Mail.Send / Mail.ReadWrite for this app is limited to members of '$GroupName'."
