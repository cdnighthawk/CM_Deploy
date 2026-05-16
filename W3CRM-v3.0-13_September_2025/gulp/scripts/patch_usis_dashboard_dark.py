"""One-off patch: commercial construction labels on usis-dashboard-dark.html."""
from __future__ import annotations

from pathlib import Path

p = Path(__file__).resolve().parent.parent / "src" / "usis-dashboard-dark.html"
t = p.read_text(encoding="utf-8")

t = t.replace(
    "<p class=\"text-muted small mb-0\">W3CRM dark-theme KPI dashboard (charts, widgets, activity). Theme loads automatically on this page.</p>",
    "<p class=\"text-muted small mb-0\">Commercial construction KPI layout — month-end billing and job status. Figures are <strong>placeholders</strong> until connected to Corecon / billing data.</p>",
)
t = t.replace(
    "<p class=\"text-muted small mt-2 mb-0\">Plan reference: USIS Plan 20 — Site map and navigation (repository documentation).</p>",
    "<p class=\"text-muted small mt-2 mb-0\">Sample layout only; live totals will come from projects, leads, and Corecon imports (Phase 2).</p>",
)

if "usis-dashboard-dark-page" not in t:
    t = t.replace(
        '\n\t\t\t<div class="container-fluid">\n\t\t\t\n\t\t\t\t<div class="row">',
        '\n\t\t\t<div id="usis-dashboard-dark-page" class="container-fluid">\n\t\t\t\n\t\t\t\t<div class="row">',
        1,
    )

replacements = [
    (
        '<h6 class="mb-0">Total Deposit</h6>\n\t\t\t\t\t\t\t\t\t\t\t\t<h3>$1200.00</h3>',
        '<h6 class="mb-0">Billed this month</h6>\n\t\t\t\t\t\t\t\t\t\t\t\t<h3>$—</h3>',
    ),
    ("<h6>All Projects</h6>", "<h6>Active jobs</h6>"),
    (
        '<i class="fa-solid fa-square text-success me-1 fs-12"></i> Compete ',
        '<i class="fa-solid fa-square text-success me-1 fs-12"></i> In progress ',
    ),
    (
        '<i class="fa-solid fa-square text-primary me-1 fs-12"></i> Pending ',
        '<i class="fa-solid fa-square text-primary me-1 fs-12"></i> Punch ',
    ),
    (
        '<i class="fa-solid fa-square text-secondary me-1 fs-12"></i> Not Start ',
        '<i class="fa-solid fa-square text-secondary me-1 fs-12"></i> Closed ',
    ),
    (
        '<h6 class="mb-0">Total Expenses</h6>\n\t\t\t\t\t\t\t\t\t\t\t\t<h3>$1200.00</h3>',
        '<h6 class="mb-0">Job costs MTD</h6>\n\t\t\t\t\t\t\t\t\t\t\t\t<h3>$—</h3>',
    ),
    (
        '<h6 class="mb-0">Total Deposit</h6>\n\t\t\t\t\t\t\t\t\t\t\t\t<h3>20</h3>',
        '<h6 class="mb-0">Month-end billing</h6>\n\t\t\t\t\t\t\t\t\t\t\t\t<h3>12 / 18</h3>',
    ),
    (
        '<p class="mb-0">Tasks Not Finished</p>\n\t\t\t\t\t\t\t\t\t\t\t\t<p class="mb-0">20/28</p>',
        '<p class="mb-0">Jobs ready to invoice</p>\n\t\t\t\t\t\t\t\t\t\t\t\t<p class="mb-0">12 / 18</p>',
    ),
    ("Projects Overview", "Billing &amp; revenue trend"),
    (
        '<h5 class="mb-0">12,721</h5>\n\t\t\t\t\t\t\t\t\t\t\t\t<span>Number of Projects</span>',
        '<h5 class="mb-0">—</h5>\n\t\t\t\t\t\t\t\t\t\t\t\t<span>Active jobs</span>',
    ),
    (
        '<h5 class="mb-0 text-primary">721</h5>\n\t\t\t\t\t\t\t\t\t\t\t\t<span>Active Projects</span>',
        '<h5 class="mb-0 text-primary">$—</h5>\n\t\t\t\t\t\t\t\t\t\t\t\t<span>Invoiced MTD</span>',
    ),
    (
        '<h5 class="mb-0">$2,50,523</h5>\n\t\t\t\t\t\t\t\t\t\t\t\t<span>Revenue</span>',
        '<h5 class="mb-0">$—</h5>\n\t\t\t\t\t\t\t\t\t\t\t\t<span>AR outstanding</span>',
    ),
    (
        '<h5 class="mb-0 text-success">12,275h</h5>\n\t\t\t\t\t\t\t\t\t\t\t\t<span>Working Hours</span>',
        '<h5 class="mb-0 text-success">$—</h5>\n\t\t\t\t\t\t\t\t\t\t\t\t<span>Backlog (WIP)</span>',
    ),
    ("My To Do Items", "Month-end checklist"),
    ("Latest to do's", "Month-end tasks"),
    ("Total Earning", "Collections vs billings"),
    (
        '<h2 class="text-center fw-semibold display-6 mb-0">$6,743.00</h2>',
        '<h2 class="text-center fw-semibold display-6 mb-0">$—</h2>',
    ),
    ("Active Projects", "Jobs billing this period"),
    ("Project Name", "Job"),
    ("Project Lead", "PM"),
    ("Assignee", "Billing status"),
    ("Due Date", "Period end"),
    ("Upcoming Schedules", "Billing calendar"),
    ('<h6 class="text-primary mb-1 fw-semibold">EVENTS</h6>', '<h6 class="text-primary mb-1 fw-semibold">BILLING &amp; CLOSE</h6>'),
    ("Development Planning", "Invoice all active jobs"),
    ("Business Planning", "Lien waivers &amp; backups"),
    ("Software Planning", "Sync Corecon / close books"),
    ("w3it Technologies", "USIS — sample"),
    ("Projects Status", "Job pipeline"),
    ("Completed Projects", "Closed"),
    ("Progress Projects", "Active"),
    ("Cancelled Projects", "On hold"),
    ("Yet to Start", "Bid / pre-award"),
]
for a, b in replacements:
    t = t.replace(a, b)

old_tabs = """\t\t\t\t\t\t\t\t<ul class="nav nav-pills nav-pills-sm nav-pills-bg gap-2 mix-chart-tab" id="pills-tab" role="tablist">
\t\t\t\t\t\t\t\t\t<li class="nav-item" role="presentation">
\t\t\t\t\t\t\t\t\t\t<button class="nav-link active" data-series="week" id="pills-week-tab" data-bs-toggle="pill" data-bs-target="#pills-week" type="button" role="tab"  aria-selected="true">Week</button>
\t\t\t\t\t\t\t\t\t</li>
\t\t\t\t\t\t\t\t\t<li class="nav-item" role="presentation">
\t\t\t\t\t\t\t\t\t\t<button class="nav-link" data-series="month" id="pills-month-tab" data-bs-toggle="pill" data-bs-target="#pills-month" type="button" role="tab"  aria-selected="false">Month</button>
\t\t\t\t\t\t\t\t\t</li>
\t\t\t\t\t\t\t\t\t<li class="nav-item" role="presentation">
\t\t\t\t\t\t\t\t\t\t<button class="nav-link" data-series="year" id="pills-year-tab" data-bs-toggle="pill" data-bs-target="#pills-year" type="button" role="tab"  aria-selected="false">Year</button>
\t\t\t\t\t\t\t\t\t</li>
\t\t\t\t\t\t\t\t\t<li class="nav-item" role="presentation">
\t\t\t\t\t\t\t\t\t\t<button class="nav-link" data-series="all" id="pills-all-tab" data-bs-toggle="pill" data-bs-target="#pills-all" type="button" role="tab" aria-selected="false">All</button>
\t\t\t\t\t\t\t\t\t</li>
\t\t\t\t\t\t\t\t</ul>"""
new_tabs = """\t\t\t\t\t\t\t\t<ul class="nav nav-pills nav-pills-sm nav-pills-bg gap-2 mix-chart-tab" id="pills-tab" role="tablist">
\t\t\t\t\t\t\t\t\t<li class="nav-item" role="presentation">
\t\t\t\t\t\t\t\t\t\t<button class="nav-link active" data-series="month" id="pills-month-tab" data-bs-toggle="pill" data-bs-target="#pills-month" type="button" role="tab" aria-selected="true">Month</button>
\t\t\t\t\t\t\t\t\t</li>
\t\t\t\t\t\t\t\t\t<li class="nav-item" role="presentation">
\t\t\t\t\t\t\t\t\t\t<button class="nav-link" data-series="week" id="pills-week-tab" data-bs-toggle="pill" data-bs-target="#pills-week" type="button" role="tab" aria-selected="false">Quarter</button>
\t\t\t\t\t\t\t\t\t</li>
\t\t\t\t\t\t\t\t\t<li class="nav-item" role="presentation">
\t\t\t\t\t\t\t\t\t\t<button class="nav-link" data-series="year" id="pills-year-tab" data-bs-toggle="pill" data-bs-target="#pills-year" type="button" role="tab" aria-selected="false">YTD</button>
\t\t\t\t\t\t\t\t\t</li>
\t\t\t\t\t\t\t\t\t<li class="nav-item" role="presentation">
\t\t\t\t\t\t\t\t\t\t<button class="nav-link" data-series="all" id="pills-all-tab" data-bs-toggle="pill" data-bs-target="#pills-all" type="button" role="tab" aria-selected="false">All</button>
\t\t\t\t\t\t\t\t\t</li>
\t\t\t\t\t\t\t\t</ul>"""
t = t.replace(old_tabs, new_tabs)

t = t.replace(
    'class="nav-link py-2 px-0 border-3 m-0 active" data-series="day"',
    'class="nav-link py-2 px-0 border-3 m-0" data-series="day"',
)
t = t.replace(
    'class="nav-link py-2 px-0 border-3 m-0" id="pills-month-tab1"',
    'class="nav-link py-2 px-0 border-3 m-0 active" id="pills-month-tab1"',
    1,
)
t = t.replace(
    'id="pills-day-tab1" data-bs-toggle="pill" data-bs-target="#pills-day1" type="button" role="tab" aria-selected="true">Day</button>',
    'id="pills-day-tab1" data-bs-toggle="pill" data-bs-target="#pills-day1" type="button" role="tab" aria-selected="false">Day</button>',
)
t = t.replace(
    'id="pills-month-tab1" data-bs-toggle="pill" data-bs-target="#pills-month1" type="button" role="tab" aria-selected="false">Month</button>',
    'id="pills-month-tab1" data-bs-toggle="pill" data-bs-target="#pills-month1" type="button" role="tab" aria-selected="true">Month</button>',
)

t = t.replace(
    '<a href="javascript:void(0);" class="text-primary me-2">View All</a>',
    '<a href="construction/projects.html" class="text-primary me-2">View jobs</a>',
    1,
)

hide_cols = [
    ("<!-- Start - Active users -->\n\t\t\t\t\t<div class=\"col-xxl-6 col-md-12\">", "<!-- Start - Active users -->\n\t\t\t\t\t<div class=\"col-xxl-6 col-md-12 d-none\">"),
    ("<!-- Start - Chat -->\n\t\t\t\t\t<div class=\"col-xxl-6 col-md-12\">", "<!-- Start - Chat -->\n\t\t\t\t\t<div class=\"col-xxl-6 col-md-12 d-none\">"),
    ("<!-- Start - Best Selling Products -->\n\t\t\t\t\t<div class=\"col-xxl-12\">", "<!-- Start - Best Selling Products -->\n\t\t\t\t\t<div class=\"col-xxl-12 d-none\">"),
    ("<!-- Start - Employees -->\n\t\t\t\t\t<div class=\"col-xxl-9 col-xl-8\">", "<!-- Start - Employees -->\n\t\t\t\t\t<div class=\"col-xxl-9 col-xl-8 d-none\">"),
]
for a, b in hide_cols:
    if a in t:
        t = t.replace(a, b, 1)

# Sample first todo label
t = t.replace(
    '<label class="form-check-label" for="toDoCheck1">Compete this projects Monday</label>',
    '<label class="form-check-label" for="toDoCheck1">Invoice Job 2024-014 — month-end</label>',
    1,
)

p.write_text(t, encoding="utf-8")
print("patched", p)
