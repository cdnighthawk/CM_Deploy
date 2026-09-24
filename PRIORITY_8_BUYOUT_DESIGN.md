# Priority 8: Buyout Procurement System

## Summary
Implement PO receiving, 3-way match (PO / receipt / invoice), spend-authorization chain (Creator → PM → Director → President with no skip-down), and enforce submittal QC gate.

## Current State

### Purchase Orders
- POs can be created and linked to RFPs/subcontracts
- **Missing**: Receiving workflow, 3-way match, approval chain

### Submittals
- Have "In QC" status available
- **Missing**: Enforced QC gate before GC/AE submission or PO issuance

### Invoices
- Can be uploaded and tracked
- **Missing**: Match to PO and receipt for payment approval

## Requirements

### 1. PO Receiving Workflow

**Process**:
1. Goods/services arrive on site
2. Field staff creates receipt record
3. Receipt references PO line items
4. Quantities received vs ordered tracked
5. Partial receipts supported
6. Receipts feed into 3-way match

**UI**: 
- "Receive" button on PO detail page
- Receipt entry form with line-item grid
- Photo upload for received materials
- GeoStamp location/timestamp

**Database**:
```sql
CREATE TABLE po_receipts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  receipt_number TEXT,
  received_at TIMESTAMPTZ NOT NULL,
  received_by_user_id UUID REFERENCES users(id),
  location GEOGRAPHY(POINT, 4326),
  notes TEXT,
  status TEXT DEFAULT 'draft', -- draft, confirmed, voided
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE po_receipt_line_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_id UUID NOT NULL REFERENCES po_receipts(id),
  po_line_item_id UUID REFERENCES purchase_order_line_items(id),
  description TEXT,
  quantity_received DECIMAL(15,4),
  unit TEXT,
  condition TEXT, -- good, damaged, incorrect
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE po_receipt_photos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_id UUID NOT NULL REFERENCES po_receipts(id),
  file_id UUID REFERENCES files(id),
  caption TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2. Three-Way Match

**Principle**: Invoice payment requires matching PO + Receipt + Invoice

**Match Logic**:
```
For each invoice line item:
1. Find corresponding PO line item (by description, cost code, or link)
2. Find corresponding receipt line item(s) for that PO line
3. Compare:
   - Quantity: Invoice <= Received <= Ordered (with tolerance)
   - Price: Invoice ≈ PO unit price (with variance %)
   - Total: Invoice amount ≤ (Received qty × PO price) + variance

Status:
- MATCHED: All checks pass
- VARIANCE: Minor discrepancy within tolerance (auto-flag for review)
- EXCEPTION: Major discrepancy (block payment, require approval override)
```

**UI**:
- Invoice detail page shows match status per line
- Visual indicator: ✓ Matched, ⚠ Variance, ✗ Exception
- Drill-down to see PO + Receipt + Invoice side-by-side
- Override button for exceptions (requires Director+ approval)

**Database**:
```sql
CREATE TABLE invoice_line_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id UUID NOT NULL REFERENCES invoices(id),
  po_line_item_id UUID REFERENCES purchase_order_line_items(id),
  description TEXT,
  quantity DECIMAL(15,4),
  unit_price DECIMAL(15,2),
  amount DECIMAL(15,2),
  match_status TEXT, -- matched, variance, exception, unmatched
  match_notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE three_way_match_exceptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_line_item_id UUID REFERENCES invoice_line_items(id),
  exception_type TEXT, -- quantity_variance, price_variance, missing_receipt, missing_po
  variance_amount DECIMAL(15,2),
  variance_pct DECIMAL(5,2),
  notes TEXT,
  resolved_at TIMESTAMPTZ,
  resolved_by_user_id UUID REFERENCES users(id),
  resolution_notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Configuration**:
```python
# backend/app/services/three_way_match.py
MATCH_TOLERANCES = {
    "quantity_variance_pct": 5.0,  # ±5% quantity variance allowed
    "price_variance_pct": 2.0,     # ±2% price variance allowed
    "total_variance_dollars": 100.0 # $100 total variance allowed
}
```

### 3. Spend Authorization Chain

**Hierarchy**: Creator → PM → Director → President

**Rules**:
1. **No skip-down**: Cannot jump from Creator to Director (must go through PM)
2. **Thresholds**: 
   - < $5k: PM approval sufficient
   - $5k-$50k: Director approval required (after PM)
   - > $50k: President approval required (after Director)
3. **Parallel**: Multiple approvers at same level can approve in parallel
4. **Serial**: Cannot advance to next level until current level complete

**States**:
- `draft`: Creator working on it
- `pending_pm`: Awaiting PM review
- `pending_director`: Awaiting Director review (PM approved)
- `pending_president`: Awaiting President review (Director approved)
- `approved`: Fully approved
- `rejected`: Rejected at any level (returns to Creator)

**Database**:
```sql
CREATE TABLE purchase_order_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  approval_level TEXT NOT NULL, -- pm, director, president
  required BOOLEAN DEFAULT true,
  status TEXT DEFAULT 'pending', -- pending, approved, rejected
  approver_user_id UUID REFERENCES users(id),
  approved_at TIMESTAMPTZ,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE approval_policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL,
  document_type TEXT NOT NULL, -- purchase_order, change_order, subcontract
  threshold_low DECIMAL(15,2),
  threshold_mid DECIMAL(15,2),
  threshold_high DECIMAL(15,2),
  require_pm BOOLEAN DEFAULT true,
  require_director BOOLEAN DEFAULT false,
  require_president BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Approval Logic**:
```python
def get_required_approvals(po: PurchaseOrder) -> list[str]:
    """
    Return required approval levels based on PO amount.
    """
    amount = po.total_amount
    policy = get_approval_policy(po.organization_id, 'purchase_order')
    
    levels = ['pm']  # PM always required
    
    if amount > policy.threshold_mid:
        levels.append('director')
    
    if amount > policy.threshold_high:
        levels.append('president')
    
    return levels

def can_approve_at_level(user: User, level: str, po: PurchaseOrder) -> bool:
    """
    Check if user has permission to approve at this level.
    No skip-down: must check previous levels are complete.
    """
    if level == 'pm':
        return user.has_role('project_manager', po.project_id)
    elif level == 'director':
        # Director can only approve after PM
        if not po.is_approved_by_pm():
            return False
        return user.has_role('director')
    elif level == 'president':
        # President can only approve after Director
        if not po.is_approved_by_director():
            return False
        return user.has_role('president')
    
    return False
```

**UI**:
- Approval status badge on PO header
- Approval chain visual (PM → Director → President) with checkmarks
- "Approve" button visible only to authorized users
- Notification to next approver when previous level completes
- Email digest of pending approvals

### 4. Submittal QC Gate

**Requirement**: Submittals must pass internal QC before:
1. Submission to GC/AE
2. PO issuance for that scope

**Process**:
1. Creator uploads submittal → status = `draft`
2. Internal QC review → status = `in_qc`
3. QC approves → status = `approved_internal`
4. Now can submit to GC/AE → status = `submitted`
5. GC/AE reviews → status = `approved` or `rejected`

**Enforcement**:
```python
def can_submit_to_gc(submittal: Submittal) -> tuple[bool, str]:
    """
    Check if submittal can be submitted to GC/AE.
    """
    if submittal.status != 'approved_internal':
        return False, "Submittal must pass internal QC before submission to GC/AE"
    return True, ""

def can_issue_po_for_scope(po: PurchaseOrder) -> tuple[bool, str]:
    """
    Check if PO can be issued (submittal QC gate).
    """
    # Find submittals for this PO's scope/spec section
    submittals = get_submittals_for_po(po)
    
    if not submittals:
        # No submittals required (e.g., labor-only)
        return True, ""
    
    unapproved = [s for s in submittals if s.status not in ('approved_internal', 'approved')]
    
    if unapproved:
        return False, f"{len(unapproved)} submittal(s) must pass QC before PO issuance"
    
    return True, ""
```

**Database**:
```sql
-- Add to existing submittals table
ALTER TABLE submittals 
  ADD COLUMN qc_status TEXT DEFAULT 'pending', -- pending, in_review, approved, rejected
  ADD COLUMN qc_reviewer_id UUID REFERENCES users(id),
  ADD COLUMN qc_reviewed_at TIMESTAMPTZ,
  ADD COLUMN qc_notes TEXT;

CREATE TABLE submittal_qc_checklist_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  submittal_id UUID NOT NULL REFERENCES submittals(id),
  checklist_item TEXT NOT NULL,
  passed BOOLEAN,
  notes TEXT,
  checked_by_user_id UUID REFERENCES users(id),
  checked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**UI**:
- QC review form with checklist
- "Submit to GC/AE" button disabled until QC approved
- PO create wizard checks submittal status, blocks with clear message
- QC status badge on submittal list

## Database Migration Plan

### Migration 001: PO Receiving Tables
```sql
-- Create tables for PO receiving workflow
-- (See section 1 above for full DDL)
```

### Migration 002: Invoice Line Items & 3-Way Match
```sql
-- Create tables for invoice matching
-- (See section 2 above for full DDL)
```

### Migration 003: Approval Policies & PO Approvals
```sql
-- Create approval workflow tables
-- (See section 3 above for full DDL)
```

### Migration 004: Submittal QC Fields
```sql
-- Add QC fields to submittals table
-- (See section 4 above for full DDL)
```

## API Endpoints

### Receiving
- `POST /api/v1/purchase-orders/{id}/receipts` - Create receipt
- `GET /api/v1/purchase-orders/{id}/receipts` - List receipts
- `PATCH /api/v1/receipts/{id}` - Update receipt
- `POST /api/v1/receipts/{id}/photos` - Upload receipt photo

### Three-Way Match
- `GET /api/v1/invoices/{id}/match-status` - Get match status
- `POST /api/v1/invoices/{id}/resolve-exception` - Resolve match exception
- `GET /api/v1/three-way-match-exceptions` - List open exceptions

### Approvals
- `POST /api/v1/purchase-orders/{id}/submit-for-approval` - Submit PO
- `POST /api/v1/purchase-orders/{id}/approve` - Approve at current level
- `POST /api/v1/purchase-orders/{id}/reject` - Reject with reason
- `GET /api/v1/me/pending-approvals` - My pending approvals queue

### Submittal QC
- `POST /api/v1/submittals/{id}/start-qc` - Begin QC review
- `POST /api/v1/submittals/{id}/complete-qc` - Complete QC (pass/fail)
- `GET /api/v1/submittals/{id}/qc-checklist` - Get QC checklist

## UI Pages

### New Pages
1. `/construction/po-receive.html?po_id=<uuid>` - Receipt entry form
2. `/construction/three-way-match.html?invoice_id=<uuid>` - Match review
3. `/construction/approval-queue.html` - My pending approvals
4. `/construction/submittal-qc.html?submittal_id=<uuid>` - QC review form

### Modified Pages
- `/construction/procurement-detail.html` - Add Receive button, approvals section
- `/construction/invoice-detail.html` - Add match status, variance details
- `/construction/submittal-detail.html` - Add QC status, QC review link

## Testing Checklist

### PO Receiving
- [ ] Create receipt from PO with multiple line items
- [ ] Partial receipt (receive 50% of ordered qty)
- [ ] Multiple receipts for same PO
- [ ] Upload receipt photos with location stamp
- [ ] Void incorrect receipt

### Three-Way Match
- [ ] Invoice matches PO and receipt exactly
- [ ] Invoice with minor quantity variance (within tolerance)
- [ ] Invoice with major price variance (exception)
- [ ] Invoice for unreceived items (blocked)
- [ ] Override exception with Director approval

### Approval Chain
- [ ] PO < $5k approved by PM only
- [ ] PO $5k-$50k requires PM + Director
- [ ] PO > $50k requires PM + Director + President
- [ ] Cannot skip from Creator to Director (must go through PM)
- [ ] Rejection returns to Creator for revision
- [ ] Email notifications sent to next approver

### Submittal QC Gate
- [ ] Cannot submit to GC/AE before internal QC approval
- [ ] Cannot issue PO when linked submittal not QC-approved
- [ ] QC checklist saves progress
- [ ] QC rejection returns to creator with notes
- [ ] Approved submittal allows PO issuance

## Implementation Phases

### Phase 1: Database & Models (Week 1)
- Create migration files
- Add SQLAlchemy models
- Write seed data for testing

### Phase 2: Backend API (Week 2-3)
- Implement receiving endpoints
- Implement 3-way match logic
- Implement approval chain enforcement
- Implement QC gate checks

### Phase 3: UI Scaffolds (Week 4)
- Create HTML templates
- Wire up JavaScript for forms
- Add approval buttons and status badges

### Phase 4: Integration & Testing (Week 5)
- End-to-end testing
- UAT with stakeholders
- Fix bugs and refinements

### Phase 5: Documentation & Training (Week 6)
- User guides
- Video tutorials
- Admin configuration guide

## Configuration

### Approval Thresholds (Admin Configurable)
```python
# backend/app/config.py or settings UI
APPROVAL_THRESHOLDS = {
    "purchase_order": {
        "pm_only_max": 5000.00,
        "director_required_min": 5000.00,
        "president_required_min": 50000.00,
    },
    "change_order": {
        "pm_only_max": 2500.00,
        "director_required_min": 2500.00,
        "president_required_min": 25000.00,
    }
}
```

### Match Tolerances (Admin Configurable)
```python
MATCH_TOLERANCES = {
    "quantity_variance_pct": 5.0,
    "price_variance_pct": 2.0,
    "total_variance_dollars": 100.0,
}
```

## Security Considerations

1. **Approval Authority**: Role-based permissions strictly enforced
2. **No Skip-Down**: Backend validates previous approval levels complete
3. **Audit Trail**: All approvals/rejections logged with user + timestamp
4. **Override Logging**: Match exception overrides logged for audit
5. **Receipt Tampering**: Receipts immutable after confirmation (void creates new record)

## Success Metrics

- **Receiving**: % POs with receipts entered within 24hrs of delivery
- **Match**: % invoices auto-matched vs requiring manual review
- **Approvals**: Average time from submission to final approval
- **QC Gate**: % submittals caught in QC vs rejected by GC/AE
- **Compliance**: Zero skip-down violations in approval chain

## Future Enhancements

- Mobile app for field receiving (barcode scanner)
- Automatic invoice OCR and matching
- Predictive analytics for approval bottlenecks
- Vendor performance scoring based on receipt vs PO accuracy
