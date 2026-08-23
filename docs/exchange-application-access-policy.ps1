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

$existing = Get-ApplicationAccessPolicy | Where-Object { $_.AppId -eq $AppId }
if ($existing) {
    Set-ApplicationAccessPolicy -Identity $existing.Identity -PolicyScopeGroupId $group.PrimarySmtpAddress
} else {
    New-ApplicationAccessPolicy `
        -AppId $AppId `
        -PolicyScopeGroupId $group.PrimarySmtpAddress `
        -AccessRight RestrictAccess `
        -Description "USIS CRM may only send/read mail for gousis.com + noreply"
}

Write-Host "Application access policy applied for $AppId on group '$GroupName'."
