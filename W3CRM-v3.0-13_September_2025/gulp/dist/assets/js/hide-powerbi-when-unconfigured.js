// Hide Power BI panel when not configured
(function() {
  var panel = document.getElementById('usis-powerbi-panel');
  var embed = document.getElementById('usis-powerbi-embed');
  var empty = document.getElementById('usis-powerbi-empty');
  var status = document.getElementById('usis-powerbi-status');
  
  // Check if Power BI is configured
  var hasWorkspaceId = window.POWERBI_WORKSPACE_ID && window.POWERBI_WORKSPACE_ID.trim();
  var hasReportId = window.POWERBI_REPORT_ID && window.POWERBI_REPORT_ID.trim();
  
  if (!hasWorkspaceId || !hasReportId) {
    // Not configured - show empty state
    if (embed) embed.classList.add('d-none');
    if (status) status.classList.add('d-none');
    if (empty) empty.classList.remove('d-none');
    if (panel) panel.classList.add('d-none'); // Hide entire panel
  }
})();
