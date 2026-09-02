/**
 * USIS CM Time office UI (W3CRM + DataTables + USISUi).
 */
(function () {
	"use strict";

	function api() {
		return window.USIS_API || {};
	}
	function fetchJson(path, opts) {
		return api().fetchJson ? api().fetchJson(path, opts || {}) : Promise.reject(new Error("API missing"));
	}
	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;");
	}
	function chip(status, opts) {
		if (window.USISUi && window.USISUi.statusChip) return window.USISUi.statusChip(status, opts || {});
		return '<span class="badge bg-secondary">' + esc((opts && opts.label) || status) + "</span>";
	}
	function empty(title, body) {
		if (window.USISUi && window.USISUi.emptyState) return window.USISUi.emptyState({ title: title, body: body });
		return '<p class="text-muted">' + esc(body || title) + "</p>";
	}
	function fmtHours(n) {
		if (n == null || n === "") return "0.00";
		return Number(n).toFixed(2);
	}
	function fmtTime(iso) {
		if (!iso) return "—";
		var d = new Date(iso);
		if (isNaN(d.getTime())) return "—";
		return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
	}
	function qs(name) {
		return new URLSearchParams(window.location.search).get(name);
	}
	function subnav(active) {
		var items = [
			["live", "usis-time-live.html", "Live"],
			["me", "usis-time-me.html", "My Time"],
			["cards", "usis-time-cards.html", "Time cards"],
			["events", "usis-time-events.html", "Event log"],
			["exceptions", "usis-time-exceptions.html", "Exceptions"],
			["payroll", "usis-time-payroll.html", "Payroll period"],
			["map", "usis-time-map.html", "Map"],
			["settings", "usis-time-settings.html", "Settings"],
		];
		return (
			'<ul class="nav nav-pills mb-3">' +
			items
				.map(function (it) {
					return (
						'<li class="nav-item"><a class="nav-link' +
						(it[0] === active ? " active" : "") +
						'" href="' +
						it[1] +
						'">' +
						esc(it[2]) +
						"</a></li>"
					);
				})
				.join("") +
			"</ul>"
		);
	}

	function kpiCard(label, value, href) {
		return (
			'<a class="card h-100 text-decoration-none text-reset" href="' +
			esc(href || "#") +
			'"><div class="card-body py-3"><div class="text-muted small">' +
			esc(label) +
			'</div><div class="fs-4 fw-semibold" style="color:#1F4E5F">' +
			esc(String(value)) +
			"</div></div></a>"
		);
	}

	function dt(tableId) {
		var el = document.getElementById(tableId);
		if (!el || !window.jQuery || !window.jQuery.fn || !window.jQuery.fn.DataTable) return;
		if (window.jQuery.fn.DataTable.isDataTable(el)) window.jQuery(el).DataTable().destroy();
		window.jQuery(el).DataTable({ pageLength: 25, order: [] });
	}

	function promptReason() {
		return window.prompt("Reason (required)") || "";
	}

	function renderLive(root) {
		var projectId = qs("project_id");
		root.innerHTML = subnav("live") + '<p class="small text-muted" id="usis-time-updated"></p><div id="usis-time-live-body">Loading…</div>';
		function load() {
			var url = "/api/time/live" + (projectId ? "?project_id=" + encodeURIComponent(projectId) : "");
			fetchJson(url).then(function (data) {
				var k = data.kpis || {};
				var body = document.getElementById("usis-time-live-body");
				var roster = data.roster || [];
				var tab = (window.localStorage.getItem("usis-time-live-tab") || "in");
				var filtered = roster.filter(function (r) {
					if (tab === "in") return r.status === "in";
					if (tab === "break") return r.status === "break";
					return true;
				});
				body.innerHTML =
					'<div class="row g-2 mb-3">' +
					'<div class="col">' + kpiCard("Clocked in", k.clocked_in || 0, "usis-time-live.html") + "</div>" +
					'<div class="col">' + kpiCard("On break", k.on_break || 0, "usis-time-live.html") + "</div>" +
					'<div class="col">' + kpiCard("Open >" + (data.open_punch_flag_after_hours || 12) + "h", k.open_old || 0, "usis-time-exceptions.html") + "</div>" +
					'<div class="col">' + kpiCard("Flags today", k.flags_today || 0, "usis-time-exceptions.html") + "</div>" +
					'<div class="col">' + kpiCard("Unsigned 7d", k.unsigned_7d || 0, "usis-time-exceptions.html") + "</div>" +
					"</div>" +
					'<div class="row g-2 mb-3">' +
					'<div class="col-md-4">' + kpiCard("Hours this period", fmtHours(k.hours_period), "usis-time-cards.html") + "</div>" +
					'<div class="col-md-4">' + kpiCard("OT this period", fmtHours(k.ot_period), "usis-time-cards.html") + "</div>" +
					'<div class="col-md-4">' + kpiCard("Meal/rest 7d", k.meal_7d || 0, "usis-time-exceptions.html?type=missing_meal,missing_rest") + "</div>" +
					"</div>" +
					'<div class="row g-2 mb-3">' +
					'<div class="col-md-4">' + kpiCard("Inaccurate 7d", k.inaccurate_7d || 0, "usis-time-exceptions.html") + "</div>" +
					'<div class="col-md-4">' + kpiCard("Injuries 7d", k.injuries_7d || 0, "usis-time-exceptions.html?type=injury_reported") + "</div>" +
					"</div>" +
					'<ul class="nav nav-tabs mb-2" id="usis-live-tabs">' +
					'<li class="nav-item"><button type="button" class="nav-link' + (tab === "in" ? " active" : "") + '" data-tab="in">Clocked in</button></li>' +
					'<li class="nav-item"><button type="button" class="nav-link' + (tab === "break" ? " active" : "") + '" data-tab="break">On break</button></li>' +
					'<li class="nav-item"><button type="button" class="nav-link' + (tab === "all" ? " active" : "") + '" data-tab="all">Show all</button></li>' +
					"</ul>" +
					(filtered.length
						? '<div class="table-responsive"><table class="table table-sm table-hover" id="usis-live-table"><thead><tr>' +
							"<th>Employee</th><th>Status</th><th>Project</th><th>Since</th><th>Elapsed</th><th>Day start</th><th>GPS</th><th>Flag</th><th></th></tr></thead><tbody>" +
							filtered
								.map(function (r) {
									var mins = Math.floor((r.elapsed_seconds || 0) / 60);
									return (
										"<tr><td>" +
										esc(r.employee) +
										"</td><td>" +
										chip(r.status === "in" ? "In" : r.status === "break" ? "Break" : "Out") +
										"</td><td>" +
										esc(r.project) +
										"</td><td>" +
										esc(fmtTime(r.since)) +
										"</td><td>" +
										esc(String(Math.floor(mins / 60) + ":" + String(mins % 60).padStart(2, "0"))) +
										"</td><td>" +
										esc(fmtTime(r.day_start)) +
										"</td><td>" +
										(r.gps ? "pin" : "") +
										"</td><td>" +
										(r.flag ? chip("warning", { label: "Flag" }) : "") +
										'</td><td class="text-nowrap"><a class="btn btn-sm btn-outline-secondary" href="usis-time-cards.html?user_id=' +
										esc(r.user_id) +
										'">Card</a> <a class="btn btn-sm btn-outline-secondary" href="usis-time-map.html?user_id=' +
										esc(r.user_id) +
										'">Map</a> <button type="button" class="btn btn-sm btn-outline-primary" data-out="' +
										esc(r.user_id) +
										'">Clock out</button></td></tr>'
									);
								})
								.join("") +
							"</tbody></table></div>"
						: empty("Nobody is on the clock.", "Clock-ins from the phone appear here within 30 seconds."));
				document.getElementById("usis-time-updated").textContent = "Updated just now";
				dt("usis-live-table");
				document.querySelectorAll("#usis-live-tabs [data-tab]").forEach(function (btn) {
					btn.addEventListener("click", function () {
						window.localStorage.setItem("usis-time-live-tab", btn.getAttribute("data-tab"));
						load();
					});
				});
				body.querySelectorAll("[data-out]").forEach(function (btn) {
					btn.addEventListener("click", function () {
						var reason = promptReason();
						if (!reason) return;
						fetchJson("/api/time/punch", {
							method: "POST",
							body: { action: "clock_out", user_id: btn.getAttribute("data-out"), local_id: crypto.randomUUID(), source: "web", reason: reason },
						}).then(load);
					});
				});
			});
		}
		load();
		setInterval(function () {
			if (document.hidden) return;
			load();
		}, 30000);
	}

	function renderMe(root) {
		root.innerHTML = subnav("me") + '<div id="usis-time-me">Loading…</div>';
		fetchJson("/api/time/me").then(function (data) {
			var box = document.getElementById("usis-time-me");
			var st = data.status || "out";
			var banner = data.sign_ready
				? '<div class="alert mb-3" style="background:#1F4E5F;color:#fff">Time card ready to sign. <button type="button" class="btn btn-sm btn-light" id="usis-sign">Review &amp; Sign</button></div>'
				: "";
			var punchBtns = data.web_punch_allowed
				? '<div class="btn-group mb-3" id="usis-punch-btns">' +
					'<button type="button" class="btn btn-primary" data-act="clock_in">Clock in</button>' +
					'<button type="button" class="btn btn-outline-primary" data-act="break_start">Break</button>' +
					'<button type="button" class="btn btn-outline-primary" data-act="break_end">End break</button>' +
					'<button type="button" class="btn btn-outline-primary" data-act="switch">Switch</button>' +
					'<button type="button" class="btn btn-outline-secondary" data-act="clock_out">Clock out</button></div>'
				: "";
			var h = data.hours || {};
			box.innerHTML =
				'<div class="d-flex flex-wrap align-items-center gap-2 mb-3"><h4 class="mb-0">' +
				esc((data.profile && data.profile.name) || "") +
				"</h4>" +
				chip(st === "in" ? "In" : st === "break" ? "Break" : "Out") +
				'<a class="btn btn-sm btn-outline-secondary" href="usis-time-cards.html">Time card</a></div>' +
				banner +
				punchBtns +
				'<div class="row g-2 mb-3"><div class="col">' +
				kpiCard("Today", fmtHours((h.today || {}).total), "usis-time-cards.html") +
				'</div><div class="col">' +
				kpiCard("This week", fmtHours((h.week || {}).total), "usis-time-cards.html") +
				'</div><div class="col">' +
				kpiCard("Pay period", fmtHours((h.period || {}).total), "usis-time-cards.html") +
				"</div></div>" +
				'<h6>Today</h6><div id="usis-today-tl"></div><h6 class="mt-3">Hours by project · 14 days</h6><div id="usis-by-proj"></div>';
			document.getElementById("usis-today-tl").innerHTML = (data.today || [])
				.map(function (e) {
					return '<div class="small">' + esc(fmtTime(e.start_at)) + " – " + esc(fmtTime(e.end_at)) + " · " + esc(e.entry_type) + "</div>";
				})
				.join("") || empty("No punches today.", "");
			document.getElementById("usis-by-proj").innerHTML = (data.hours_by_project || [])
				.map(function (p) {
					return '<div class="d-flex justify-content-between border-bottom py-1"><span>' + esc(p.name) + "</span><span>" + fmtHours(p.hours) + "</span></div>";
				})
				.join("") || empty("No hours in the last 14 days.", "");
			var sign = document.getElementById("usis-sign");
			if (sign && data.period) {
				sign.addEventListener("click", function () {
					fetchJson("/api/time/periods/" + data.period.id + "/sign", { method: "POST", body: { attested: true, signature_png: "signed" } }).then(function () {
						location.reload();
					});
				});
			}
			document.querySelectorAll("#usis-punch-btns [data-act]").forEach(function (btn) {
				btn.addEventListener("click", function () {
					var act = btn.getAttribute("data-act");
					var projectId = (data.open && data.open.project_id) || qs("project_id") || window.prompt("Project UUID");
					if ((act === "clock_in" || act === "switch") && !projectId) return;
					fetchJson("/api/time/punch", {
						method: "POST",
						body: { action: act, project_id: projectId, local_id: crypto.randomUUID(), source: "web" },
					}).then(function () {
						location.reload();
					});
				});
			});
		});
	}

	function renderCards(root) {
		root.innerHTML = subnav("cards") + '<div class="mb-2 btn-group" id="usis-card-view">' +
			'<button class="btn btn-sm btn-primary" data-view="summary">Summary</button>' +
			'<button class="btn btn-sm btn-outline-primary" data-view="card">Card</button>' +
			'<button class="btn btn-sm btn-outline-primary" data-view="entries">Entries</button></div>' +
			'<div id="usis-cards-body">Loading…</div>';
		function load(view) {
			fetchJson("/api/time/cards").then(function (data) {
				var body = document.getElementById("usis-cards-body");
				var items = data.items || [];
				if (view === "entries") {
					fetchJson("/api/time/entries").then(function (en) {
						var rows = en.items || [];
						body.innerHTML = rows.length
							? '<div class="table-responsive"><table class="table table-sm" id="usis-entries-table"><thead><tr><th>Date</th><th>Start</th><th>End</th><th>Project</th><th>Source</th><th></th></tr></thead><tbody>' +
								rows
									.map(function (e) {
										return (
											"<tr><td>" +
											esc(e.work_date) +
											"</td><td>" +
											esc(fmtTime(e.start_at)) +
											"</td><td>" +
											esc(fmtTime(e.end_at)) +
											"</td><td>" +
											esc(e.project_id) +
											"</td><td>" +
											esc(e.source) +
											'</td><td><button class="btn btn-sm btn-outline-secondary" data-split="' +
											esc(e.id) +
											'">Split</button></td></tr>'
										);
									})
									.join("") +
								"</tbody></table></div>"
							: empty("No entries.", "");
						dt("usis-entries-table");
						body.querySelectorAll("[data-split]").forEach(function (btn) {
							btn.addEventListener("click", function () {
								var at = window.prompt("Split at (ISO)");
								var reason = promptReason();
								if (!at || !reason) return;
								fetchJson("/api/time/entries/" + btn.getAttribute("data-split") + "/split", { method: "POST", body: { at: at, reason: reason } }).then(function () {
									load("entries");
								});
							});
						});
					});
					return;
				}
				if (view === "card") {
					body.innerHTML = items.length
						? items
								.map(function (i) {
									return (
										'<div class="card mb-2"><div class="card-body py-2"><div class="d-flex justify-content-between"><strong>' +
										esc(i.employee) +
										"</strong><span>" +
										fmtHours(i.total) +
										" h</span></div>" +
										((i.days || [])
											.map(function (d) {
												return (
													'<div class="small d-flex justify-content-between border-bottom py-1"><span>' +
													esc(d.date) +
													(d.signed ? " · signed" : "") +
													"</span><span>Reg " +
													fmtHours(d.regular) +
													" · OT " +
													fmtHours(d.ot) +
													" · DT " +
													fmtHours(d.dt) +
													"</span></div>"
												);
											})
											.join("") || empty("No days.", "")) +
										"</div></div>"
									);
								})
								.join("")
						: empty("No time cards this period.", "");
					return;
				}
				body.innerHTML = items.length
					? '<div class="table-responsive"><table class="table table-sm" id="usis-cards-table"><thead><tr><th>Employee</th><th>Emp signed</th><th>Approved</th><th>Flags</th><th>Reg</th><th>OT</th><th>DT</th><th>Premium</th><th>Total</th></tr></thead><tbody>' +
						items
							.map(function (i) {
								return (
									"<tr><td>" +
									esc(i.employee) +
									"</td><td>" +
									(i.emp_signed ? "Yes" : "No") +
									"</td><td>" +
									(i.super_approved ? "Yes" : "No") +
									"</td><td>" +
									esc((i.flags || []).join(", ")) +
									"</td><td>" +
									fmtHours(i.regular) +
									"</td><td>" +
									fmtHours(i.ot) +
									"</td><td>" +
									fmtHours(i.dt) +
									"</td><td>" +
									fmtHours(i.premium) +
									"</td><td>" +
									fmtHours(i.total) +
									"</td></tr>"
								);
							})
							.join("") +
						"</tbody></table></div>"
					: empty("No time cards this period.", "");
				dt("usis-cards-table");
			});
		}
		load("summary");
		document.querySelectorAll("#usis-card-view [data-view]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				load(btn.getAttribute("data-view"));
			});
		});
	}

	function renderEvents(root) {
		root.innerHTML = subnav("events") + '<div id="usis-events">Loading…</div>';
		fetchJson("/api/time/events").then(function (data) {
			var rows = data.items || [];
			document.getElementById("usis-events").innerHTML = rows.length
				? '<div class="table-responsive"><table class="table table-sm" id="usis-events-table"><thead><tr><th>When</th><th>Action</th><th>Whose card</th><th>By</th><th>Source</th><th>Reason</th></tr></thead><tbody>' +
					rows
						.map(function (e) {
							return (
								"<tr><td>" +
								esc(fmtTime(e.at || e.occurred_at)) +
								"</td><td>" +
								esc(e.kind) +
								"</td><td>" +
								esc(e.employee) +
								"</td><td>" +
								esc(e.performed_by) +
								"</td><td>" +
								esc(e.source) +
								"</td><td>" +
								esc(e.reason || "") +
								"</td></tr>"
							);
						})
						.join("") +
					"</tbody></table></div>"
				: empty("No events.", "");
			dt("usis-events-table");
		});
	}

	function renderExceptions(root) {
		var type = qs("type") || "";
		root.innerHTML = subnav("exceptions") + '<div id="usis-ex">Loading…</div>';
		fetchJson("/api/time/flags?status=open" + (type ? "&type=" + encodeURIComponent(type) : "")).then(function (data) {
			var rows = data.items || [];
			document.getElementById("usis-ex").innerHTML = rows.length
				? '<div class="table-responsive"><table class="table table-sm" id="usis-ex-table"><thead><tr><th>When</th><th>Employee</th><th>Project</th><th>Type</th><th>Detail</th><th>Status</th><th></th></tr></thead><tbody>' +
					rows
						.map(function (f) {
							return (
								"<tr><td>" +
								esc(fmtTime(f.when)) +
								"</td><td>" +
								esc(f.employee) +
								"</td><td>" +
								esc(f.project) +
								"</td><td>" +
								esc(f.type) +
								"</td><td>" +
								esc(f.detail || "") +
								"</td><td>" +
								chip(f.status) +
								'</td><td><button class="btn btn-sm btn-outline-primary" data-acc="' +
								esc(f.id) +
								'">Accept</button> <button class="btn btn-sm btn-outline-secondary" data-dis="' +
								esc(f.id) +
								'">Dismiss</button></td></tr>'
							);
						})
						.join("") +
					"</tbody></table></div>"
				: empty("No open exceptions.", "Payroll’s morning queue is clear.");
			dt("usis-ex-table");
			function act(id, path) {
				var reason = promptReason();
				if (!reason) return;
				fetchJson("/api/time/flags/" + id + "/" + path, { method: "POST", body: { reason: reason } }).then(function () {
					location.reload();
				});
			}
			document.querySelectorAll("[data-acc]").forEach(function (b) {
				b.addEventListener("click", function () {
					act(b.getAttribute("data-acc"), "accept");
				});
			});
			document.querySelectorAll("[data-dis]").forEach(function (b) {
				b.addEventListener("click", function () {
					act(b.getAttribute("data-dis"), "dismiss");
				});
			});
		});
	}

	function renderPayroll(root) {
		root.innerHTML = subnav("payroll") + '<div id="usis-pay">Loading…</div>';
		fetchJson("/api/time/periods").then(function (data) {
			var cur = (data.items || [])[0];
			if (!cur) {
				document.getElementById("usis-pay").innerHTML = empty("No pay period.", "");
				return;
			}
			fetchJson("/api/time/periods/" + cur.id).then(function (detail) {
				var scan = ((detail.scan && detail.scan.checks) || [])
					.map(function (c) {
						return '<div>' + (c.ok ? "✓" : "○") + " " + esc(c.label) + (c.remaining ? " (" + c.remaining + ")" : "") + "</div>";
					})
					.join("");
				var t = detail.totals || {};
				document.getElementById("usis-pay").innerHTML =
					'<div class="d-flex justify-content-between align-items-center mb-3"><h5 class="mb-0">' +
					esc(detail.period.start) +
					" – " +
					esc(detail.period.end) +
					'</h5><div><button class="btn btn-sm btn-outline-secondary" id="usis-lock">Lock</button> <button class="btn btn-sm btn-primary" id="usis-export">Export CSV</button> <a class="btn btn-sm btn-outline-primary" href="/api/time/periods/' +
					esc(cur.id) +
					'/pdf" target="_blank">Print PDF</a></div></div>' +
					'<div class="row g-2 mb-3"><div class="col">' +
					kpiCard("Regular", fmtHours(t.regular)) +
					'</div><div class="col">' +
					kpiCard("OT", fmtHours(t.ot)) +
					'</div><div class="col">' +
					kpiCard("DT", fmtHours(t.dt)) +
					'</div><div class="col">' +
					kpiCard("Total", fmtHours(t.total)) +
					"</div></div><h6>Scan</h6>" +
					scan +
					'<div class="table-responsive mt-3"><table class="table table-sm" id="usis-pay-table"><thead><tr><th>Employee</th><th>Class</th><th>Signed</th><th>Approved</th><th>Reg</th><th>OT</th><th>DT</th><th>Total</th></tr></thead><tbody>' +
					(detail.items || [])
						.map(function (i) {
							return (
								"<tr><td>" +
								esc(i.employee) +
								"</td><td>" +
								esc(i.classification || "—") +
								"</td><td>" +
								(i.emp_signed ? "Yes" : "No") +
								"</td><td>" +
								(i.super_approved ? "Yes" : "No") +
								"</td><td>" +
								fmtHours(i.regular) +
								"</td><td>" +
								fmtHours(i.ot) +
								"</td><td>" +
								fmtHours(i.dt) +
								"</td><td>" +
								fmtHours(i.total) +
								"</td></tr>"
							);
						})
						.join("") +
					"</tbody></table></div>";
				dt("usis-pay-table");
				document.getElementById("usis-lock").addEventListener("click", function () {
					fetchJson("/api/time/periods/" + cur.id + "/lock", { method: "POST", body: {} }).then(function () {
						location.reload();
					});
				});
				document.getElementById("usis-export").addEventListener("click", function () {
					fetchJson("/api/time/periods/" + cur.id + "/export", { method: "POST", body: {} })
						.then(function (res) {
							var csv = res.item && res.item.csv;
							if (csv) {
								var blob = new Blob([csv], { type: "text/csv" });
								var a = document.createElement("a");
								a.href = URL.createObjectURL(blob);
								a.download = "payroll.csv";
								a.click();
							}
							if (res.item && res.item.file_url) window.open(res.item.file_url, "_blank");
						})
						.catch(function () {
							window.alert("Export blocked — clear open flags first.");
						});
				});
			});
		});
	}

	function renderMap(root) {
		root.innerHTML = subnav("map") + '<div id="usis-map" style="height:70vh;background:#F4F6F8"></div><p class="small text-muted mt-2">Pins are people currently on the clock. Trails are labeled pings, not routes.</p>';
		var css = document.createElement("link");
		css.rel = "stylesheet";
		css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
		document.head.appendChild(css);
		var s = document.createElement("script");
		s.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
		s.onload = function () {
			var map = window.L.map("usis-map").setView([36.7, -119.7], 6);
			window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap" }).addTo(map);
			var q = "/api/time/map";
			var uid = qs("user_id");
			var pid = qs("project_id");
			if (uid) q += (q.indexOf("?") >= 0 ? "&" : "?") + "user_id=" + encodeURIComponent(uid);
			if (pid) q += (q.indexOf("?") >= 0 ? "&" : "?") + "project_id=" + encodeURIComponent(pid);
			if (qs("date")) q += "&date=" + encodeURIComponent(qs("date"));
			fetchJson(q).then(function (data) {
				(data.pins || []).forEach(function (p) {
					window.L.marker([p.lat, p.lon]).addTo(map).bindPopup(esc(p.name) + "<br>" + esc(p.project || ""));
				});
				if ((data.pings || []).length) {
					var latlngs = data.pings.map(function (p) {
						return [p.lat, p.lon];
					});
					window.L.polyline(latlngs, { color: "#1F4E5F" }).addTo(map);
				}
			});
		};
		document.body.appendChild(s);
	}

	function renderSettings(root) {
		root.innerHTML = subnav("settings") + '<div id="usis-set">Loading…</div>';
		fetchJson("/api/time/settings").then(function (data) {
			var p = data.policy || {};
			var codes = data.cost_codes || [];
			document.getElementById("usis-set").innerHTML =
				'<div class="card mb-3"><div class="card-body"><h6>Policy</h6><pre class="small mb-2">' +
				esc(JSON.stringify(p, null, 2)) +
				'</pre>' +
				(data.can_edit
					? '<label class="form-label small">Edit JSON</label><textarea class="form-control form-control-sm mb-2" id="usis-policy-json" rows="10">' +
						esc(JSON.stringify(p, null, 2)) +
						'</textarea><button class="btn btn-sm btn-primary" id="usis-save-policy">Save policy</button>'
					: "") +
				"</div></div>" +
				'<div class="card"><div class="card-body"><h6>Cost code library</h6><p class="small text-muted">Optional punch field. Not a live tracker.</p><table class="table table-sm"><thead><tr><th>Code</th><th>Name</th><th>Trade</th></tr></thead><tbody>' +
				codes
					.map(function (c) {
						return "<tr><td>" + esc(c.code) + "</td><td>" + esc(c.name) + "</td><td>" + esc(c.trade || "") + "</td></tr>";
					})
					.join("") +
				"</tbody></table></div></div>";
			var save = document.getElementById("usis-save-policy");
			if (save) {
				save.addEventListener("click", function () {
					try {
						var parsed = JSON.parse(document.getElementById("usis-policy-json").value);
						fetchJson("/api/time/settings", { method: "PUT", body: parsed }).then(function () {
							location.reload();
						});
					} catch (e) {
						window.alert("Invalid JSON");
					}
				});
			}
		});
	}

	function renderProjectTime(root) {
		var pid = qs("id") || qs("project_id");
		root.innerHTML = '<div id="usis-proj-time">Loading Field Time…</div>';
		if (!pid) {
			document.getElementById("usis-proj-time").innerHTML = empty("Open a project.", "Field Time needs a project id in the URL.");
			return;
		}
		Promise.all([
			fetchJson("/api/time/live?project_id=" + encodeURIComponent(pid)),
			fetchJson("/api/time/projects/" + encodeURIComponent(pid) + "/geofence"),
			fetchJson("/api/time/job-cost?project_id=" + encodeURIComponent(pid)),
			fetchJson("/api/time/cards?project_id=" + encodeURIComponent(pid)),
		]).then(function (res) {
			var live = res[0];
			var fence = (res[1] && res[1].item) || {};
			var cost = res[2] || {};
			var cards = (res[3] && res[3].items) || [];
			var roster = live.roster || [];
			document.getElementById("usis-proj-time").innerHTML =
				'<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">' +
				"<div><h5 class=\"mb-0\">Time on this job</h5><p class=\"small text-muted mb-0\">Same clock as Time → Live, scoped to this project. Field → Schedule is still the construction plan.</p></div>" +
				'<a class="btn btn-sm btn-outline-secondary" href="usis-time-map.html?project_id=' +
				esc(pid) +
				'">Open map</a></div>' +
				'<div class="row g-2 mb-3"><div class="col">' +
				kpiCard("On site", (live.kpis && live.kpis.clocked_in) || 0, "usis-time-live.html?project_id=" + pid) +
				'</div><div class="col">' +
				kpiCard("On break", (live.kpis && live.kpis.on_break) || 0) +
				'</div><div class="col">' +
				kpiCard("Hours this range", fmtHours(cost.actual_hours), "usis-time-cards.html?project_id=" + pid) +
				"</div></div>" +
				"<h6>Live on this job</h6>" +
				(roster.length
					? '<div class="table-responsive mb-3"><table class="table table-sm" id="usis-proj-live"><thead><tr><th>Employee</th><th>Status</th><th>Since</th><th>Elapsed</th><th>Flag</th></tr></thead><tbody>' +
						roster
							.map(function (r) {
								var mins = Math.floor((r.elapsed_seconds || 0) / 60);
								return (
									"<tr><td>" +
									esc(r.employee) +
									"</td><td>" +
									chip(r.status === "in" ? "In" : "Break") +
									"</td><td>" +
									esc(fmtTime(r.since)) +
									"</td><td>" +
									esc(String(Math.floor(mins / 60) + ":" + String(mins % 60).padStart(2, "0"))) +
									"</td><td>" +
									(r.flag ? chip("warning", { label: "Flag" }) : "") +
									"</td></tr>"
								);
							})
							.join("") +
						"</tbody></table></div>"
					: empty("Nobody is on this job.", "Clock-ins on this project appear here.")) +
				'<div class="card mb-3"><div class="card-body"><h6>Geofence</h6><p class="small text-muted">Verification only. Does not auto clock anyone in or out.</p><div class="row g-2">' +
				'<div class="col-md-2"><label class="form-label small">Mode</label><select class="form-select form-select-sm" id="gf-mode"><option value="flag">flag</option><option value="block">block</option></select></div>' +
				'<div class="col-md-2"><label class="form-label small">Lat</label><input class="form-control form-control-sm" id="gf-lat"></div>' +
				'<div class="col-md-2"><label class="form-label small">Lon</label><input class="form-control form-control-sm" id="gf-lon"></div>' +
				'<div class="col-md-2"><label class="form-label small">Radius m</label><input class="form-control form-control-sm" id="gf-r"></div>' +
				'<div class="col-md-2 d-flex align-items-end"><button class="btn btn-sm btn-primary" id="gf-save">Save fence</button></div></div></div></div>' +
				'<div class="card mb-3"><div class="card-body"><h6>Hours this range vs estimate</h6><p class="mb-0">' +
				fmtHours(cost.actual_hours) +
				" actual hours" +
				(cost.estimate_hours != null ? " vs " + fmtHours(cost.estimate_hours) + " estimate lines" : " (no estimate hours on file)") +
				"</p></div></div>" +
				"<h6>Cards that touched this job</h6>" +
				(cards.length
					? '<div class="table-responsive"><table class="table table-sm"><thead><tr><th>Employee</th><th>Signed</th><th>Reg</th><th>OT</th><th>Total</th></tr></thead><tbody>' +
						cards
							.map(function (i) {
								return (
									"<tr><td>" +
									esc(i.employee) +
									"</td><td>" +
									(i.emp_signed ? "Yes" : "No") +
									"</td><td>" +
									fmtHours(i.regular) +
									"</td><td>" +
									fmtHours(i.ot) +
									"</td><td>" +
									fmtHours(i.total) +
									"</td></tr>"
								);
							})
							.join("") +
						"</tbody></table></div>"
					: empty("No cards this period.", ""));
			dt("usis-proj-live");
			document.getElementById("gf-mode").value = fence.mode || "flag";
			document.getElementById("gf-lat").value = fence.center_lat || "";
			document.getElementById("gf-lon").value = fence.center_lon || "";
			document.getElementById("gf-r").value = fence.radius_m || "";
			document.getElementById("gf-save").addEventListener("click", function () {
				fetchJson("/api/time/projects/" + encodeURIComponent(pid) + "/geofence", {
					method: "PUT",
					body: {
						mode: document.getElementById("gf-mode").value,
						shape: "circle",
						center_lat: document.getElementById("gf-lat").value,
						center_lon: document.getElementById("gf-lon").value,
						radius_m: document.getElementById("gf-r").value,
					},
				});
			});
		});
	}

	function init() {
		var page = (document.body.getAttribute("data-time-page") || "").trim();
		var root = document.getElementById("usis-time-root");
		if (!root) {
			root = document.getElementById("usis-proj-time-root");
			if (root && !page) page = "project";
		}
		if (!root) return;
		if (page === "live") renderLive(root);
		else if (page === "me") renderMe(root);
		else if (page === "cards") renderCards(root);
		else if (page === "events") renderEvents(root);
		else if (page === "exceptions") renderExceptions(root);
		else if (page === "payroll") renderPayroll(root);
		else if (page === "map") renderMap(root);
		else if (page === "settings") renderSettings(root);
		else if (page === "project") renderProjectTime(root);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
