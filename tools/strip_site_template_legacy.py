#!/usr/bin/env python3
"""Remove hardcoded W3CRM template demo content from USIS site pages (Plan 20 §A–B)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GULP = REPO / "W3CRM-v3.0-13_September_2025" / "gulp" / "src"


def write_chatbox(path: Path) -> None:
    path.write_text(
        """<!-- Start - Sidebar Chat Box  -->
\t\t<div class="chatbox">
\t\t\t<div class="chatbox-close"></div>
\t\t\t<div class="clearfix">
\t\t\t\t<ul class="nav nav-underline">
\t\t\t\t\t<li class="nav-item">
\t\t\t\t\t\t<a class="nav-link" data-bs-toggle="tab" href="#notes">Notes</a>
\t\t\t\t\t</li>
\t\t\t\t\t<li class="nav-item">
\t\t\t\t\t\t<a class="nav-link" data-bs-toggle="tab" href="#alerts">Alerts</a>
\t\t\t\t\t</li>
\t\t\t\t\t<li class="nav-item">
\t\t\t\t\t\t<a class="nav-link active" data-bs-toggle="tab" href="#chat">Chat</a>
\t\t\t\t\t</li>
\t\t\t\t</ul>
\t\t\t\t<div class="tab-content">
\t\t\t\t\t<div class="tab-pane fade" id="notes">
\t\t\t\t\t\t<div class="card mb-0">
\t\t\t\t\t\t\t<div class="card-body py-4 text-center text-muted small">
\t\t\t\t\t\t\t\t<p class="mb-0">Project notes will appear here when messaging is enabled.</p>
\t\t\t\t\t\t\t</motionless>
\t\t\t\t\t\t</div>
\t\t\t\t\t</div>
\t\t\t\t\t<div class="tab-pane fade" id="alerts">
\t\t\t\t\t\t<div class="card mb-0">
\t\t\t\t\t\t\t<div class="card-body py-4 text-center text-muted small">
\t\t\t\t\t\t\t\t<p class="mb-0">System alerts will appear here when configured.</p>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t</div>
\t\t\t\t\t</div>
\t\t\t\t\t<div class="tab-pane fade active show" id="chat">
\t\t\t\t\t\t<div class="card mb-0">
\t\t\t\t\t\t\t<div class="card-body py-4 text-center text-muted small">
\t\t\t\t\t\t\t\t<p class="mb-0">Team chat is not enabled yet.</p>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t</div>
\t\t\t\t\t</motionless>
\t\t\t\t</div>
\t\t\t</div>
\t\t</div>
\t\t<!-- End - Sidebar Chat Box  -->
""".replace("</motionless>", "</div>").replace("<motionless>", "<div>"),
        encoding="utf-8",
    )


def strip_header_notifications(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(<div class="dz-scroll p-2" style="height: 380px;">).*?(</motionless>\s*<a class="d-block text-center p-3 border-top")'.replace(
            "</motionless>", "</motionless>"
        ),
        re.DOTALL,
    )
    # Fix pattern - closing tag is </motionless> typo
    pattern = re.compile(
        r'(<motionless class="dz-scroll p-2" style="height: 380px;">).*?(<a class="d-block text-center p-3 border-top")',
        re.DOTALL,
    )
    pattern = re.compile(
        r'(<div class="dz-scroll p-2" style="height: 380px;">).*?(<a class="d-block text-center p-3 border-top")',
        re.DOTALL,
    )
    repl = (
        r'\1\n\t\t\t\t\t\t\t\t<p class="text-muted small text-center mb-0 py-5">No notifications.</p>\n\t\t\t\t\t\t\t\2'
    )
    new_text, n = pattern.subn(repl, text, count=1)
    if n:
        path.write_text(new_text, encoding="utf-8")
    return n > 0


def strip_core_hr(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    # Monthly attendance grid (template fake names)
    pattern = re.compile(
        r"\t\t\t\t\t\t\t<div class=\"col-xl-12\">\s*"
        r"<div class=\"card\">\s*"
        r"<div class=\"card-header border-0 d-flex align-items-center\">\s*"
        r"<h4 class=\"card-title\">Attendance</h4>.*?"
        r"<!-- End - Attendance -->\s*"
        r"</div>\s*</div>\s*</div>\s*</motionless>\s*</div>\s*</div>\s*"
        r"\s*<div class=\"col-xxl-3 col-xl-4\">",
        re.DOTALL,
    )
    pattern = re.compile(
        r"(\t\t\t\t\t\t\t<div class=\"col-xl-12\">\s*"
        r"<div class=\"card\">\s*"
        r"<div class=\"card-header border-0 d-flex align-items-center\">\s*"
        r"<h4 class=\"card-title\">Attendance</h4>).*?"
        r"(</div>\s*</div>\s*</div>\s*</div>\s*</div>\s*"
        r"\s*<motionless class=\"col-xxl-3 col-xl-4\">)",
        re.DOTALL,
    )
    pattern = re.compile(
        r"(\t\t\t\t\t\t\t<div class=\"col-xl-12\">\s*"
        r"<motionless class=\"card\">\s*"
        r"<div class=\"card-header border-0 d-flex align-items-center\">\s*"
        r"<h4 class=\"card-title\">Attendance</h4>).*?"
        r"(\t\t\t\t\t</div>\s*</div>\s*</div>\s*"
        r"\s*<div class=\"col-xxl-3 col-xl-4\">)",
        re.DOTALL,
    )
    # Simpler: from first Attendance card after Employees through col-xxl-3 sidebar
    start = text.find("\t\t\t\t\t\t\t<div class=\"col-xl-12\">\n\t\t\t\t\t\t\t\t<div class=\"card\">\n\t\t\t\t\t\t\t\t\t<div class=\"card-header border-0 d-flex align-items-center\">\n\t\t\t\t\t\t\t\t\t\t<h4 class=\"card-title\">Attendance</h4>")
    if start < 0:
        return False
    end = text.find("\t\t\t\t\t<div class=\"col-xxl-3 col-xl-4\">", start)
    if end < 0:
        return False
    block = """\t\t\t\t\t\t\t<div class="col-xl-12">
\t\t\t\t\t\t\t\t<div class="card">
\t\t\t\t\t\t\t\t\t<div class="card-header border-0 d-flex align-items-center">
\t\t\t\t\t\t\t\t\t\t<h4 class="card-title">Attendance</h4>
\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t<div class="card-body">
\t\t\t\t\t\t\t\t\t\t<p class="text-muted small mb-0">Monthly attendance will connect to HRMS timesheets. Use <a href="usis-hrms-home.html">HR suite</a> for live hours.</p>
\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t</motionless>
""".replace("</motionless>", "</div>")
    text = text[:start] + block + text[end:]
    # Sidebar attendance chart + fake holidays
    text = re.sub(
        r"<!-- Start - Attendance -->\s*<div class=\"col-xl-12 col-md-6\">.*?</div>\s*<!-- End - Attendance -->",
        """<!-- Start - Attendance -->
\t\t\t\t\t\t\t<div class="col-xl-12 col-md-6">
\t\t\t\t\t\t\t\t<div class="card">
\t\t\t\t\t\t\t\t\t<div class="card-header pb-0 border-0">
\t\t\t\t\t\t\t\t\t\t<h4 class="card-title">Attendance</h4>
\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t<div class="card-body">
\t\t\t\t\t\t\t\t\t\t<p class="text-muted small mb-0">Summary charts will use HRMS data when wired.</p>
\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<!-- End - Attendance -->""",
        text,
        count=1,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"<!-- Start - Upcoming Holidays -->.*?<!-- End - Upcoming Holidays -->",
        """<!-- Start - Upcoming Holidays -->
\t\t\t\t\t\t\t<div class="col-xl-12 col-md-6">
\t\t\t\t\t\t\t\t<div class="card">
\t\t\t\t\t\t\t\t\t<div class="card-header border-0 pb-2">
\t\t\t\t\t\t\t\t\t\t<h4 class="card-title">Upcoming Holidays</h4>
\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t\t<div class="card-body">
\t\t\t\t\t\t\t\t\t\t<p class="text-muted small mb-0">Company holidays will list here when configured in HRMS.</p>
\t\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t</div>
\t\t\t\t\t\t\t<!-- End - Upcoming Holidays -->""",
        text,
        count=1,
        flags=re.DOTALL,
    )
    path.write_text(text, encoding="utf-8")
    return True


def strip_reports(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    text2, n = re.subn(
        r"\n\t\t\t<!-- Start - Reports -->.*?<!-- End - Reports -->",
        "",
        text,
        count=1,
        flags=re.DOTALL,
    )
    text2, n2 = re.subn(
        r"\n    <!-- Start - Download Modal -->.*?<!-- End - Download Modal -->",
        "",
        text2,
        count=1,
        flags=re.DOTALL,
    )
    text2 = text2.replace(
        "Legacy W3CRM category cards remain design references.",
        "Template category cards were removed; use Print reports (USIS) above.",
    )
    if n or n2:
        path.write_text(text2, encoding="utf-8")
    return (n + n2) > 0


def strip_dashboard_dark(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    text2 = re.sub(
        r"\t\t\t\t\t\t\t\t\t\t\t<tr>\s*<td>.*?\$85\.20.*?</tr>\s*",
        "",
        text,
        flags=re.DOTALL,
    )
    text2 = re.sub(
        r"\t\t\t\t\t\t\t\t\t\t\t<tr>\s*<td>.*?\$86\.20.*?</tr>\s*",
        "",
        text2,
        flags=re.DOTALL,
    )
    text2 = re.sub(
        r'<li class="list-group-item[^"]*">.*?USIS — sample.*?</li>\s*',
        "",
        text2,
        flags=re.DOTALL,
    )
    # Empty transaction tbody if rows removed
    text2 = re.sub(
        r"(<tbody id=\"usis-dark-transactions-tbody\">)\s*(</tbody>)",
        r'\1\n\t\t\t\t\t\t\t\t\t\t\t<tr><td colspan="6" class="text-muted text-center py-4">No transactions yet.</td></tr>\n\t\t\t\t\t\t\t\t\t\t\2',
        text2,
        count=1,
    )
    if text2 != text:
        path.write_text(text2, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed: list[str] = []
    chat_path = GULP / "elements" / "chatbox-construction.html"
    write_chatbox(chat_path)
    changed.append(str(chat_path.relative_to(REPO)))

    header_path = GULP / "elements" / "header-construction.html"
    if strip_header_notifications(header_path):
        changed.append(str(header_path.relative_to(REPO)))

    core_hr = GULP / "core-hr.html"
    if strip_core_hr(core_hr):
        changed.append(str(core_hr.relative_to(REPO)))

    reports = GULP / "reports.html"
    if strip_reports(reports):
        changed.append(str(reports.relative_to(REPO)))

    dark = GULP / "usis-dashboard-dark.html"
    if strip_dashboard_dark(dark):
        changed.append(str(dark.relative_to(REPO)))

    print("Updated:", *changed, sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
