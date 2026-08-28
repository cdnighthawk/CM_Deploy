/**
 * Plan Room–style list-query drawer for construction/leads.html.
 * Drawer filters are the list query. Column AutoFilter is in-grid refinement.
 */
(function (global) {
	"use strict";

	function t(key) {
		return window.USISI18n && typeof window.USISI18n.tr === "function" ? window.USISI18n.tr(key) : key;
	}

	var TABLE_KEY = "crm.leads";
	var LS_KEY = "crm.leads.query";
	var QUERY_KEYS = [
		"q",
		"trade",
		"company_id",
		"sector",
		"stage",
		"due_from",
		"due_to",
		"start_from",
		"start_to",
		"activity_from",
		"activity_to",
		"value_min",
		"value_max",
		"distance_miles",
		"owner_id",
		"sort",
		"saved_filter_id",
	];
	var DISTANCE_PRESETS = { "25": true, "50": true, "100": true, "150": true, "250": true };

	var TRADE_LABELS = {
		drywall: "Drywall",
		paint: "Paint",
		flooring: "Flooring",
		ceilings: "Ceilings",
		trim: "Trim",
		specialties: "Specialties",
		multi: "Multi",
	};
	var STAGE_LABELS = {
		new: "New Lead",
		invited: "Invited",
		estimating: "Estimating",
		submitted: "Submitted",
		awarded: "Awarded",
		lost: "Lost",
	};
	var SECTOR_LABELS = { commercial: "Commercial", government: "Government" };

	var applied = emptyQuery();
	var companyLabels = {};
	var ownerLabels = {};
	var savedItems = [];
	var companyTimer = null;
	var opts = {};

	function api() {
		return global.USIS_API;
	}

	function notify(kind, msg) {
		var n = global.USISNotify;
		if (n && typeof n[kind] === "function") n[kind](msg);
	}

	function emptyQuery() {
		return {
			q: "",
			trade: [],
			company_id: [],
			sector: [],
			stage: [],
			due_from: "",
			due_to: "",
			start_from: "",
			start_to: "",
			activity_from: "",
			activity_to: "",
			value_min: "",
			value_max: "",
			distance_miles: "",
			owner_id: [],
			sort: "due_date.asc",
			saved_filter_id: "",
		};
	}

	function cloneQuery(q) {
		return JSON.parse(JSON.stringify(q || emptyQuery()));
	}

	function csv(v) {
		if (Array.isArray(v)) return v.filter(Boolean).join(",");
		return v == null ? "" : String(v);
	}

	function splitCsv(v) {
		if (Array.isArray(v)) return v.map(String).filter(Boolean);
		return String(v || "")
			.split(",")
			.map(function (s) {
				return s.trim();
			})
			.filter(Boolean);
	}

	function multiValues(sel) {
		if (!sel) return [];
		return Array.prototype.slice.call(sel.selectedOptions).map(function (o) {
			return o.value;
		});
	}

	function setMultiValues(sel, values) {
		if (!sel) return;
		var set = {};
		(values || []).forEach(function (v) {
			set[String(v)] = true;
		});
		Array.prototype.forEach.call(sel.options, function (o) {
			o.selected = !!set[o.value];
		});
	}

	function queryHasCriteria(q) {
		return activeCriteria(q).length > 0;
	}

	function activeCriteria(q) {
		q = q || applied;
		var out = [];
		if (q.q) out.push({ key: "q", label: "Search: " + q.q });
		(q.trade || []).forEach(function (t) {
			out.push({ key: "trade", value: t, label: "Trade: " + (TRADE_LABELS[t] || t) });
		});
		(q.company_id || []).forEach(function (id) {
			out.push({ key: "company_id", value: id, label: "GC: " + (companyLabels[id] || id) });
		});
		(q.sector || []).forEach(function (s) {
			out.push({ key: "sector", value: s, label: "Sector: " + (SECTOR_LABELS[s] || s) });
		});
		(q.stage || []).forEach(function (s) {
			out.push({ key: "stage", value: s, label: "Stage: " + (STAGE_LABELS[s] || s) });
		});
		if (q.due_from || q.due_to) {
			out.push({ key: "due", label: "Due: " + formatRange(q.due_from, q.due_to) });
		}
		if (q.start_from || q.start_to) {
			out.push({ key: "start", label: "Start: " + formatRange(q.start_from, q.start_to) });
		}
		if (q.activity_from || q.activity_to) {
			out.push({ key: "activity", label: "Activity: " + formatRange(q.activity_from, q.activity_to) });
		}
		if (q.value_min || q.value_max) {
			out.push({
				key: "value",
				label: "Value: " + (q.value_min ? "$" + q.value_min : "…") + " – " + (q.value_max ? "$" + q.value_max : "…"),
			});
		}
		if (q.distance_miles) {
			out.push({ key: "distance", label: "Within " + q.distance_miles + " mi of office" });
		}
		(q.owner_id || []).forEach(function (id) {
			out.push({ key: "owner_id", value: id, label: "Owner: " + (ownerLabels[id] || id) });
		});
		return out;
	}

	function formatRange(from, to) {
		return (from ? formatDateChip(from) : "…") + " → " + (to ? formatDateChip(to) : "…");
	}

	function formatDateChip(iso) {
		var p = String(iso).slice(0, 10).split("-");
		if (p.length !== 3) return iso;
		return Number(p[1]) + "/" + Number(p[2]) + "/" + p[0];
	}

	function criterionCount(q) {
		return activeCriteria(q).length;
	}

	function relaxesOpenBoard(q) {
		q = q || applied;
		var stages = q.stage || [];
		if (stages.indexOf("lost") >= 0 || stages.indexOf("awarded") >= 0 || stages.indexOf("dead") >= 0) return true;
		return !!(q.due_from || q.due_to);
	}

	function listParams(q) {
		q = q || applied;
		var params = { limit: 500, submission_state: "undecided", sort: q.sort || "due_date.asc" };
		if (q.q) params.q = q.q;
		if (q.trade && q.trade.length) params.trade = csv(q.trade);
		if (q.company_id && q.company_id.length) params.company_id = csv(q.company_id);
		if (q.sector && q.sector.length) params.sector = csv(q.sector);
		if (q.stage && q.stage.length) params.stage = csv(q.stage);
		if (q.due_from) params.due_from = q.due_from;
		if (q.due_to) params.due_to = q.due_to;
		if (q.start_from) params.start_from = q.start_from;
		if (q.start_to) params.start_to = q.start_to;
		if (q.activity_from) params.activity_from = q.activity_from;
		if (q.activity_to) params.activity_to = q.activity_to;
		if (q.value_min) params.value_min = q.value_min;
		if (q.value_max) params.value_max = q.value_max;
		if (q.distance_miles) params.distance_miles = q.distance_miles;
		if (q.owner_id && q.owner_id.length) params.owner_id = csv(q.owner_id);
		if (q.saved_filter_id) params.saved_filter_id = q.saved_filter_id;
		return params;
	}

	var officeState = { configured: false, label: "" };

	function readDistanceMiles() {
		var preset = document.getElementById("usis-leads-f-distance-preset");
		var custom = document.getElementById("usis-leads-f-distance");
		var choice = preset && preset.value ? String(preset.value) : "";
		if (choice === "custom") {
			return custom && custom.value ? String(custom.value).trim() : "";
		}
		return choice;
	}

	function writeDistanceMiles(raw) {
		var preset = document.getElementById("usis-leads-f-distance-preset");
		var custom = document.getElementById("usis-leads-f-distance");
		var miles = raw ? String(raw).trim() : "";
		if (!preset) return;
		if (!miles) {
			preset.value = "";
		} else if (DISTANCE_PRESETS[miles]) {
			preset.value = miles;
		} else {
			preset.value = "custom";
			if (custom) custom.value = miles;
		}
		toggleCustomDistance();
	}

	function toggleCustomDistance() {
		var preset = document.getElementById("usis-leads-f-distance-preset");
		var custom = document.getElementById("usis-leads-f-distance");
		if (!custom) return;
		var show = !!(preset && preset.value === "custom");
		custom.classList.toggle("d-none", !show);
		if (show) custom.focus();
	}

	function paintOffice() {
		var label = document.getElementById("usis-leads-f-office-label");
		var form = document.getElementById("usis-leads-f-office-form");
		if (label) {
			if (officeState.configured && officeState.label) {
				label.textContent = "From your office in " + officeState.label + ". Jobs without a mapped site are hidden.";
			} else if (officeState.configured) {
				label.textContent = "From your saved office. Jobs without a mapped site are hidden.";
			} else {
				label.textContent = "Save your office city or ZIP to filter by distance. Jobs without a mapped site are hidden.";
			}
		}
		if (form) form.classList.toggle("d-none", !!officeState.configured);
	}

	function loadOffice() {
		if (!api()) return Promise.resolve(officeState);
		return api()
			.fetchJson("/api/v1/office-location")
			.then(function (data) {
				officeState = {
					configured: !!(data && data.configured),
					label: (data && (data.label || [data.city, data.state].filter(Boolean).join(", "))) || "",
				};
				paintOffice();
				return officeState;
			})
			.catch(function () {
				paintOffice();
				return officeState;
			});
	}

	function saveOffice() {
		if (!api()) return;
		var city = document.getElementById("usis-leads-f-office-city");
		var state = document.getElementById("usis-leads-f-office-state");
		var zip = document.getElementById("usis-leads-f-office-zip");
		var payload = {
			city: city && city.value ? city.value.trim() : "",
			state: state && state.value ? state.value.trim() : "",
			postal_code: zip && zip.value ? zip.value.trim() : "",
		};
		if (!payload.city && !payload.postal_code) {
			notify("warning", "Enter a city or ZIP for your office");
			return;
		}
		var btn = document.getElementById("usis-leads-f-office-save");
		if (btn) btn.disabled = true;
		api()
			.fetchJson("/api/v1/office-location", { method: "PATCH", body: payload })
			.then(function (data) {
				officeState = {
					configured: !!(data && data.configured),
					label: (data && (data.label || [data.city, data.state].filter(Boolean).join(", "))) || "",
				};
				paintOffice();
				notify("success", officeState.label ? "Office set to " + officeState.label : "Office location saved");
			})
			.catch(function () {
				notify("error", "Could not map that office address. Try a US city and state or ZIP.");
			})
			.then(function () {
				if (btn) btn.disabled = false;
			});
	}

	function readDraft() {
		var q = emptyQuery();
		var el;
		el = document.getElementById("usis-leads-f-q");
		q.q = el && el.value ? el.value.trim() : "";
		q.trade = multiValues(document.getElementById("usis-leads-f-trade"));
		q.company_id = Object.keys(companyLabels);
		q.sector = [];
		["commercial", "government"].forEach(function (s) {
			var box = document.getElementById("usis-leads-f-sector-" + s);
			if (box && box.checked) q.sector.push(s);
		});
		q.stage = multiValues(document.getElementById("usis-leads-f-stage"));
		["due_from", "due_to", "start_from", "start_to", "activity_from", "activity_to"].forEach(function (k) {
			el = document.getElementById("usis-leads-f-" + k.replace(/_/g, "-"));
			q[k] = el && el.value ? el.value : "";
		});
		el = document.getElementById("usis-leads-f-value-min");
		q.value_min = el && el.value ? el.value : "";
		el = document.getElementById("usis-leads-f-value-max");
		q.value_max = el && el.value ? el.value : "";
		q.distance_miles = readDistanceMiles();
		q.owner_id = multiValues(document.getElementById("usis-leads-f-owner"));
		q.sort = "due_date.asc";
		return q;
	}

	function writeDraft(q) {
		q = q || emptyQuery();
		var el = document.getElementById("usis-leads-f-q");
		if (el) el.value = q.q || "";
		setMultiValues(document.getElementById("usis-leads-f-trade"), q.trade);
		var prevCompanies = companyLabels;
		companyLabels = {};
		(q.company_id || []).forEach(function (id) {
			companyLabels[id] = (q._company_labels && q._company_labels[id]) || prevCompanies[id] || id;
		});
		renderCompanyChips();
		["commercial", "government"].forEach(function (s) {
			var box = document.getElementById("usis-leads-f-sector-" + s);
			if (box) box.checked = (q.sector || []).indexOf(s) >= 0;
		});
		setMultiValues(document.getElementById("usis-leads-f-stage"), q.stage);
		[
			["due_from", "usis-leads-f-due-from"],
			["due_to", "usis-leads-f-due-to"],
			["start_from", "usis-leads-f-start-from"],
			["start_to", "usis-leads-f-start-to"],
			["activity_from", "usis-leads-f-activity-from"],
			["activity_to", "usis-leads-f-activity-to"],
		].forEach(function (pair) {
			el = document.getElementById(pair[1]);
			if (el) el.value = (q[pair[0]] || "").slice(0, 10);
		});
		el = document.getElementById("usis-leads-f-value-min");
		if (el) el.value = q.value_min || "";
		el = document.getElementById("usis-leads-f-value-max");
		if (el) el.value = q.value_max || "";
		writeDistanceMiles(q.distance_miles);
		setMultiValues(document.getElementById("usis-leads-f-owner"), q.owner_id);
		if ((q.activity_from || q.activity_to) && document.getElementById("usis-leads-f-extra-dates")) {
			document.getElementById("usis-leads-f-extra-dates").classList.remove("d-none");
		}
	}

	function persist(q) {
		try {
			localStorage.setItem(LS_KEY, JSON.stringify({ query: q, companyLabels: companyLabels, ownerLabels: ownerLabels }));
		} catch (e) {}
	}

	function loadPersisted() {
		try {
			var raw = localStorage.getItem(LS_KEY);
			if (!raw) return null;
			var parsed = JSON.parse(raw);
			if (parsed && parsed.query) {
				if (parsed.companyLabels) companyLabels = parsed.companyLabels;
				if (parsed.ownerLabels) ownerLabels = parsed.ownerLabels;
				return normalizeQuery(parsed.query);
			}
			return normalizeQuery(parsed);
		} catch (e) {
			return null;
		}
	}

	function normalizeQuery(raw) {
		var q = emptyQuery();
		if (!raw || typeof raw !== "object") return q;
		q.q = raw.q ? String(raw.q) : "";
		q.trade = splitCsv(raw.trade);
		q.company_id = splitCsv(raw.company_id);
		q.sector = splitCsv(raw.sector);
		q.stage = splitCsv(raw.stage);
		["due_from", "due_to", "start_from", "start_to", "activity_from", "activity_to", "value_min", "value_max", "distance_miles", "saved_filter_id"].forEach(
			function (k) {
				q[k] = raw[k] ? String(raw[k]) : "";
			}
		);
		q.owner_id = splitCsv(raw.owner_id);
		q.sort = raw.sort || "due_date.asc";
		if (raw._company_labels) companyLabels = Object.assign({}, companyLabels, raw._company_labels);
		return q;
	}

	function urlHasFilters() {
		var sp = new URLSearchParams(global.location.search);
		return QUERY_KEYS.some(function (k) {
			return k !== "sort" && sp.has(k) && String(sp.get(k) || "").trim() !== "";
		});
	}

	function fromUrl() {
		var sp = new URLSearchParams(global.location.search);
		var raw = {};
		QUERY_KEYS.forEach(function (k) {
			if (sp.has(k)) raw[k] = sp.get(k);
		});
		return normalizeQuery(raw);
	}

	function writeUrl(q) {
		var sp = new URLSearchParams(global.location.search);
		QUERY_KEYS.forEach(function (k) {
			sp.delete(k);
		});
		var params = listParams(q);
		Object.keys(params).forEach(function (k) {
			if (k === "limit" || k === "submission_state") return;
			if (params[k] !== undefined && params[k] !== null && params[k] !== "") sp.set(k, params[k]);
		});
		var next = sp.toString();
		var path = global.location.pathname + (next ? "?" + next : "") + global.location.hash;
		global.history.replaceState({}, "", path);
	}

	function renderChips() {
		var host = document.getElementById("usis-leads-filter-chips");
		if (!host) return;
		var chips = activeCriteria(applied);
		if (!chips.length) {
			host.classList.add("d-none");
			host.innerHTML = "";
			return;
		}
		host.classList.remove("d-none");
		host.innerHTML =
			chips
				.map(function (c) {
					return (
						'<span class="usis-leads-chip">' +
						esc(c.label) +
						'<button type="button" class="usis-leads-chip__x" data-chip-key="' +
						esc(c.key) +
						'" data-chip-value="' +
						esc(c.value || "") +
						'" aria-label="Remove ' +
						esc(c.label) +
						'">×</button></span>'
					);
				})
				.join("") +
			'<button type="button" class="btn btn-link btn-sm px-1" id="usis-leads-chips-clear">' + t("Clear all") + "</button>";
	}

	function paintToolbar() {
		var btn = document.getElementById("usis-leads-filter-btn");
		var badge = document.getElementById("usis-leads-filter-badge");
		var n = criterionCount(applied);
		if (btn) btn.classList.toggle("active", n > 0);
		if (badge) {
			badge.textContent = n ? String(n) : "";
			badge.classList.toggle("d-none", !n);
		}
		renderChips();
		renderSavedShortcut();
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function applyQuery(q, meta) {
		applied = normalizeQuery(q);
		applied.sort = "due_date.asc";
		if (meta && meta.saved_filter_id) applied.saved_filter_id = meta.saved_filter_id;
		else if (!(meta && meta.keepSavedId)) applied.saved_filter_id = q.saved_filter_id || "";
		writeDraft(applied);
		writeUrl(applied);
		persist(applied);
		paintToolbar();
		var af = opts.getAutoFilter && opts.getAutoFilter();
		// Drawer Apply is the list query; clear in-grid AutoFilter so the two do not stack invisibly.
		if (af && typeof af.clearFilters === "function") af.clearFilters();
		else if (af && typeof af.reset === "function" && meta && meta.resetGrid) af.reset();
		if (typeof opts.onApply === "function") opts.onApply(applied);
		return applied;
	}

	function resetAll() {
		companyLabels = {};
		applied = emptyQuery();
		writeDraft(applied);
		writeUrl(applied);
		persist(applied);
		paintToolbar();
		if (typeof opts.onReset === "function") opts.onReset();
		else if (typeof opts.onApply === "function") opts.onApply(applied);
	}

	function removeChip(key, value) {
		var q = cloneQuery(applied);
		if (key === "q") q.q = "";
		else if (key === "due") {
			q.due_from = "";
			q.due_to = "";
		} else if (key === "start") {
			q.start_from = "";
			q.start_to = "";
		} else if (key === "activity") {
			q.activity_from = "";
			q.activity_to = "";
		} else if (key === "value") {
			q.value_min = "";
			q.value_max = "";
		} else if (key === "distance") {
			q.distance_miles = "";
		} else if (key === "company_id") {
			q.company_id = (q.company_id || []).filter(function (id) {
				return id !== value;
			});
			delete companyLabels[value];
		} else if (Array.isArray(q[key])) {
			q[key] = q[key].filter(function (v) {
				return v !== value;
			});
		} else q[key] = "";
		applyQuery(q);
	}

	function closeDrawer() {
		var el = document.getElementById("usis-leads-filter-drawer");
		if (el && global.bootstrap && bootstrap.Offcanvas) {
			bootstrap.Offcanvas.getOrCreateInstance(el).hide();
		}
	}

	function showTab(which) {
		var btn = document.getElementById(which === "saved" ? "usis-leads-tab-saved-btn" : "usis-leads-tab-filter-btn");
		if (btn && global.bootstrap && bootstrap.Tab) bootstrap.Tab.getOrCreateInstance(btn).show();
		else if (btn) btn.click();
	}

	function renderCompanyChips() {
		var host = document.getElementById("usis-leads-f-company-chips");
		if (!host) return;
		host.innerHTML = Object.keys(companyLabels)
			.map(function (id) {
				return (
					'<span class="usis-leads-chip">' +
					esc(companyLabels[id]) +
					'<button type="button" class="usis-leads-chip__x" data-remove-company="' +
					esc(id) +
					'" aria-label="Remove company">×</button></span>'
				);
			})
			.join("");
	}

	function addCompany(id, name) {
		if (!id) return;
		companyLabels[id] = name || id;
		renderCompanyChips();
		var input = document.getElementById("usis-leads-f-company-q");
		if (input) input.value = "";
		hideCompanyResults();
	}

	function hideCompanyResults() {
		var box = document.getElementById("usis-leads-f-company-results");
		if (box) {
			box.classList.add("d-none");
			box.innerHTML = "";
		}
	}

	function searchCompanies(term) {
		if (!api()) return;
		api()
			.fetchJson("/api/v1/rfi-companies", { params: { q: term, limit: 20 } })
			.then(function (data) {
				var box = document.getElementById("usis-leads-f-company-results");
				if (!box) return;
				var items = (data.items || []).filter(function (c) {
					var t = String(c.company_type || "").toLowerCase();
					return !t || t === "gc" || t === "owner" || t === "architect";
				});
				if (!items.length) {
					box.classList.add("d-none");
					box.innerHTML = "";
					return;
				}
				box.innerHTML = items
					.map(function (c) {
						return (
							'<button type="button" class="list-group-item list-group-item-action py-1" data-company-id="' +
							esc(c.id) +
							'" data-company-name="' +
							esc(c.name) +
							'">' +
							esc(c.name) +
							(c.company_type ? ' <span class="text-muted small">(' + esc(c.company_type) + ")</span>" : "") +
							"</button>"
						);
					})
					.join("");
				box.classList.remove("d-none");
			})
			.catch(function () {
				hideCompanyResults();
			});
	}

	function loadOwners() {
		if (!api()) return Promise.resolve();
		return api()
			.fetchJson("/api/v1/rfi-users", { params: { limit: 200 } })
			.then(function (data) {
				var sel = document.getElementById("usis-leads-f-owner");
				if (!sel) return;
				sel.innerHTML = (data.items || [])
					.map(function (u) {
						ownerLabels[u.id] = u.name || u.email || u.id;
						return '<option value="' + esc(u.id) + '">' + esc(ownerLabels[u.id]) + "</option>";
					})
					.join("");
				setMultiValues(sel, applied.owner_id);
			})
			.catch(function () {});
	}

	function loadSaved() {
		if (!api()) return Promise.resolve([]);
		return api()
			.fetchJson("/api/v1/saved-filters", { params: { table_key: TABLE_KEY } })
			.then(function (data) {
				savedItems = data.items || [];
				renderSavedList();
				renderSavedShortcut();
				return savedItems;
			})
			.catch(function () {
				savedItems = [];
				renderSavedList();
				return [];
			});
	}

	function criteriaSummary(q) {
		return activeCriteria(normalizeQuery(q))
			.map(function (c) {
				return c.label.split(":")[0];
			})
			.filter(function (v, i, a) {
				return a.indexOf(v) === i;
			})
			.join(" · ");
	}

	function renderSavedList() {
		var empty = document.getElementById("usis-leads-saved-empty");
		var list = document.getElementById("usis-leads-saved-list");
		if (!empty || !list) return;
		if (!savedItems.length) {
			empty.classList.remove("d-none");
			list.classList.add("d-none");
			list.innerHTML = "";
			return;
		}
		empty.classList.add("d-none");
		list.classList.remove("d-none");
		list.innerHTML = savedItems
			.map(function (row) {
				var selected = applied.saved_filter_id === row.id ? " usis-leads-saved-row--active" : "";
				return (
					'<div class="usis-leads-saved-row' +
					selected +
					'" data-saved-id="' +
					esc(row.id) +
					'">' +
					'<div class="min-w-0">' +
					'<div class="fw-semibold">' +
					esc(row.name) +
					(row.is_default ? ' <span class="badge text-bg-light border">Default</span>' : "") +
					"</div>" +
					'<div class="small text-muted">' +
					esc(criteriaSummary(row.query_json) || t("No criteria")) +
					"</div></div>" +
					'<div class="d-flex align-items-center gap-1">' +
					'<button type="button" class="btn btn-sm btn-outline-primary" data-saved-apply="' +
					esc(row.id) +
					'">' + t("Apply") + "</button>" +
					'<div class="dropdown">' +
					'<button type="button" class="btn btn-sm btn-link" data-bs-toggle="dropdown" aria-label="Saved filter actions">⋯</button>' +
					'<ul class="dropdown-menu dropdown-menu-end">' +
					'<li><button type="button" class="dropdown-item" data-saved-rename="' +
					esc(row.id) +
					'">Rename</button></li>' +
					'<li><button type="button" class="dropdown-item" data-saved-overwrite="' +
					esc(row.id) +
					'">Overwrite with current</button></li>' +
					'<li><button type="button" class="dropdown-item" data-saved-default="' +
					esc(row.id) +
					'">Make default</button></li>' +
					'<li><button type="button" class="dropdown-item text-danger" data-saved-delete="' +
					esc(row.id) +
					'">Delete</button></li>' +
					"</ul></div></div></div>"
				);
			})
			.join("");
	}

	function renderSavedShortcut() {
		var menu = document.getElementById("usis-leads-saved-menu");
		if (!menu) return;
		if (!savedItems.length) {
			menu.innerHTML = '<li><span class="dropdown-item-text text-muted">' + t("No saved filters yet") + "</span></li>";
			return;
		}
		menu.innerHTML = savedItems
			.map(function (row) {
				return (
					'<li><button type="button" class="dropdown-item" data-saved-apply="' +
					esc(row.id) +
					'">' +
					esc(row.name) +
					(row.is_default ? " (default)" : "") +
					"</button></li>"
				);
			})
			.join("");
	}

	function findSaved(id) {
		return savedItems.filter(function (r) {
			return r.id === id;
		})[0];
	}

	function applySaved(id) {
		var row = findSaved(id);
		if (!row) return;
		var q = normalizeQuery(row.query_json);
		q.saved_filter_id = row.id;
		applyQuery(q, { saved_filter_id: row.id });
		closeDrawer();
	}

	function saveCurrent() {
		var draft = readDraft();
		if (!queryHasCriteria(draft) && !queryHasCriteria(applied)) {
			notify("warning", "Add a filter before saving");
			return;
		}
		var nameEl = document.getElementById("usis-leads-save-name");
		var defEl = document.getElementById("usis-leads-save-default");
		if (nameEl) nameEl.value = "";
		if (defEl) defEl.checked = false;
		var modal = document.getElementById("usis-leads-save-modal");
		if (modal && global.bootstrap && bootstrap.Modal) bootstrap.Modal.getOrCreateInstance(modal).show();
	}

	function confirmSave(overwrite) {
		if (!api()) return;
		var nameEl = document.getElementById("usis-leads-save-name");
		var name = nameEl && nameEl.value ? nameEl.value.trim() : "";
		if (!name) {
			notify("warning", t("Filter name is required"));
			return;
		}
		var draft = queryHasCriteria(readDraft()) ? readDraft() : cloneQuery(applied);
		var payload = {
			table_key: TABLE_KEY,
			name: name,
			query_json: persistableQuery(draft),
			is_default: !!(document.getElementById("usis-leads-save-default") && document.getElementById("usis-leads-save-default").checked),
			overwrite: !!overwrite,
		};
		api()
			.fetchJson("/api/v1/saved-filters", { method: "POST", body: payload })
			.then(function (data) {
				applied.saved_filter_id = data.item && data.item.id;
				hideSaveModal();
				loadSaved().then(function () {
					showTab("saved");
					notify("success", overwrite ? t("Filter updated") : t("Filter saved"));
				});
			})
			.catch(function (err) {
				if (err && err.status === 409 && !overwrite) {
					if (global.confirm('A filter named "' + name + '" already exists. Overwrite it?')) confirmSave(true);
					return;
				}
				notify("error", "Could not save filter");
			});
	}

	function persistableQuery(q) {
		var out = persistableFields(q);
		out._company_labels = companyLabels;
		return out;
	}

	function persistableFields(q) {
		var out = {};
		QUERY_KEYS.forEach(function (k) {
			if (k === "sort" || k === "saved_filter_id") return;
			var v = q[k];
			if (Array.isArray(v) && v.length) out[k] = v;
			else if (v && !Array.isArray(v)) out[k] = v;
		});
		return out;
	}

	function hideSaveModal() {
		var modal = document.getElementById("usis-leads-save-modal");
		if (modal && global.bootstrap && bootstrap.Modal) {
			var inst = bootstrap.Modal.getInstance(modal);
			if (inst) inst.hide();
		}
	}

	function bindEvents() {
		var more = document.getElementById("usis-leads-f-more-dates");
		if (more) {
			more.addEventListener("click", function () {
				var extra = document.getElementById("usis-leads-f-extra-dates");
				if (!extra) return;
				extra.classList.toggle("d-none");
				more.setAttribute("aria-expanded", extra.classList.contains("d-none") ? "false" : "true");
			});
		}
		var applyBtn = document.getElementById("usis-leads-filter-apply");
		if (applyBtn) {
			applyBtn.addEventListener("click", function () {
				var draft = readDraft();
				if (draft.distance_miles && !officeState.configured) {
					notify("warning", "Save your office location before filtering by distance");
					var form = document.getElementById("usis-leads-f-office-form");
					if (form) form.classList.remove("d-none");
					return;
				}
				applyQuery(draft);
				closeDrawer();
			});
		}
		var preset = document.getElementById("usis-leads-f-distance-preset");
		if (preset) {
			preset.addEventListener("change", toggleCustomDistance);
		}
		var officeSave = document.getElementById("usis-leads-f-office-save");
		if (officeSave) officeSave.addEventListener("click", saveOffice);
		var resetBtn = document.getElementById("usis-leads-filter-reset");
		if (resetBtn) resetBtn.addEventListener("click", resetAll);
		var saveBtn = document.getElementById("usis-leads-filter-save");
		if (saveBtn) saveBtn.addEventListener("click", saveCurrent);
		var saveConfirm = document.getElementById("usis-leads-save-confirm");
		if (saveConfirm) saveConfirm.addEventListener("click", function () {
			confirmSave(false);
		});
		var chips = document.getElementById("usis-leads-filter-chips");
		if (chips) {
			chips.addEventListener("click", function (e) {
				if (e.target.id === "usis-leads-chips-clear") {
					resetAll();
					return;
				}
				var x = e.target.closest("[data-chip-key]");
				if (!x) return;
				removeChip(x.getAttribute("data-chip-key"), x.getAttribute("data-chip-value"));
			});
		}
		var companyQ = document.getElementById("usis-leads-f-company-q");
		if (companyQ) {
			companyQ.addEventListener("input", function () {
				clearTimeout(companyTimer);
				var term = companyQ.value.trim();
				if (term.length < 2) {
					hideCompanyResults();
					return;
				}
				companyTimer = setTimeout(function () {
					searchCompanies(term);
				}, 250);
			});
		}
		var companyResults = document.getElementById("usis-leads-f-company-results");
		if (companyResults) {
			companyResults.addEventListener("click", function (e) {
				var btn = e.target.closest("[data-company-id]");
				if (!btn) return;
				addCompany(btn.getAttribute("data-company-id"), btn.getAttribute("data-company-name"));
			});
		}
		var companyChips = document.getElementById("usis-leads-f-company-chips");
		if (companyChips) {
			companyChips.addEventListener("click", function (e) {
				var btn = e.target.closest("[data-remove-company]");
				if (!btn) return;
				delete companyLabels[btn.getAttribute("data-remove-company")];
				renderCompanyChips();
			});
		}
		document.addEventListener("click", function (e) {
			var apply = e.target.closest("[data-saved-apply]");
			if (apply) {
				e.preventDefault();
				applySaved(apply.getAttribute("data-saved-apply"));
				return;
			}
			var rename = e.target.closest("[data-saved-rename]");
			if (rename) {
				e.preventDefault();
				renameSaved(rename.getAttribute("data-saved-rename"));
				return;
			}
			var overwrite = e.target.closest("[data-saved-overwrite]");
			if (overwrite) {
				e.preventDefault();
				overwriteSaved(overwrite.getAttribute("data-saved-overwrite"));
				return;
			}
			var makeDef = e.target.closest("[data-saved-default]");
			if (makeDef) {
				e.preventDefault();
				makeDefault(makeDef.getAttribute("data-saved-default"));
				return;
			}
			var del = e.target.closest("[data-saved-delete]");
			if (del) {
				e.preventDefault();
				deleteSaved(del.getAttribute("data-saved-delete"));
			}
		});
	}

	function renameSaved(id) {
		var row = findSaved(id);
		if (!row || !api()) return;
		var name = global.prompt("Filter name", row.name);
		if (name == null) return;
		name = String(name).trim();
		if (!name) return;
		api()
			.fetchJson("/api/v1/saved-filters/" + encodeURIComponent(id), { method: "PATCH", body: { name: name } })
			.then(function () {
				return loadSaved();
			})
			.catch(function () {
				notify("error", "Could not rename filter");
			});
	}

	function overwriteSaved(id) {
		var row = findSaved(id);
		if (!row || !api()) return;
		var draft = queryHasCriteria(readDraft()) ? readDraft() : cloneQuery(applied);
		api()
			.fetchJson("/api/v1/saved-filters/" + encodeURIComponent(id), {
				method: "PATCH",
				body: { query_json: persistableQuery(draft) },
			})
			.then(function () {
				notify("success", t("Filter updated"));
				return loadSaved();
			})
			.catch(function () {
				notify("error", "Could not overwrite filter");
			});
	}

	function makeDefault(id) {
		if (!api()) return;
		api()
			.fetchJson("/api/v1/saved-filters/" + encodeURIComponent(id), { method: "PATCH", body: { is_default: true } })
			.then(function () {
				return loadSaved();
			})
			.catch(function () {
				notify("error", "Could not set default");
			});
	}

	function deleteSaved(id) {
		if (!api() || !global.confirm("Delete this saved filter?")) return;
		api()
			.fetchJson("/api/v1/saved-filters/" + encodeURIComponent(id), { method: "DELETE" })
			.then(function () {
				if (applied.saved_filter_id === id) applied.saved_filter_id = "";
				return loadSaved();
			})
			.catch(function () {
				notify("error", "Could not delete filter");
			});
	}

	function bootInitialQuery() {
		if (urlHasFilters()) {
			applied = fromUrl();
			writeDraft(applied);
			persist(applied);
			paintToolbar();
			return Promise.resolve(applied);
		}
		return loadSaved().then(function (items) {
			var def = (items || []).filter(function (r) {
				return r.is_default;
			})[0];
			if (def) {
				applied = normalizeQuery(def.query_json);
				applied.saved_filter_id = def.id;
				writeDraft(applied);
				writeUrl(applied);
				persist(applied);
				paintToolbar();
				return applied;
			}
			var stored = loadPersisted();
			if (stored && queryHasCriteria(stored)) {
				applied = stored;
				writeDraft(applied);
				writeUrl(applied);
				paintToolbar();
				return applied;
			}
			applied = emptyQuery();
			writeDraft(applied);
			paintToolbar();
			return applied;
		});
	}

	function init(options) {
		opts = options || {};
		bindEvents();
		writeDraft(applied);
		paintOffice();
		return Promise.all([loadOwners(), loadOffice(), bootInitialQuery()]).then(function () {
			return applied;
		});
	}

	function statusLine(shown, total) {
		var labels = activeCriteria(applied).map(function (c) {
			return c.label.split(":")[0];
		});
		var uniq = labels.filter(function (v, i, a) {
			return a.indexOf(v) === i;
		});
		var parts = ["Showing " + shown + " of " + total + " leads"];
		if (uniq.length) parts.push("Filters on: " + uniq.join(", "));
		return parts.join(" · ");
	}

	global.USISLeadsFilters = {
		init: init,
		applyQuery: applyQuery,
		resetAll: resetAll,
		listParams: listParams,
		getApplied: function () {
			return cloneQuery(applied);
		},
		criterionCount: function () {
			return criterionCount(applied);
		},
		relaxesOpenBoard: function () {
			return relaxesOpenBoard(applied);
		},
		statusLine: statusLine,
		paint: paintToolbar,
	};
})(typeof window !== "undefined" ? window : this);
