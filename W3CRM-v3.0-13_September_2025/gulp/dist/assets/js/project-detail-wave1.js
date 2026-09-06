/**
 * Wave 1 Sage CM: job cost codes, CPR/CO, directory, daily log, SCO.
 */
(function () {
	"use strict";

	function api() {
		return window.USIS_API || {};
	}

	function projectId() {
		if (window.USISProjectContext && typeof window.USISProjectContext.projectIdFromQuery === "function") {
			return window.USISProjectContext.projectIdFromQuery();
		}
		var p = new URLSearchParams(window.location.search);
		return (p.get("id") || p.get("project_id") || p.get("projectId") || "").trim() || null;
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function money(n) {
		if (n == null || n === "") return "—";
		var x = Number(n);
		if (isNaN(x)) return String(n);
		return x.toLocaleString(undefined, { style: "currency", currency: "USD" });
	}

	function fetchJson(path, opts) {
		return api().fetchJson(path, opts || {});
	}

	function pidPath(suffix) {
		return "/api/v1/projects/" + encodeURIComponent(projectId()) + suffix;
	}

	function emptyRow(cols, msg) {
		return '<tr><td colspan="' + cols + '" class="text-muted">' + esc(msg) + "</td></tr>";
	}

	function linesToList(text) {
		return String(text || "")
			.split("\n")
			.map(function (s) {
				return s.trim();
			})
			.filter(Boolean)
			.map(function (line) {
				return { notes: line };
			});
	}

	function listToLines(arr) {
		if (!arr) return "";
		if (typeof arr === "string") return arr;
		if (!Array.isArray(arr)) return "";
		return arr
			.map(function (x) {
				if (typeof x === "string") return x;
				if (x.company || x.count) {
					return [x.company, x.count, x.notes].filter(Boolean).join(" — ");
				}
				return x.notes || x.name || x.description || "";
			})
			.filter(Boolean)
			.join("\n");
	}

	function loadJcc() {
		var tbody = document.getElementById("usis-jcc-tbody");
		if (!tbody || !projectId()) return Promise.resolve();
		return fetchJson(pidPath("/rfi-lookups/cost_codes"))
			.then(function (data) {
				var items = (data && data.items) || data || [];
				if (!Array.isArray(items)) items = [];
				if (!items.length) {
					tbody.innerHTML = emptyRow(7, "No takeoff cost codes yet. Assign codes on takeoff lines.");
					return;
				}
				tbody.innerHTML = items
					.map(function (cc) {
						var warn = cc.in_company_list === false ? ' <span class="text-muted">(not in company list)</span>' : "";
						return (
							'<tr data-id="' +
							esc(cc.id) +
							'"><td>' +
							esc(cc.order_number != null ? cc.order_number : "") +
							"</td><td>" +
							esc(cc.code || "") +
							"</td><td>" +
							esc(cc.description || "") +
							warn +
							"</td><td>" +
							esc(cc.quantity != null ? cc.quantity : "") +
							"</td><td>" +
							esc(cc.units || "") +
							'</td><td class="text-end">' +
							money(cc.revenue_budget) +
							'</td><td class="text-end">' +
							esc(cc.takeoff_line_count != null ? cc.takeoff_line_count : "") +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(7, "Could not load cost codes.");
			});
	}

	function renderChangeRows(tbody, items, cols, convert, kind) {
		if (!tbody) return;
		if (!items || !items.length) {
			var emptyMsg =
				kind === "cpr"
					? "No change proposal requests."
					: kind === "sco"
						? "No subcontract change orders."
						: "No prime change orders.";
			if (window.USISUi && window.USISUi.emptyState) {
				tbody.innerHTML =
					'<tr><td colspan="' +
					cols +
					'">' +
					window.USISUi.emptyState({ title: emptyMsg, body: "" }) +
					"</td></tr>";
			} else {
				tbody.innerHTML = emptyRow(cols, emptyMsg);
			}
			return;
		}
		var createTarget =
			kind === "cpr" ? "#usis-ca-cpr-add" : kind === "sco" ? "#usis-sco-add" : "#usis-ca-co-add";
		var delClass =
			kind === "cpr" ? "usis-cpr-del" : kind === "sco" ? "usis-sco-del" : "usis-co-del";
		var chip = function (st) {
			return window.USISUi && window.USISUi.statusChip ? window.USISUi.statusChip(st || "") : esc(st || "");
		};
		var openHref = function (it) {
			var pid = projectId();
			var page =
				kind === "cpr"
					? "construction/cpr-create.html"
					: kind === "sco"
						? "construction/sco-create.html"
						: "construction/prime-co-create.html";
			return page + "?project_id=" + encodeURIComponent(pid) + "&id=" + encodeURIComponent(it.id);
		};
		tbody.innerHTML = items
			.map(function (it) {
				var extras = convert
					? [{ label: "To prime CO", className: "usis-cpr-to-co", data: { id: it.id } }]
					: [];
				var menu =
					window.USISUi && window.USISUi.rowMenu
						? window.USISUi.rowMenu({
								id: it.id,
								createTarget: createTarget,
								deleteClass: delClass,
								extras: extras,
							})
						: "";
				var open = '<a class="text-decoration-none" href="' + esc(openHref(it)) + '">';
				if (kind === "cpr") {
					return (
						"<tr>" +
						"<td>" +
						open +
						esc(it.number || "") +
						"</a></td><td>" +
						open +
						esc(it.subject || it.title || "") +
						"</a></td><td>" +
						esc(it.origin || "") +
						"</td><td>" +
						esc(it.impacted_company_name || "") +
						"</td><td>" +
						chip(it.status) +
						"</td><td>" +
						esc(it.status_date || "") +
						'</td><td class="text-end">' +
						money(it.amount) +
						"</td><td>" +
						esc(it.source_tm_ticket_id ? "T&M" : "—") +
						"</td><td>" +
						esc(it.prime_co_number || "—") +
						'</td><td class="text-end">' +
						menu +
						"</td></tr>"
					);
				}
				if (kind === "sco") {
					return (
						"<tr>" +
						"<td>" +
						open +
						esc(it.number || "") +
						"</a></td><td>" +
						esc(it.subcontract_number || "") +
						"</td><td>" +
						esc(it.vendor_name || "") +
						"</td><td>" +
						open +
						esc(it.subject || "") +
						"</a></td><td>" +
						chip(it.status) +
						"</td><td>" +
						esc(it.status_date || "") +
						'</td><td class="text-end">' +
						money(it.amount) +
						'</td><td class="text-end">' +
						menu +
						"</td></tr>"
					);
				}
				return (
					"<tr>" +
					"<td>" +
					open +
					esc(it.number || "") +
					"</a></td><td>" +
					open +
					esc(it.subject || it.title || "") +
					"</a></td><td>" +
					chip(it.status) +
					"</td><td>" +
					esc(it.status_date || "") +
					'</td><td class="text-end">' +
					money(it.amount) +
					"</td><td>" +
					esc(it.contract_number || "") +
					"</td><td>" +
					esc(it.gc_company_name || "USIS") +
					"</td><td>" +
					(it.revises_contract || it.approved_revises_contract ? "Yes" : "No") +
					'</td><td class="text-end">' +
					menu +
					"</td></tr>"
				);
			})
			.join("");
	}

	function loadCprs() {
		var tbody = document.getElementById("usis-ca-cpr-tbody");
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/cprs"))
			.then(function (data) {
				renderChangeRows(tbody, data.items || [], 10, true, "cpr");
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(5, "Could not load CPRs.");
			});
	}

	function loadCos() {
		var tbody = document.getElementById("usis-ca-co-tbody");
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/change-orders"))
			.then(function (data) {
				renderChangeRows(tbody, data.items || [], 9, false, "co");
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(5, "Could not load change orders.");
			});
	}

	function addCpr() {
		var pid = projectId();
		if (!pid) return;
		window.location.href = "construction/cpr-create.html?project_id=" + encodeURIComponent(pid);
	}

	function addCo() {
		var pid = projectId();
		if (!pid) return;
		window.location.href = "construction/prime-co-create.html?project_id=" + encodeURIComponent(pid);
	}

	function cprToCo(cprId) {
		fetchJson(pidPath("/cprs/" + encodeURIComponent(cprId) + "/convert-to-prime-co"), { method: "POST", body: {} })
			.then(function (data) {
				loadCos();
				loadCprs();
				var co = data && data.item;
				if (co && co.id) {
					window.location.href =
						"construction/prime-co-create.html?project_id=" +
						encodeURIComponent(projectId()) +
						"&id=" +
						encodeURIComponent(co.id);
				}
			})
			.catch(function (err) {
				window.alert((err && err.body) || "Could not convert CPR.");
			});
	}

	function loadDirectory() {
		var tbody = document.getElementById("usis-ca-dir-tbody");
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/directory/companies?all=1"))
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					tbody.innerHTML = emptyRow(3, "No companies in the project directory.");
					return;
				}
				tbody.innerHTML = items
					.map(function (it) {
						return (
							"<tr><td>" +
							esc(it.name) +
							"</td><td>" +
							esc(it.company_type || "") +
							"</td><td>" +
							esc(it.directory_role || "") +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(3, "Could not load directory.");
			});
	}

	var dailyReportId = null;

	function loadDailyLog() {
		var dateEl = document.getElementById("usis-dailylog-date");
		if (!dateEl || !projectId()) return;
		if (!dateEl.value) {
			var d = new Date();
			dateEl.value =
				d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
		}
		fetchJson(pidPath("/daily-reports?date=" + encodeURIComponent(dateEl.value)))
			.then(function (data) {
				var item = data.item || data;
				dailyReportId = item.id;
				var sec = item.sections || {};
				var weather = sec.weather || {};
				document.getElementById("usis-dailylog-weather").value = weather.notes || weather.conditions || "";
				document.getElementById("usis-dailylog-work").value = typeof sec.work_performed === "string" ? sec.work_performed : "";
				document.getElementById("usis-dailylog-manpower").value = listToLines(sec.manpower);
				document.getElementById("usis-dailylog-equipment").value = listToLines(sec.equipment);
				document.getElementById("usis-dailylog-deliveries").value = listToLines(sec.deliveries);
				document.getElementById("usis-dailylog-visitors").value = listToLines(sec.visitors);
				document.getElementById("usis-dailylog-delays").value = typeof sec.delays === "string" ? sec.delays : listToLines(sec.delays);
				var st = document.getElementById("usis-dailylog-status");
				if (st) st.textContent = "Loaded " + (item.date || dateEl.value) + " (" + (item.status || "draft") + ").";
			})
			.catch(function () {
				var st = document.getElementById("usis-dailylog-status");
				if (st) st.textContent = "Could not load daily log.";
			});
	}

	function prefillDailyLog() {
		var dateEl = document.getElementById("usis-dailylog-date");
		var box = document.getElementById("usis-dailylog-manpower");
		var st = document.getElementById("usis-dailylog-status");
		if (!box || !projectId()) return;
		var day = (dateEl && dateEl.value) || "";
		if (!day) {
			var d = new Date();
			day = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
		}
		fetchJson("/api/time/projects/" + encodeURIComponent(projectId()) + "/manpower-prefill?date=" + encodeURIComponent(day))
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					if (st) st.textContent = "No punches on " + day + " to prefill.";
					return;
				}
				var lines = items.map(function (it) {
					return (it.company || "USIS") + " — " + (it.count || 1) + " — " + (it.notes || "");
				});
				box.value = lines.join("\n");
				if (st) st.textContent = "Prefill from " + items.length + " punch" + (items.length === 1 ? "" : "es") + ". Save to keep.";
			})
			.catch(function () {
				if (st) st.textContent = "Could not prefill from punches.";
			});
	}

	function saveDailyLog() {
		if (!dailyReportId) {
			loadDailyLog();
			return;
		}
		var weather = (document.getElementById("usis-dailylog-weather") || {}).value || "";
		fetchJson("/api/v1/daily-reports/" + encodeURIComponent(dailyReportId), {
			method: "PUT",
			body: {
				sections: {
					weather: { notes: weather, conditions: weather },
					work_performed: (document.getElementById("usis-dailylog-work") || {}).value || "",
					manpower: linesToList((document.getElementById("usis-dailylog-manpower") || {}).value),
					equipment: linesToList((document.getElementById("usis-dailylog-equipment") || {}).value),
					deliveries: linesToList((document.getElementById("usis-dailylog-deliveries") || {}).value),
					visitors: linesToList((document.getElementById("usis-dailylog-visitors") || {}).value),
					delays: (document.getElementById("usis-dailylog-delays") || {}).value || "",
				},
			},
		})
			.then(function () {
				var st = document.getElementById("usis-dailylog-status");
				if (st) st.textContent = "Saved.";
			})
			.catch(function () {
				var st = document.getElementById("usis-dailylog-status");
				if (st) st.textContent = "Save failed.";
			});
	}

	function loadScos() {
		var tbody = document.getElementById("usis-sco-tbody");
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/scos"))
			.then(function (data) {
				renderChangeRows(tbody, data.items || [], 8, false, "sco");
			})
			.catch(function () {
				tbody.innerHTML = emptyRow(5, "Could not load SCOs.");
			});
	}

	function addSco() {
		var pid = projectId();
		if (!pid) return;
		window.location.href = "construction/sco-create.html?project_id=" + encodeURIComponent(pid);
	}

	function onReady() {
		if (!projectId()) return;
		loadJcc();
		loadCprs();
		loadCos();
		loadDirectory();
		loadDailyLog();
		loadScos();

		var addCprBtn = document.getElementById("usis-ca-cpr-add");
		if (addCprBtn) addCprBtn.addEventListener("click", addCpr);
		var addCoBtn = document.getElementById("usis-ca-co-add");
		if (addCoBtn) addCoBtn.addEventListener("click", addCo);
		var cprBody = document.getElementById("usis-ca-cpr-tbody");
		if (cprBody) {
			cprBody.addEventListener("click", function (e) {
				var btn = e.target.closest(".usis-cpr-to-co");
				if (btn) cprToCo(btn.getAttribute("data-id"));
				var del = e.target.closest(".usis-cpr-del");
				if (del) {
					var id = del.getAttribute("data-id");
					if (!id || !window.confirm("Delete this CPR?")) return;
					fetchJson(pidPath("/cprs/" + encodeURIComponent(id)), { method: "DELETE" })
						.then(loadCprs)
						.catch(function (err) {
							window.alert((err && err.body) || "Could not delete CPR.");
						});
				}
			});
		}
		var coBody = document.getElementById("usis-ca-co-tbody");
		if (coBody) {
			coBody.addEventListener("click", function (e) {
				var del = e.target.closest(".usis-co-del");
				if (!del) return;
				var id = del.getAttribute("data-id");
				if (!id || !window.confirm("Delete this change order?")) return;
				fetchJson(pidPath("/change-orders/" + encodeURIComponent(id)), { method: "DELETE" })
					.then(loadCos)
					.catch(function (err) {
						window.alert((err && err.body) || "Could not delete change order.");
					});
			});
		}
		var scoBody = document.getElementById("usis-sco-tbody");
		if (scoBody) {
			scoBody.addEventListener("click", function (e) {
				var del = e.target.closest(".usis-sco-del");
				if (!del) return;
				var id = del.getAttribute("data-id");
				if (!id || !window.confirm("Delete this SCO?")) return;
				fetchJson(pidPath("/scos/" + encodeURIComponent(id)), { method: "DELETE" })
					.then(loadScos)
					.catch(function (err) {
						window.alert((err && err.body) || "Could not delete SCO.");
					});
			});
		}
		var saveDl = document.getElementById("usis-dailylog-save");
		if (saveDl) saveDl.addEventListener("click", saveDailyLog);
		var prefillDl = document.getElementById("usis-dailylog-prefill");
		if (prefillDl) prefillDl.addEventListener("click", prefillDailyLog);
		var dateEl = document.getElementById("usis-dailylog-date");
		if (dateEl) dateEl.addEventListener("change", loadDailyLog);
		var addScoBtn = document.getElementById("usis-sco-add");
		if (addScoBtn) addScoBtn.addEventListener("click", addSco);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
})();
