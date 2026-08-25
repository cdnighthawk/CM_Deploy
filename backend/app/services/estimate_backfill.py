"""SQL backfill: one default Estimate per lead, re-point takeoff lines.

Used by migration 0057 and by tests that simulate pre-migration rows.
"""
from __future__ import annotations

from sqlalchemy import text

BACKFILL_SQL = """
UPDATE estimates e
SET
  name = COALESCE(NULLIF(BTRIM(e.name), ''), NULLIF(BTRIM(e.title), ''), 'Original Estimate'),
  title = COALESCE(NULLIF(BTRIM(e.title), ''), NULLIF(BTRIM(e.name), ''), 'Original Estimate'),
  fee_percentage = COALESCE(e.fee_percentage, le.fee_percentage, 0),
  profit_margin = COALESCE(e.profit_margin, le.profit_margin),
  rom = COALESCE(e.rom, le.rom),
  estimate_locked_at = COALESCE(e.estimate_locked_at, le.estimate_locked_at),
  approved_at = COALESCE(e.approved_at, le.estimate_approved_at),
  status = CASE
    WHEN lower(COALESCE(le.crm_stage, '')) = 'awarded' THEN 'awarded'
    ELSE lower(COALESCE(NULLIF(BTRIM(e.status), ''), 'draft'))
  END
FROM lead_estimates le
WHERE e.lead_estimate_id = le.id;

INSERT INTO estimates (
  id, created_at, updated_at, lead_estimate_id, project_id,
  version, status, title, name, notes, total, due_at,
  fee_percentage, profit_margin, rom, is_current,
  estimate_locked_at, approved_at
)
SELECT
  gen_random_uuid(), now(), now(), le.id, le.project_id,
  1,
  CASE WHEN lower(COALESCE(le.crm_stage, '')) = 'awarded' THEN 'awarded' ELSE 'draft' END,
  'Original Estimate',
  'Original Estimate',
  NULL,
  NULL,
  le.due_at,
  COALESCE(le.fee_percentage, 0),
  le.profit_margin,
  le.rom,
  true,
  le.estimate_locked_at,
  le.estimate_approved_at
FROM lead_estimates le
WHERE NOT EXISTS (
  SELECT 1 FROM estimates e WHERE e.lead_estimate_id = le.id
)
AND (
  EXISTS (SELECT 1 FROM takeoff_line_items t WHERE t.lead_estimate_id = le.id)
  OR le.estimate_locked_at IS NOT NULL
  OR le.estimate_approved_at IS NOT NULL
  OR le.fee_percentage IS NOT NULL
  OR le.rom IS NOT NULL
  OR le.profit_margin IS NOT NULL
  OR le.primary_estimate_id IS NOT NULL
);

UPDATE estimates e
SET is_current = true
FROM lead_estimates le
WHERE le.primary_estimate_id IS NOT NULL
  AND e.id = le.primary_estimate_id;

UPDATE estimates e
SET is_current = true
WHERE e.id IN (
  SELECT DISTINCT ON (lead_estimate_id) id
  FROM estimates
  WHERE lead_estimate_id IS NOT NULL
    AND lead_estimate_id NOT IN (
      SELECT lead_estimate_id
      FROM estimates
      WHERE is_current IS true
        AND lead_estimate_id IS NOT NULL
    )
  ORDER BY lead_estimate_id, created_at ASC, id ASC
);

UPDATE takeoff_line_items t
SET estimate_id = e.id
FROM estimates e
WHERE t.lead_estimate_id IS NOT NULL
  AND t.estimate_id IS NULL
  AND e.lead_estimate_id = t.lead_estimate_id
  AND e.is_current IS true;

UPDATE lead_estimates le
SET primary_estimate_id = e.id
FROM estimates e
WHERE e.lead_estimate_id = le.id
  AND e.is_current IS true
  AND le.primary_estimate_id IS NULL;
"""


def backfill_default_estimates(connection) -> None:
    """Create default estimates and attach orphaned lead-scoped takeoff lines."""
    connection.execute(text(BACKFILL_SQL))


def backfill_default_estimate_for_lead(connection, lead_id) -> None:
    """Same rules as the migration, scoped to one lead (for tests)."""
    params = {"lead_id": lead_id}
    connection.execute(
        text(
            """
            INSERT INTO estimates (
              id, created_at, updated_at, lead_estimate_id, project_id,
              version, status, title, name, fee_percentage, profit_margin, rom,
              is_current, estimate_locked_at, approved_at, due_at
            )
            SELECT
              gen_random_uuid(), now(), now(), le.id, le.project_id,
              1,
              CASE WHEN lower(COALESCE(le.crm_stage, '')) = 'awarded' THEN 'awarded' ELSE 'draft' END,
              'Original Estimate',
              'Original Estimate',
              COALESCE(le.fee_percentage, 0),
              le.profit_margin,
              le.rom,
              true,
              le.estimate_locked_at,
              le.estimate_approved_at,
              le.due_at
            FROM lead_estimates le
            WHERE le.id = :lead_id
              AND NOT EXISTS (SELECT 1 FROM estimates e WHERE e.lead_estimate_id = le.id)
            """
        ),
        params,
    )
    connection.execute(
        text(
            """
            UPDATE takeoff_line_items t
            SET estimate_id = e.id
            FROM estimates e
            WHERE t.lead_estimate_id = :lead_id
              AND t.estimate_id IS NULL
              AND e.lead_estimate_id = t.lead_estimate_id
              AND e.is_current IS true
            """
        ),
        params,
    )
    connection.execute(
        text(
            """
            UPDATE lead_estimates le
            SET primary_estimate_id = e.id
            FROM estimates e
            WHERE le.id = :lead_id
              AND e.lead_estimate_id = le.id
              AND e.is_current IS true
              AND le.primary_estimate_id IS NULL
            """
        ),
        params,
    )
