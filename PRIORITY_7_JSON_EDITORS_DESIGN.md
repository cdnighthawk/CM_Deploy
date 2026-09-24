# Priority 7: Replace JSON Editors & Admin Console Cleanup

## Summary
Replace raw JSON editors with proper forms, consolidate Admin sidebar, fix nested asset paths, and hide unconfigured Power BI.

## Current State

### 1. Raw JSON Editors
**Location**: `/settings/projects` (via usis-settings.js dynamic rendering)
**Problem**: Users edit project settings via raw JSON textarea
**Impact**: Error-prone, no validation, poor UX

**Location**: `/usis-time-settings.html` 
**Problem**: Time policy configured via JSON
**Impact**: Complex policies difficult to manage

### 2. Duplicate Admin Sidebar
**Problem**: Two admin menus exist:
- `/settings` (proper company settings UI)
- Legacy "Admin" sidebar item with duplicate entries
**Impact**: Confusing navigation, duplicate pathways

### 3. Nested `/admin/*.html` Asset Paths
**Problem**: Templates under `/admin/` use relative paths that break
**Example**: `<link href="assets/css/style.css">` from `/admin/users.html` resolves incorrectly
**Impact**: Unstyled pages

### 4. Power BI Panel
**Location**: `/reports.html`
**Problem**: Empty Power BI embed shown when not configured
**Impact**: Broken UI element confuses users

## Proposed Solution

### 1A. `/settings/projects` Form UI

Replace JSON textarea with structured form:

```html
<div class="card">
  <div class="card-header">Project Settings</div>
  <div class="card-body">
    <div class="mb-3">
      <label class="form-label">Default Bid Margin (%)</label>
      <input type="number" class="form-control" min="0" max="100" step="0.1">
    </div>
    <div class="mb-3">
      <label class="form-label">Retention Rate (%)</label>
      <input type="number" class="form-control" min="0" max="100" step="0.1">
    </div>
    <div class="mb-3">
      <label class="form-label">Cost Code Prefix</label>
      <input type="text" class="form-control" maxlength="10">
    </div>
    <!-- Additional fields as needed -->
  </div>
</div>
```

**Backend**: Add `PATCH /api/v1/settings/projects` endpoint with validation.

### 1B. Time Policy Form UI

Replace JSON with wizard/step form:

```html
<div class="card">
  <div class="card-header">Time & Attendance Policy</div>
  <div class="card-body">
    <h6>Work Week</h6>
    <div class="row mb-3">
      <div class="col-md-6">
        <label>Hours per day</label>
        <input type="number" class="form-control" min="0" max="24" step="0.5">
      </div>
      <div class="col-md-6">
        <label>Days per week</label>
        <input type="number" class="form-control" min="1" max="7">
      </div>
    </div>
    
    <h6>Overtime Rules</h6>
    <div class="mb-3">
      <div class="form-check">
        <input class="form-check-input" type="checkbox" id="ot-daily">
        <label class="form-check-label" for="ot-daily">
          Daily OT after <input type="number" class="form-control-sm d-inline" style="width:4rem"> hours
        </label>
      </div>
      <div class="form-check">
        <input class="form-check-input" type="checkbox" id="ot-weekly">
        <label class="form-check-label" for="ot-weekly">
          Weekly OT after <input type="number" class="form-control-sm d-inline" style="width:4rem"> hours
        </label>
      </div>
    </div>
    
    <h6>Break Policy</h6>
    <!-- Break policy fields -->
  </div>
</div>
```

**Backend**: Add `PATCH /api/v1/settings/time-policy` with validation.

### 2. Admin Sidebar Consolidation

**Remove**: Legacy "Admin" sidebar item from `deznav-construction.html`

**Add to /settings**: 
- Cost codes (already exists)
- Contractors/vendors (link to `/usis-companies.html`)
- Company info (already exists)

**Implementation**:
1. Remove `<li>` for "Admin" from navigation
2. Ensure `/settings` has all admin functions accessible
3. Redirect old `/admin/*` routes to `/settings/*` equivalents

### 3. Fix Nested `/admin/*.html` Asset Paths

**Problem**: Relative paths in `/admin/` subfolder templates

**Solution**: Use absolute paths or `<base>` tag

```html
<head>
  <base href="/">
  <link href="assets/css/style.css" rel="stylesheet">
  <!-- Now resolves correctly from any depth -->
</head>
```

**Files to Fix**:
- `/admin/users.html`
- `/admin/roles.html`
- Any other nested admin templates

### 4. Hide Power BI Panel

**File**: `/usis-reports.html` or equivalent

**Change**:
```javascript
// In reports page init
if (!window.POWERBI_WORKSPACE_ID || !window.POWERBI_REPORT_ID) {
  document.getElementById('powerbi-panel').classList.add('d-none');
  document.getElementById('powerbi-empty-state').classList.remove('d-none');
}
```

```html
<div id="powerbi-panel">
  <!-- Power BI embed -->
</div>
<div id="powerbi-empty-state" class="d-none">
  <p class="text-muted">Power BI reporting is not configured. Contact your administrator.</p>
</div>
```

## Migration Plan

### Phase 1: Form UI (High Priority)
1. Create form templates for project settings and time policy
2. Add backend validation endpoints
3. Test with existing data
4. Deploy with fallback to JSON if forms fail

### Phase 2: Admin Consolidation (Medium Priority)
1. Audit all admin routes
2. Map to /settings equivalents
3. Remove duplicate sidebar
4. Add redirects

### Phase 3: Asset Path Fix (Low Priority)
1. Add `<base href="/">` to nested templates
2. Test routing from all depths
3. Verify styles load correctly

### Phase 4: Power BI Hide (Quick Win)
1. Add config check
2. Show/hide panel based on config
3. Deploy

## Testing Checklist

- [ ] Project settings form saves correctly
- [ ] Time policy form validates rules
- [ ] All admin functions accessible from /settings
- [ ] No broken styles on nested admin pages
- [ ] Power BI hidden when not configured
- [ ] Existing JSON data migrates cleanly to forms

## Files to Modify

### Templates
- `W3CRM-v3.0-13_September_2025/gulp/src/usis-settings.html`
- `W3CRM-v3.0-13_September_2025/gulp/src/usis-time-settings.html`
- `W3CRM-v3.0-13_September_2025/gulp/src/elements/deznav-construction.html`
- `W3CRM-v3.0-13_September_2025/gulp/src/admin/*.html` (add base tags)
- `W3CRM-v3.0-13_September_2025/gulp/src/usis-reports.html`

### JavaScript
- `W3CRM-v3.0-13_September_2025/gulp/src/assets/js/usis-settings.js`
- `W3CRM-v3.0-13_September_2025/gulp/src/assets/js/usis-time-app.js`
- New: `usis-settings-projects-form.js`
- New: `usis-time-policy-form.js`

### Backend
- New: `backend/app/api/v1.py` - add settings endpoints
- New: `backend/app/services/settings_validation.py`

## Out of Scope

- Complete UI redesign of settings pages
- Data migration scripts (existing JSON still supported)
- Full admin permission overhaul
