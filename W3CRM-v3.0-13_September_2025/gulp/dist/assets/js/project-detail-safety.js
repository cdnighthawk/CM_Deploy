(function () {
	"use strict";

	var SCOPE_FLAGS = [
		["interiors", "Interiors"],
		["ladders", "Ladders"],
		["scaffolds", "Scaffolds"],
		["aerialLifts", "Aerial lifts"],
		["powderActuatedTools", "Powder-actuated tools"],
		["silicaCuttingGrinding", "Silica / cutting"],
		["hotWork", "Hot work"],
		["electricalTempPower", "Temp power / GFCI"],
		["occupiedBuilding", "Occupied building"],
		["publicInterface", "Public interface"],
		["confinedSpace", "Confined space"],
		["excavation", "Excavation"],
		["craneOrHoist", "Crane / hoist"],
		["steelErection", "Steel erection"],
		["demolition", "Demolition"],
		["leadPaint", "Lead"],
		["asbestosPossible", "Possible asbestos"],
	];

	var projectId = "";
	var canEdit = true;
	var canPublish = false;

	function api() {
		return window.USIS_API;
	}

	function projectIdFromUrl() {
		var p = new URLSearchParams(window.location.search);
		return (p.get("id") || p.get("project_id") || p.get("projectId") || "").trim();
	}

	function el(html) {
		var d = document.createElement("div");
		d.innerHTML = html;
		return d.firstElementChild;
	}

	function field(id, label, value, extra) {
		extra = extra || "";
		return (
			'<div class="' +
			(extra.col || "col-md-6") +
			'">' +
			'<label class="form-label small mb-0" for="' +
			id +
			'">' +
			label +
			"</label>" +
			(extra.ta
				? '<textarea class="form-control form-control-sm" id="' +
					id +
					'" rows="' +
					(extra.rows || 2) +
					'">' +
					escapeHtml(value) +
					"</textarea>"
				: '<input class="form-control form-control-sm" id="' +
					id +
					'" value="' +
					escapeHtml(value) +
					'" />') +
			"</div>"
		);
	}

	function escapeHtml(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function get(id) {
		var n = document.getElementById(id);
		if (!n) return "";
		if (n.type === "checkbox") return n.checked;
		return String(n.value || "").trim();
	}

	function person(prefix, src) {
		src = src || {};
		return (
			field(prefix + "-name", "Name", src.name) +
			field(prefix + "-phone", "Phone", src.phone) +
			field(prefix + "-title", "Title", src.title) +
			field(prefix + "-email", "Email", src.email)
		);
	}

	function readPerson(prefix) {
		return {
			name: get(prefix + "-name"),
			phone: get(prefix + "-phone"),
			title: get(prefix + "-title"),
			email: get(prefix + "-email"),
		};
	}

	function render(root, item) {
		var p = item.payload || {};
		var ident = item.identity || {};
		var em = p.emergency || {};
		var hosp = em.hospital || {};
		var clinic = em.clinic || {};
		var cal = em.calOshaDistrictOffice || {};
		var cl = p.climate || {};
		var scope = p.scope || {};
		var cp = p.competentPersons || {};
		var miss = item.missing_fields || [];
		var packet = item.packet;
		var status = packet ? packet.status : "none";
		var chip =
			status === "published"
				? '<span class="usis-status-chip usis-status-chip--success">Published</span>'
				: '<span class="usis-status-chip usis-status-chip--draft">Draft — not for mobilization</span>';

		var scopeBoxes = SCOPE_FLAGS.map(function (pair) {
			var checked = scope[pair[0]] ? " checked" : "";
			return (
				'<div class="col-md-4 col-sm-6"><div class="form-check">' +
				'<input class="form-check-input" type="checkbox" id="usis-saf-scope-' +
				pair[0] +
				'"' +
				checked +
				" />" +
				'<label class="form-check-label small" for="usis-saf-scope-' +
				pair[0] +
				'">' +
				pair[1] +
				"</label></div></div>"
			);
		}).join("");

		var chemicals = Array.isArray(p.chemicals) ? p.chemicals : [];
		var chemRows = chemicals
			.map(function (c, i) {
				return chemRowHtml(i, c);
			})
			.join("");
		if (!chemRows) chemRows = chemRowHtml(0, {});

		root.innerHTML =
			'<div class="d-flex flex-wrap align-items-center gap-2 justify-content-between mb-3">' +
			"<div><h5 class=\"mb-1\">Project safety packet</h5>" +
			'<p class="text-muted small mb-0">' +
			escapeHtml(ident.name || p.projectName || "") +
			(ident.number ? " · " + escapeHtml(ident.number) : "") +
			"</p></div>" +
			"<div>" +
			chip +
			' <button type="button" class="btn btn-outline-secondary btn-sm" id="usis-saf-save">Save draft</button>' +
			' <button type="button" class="btn btn-outline-primary btn-sm" id="usis-saf-regen">Regenerate packet</button>' +
			' <button type="button" class="btn btn-primary btn-sm" id="usis-saf-publish">Publish</button>' +
			"</div></div>" +
			'<div class="alert alert-danger d-none py-2" id="usis-saf-err"></div>' +
			'<div class="alert alert-success d-none py-2" id="usis-saf-ok"></div>' +
			(miss.length
				? '<div class="alert alert-warning py-2">Missing for publish: ' +
					escapeHtml(miss.join(", ")) +
					"</div>"
				: "") +
			'<p class="small text-muted">Job name, number, and address come from Job info. Fill people, emergency, climate, and scope here.</p>' +
			'<form id="usis-saf-form" class="row g-3">' +
			'<div class="col-12"><h6 class="mb-0">People</h6></div>' +
			'<div class="col-12"><p class="small fw-semibold mb-1">Superintendent (required to publish)</p><div class="row g-2">' +
			person("usis-saf-sup", p.superintendent) +
			"</div></div>" +
			'<div class="col-12"><p class="small fw-semibold mb-1">Project manager</p><div class="row g-2">' +
			person("usis-saf-pm", p.projectManager) +
			"</div></div>" +
			'<div class="col-md-3">' +
			field("usis-saf-role", "Role on site", p.roleOnSite || "subcontractor", { col: "col-12" }).replace(
				'class="col-12"',
				'class="w-100"'
			) +
			"</div>" +
			field("usis-saf-client", "Client", p.clientName, { col: "col-md-3" }) +
			field("usis-saf-gc", "GC", p.gcName, { col: "col-md-3" }) +
			field("usis-saf-crew", "Typical crew", p.crewSizeTypical, { col: "col-md-3" }) +
			'<div class="col-12"><h6 class="mb-0">Emergency</h6></div>' +
			field("usis-saf-muster", "Muster point", em.musterPoint) +
			field("usis-saf-muster2", "Secondary muster", em.secondaryMuster) +
			field("usis-saf-who911", "Who calls 911", em.whoCalls911) +
			field("usis-saf-whoCal", "Who calls Cal/OSHA", em.whoCallsCalOsha) +
			field("usis-saf-dir911", "What to tell 911", em.directionsFor911, { col: "col-12", ta: true }) +
			field("usis-saf-hosp-name", "Hospital name", hosp.name) +
			field("usis-saf-hosp-phone", "Hospital phone", hosp.phone) +
			field("usis-saf-hosp-addr", "Hospital address", hosp.address, { col: "col-12" }) +
			field("usis-saf-hosp-dir", "Hospital directions", hosp.directions, { col: "col-12", ta: true }) +
			field("usis-saf-clinic-name", "Clinic", clinic.name) +
			field("usis-saf-clinic-phone", "Clinic phone", clinic.phone) +
			field("usis-saf-fire", "Fire", em.fireDept) +
			field("usis-saf-police", "Police", em.police) +
			field("usis-saf-cal-name", "Cal/OSHA district", cal.name) +
			field("usis-saf-cal-phone", "Cal/OSHA phone", cal.phone) +
			field("usis-saf-radio", "Radio channel", em.radioChannel) +
			'<div class="col-md-6 d-flex align-items-end"><div class="form-check mb-1">' +
			'<input class="form-check-input" type="checkbox" id="usis-saf-cell"' +
			(em.cellCoverageReliable ? " checked" : "") +
			" />" +
			'<label class="form-check-label" for="usis-saf-cell">Cell coverage reliable</label></div></div>' +
			'<div class="col-12"><h6 class="mb-0">Climate</h6></div>' +
			'<div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="usis-saf-out"' +
			(cl.outdoorWork ? " checked" : "") +
			' /><label class="form-check-label" for="usis-saf-out">Outdoor work</label></div></div>' +
			'<div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="usis-saf-in"' +
			(cl.indoorWork ? " checked" : "") +
			' /><label class="form-check-label" for="usis-saf-in">Indoor work</label></div></div>' +
			'<div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="usis-saf-cold"' +
			(cl.coldIceSnow ? " checked" : "") +
			' /><label class="form-check-label" for="usis-saf-cold">Ice / snow</label></div></div>' +
			'<div class="col-md-3"><div class="form-check mt-4"><input class="form-check-input" type="checkbox" id="usis-saf-smoke"' +
			(cl.wildfireSmokePossible ? " checked" : "") +
			' /><label class="form-check-label" for="usis-saf-smoke">Wildfire smoke possible</label></div></div>' +
			field("usis-saf-elev", "Elevation (ft)", cl.elevationFt, { col: "col-md-3" }) +
			field("usis-saf-heat", "Heat risk (low/moderate/high)", cl.heatRisk || "moderate", { col: "col-md-3" }) +
			field("usis-saf-clnotes", "Climate notes", cl.notes, { col: "col-12", ta: true }) +
			'<div class="col-12"><h6 class="mb-0">Scope (SSSP chapters)</h6></div>' +
			'<div class="col-12"><div class="row g-1">' +
			scopeBoxes +
			"</div></div>" +
			'<div class="col-12"><h6 class="mb-0">PPE, chemicals, notes</h6></div>' +
			field("usis-saf-ppe", "PPE (one per line)", (p.ppeRequired || []).join("\n"), {
				col: "col-12",
				ta: true,
				rows: 4,
			}) +
			'<div class="col-12"><p class="small fw-semibold mb-1">Chemicals</p>' +
			'<div id="usis-saf-chem">' +
			chemRows +
			"</div>" +
			'<button type="button" class="btn btn-sm btn-outline-secondary mt-1" id="usis-saf-chem-add">Add chemical</button></div>' +
			field("usis-saf-gcrules", "GC stricter rules", p.gcRulesStricter, { col: "col-12", ta: true }) +
			field("usis-saf-notes", "Notes", p.notes, { col: "col-12", ta: true }) +
			field("usis-saf-access", "Access notes", p.accessNotes, { col: "col-12", ta: true }) +
			"</form>" +
			'<div class="mt-3"><h6>Packet preview</h6>' +
			'<iframe id="usis-saf-preview" title="Safety packet preview" style="width:100%;min-height:32rem;border:1px solid #dee2e6;background:#fff;"></iframe></div>';

		var add = document.getElementById("usis-saf-chem-add");
		if (add) {
			add.addEventListener("click", function () {
				var box = document.getElementById("usis-saf-chem");
				if (!box) return;
				box.insertAdjacentHTML("beforeend", chemRowHtml(box.querySelectorAll("[data-chem]").length, {}));
			});
		}
		var saveBtn = document.getElementById("usis-saf-save");
		if (saveBtn) saveBtn.addEventListener("click", saveDraft);
		var regenBtn = document.getElementById("usis-saf-regen");
		if (regenBtn) regenBtn.addEventListener("click", regenerate);
		var pubBtn = document.getElementById("usis-saf-publish");
		if (pubBtn) {
			pubBtn.disabled = !canPublish || miss.length > 0;
			pubBtn.addEventListener("click", publish);
		}
		if (packet) loadPreview();
		if (!canEdit) {
			root.querySelectorAll("input, textarea, select, button").forEach(function (n) {
				if (n.id === "usis-saf-preview") return;
				n.disabled = true;
			});
		}
	}

	function chemRowHtml(i, c) {
		c = c || {};
		return (
			'<div class="row g-2 mb-1" data-chem>' +
			'<div class="col-md-3"><input class="form-control form-control-sm" data-chem-k="productName" placeholder="Product" value="' +
			escapeHtml(c.productName) +
			'" /></div>' +
			'<div class="col-md-3"><input class="form-control form-control-sm" data-chem-k="manufacturer" placeholder="Manufacturer" value="' +
			escapeHtml(c.manufacturer) +
			'" /></div>' +
			'<div class="col-md-3"><input class="form-control form-control-sm" data-chem-k="useLocation" placeholder="Use location" value="' +
			escapeHtml(c.useLocation) +
			'" /></div>' +
			'<div class="col-md-3"><input class="form-control form-control-sm" data-chem-k="sdsUrl" placeholder="SDS URL" value="' +
			escapeHtml(c.sdsUrl) +
			'" /></div></div>'
		);
	}

	function collectChemicals() {
		var out = [];
		document.querySelectorAll("#usis-saf-chem [data-chem]").forEach(function (row) {
			var item = {};
			row.querySelectorAll("[data-chem-k]").forEach(function (inp) {
				item[inp.getAttribute("data-chem-k")] = String(inp.value || "").trim();
			});
			if (item.productName) out.push(item);
		});
		return out;
	}

	function collectPayload() {
		var scope = {};
		SCOPE_FLAGS.forEach(function (pair) {
			scope[pair[0]] = !!get("usis-saf-scope-" + pair[0]);
		});
		var crewRaw = get("usis-saf-crew");
		var elevRaw = get("usis-saf-elev");
		return {
			clientName: get("usis-saf-client"),
			gcName: get("usis-saf-gc"),
			roleOnSite: get("usis-saf-role") || "subcontractor",
			crewSizeTypical: crewRaw ? parseInt(crewRaw, 10) : null,
			accessNotes: get("usis-saf-access"),
			superintendent: readPerson("usis-saf-sup"),
			projectManager: readPerson("usis-saf-pm"),
			emergency: {
				musterPoint: get("usis-saf-muster"),
				secondaryMuster: get("usis-saf-muster2"),
				whoCalls911: get("usis-saf-who911"),
				whoCallsCalOsha: get("usis-saf-whoCal"),
				directionsFor911: get("usis-saf-dir911"),
				hospital: {
					name: get("usis-saf-hosp-name"),
					phone: get("usis-saf-hosp-phone"),
					address: get("usis-saf-hosp-addr"),
					directions: get("usis-saf-hosp-dir"),
				},
				clinic: { name: get("usis-saf-clinic-name"), phone: get("usis-saf-clinic-phone") },
				fireDept: get("usis-saf-fire"),
				police: get("usis-saf-police"),
				calOshaDistrictOffice: { name: get("usis-saf-cal-name"), phone: get("usis-saf-cal-phone") },
				cellCoverageReliable: !!get("usis-saf-cell"),
				radioChannel: get("usis-saf-radio"),
			},
			climate: {
				outdoorWork: !!get("usis-saf-out"),
				indoorWork: !!get("usis-saf-in"),
				coldIceSnow: !!get("usis-saf-cold"),
				wildfireSmokePossible: !!get("usis-saf-smoke"),
				elevationFt: elevRaw ? parseInt(elevRaw, 10) : null,
				heatRisk: get("usis-saf-heat") || "moderate",
				notes: get("usis-saf-clnotes"),
			},
			scope: scope,
			ppeRequired: get("usis-saf-ppe")
				.split("\n")
				.map(function (s) {
					return s.trim();
				})
				.filter(Boolean),
			chemicals: collectChemicals(),
			gcRulesStricter: get("usis-saf-gcrules"),
			notes: get("usis-saf-notes"),
		};
	}

	function flash(ok, msg) {
		var err = document.getElementById("usis-saf-err");
		var good = document.getElementById("usis-saf-ok");
		if (err) {
			err.textContent = ok ? "" : msg;
			err.classList.toggle("d-none", ok || !msg);
		}
		if (good) {
			good.textContent = ok ? msg : "";
			good.classList.toggle("d-none", !ok || !msg);
		}
	}

	function saveDraft() {
		if (!api() || !projectId) return;
		flash(true, "");
		api()
			.fetchJson("/api/v1/projects/" + projectId + "/safety-profile", {
				method: "PUT",
				body: { payload: collectPayload() },
			})
			.then(function (body) {
				canEdit = !!body.can_edit;
				canPublish = !!body.can_publish;
				render(document.getElementById("usis-proj-safety-root"), body.item);
				flash(true, "Safety profile saved.");
			})
			.catch(function (e) {
				flash(false, (e && e.body) || e.message || "Save failed");
			});
	}

	function regenerate() {
		if (!api() || !projectId) return;
		flash(true, "");
		api()
			.fetchJson("/api/v1/projects/" + projectId + "/safety-profile", {
				method: "PUT",
				body: { payload: collectPayload() },
			})
			.then(function () {
				return api().fetchJson("/api/v1/projects/" + projectId + "/safety-packet/regenerate", {
					method: "POST",
					body: {},
				});
			})
			.then(function () {
				return load(true);
			})
			.then(function () {
				flash(true, "Packet regenerated.");
			})
			.catch(function (e) {
				flash(false, (e && e.body) || e.message || "Regenerate failed");
			});
	}

	function publish() {
		if (!api() || !projectId) return;
		flash(true, "");
		api()
			.fetchJson("/api/v1/projects/" + projectId + "/safety-packet/publish", { method: "POST", body: {} })
			.then(function () {
				return load(true);
			})
			.then(function () {
				flash(true, "Packet published.");
			})
			.catch(function (e) {
				flash(false, (e && e.body) || e.message || "Publish blocked");
			});
	}

	function loadPreview() {
		var frame = document.getElementById("usis-saf-preview");
		if (!frame || !api()) return;
		fetch(api().buildUrl("/api/v1/projects/" + projectId + "/safety-packet/preview"), {
			credentials: "include",
			headers: Object.assign({ Accept: "text/html" }, api().actorHeaders()),
		})
			.then(function (res) {
				if (!res.ok) return "";
				return res.text();
			})
			.then(function (html) {
				if (html) frame.srcdoc = html;
			})
			.catch(function () {});
	}

	function load(keepFlash) {
		var root = document.getElementById("usis-proj-safety-root");
		if (!root || !api() || !projectId) return Promise.resolve();
		return api()
			.fetchJson("/api/v1/projects/" + projectId + "/safety-profile")
			.then(function (body) {
				canEdit = !!body.can_edit;
				canPublish = !!body.can_publish;
				render(root, body.item);
				if (!keepFlash) flash(true, "");
			})
			.catch(function (e) {
				root.innerHTML =
					'<div class="alert alert-danger mb-0">' +
					escapeHtml((e && e.body) || e.message || "Could not load safety profile") +
					"</div>";
			});
	}

	function boot() {
		projectId = projectIdFromUrl();
		var root = document.getElementById("usis-proj-safety-root");
		if (!root) return;
		if (!projectId) {
			root.innerHTML = '<div class="alert alert-warning mb-0">Open this page from the Projects table so a project id is in the URL.</div>';
			return;
		}
		var tab = document.getElementById("proj-tab-safety");
		if (tab) {
			tab.addEventListener("shown.bs.tab", function () {
				load();
			});
		}
		if (root.closest(".tab-pane") && root.closest(".tab-pane").classList.contains("active")) {
			load();
		}
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot);
	} else {
		boot();
	}
})();
