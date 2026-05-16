/**
 * USIS Dark Dashboard — hours worked by project (HRMS timesheet entries).
 * Requires #usis-dashboard-dark-page and #usisHoursByProjectChart.
 */
(function () {
	"use strict";

	var chart = null;
	var currentPeriod = "month";

	function isDarkDash() {
		return !!document.getElementById("usis-dashboard-dark-page");
	}

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var port = String(loc.port || "");
		if (["3000", "3001", "3002", "3003"].indexOf(port) >= 0) return "";
		if (loc.hostname === "localhost" || loc.hostname === "127.0.0.1") {
			return loc.protocol + "//" + loc.hostname + ":5000";
		}
		return "";
	}

	function fmtHours(n) {
		if (n == null || isNaN(Number(n))) return "—";
		return Number(n).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
	}

	function setVisible(id, show) {
		var el = document.getElementById(id);
		if (el) el.classList.toggle("d-none", !show);
	}

	function setKpis(summary) {
		summary = summary || {};
		var total = document.getElementById("usis-hours-kpi-total");
		var projects = document.getElementById("usis-hours-kpi-projects");
		var avg = document.getElementById("usis-hours-kpi-avg");
		var top = document.getElementById("usis-hours-kpi-top");
		if (total) total.textContent = fmtHours(summary.total_hours);
		if (projects) projects.textContent = summary.project_count != null ? String(summary.project_count) : "—";
		if (avg) avg.textContent = fmtHours(summary.avg_hours_per_project);
		if (top) {
			var name = summary.top_project_name || "—";
			top.textContent = name;
			top.setAttribute("title", name);
		}
	}

	function truncateLabel(name, max) {
		var s = String(name || "").trim() || "—";
		if (s.length <= max) return s;
		return s.slice(0, max - 1) + "…";
	}

	function chartOptions(labels, hours) {
		return {
			series: [
				{
					name: "Hours logged",
					type: "column",
					data: hours,
				},
			],
			chart: {
				height: 300,
				type: "line",
				stacked: false,
				toolbar: { show: false },
			},
			grid: {
				borderColor: "var(--bs-border-color)",
			},
			stroke: {
				width: [0],
				curve: "straight",
			},
			legend: {
				fontSize: "13px",
				labels: { colors: "var(--bs-body-color)" },
			},
			plotOptions: {
				bar: {
					columnWidth: labels.length > 8 ? "65%" : "45%",
					borderRadius: 6,
				},
			},
			fill: {
				type: "gradient",
				gradient: {
					shade: "light",
					type: "vertical",
					colorStops: [
						{ offset: 0, color: "var(--bs-primary)", opacity: 1 },
						{ offset: 100, color: "var(--bs-primary)", opacity: 0.85 },
					],
				},
			},
			colors: ["var(--bs-primary)"],
			dataLabels: { enabled: false },
			xaxis: {
				categories: labels,
				labels: {
					rotate: labels.length > 6 ? -40 : 0,
					trim: true,
					hideOverlappingLabels: true,
					style: {
						fontSize: "12px",
						colors: "var(--bs-body-color)",
					},
				},
				tooltip: { enabled: false },
			},
			yaxis: {
				min: 0,
				title: {
					text: "Hours",
					style: { color: "var(--bs-body-color)", fontSize: "12px" },
				},
				labels: {
					style: { colors: "var(--bs-body-color)", fontSize: "12px" },
					formatter: function (v) {
						return Math.round(v);
					},
				},
			},
			tooltip: {
				shared: true,
				intersect: false,
				y: {
					formatter: function (y) {
						if (typeof y === "undefined") return y;
						return fmtHours(y) + " hrs";
					},
				},
			},
		};
	}

	function renderChart(labels, hours) {
		var el = document.querySelector("#usisHoursByProjectChart");
		if (!el || typeof ApexCharts === "undefined") return;
		setVisible("usisHoursByProjectChart", true);
		if (!chart) {
			chart = new ApexCharts(el, chartOptions(labels, hours));
			chart.render();
		} else {
			chart.updateOptions({
				xaxis: { categories: labels },
				series: [{ name: "Hours logged", type: "column", data: hours }],
			});
		}
	}

	function loadPeriod(period) {
		currentPeriod = period || "month";
		setVisible("usis-hours-project-loading", true);
		setVisible("usis-hours-project-empty", false);
		setVisible("usisHoursByProjectChart", false);

		fetch(apiBase() + "/api/v1/dashboard/hours-by-project?period=" + encodeURIComponent(currentPeriod), {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				if (!r.ok) {
					return r.json().then(function (j) {
						throw new Error((j && j.error) || "HTTP " + r.status);
					});
				}
				return r.json();
			})
			.then(function (data) {
				setVisible("usis-hours-project-loading", false);
				var items = data.projects || [];
				setKpis(data.summary);
				if (!items.length) {
					setVisible("usis-hours-project-empty", true);
					if (chart) {
						chart.updateOptions({ xaxis: { categories: [] }, series: [{ name: "Hours logged", type: "column", data: [] }] });
					}
					return;
				}
				var labels = items.map(function (p) {
					return truncateLabel(p.project_name, 28);
				});
				var hours = items.map(function (p) {
					return Number(p.hours) || 0;
				});
				renderChart(labels, hours);
			})
			.catch(function (err) {
				setVisible("usis-hours-project-loading", false);
				setVisible("usis-hours-project-empty", true);
				var empty = document.getElementById("usis-hours-project-empty");
				if (empty) {
					empty.textContent = err.message || "Could not load project hours.";
				}
			});
	}

	function wireTabs() {
		var tabs = document.querySelectorAll(".usis-hours-project-chart-tab .nav-link");
		tabs.forEach(function (btn) {
			btn.addEventListener("click", function () {
				tabs.forEach(function (b) {
					b.classList.remove("active");
					b.setAttribute("aria-selected", "false");
				});
				btn.classList.add("active");
				btn.setAttribute("aria-selected", "true");
				var period = btn.getAttribute("data-period") || "month";
				loadPeriod(period);
			});
		});
	}

	function init() {
		if (!isDarkDash()) return;
		if (!document.getElementById("usisHoursByProjectChart")) return;
		wireTabs();
		loadPeriod("month");
	}

	if (typeof jQuery !== "undefined") {
		jQuery(document).ready(function () {
			setTimeout(init, 400);
		});
	} else if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", function () {
			setTimeout(init, 400);
		});
	} else {
		setTimeout(init, 400);
	}
})();
