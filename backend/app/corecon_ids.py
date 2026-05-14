"""Stable identifiers linking Corecon rows to the synthetic BC ``lead_estimates`` row."""


def stable_active_project_external_id(
    *,
    project_corecon_id: int | None,
    project_number: str | None,
) -> str | None:
    """Same value as ``active project.csv`` ``id`` / ``LeadEstimate.external_id``.

    ``project_corecon_id`` is the integer ``ProjectId`` from Corecon exports.
    When it is missing, falls back to ``corecon-project-noid-{project_number}``.
    """
    if project_corecon_id is not None:
        return f"corecon-project-{project_corecon_id}"
    num = (project_number or "").strip()
    if num:
        return f"corecon-project-noid-{num}"
    return None
