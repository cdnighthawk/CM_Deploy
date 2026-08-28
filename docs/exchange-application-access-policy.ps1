# Restrict the USIS CRM Entra app so Graph Mail.Send / Mail.ReadWrite
# can only access @gousis.com mailboxes plus noreply@gousis.com.
#
# Run in Exchange Online PowerShell (admin):
#   Install-Module ExchangeOnlineManagement -Scope CurrentUser
#   Connect-ExchangeOnline
#   .\docs\exchange-application-access-policy.ps1

$AppId = "738dce41-ed61-4475-82ae-5800963231c0"
$GroupName = "USIS Graph mail mailboxes"
$Noreply = "noreply@gousis.com"

$group = Get-DistributionGroup -Identity $GroupName -ErrorAction SilentlyContinue
if (-not $group) {
    $group = New-DistributionGroup -Name $GroupName -Type Security -Notes "Mailboxes the USIS CRM Graph app may access"
}

# Add every licensed gousis.com mailbox + noreply (shared mailbox).
Get-Mailbox -ResultSize Unlimited | Where-Object {
    $_.PrimarySmtpAddress -like "*@gousis.com"
} | ForEach-Object {
    Add-DistributionGroupMember -Identity $GroupName -Member $_.PrimarySmtpAddress -BypassSecurityGroupManagerCheck -ErrorAction SilentlyContinue
}
Add-DistributionGroupMember -Identity $GroupName -Member $Noreply -BypassSecurityGroupManagerCheck -ErrorAction SilentlyContinue

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
    Set-ApplicationAccessPolicy -Identity $existing.Identity -PolicyScopeGroupId $group.PrimarySmtpAddress
} else {
    try {
        New-ApplicationAccessPolicy `
            -AppId $AppId `
            -PolicyScopeGroupId $group.PrimarySmtpAddress `
            -AccessRight RestrictAccess `
            -Description "USIS CRM may only send/read mail for gousis.com + noreply"
    } catch {
        if ($_.Exception.Message -notmatch "already exists") {
            throw
        }
    }
}

Write-Host "Application access policy applied for $AppId on group '$GroupName'."
