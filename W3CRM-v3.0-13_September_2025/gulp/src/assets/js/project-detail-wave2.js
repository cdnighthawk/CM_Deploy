/**
 * Wave 2 Sage CM: transmittals, punch, photos, WO, anticipated, PO CO,
 * sub invoices, meetings, incidents, QC, open items.
 */
(function () {
	"use strict";

	var KINDS = [
		{ kind: "punchlist", titleKey: "title", extra: "location", heading: "New GC punch item", submit: "Add item", customCreate: true },
		{ kind: "work-orders", titleKey: "subject", extra: "amount", heading: "New work order", submit: "Add work order" },
		{ kind: "meetings", titleKey: "subject", extra: "meeting_date", heading: "New meeting", submit: "Add meeting", customCreate: true },
		{ kind: "safety-incidents", titleKey: "subject", extra: "severity", heading: "New safety incident", submit: "Add incident" },
		{ kind: "transmittals", titleKey: "subject", extra: "due_date", heading: "New transmittal", submit: "Add transmittal" },
		{ kind: "anticipated-costs", titleKey: "subject", extra: "amount", heading: "New anticipated cost", submit: "Add cost" },
		{ kind: "po-change-orders", titleKey: "subject", extra: "amount", needCommitment: true, heading: "New PO change order", submit: "Add PO CO", customCreate: true },
		{ kind: "sub-invoices", titleKey: "subject", extra: "amount", heading: "New sub invoice", submit: "Add sub invoice", customCreate: true },
		{ kind: "qc-checklists", titleKey: "subject", extra: "review_date", heading: "New QC checklist", submit: "Add checklist" },
	];

	var EXTRA_UI = {
		amount: { label: "Amount", type: "number" },
		location: { label: "Location", type: "text" },
		severity: { label: "Severity", type: "severity" },
		meeting_date: { label: "Meeting date", type: "date" },
		due_date: { label: "Due date", type: "date" },
		review_date: { label: "Review date", type: "date" },
	};

	var pendingCfg = null;

	function projectId() {
		var p = new URLSearchParams(window.location.search);
		return (p.get("id") || p.get("project_id") || p.get("projectId") || "").trim() || null;
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function fetchJson(path, opts) {
		return window.USIS_API.fetchJson(path, opts || {});
	}

	function pidPath(suffix) {
		return "/api/v1/projects/" + encodeURIComponent(projectId()) + suffix;
	}

	function money(n) {
		if (n == null || n === "") return "—";
		var x = Number(n);
		if (isNaN(x)) return String(n);
		return x.toLocaleString(undefined, { style: "currency", currency: "USD" });
	}

	function punchHref() {
		var pid = projectId();
		if (!pid) return "construction/punch-create.html";
		return "construction/punch-create.html?project_id=" + encodeURIComponent(pid);
	}

	function docHref(page, id) {
		var pid = projectId();
		var href = "construction/" + page;
		if (!pid) return href;
		href += "?project_id=" + encodeURIComponent(pid);
		if (id) href += "&id=" + encodeURIComponent(id);
		return href;
	}

	function chip(st) {
		return window.USISUi && window.USISUi.statusChip ? window.USISUi.statusChip(st || "") : esc(st || "");
	}

	function emptyCell(cols, title) {
		if (window.USISUi && window.USISUi.emptyState) {
			return '<tr><td colspan="' + cols + '">' + window.USISUi.emptyState({ title: title, body: "" }) + "</td></tr>";
		}
		return '<tr><td colspan="' + cols + '" class="text-muted">' + esc(title) + "</td></tr>";
	}

	function loadKind(cfg) {
		var tbody = document.getElementById("usis-w2-" + cfg.kind);
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/wave2/" + cfg.kind))
			.then(function (data) {
				var items = data.items || [];
				var cols = cfg.kind === "punchlist" ? 7 : cfg.kind === "meetings" ? 10 : cfg.kind === "sub-invoices" ? 10 : cfg.kind === "po-change-orders" ? 7 : 5;
				if (!items.length) {
					var emptyTitle =
						cfg.kind === "meetings"
							? "No meetings."
							: cfg.kind === "po-change-orders"
								? "No PO change orders."
								: cfg.kind === "sub-invoices"
									? "No sub invoices."
									: "None yet.";
					tbody.innerHTML = emptyCell(cols, emptyTitle);
					return;
				}
				tbody.innerHTML = items
					.map(function (it) {
						var createTarget =
							cfg.kind === "punchlist"
								? "#usis-punch-gc-add"
								: cfg.kind === "meetings"
									? "#usis-meeting-add"
									: cfg.kind === "po-change-orders"
										? "#usis-poco-add"
										: cfg.kind === "sub-invoices"
											? "#usis-subinv-add"
											: '[data-usis-wave2-add="' + cfg.kind + '"]';
						var menu =
							window.USISUi && window.USISUi.rowMenu
								? window.USISUi.rowMenu({
										id: it.id,
										createTarget: createTarget,
										deleteClass: "usis-w2-del",
										deleteData: { kind: cfg.kind, id: it.id },
									})
								: '<button type="button" class="btn btn-link btn-sm p-0 usis-w2-del" data-kind="' +
									esc(cfg.kind) +
									'" data-id="' +
									esc(it.id) +
									'">Delete</button>';
						if (cfg.kind === "punchlist") {
							return (
								"<tr><td>" +
								esc(it.number || "") +
								"</td><td>" +
								esc(it.title || "") +
								"</td><td>" +
								esc(it.status || "") +
								"</td><td>" +
								esc(it.punch_type || "") +
								"</td><td>" +
								esc(it.location || "") +
								"</td><td>" +
								esc(it.priority || "") +
								"</td><td>" +
								menu +
								"</td></tr>"
							);
						}
						if (cfg.kind === "meetings") {
							var mhref = docHref("meeting-create.html", it.id);
							return (
								"<tr><td><a href=\"" +
								esc(mhref) +
								"\">" +
								esc(it.number || "") +
								"</a></td><td>" +
								esc(it.meeting_type || "") +
								"</td><td><a href=\"" +
								esc(mhref) +
								"\">" +
								esc(it.subject || "") +
								"</a></td><td>" +
								esc(it.meeting_date || "") +
								"</td><td>" +
								esc(it.time_range || ((it.start_time || "") + (it.end_time ? "–" + it.end_time : ""))) +
								"</td><td>" +
								esc(it.location || "") +
								"</td><td>" +
								esc(it.facilitator_name || "") +
								"</td><td>" +
								chip(it.status) +
								"</td><td>" +
								esc(it.attendee_count != null ? it.attendee_count : "") +
								"</td><td>" +
								menu +
								"</td></tr>"
							);
						}
						if (cfg.kind === "po-change-orders") {
							var phref = docHref("po-co-create.html", it.id);
							return (
								"<tr><td><a href=\"" +
								esc(phref) +
								"\">" +
								esc(it.number || "") +
								"</a></td><td>" +
								esc(it.po_number || "") +
								"</td><td><a href=\"" +
								esc(phref) +
								"\">" +
								esc(it.subject || "") +
								"</a></td><td>" +
								chip(it.status) +
								"</td><td>" +
								esc(it.status_date || "") +
								'</td><td class="text-end">' +
								money(it.amount) +
								"</td><td>" +
								menu +
								"</td></tr>"
							);
						}
						if (cfg.kind === "sub-invoices") {
							var shref = docHref("sub-invoice-create.html", it.id);
							return (
								"<tr><td><a href=\"" +
								esc(shref) +
								"\">" +
								esc(it.number || "") +
								"</a></td><td>" +
								esc(it.subcontract_number || "") +
								"</td><td>" +
								esc(it.vendor_name || "") +
								"</td><td>" +
								esc(it.period || "") +
								"</td><td>" +
								chip(it.status) +
								'</td><td class="text-end">' +
								money(it.this_period) +
								'</td><td class="text-end">' +
								money(it.retainage) +
								'</td><td class="text-end">' +
								money(it.previous_to_date) +
								'</td><td class="text-end">' +
								money(it.amount_due) +
								"</td><td>" +
								menu +
								"</td></tr>"
							);
						}
						var extra = it[cfg.extra];
						if (cfg.extra === "amount") extra = money(extra);
						return (
							"<tr><td>" +
							esc(it.number || "") +
							"</td><td>" +
							esc(it[cfg.titleKey] || "") +
							"</td><td>" +
							esc(it.status || "") +
							"</td><td>" +
							esc(extra == null ? "" : extra) +
							"</td><td>" +
							menu +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				var cols = cfg.kind === "punchlist" ? 7 : 5;
				tbody.innerHTML = '<tr><td colspan="' + cols + '" class="text-muted">Could not load.</td></tr>';
			});
	}

	function modalEls() {
		return {
			root: document.getElementById("usis-modal-wave2-create"),
			titleEl: document.getElementById("usis-modal-wave2-create-title"),
			form: document.getElementById("usis-wave2-create-form"),
			err: document.getElementById("usis-wave2-create-err"),
			titleLabel: document.getElementById("usis-wave2-title-label"),
			titleInput: document.getElementById("usis-wave2-title"),
			commitWrap: document.getElementById("usis-wave2-wrap-commitment"),
			commitSel: document.getElementById("usis-wave2-commitment"),
			extraWrap: document.getElementById("usis-wave2-wrap-extra"),
			extraLabel: document.getElementById("usis-wave2-extra-label"),
			extraInput: document.getElementById("usis-wave2-extra"),
			severitySel: document.getElementById("usis-wave2-severity"),
			submit: document.getElementById("usis-wave2-create-submit"),
		};
	}

	function setModalErr(msg) {
		var el = modalEls().err;
		if (!el) return;
		if (msg) {
			el.textContent = String(msg);
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function fillPoSelect() {
		var sel = modalEls().commitSel;
		if (!sel || !projectId()) return Promise.resolve();
		sel.innerHTML = '<option value="">Select a PO</option>';
		return fetchJson("/api/v1/projects/" + encodeURIComponent(projectId()) + "/commitments")
			.then(function (data) {
				var pos = (data.items || []).filter(function (c) {
					return (c.commitment_kind || "") === "purchase_order";
				});
				if (!pos.length) {
					sel.innerHTML = '<option value="">No purchase orders on this project</option>';
					return;
				}
				sel.innerHTML =
					'<option value="">Select a PO</option>' +
					pos
						.map(function (p) {
							var label = (p.reference_number || p.title || p.id || "").trim();
							if (p.vendor_name) label += " — " + p.vendor_name;
							return '<option value="' + esc(p.id) + '">' + esc(label) + "</option>";
						})
						.join("");
			})
			.catch(function () {
				sel.innerHTML = '<option value="">Could not load POs</option>';
			});
	}

	function openCreateModal(cfg) {
		var els = modalEls();
		if (!els.root || !window.bootstrap || !window.bootstrap.Modal) {
			window.alert("Create dialog is missing. Reload the page.");
			return;
		}
		pendingCfg = cfg;
		setModalErr("");
		if (els.titleEl) els.titleEl.textContent = cfg.heading || "New item";
		if (els.titleLabel) els.titleLabel.textContent = cfg.titleKey === "title" ? "Title" : "Subject";
		if (els.titleInput) els.titleInput.value = "";
		if (els.submit) els.submit.textContent = cfg.submit || "Create";
		if (els.commitWrap) els.commitWrap.classList.toggle("d-none", !cfg.needCommitment);
		if (els.commitSel) els.commitSel.value = "";
		var extra = EXTRA_UI[cfg.extra];
		if (els.extraWrap) els.extraWrap.classList.toggle("d-none", !extra);
		if (extra && els.extraLabel) els.extraLabel.textContent = extra.label;
		if (els.extraInput && els.severitySel) {
			var isSev = extra && extra.type === "severity";
			els.extraInput.classList.toggle("d-none", isSev);
			els.severitySel.classList.toggle("d-none", !isSev);
			els.severitySel.value = "";
			els.extraInput.value = "";
			els.extraInput.type = extra && extra.type !== "severity" ? extra.type : "text";
			els.extraInput.placeholder = extra && extra.type === "text" ? "Optional" : extra && extra.type === "number" ? "Optional" : "";
			els.extraInput.step = extra && extra.type === "number" ? "0.01" : "";
		}
		var ready = cfg.needCommitment ? fillPoSelect() : Promise.resolve();
		ready.then(function () {
			window.bootstrap.Modal.getOrCreateInstance(els.root).show();
			if (els.titleInput) els.titleInput.focus();
		});
	}

	function submitCreate(ev) {
		if (ev) ev.preventDefault();
		var cfg = pendingCfg;
		var els = modalEls();
		if (!cfg || !els.titleInput) return;
		var title = (els.titleInput.value || "").trim();
		if (!title) {
			setModalErr((cfg.titleKey === "title" ? "Title" : "Subject") + " is required.");
			els.titleInput.focus();
			return;
		}
		var body = {};
		body[cfg.titleKey] = title;
		if (cfg.needCommitment) {
			var cid = ((els.commitSel && els.commitSel.value) || "").trim();
			if (!cid) {
				setModalErr("Select a purchase order.");
				return;
			}
			body.commitment_id = cid;
		}
		var extra = EXTRA_UI[cfg.extra];
		if (extra) {
			var raw =
				extra.type === "severity"
					? ((els.severitySel && els.severitySel.value) || "").trim()
					: ((els.extraInput && els.extraInput.value) || "").trim();
			if (raw) body[cfg.extra] = raw;
		}
		if (els.submit) els.submit.disabled = true;
		setModalErr("");
		fetchJson(pidPath("/wave2/" + cfg.kind), { method: "POST", body: body })
			.then(function () {
				if (els.root && window.bootstrap && window.bootstrap.Modal) {
					window.bootstrap.Modal.getOrCreateInstance(els.root).hide();
				}
				loadKind(cfg);
			})
			.catch(function (err) {
				var msg = (err && (err.body || err.message)) || "Could not create.";
				if (typeof msg === "object") msg = (msg.error || msg.message) || JSON.stringify(msg);
				setModalErr(msg);
			})
			.finally(function () {
				if (els.submit) els.submit.disabled = false;
			});
	}

	function addKind(cfg) {
		openCreateModal(cfg);
	}

	function delKind(kind, id) {
		if (!id || !window.confirm("Delete this record?")) return;
		fetchJson(pidPath("/wave2/" + kind + "/" + encodeURIComponent(id)), { method: "DELETE" })
			.then(function () {
				var cfg = KINDS.filter(function (k) {
					return k.kind === kind;
				})[0];
				if (cfg) loadKind(cfg);
			})
			.catch(function () {
				window.alert("Could not delete.");
			});
	}

	function loadPhotos() {
		var root = document.getElementById("usis-photo-gallery");
		if (!root || !projectId()) return;
		fetchJson(pidPath("/photos"))
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					root.innerHTML = '<p class="text-muted small">No photos yet.</p>';
					return;
				}
				root.innerHTML = items
					.map(function (ph) {
						var src = window.USIS_API.apiBase() + (ph.file_url || "");
						return (
							'<div class="col-6 col-md-3"><div class="card border-0 shadow-sm h-100"><img src="' +
							esc(src) +
							'" class="card-img-top" alt="" style="height:8rem;object-fit:cover"><div class="card-body p-2 small d-flex justify-content-between align-items-start gap-2">' +
							"<span>" +
							esc(ph.caption || ph.album || "Photo") +
							'</span><button type="button" class="btn btn-sm btn-outline-danger py-0 usis-photo-del" data-id="' +
							esc(ph.id) +
							'">Delete</button></div></div></div>'
						);
					})
					.join("");
			})
			.catch(function () {
				root.innerHTML = '<p class="text-muted small">Could not load photos.</p>';
			});
	}

	function uploadPhoto() {
		var fileEl = document.getElementById("usis-photo-file");
		if (!fileEl || !fileEl.files || !fileEl.files[0]) {
			window.alert("Choose a photo first.");
			return;
		}
		var fd = new FormData();
		fd.append("file", fileEl.files[0]);
		var album = ((document.getElementById("usis-photo-album") || {}).value || "").trim();
		if (album) fd.append("album", album);
		var headers = Object.assign({}, window.USIS_API.actorHeaders());
		fetch(window.USIS_API.apiBase() + pidPath("/photos"), {
			method: "POST",
			credentials: "include",
			headers: headers,
			body: fd,
		})
			.then(function (res) {
				if (!res.ok) throw new Error("upload failed");
				fileEl.value = "";
				loadPhotos();
			})
			.catch(function () {
				window.alert("Upload failed.");
			});
	}

	var crewPunchCache = {};

	function crewEls() {
		return {
			root: document.getElementById("usis-modal-crew-punch"),
			form: document.getElementById("usis-crew-punch-form"),
			err: document.getElementById("usis-crew-punch-err"),
			title: document.getElementById("usis-crew-punch-title"),
			room: document.getElementById("usis-crew-punch-room"),
			notes: document.getElementById("usis-crew-punch-notes"),
			photo: document.getElementById("usis-crew-punch-photo"),
			submit: document.getElementById("usis-crew-punch-submit"),
			tbody: document.getElementById("usis-punch-crew-tbody"),
		};
	}

	function setCrewErr(msg) {
		var el = crewEls().err;
		if (!el) return;
		if (msg) {
			el.textContent = String(msg);
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function crewIssuePath() {
		return pidPath("/issues?source_type=crew_punch");
	}

	function crewPunchItemsPath() {
		return pidPath("/punch-items?list=ours");
	}

	function prettyPunch(v) {
		if (v == null || v === "") return "";
		return String(v).replace(/_/g, " ");
	}

	function newLocalId() {
		if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
		return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
			var r = (Math.random() * 16) | 0;
			return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
		});
	}

	function crewCacheKey(source, id) {
		return String(source || "punch_item") + ":" + String(id || "");
	}

	function photoSrc(ph) {
		var url = (ph && (ph.file_url || ph.url)) || "";
		if (!url) return "";
		if (/^https?:\/\//i.test(url)) return url;
		return (window.USIS_API.apiBase() || "") + url;
	}

	function bindPunchPhotos(root) {
		if (!root) return;
		root.querySelectorAll("img.usis-punch-photo[data-file-url]").forEach(function (img) {
			var url = img.getAttribute("data-file-url") || "";
			if (!url) return;
			fetch(url, {
				credentials: "include",
				headers: Object.assign({ Accept: "image/*" }, window.USIS_API.actorHeaders()),
			})
				.then(function (res) {
					if (!res.ok) throw new Error("photo");
					return res.blob();
				})
				.then(function (blob) {
					if (!blob || blob.size < 32) {
						img.src = url;
						return;
					}
					img.src = URL.createObjectURL(blob);
				})
				.catch(function () {
					img.src = url;
				});
		});
	}

	function normalizeFieldPunch(it) {
		return {
			source: "punch_item",
			id: it.id,
			number: it.number,
			title: it.title || "",
			room: it.location_text || "",
			status: it.status || "",
			type: it.type || "",
			priority: it.priority || "",
			trade: it.trade || "",
			description: it.description || "",
			assignee_name: it.assignee_name || "",
			due_on: it.due_on || "",
			schedule_impact: it.schedule_impact || "",
			schedule_note: it.schedule_note || "",
			cost_impact: it.cost_impact || "",
			cost_note: it.cost_note || "",
			source_label: it.source || "",
			last_notified_at: it.last_notified_at || "",
			created_at: it.created_at || "",
			updated_at: it.updated_at || "",
			distribution: it.distribution || [],
			photos: it.photos || [],
		};
	}

	function normalizeCrewIssue(it) {
		var photos = [];
		if (it.photo_id) {
			photos.push({ id: it.photo_id, file_url: "/api/v1/photos/" + it.photo_id + "/file" });
		}
		return {
			source: "issue",
			id: it.id,
			number: it.number || "",
			title: it.title || "",
			room: it.room || it.sheet_number || "",
			status: it.status || "",
			type: "",
			priority: it.severity || "",
			trade: it.trade || "",
			description: it.description || "",
			assignee_name: it.assignee_name || "",
			due_on: it.due_date || "",
			schedule_impact: it.schedule_impact_days != null ? String(it.schedule_impact_days) : "",
			schedule_note: "",
			cost_impact: it.cost_impact != null ? String(it.cost_impact) : "",
			cost_note: "",
			source_label: it.source_type || "crew_punch",
			last_notified_at: "",
			created_at: it.created_at || "",
			updated_at: it.updated_at || "",
			distribution: [],
			photos: photos,
		};
	}

	function setCrewCount(n) {
		var el = document.getElementById("usis-punch-crew-count");
		if (!el) return;
		if (n > 0) {
			el.textContent = String(n);
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function settledItems(result) {
		if (!result || result.status !== "fulfilled" || !result.value) return [];
		return result.value.items || [];
	}

	function loadCrewPunch() {
		var tbody = crewEls().tbody;
		if (!tbody || !projectId()) return;
		Promise.allSettled([fetchJson(crewPunchItemsPath()), fetchJson(crewIssuePath())])
			.then(function (results) {
				var field = settledItems(results[0]).map(normalizeFieldPunch);
				var issues = settledItems(results[1]).map(normalizeCrewIssue);
				var items = field.concat(issues);
				crewPunchCache = {};
				items.forEach(function (it) {
					crewPunchCache[crewCacheKey(it.source, it.id)] = it;
				});
				setCrewCount(field.length || items.length);
				if (!items.length) {
					var failed = results[0].status !== "fulfilled" && results[1].status !== "fulfilled";
					tbody.innerHTML =
						'<tr><td colspan="5" class="text-muted">' +
						(failed ? "Could not load." : "None yet.") +
						"</td></tr>";
					return;
				}
				tbody.innerHTML = items
					.map(function (it) {
						var closed = ["closed", "resolved", "done"].indexOf(String(it.status || "").toLowerCase()) >= 0;
						var extras = closed
							? []
							: [
									{
										label: "Resolve",
										className: "usis-punch-crew-resolve",
										data: { id: it.id, source: it.source },
									},
								];
						var menu =
							window.USISUi && window.USISUi.rowMenu
								? window.USISUi.rowMenu({
										id: it.id,
										createTarget: "#usis-punch-crew-add",
										deleteClass: "usis-punch-crew-del",
										deleteData: { id: it.id, source: it.source },
										extras: extras,
									})
								: extras.length
									? '<button type="button" class="btn btn-link btn-sm p-0 usis-punch-crew-resolve" data-id="' +
										esc(it.id) +
										'" data-source="' +
										esc(it.source) +
										'">Resolve</button>'
									: "";
						return (
							"<tr><td><a href=\"#\" class=\"usis-punch-crew-open\" data-id=\"" +
							esc(it.id) +
							'" data-source="' +
							esc(it.source) +
							'">' +
							esc(it.title || "Untitled") +
							"</a></td><td>" +
							esc(it.room || "") +
							"</td><td>" +
							esc(prettyPunch(it.status)) +
							"</td><td>" +
							esc(it.description || "") +
							"</td><td>" +
							menu +
							"</td></tr>"
						);
					})
					.join("");
			});
	}

	function punchDetailRow(label, value) {
		if (value == null || String(value).trim() === "") return "";
		return (
			'<div class="row g-2 mb-2"><div class="col-sm-3 text-muted small">' +
			esc(label) +
			'</div><div class="col-sm-9">' +
			esc(String(value)) +
			"</div></div>"
		);
	}

	function renderCrewDetail(it) {
		var heading = document.getElementById("usis-crew-punch-detail-heading");
		var body = document.getElementById("usis-crew-punch-detail-body");
		if (heading) heading.textContent = it.title || "Crew punch item";
		if (!body) return;
		var photos = it.photos || [];
		var photoHtml = photos.length
			? photos
					.map(function (ph) {
						var src = photoSrc(ph);
						if (!src) return "";
						return (
							'<img src="" data-file-url="' +
							esc(src) +
							'" alt="" class="img-fluid rounded border mb-3 usis-punch-photo" style="max-height:28rem;width:100%;object-fit:contain;background:#f8f9fa">'
						);
					})
					.join("")
			: '<p class="text-muted small mb-3">No photo.</p>';
		var dist = (it.distribution || [])
			.map(function (d) {
				return d.name ? d.name + (d.email ? " <" + d.email + ">" : "") : d.email || "";
			})
			.filter(Boolean)
			.join(", ");
		body.innerHTML =
			photoHtml +
			punchDetailRow("#", it.number) +
			punchDetailRow("Title", it.title) +
			punchDetailRow("Status", prettyPunch(it.status)) +
			punchDetailRow("Type", prettyPunch(it.type)) +
			punchDetailRow("Priority", prettyPunch(it.priority)) +
			punchDetailRow("Location", it.room) +
			punchDetailRow("Trade", prettyPunch(it.trade)) +
			punchDetailRow("Assignee", it.assignee_name) +
			punchDetailRow("Due", it.due_on) +
			punchDetailRow("Description", it.description) +
			punchDetailRow("Schedule impact", prettyPunch(it.schedule_impact)) +
			punchDetailRow("Schedule note", it.schedule_note) +
			punchDetailRow("Cost impact", prettyPunch(it.cost_impact)) +
			punchDetailRow("Cost note", it.cost_note) +
			punchDetailRow("Distribution", dist) +
			punchDetailRow("Last notified", it.last_notified_at) +
			punchDetailRow("Source", prettyPunch(it.source_label)) +
			punchDetailRow("Created", it.created_at) +
			punchDetailRow("Updated", it.updated_at);
		bindPunchPhotos(body);
	}

	function openCrewDetail(id, source) {
		source = source || "punch_item";
		var root = document.getElementById("usis-modal-crew-punch-detail");
		if (!root || !window.bootstrap || !window.bootstrap.Modal) {
			window.alert("Detail window is missing. Reload the page.");
			return;
		}
		var cached = crewPunchCache[crewCacheKey(source, id)];
		if (cached) renderCrewDetail(cached);
		else {
			var body = document.getElementById("usis-crew-punch-detail-body");
			if (body) body.innerHTML = '<p class="text-muted small mb-0">Loading…</p>';
		}
		window.bootstrap.Modal.getOrCreateInstance(root).show();
		var path =
			source === "issue"
				? "/api/v1/issues/" + encodeURIComponent(id)
				: "/api/v1/punch-items/" + encodeURIComponent(id);
		fetchJson(path)
			.then(function (data) {
				var fresh = source === "issue" ? normalizeCrewIssue(data.issue || data) : normalizeFieldPunch(data.item || data);
				crewPunchCache[crewCacheKey(source, id)] = fresh;
				renderCrewDetail(fresh);
			})
			.catch(function () {
				if (!cached) {
					var body = document.getElementById("usis-crew-punch-detail-body");
					if (body) body.innerHTML = '<p class="text-muted small mb-0">Could not load this item.</p>';
				}
			});
	}

	function openCrewModal() {
		var els = crewEls();
		if (!els.root || !window.bootstrap || !window.bootstrap.Modal) {
			window.alert("Create dialog is missing. Reload the page.");
			return;
		}
		setCrewErr("");
		if (els.title) els.title.value = "";
		if (els.room) els.room.value = "";
		if (els.notes) els.notes.value = "";
		if (els.photo) els.photo.value = "";
		window.bootstrap.Modal.getOrCreateInstance(els.root).show();
		if (els.title) els.title.focus();
	}

	function uploadCrewPhoto(file) {
		var fd = new FormData();
		fd.append("file", file);
		fd.append("album", "Crew punch");
		var headers = Object.assign({}, window.USIS_API.actorHeaders());
		return fetch(window.USIS_API.apiBase() + pidPath("/photos"), {
			method: "POST",
			credentials: "include",
			headers: headers,
			body: fd,
		}).then(function (res) {
			return res.json().then(function (data) {
				if (!res.ok) throw new Error((data && (data.error || data.message)) || "Photo upload failed.");
				return (data.item && data.item.id) || (data.id || "");
			});
		});
	}

	function submitCrewCreate(ev) {
		if (ev) ev.preventDefault();
		var els = crewEls();
		var title = ((els.title && els.title.value) || "").trim();
		var room = ((els.room && els.room.value) || "").trim();
		if (!title) {
			setCrewErr("Issue is required.");
			if (els.title) els.title.focus();
			return;
		}
		if (!room) {
			setCrewErr("Room is required.");
			if (els.room) els.room.focus();
			return;
		}
		var notes = ((els.notes && els.notes.value) || "").trim();
		var file = els.photo && els.photo.files && els.photo.files[0];
		if (els.submit) els.submit.disabled = true;
		setCrewErr("");
		var photoStep = file ? uploadCrewPhoto(file) : Promise.resolve("");
		photoStep
			.then(function (photoId) {
				var body = {
					local_id: newLocalId(),
					list: "ours",
					title: title,
					location_text: room,
					room: room,
					notify_on_save: false,
				};
				if (notes) body.description = notes;
				return fetchJson(pidPath("/punch-items"), { method: "POST", body: body }).then(function (created) {
					var item = (created && created.item) || created || {};
					if (!photoId || !item.id) return created;
					return fetchJson("/api/v1/punch-items/" + encodeURIComponent(item.id) + "/photos", {
						method: "POST",
						body: { photo_id: photoId },
					});
				});
			})
			.then(function () {
				if (els.root && window.bootstrap && window.bootstrap.Modal) {
					window.bootstrap.Modal.getOrCreateInstance(els.root).hide();
				}
				loadCrewPunch();
			})
			.catch(function (err) {
				var msg = (err && (err.body || err.message)) || "Could not create.";
				if (typeof msg === "object") msg = (msg.error || msg.message) || JSON.stringify(msg);
				setCrewErr(msg);
			})
			.finally(function () {
				if (els.submit) els.submit.disabled = false;
			});
	}

	function resolveCrewItem(id, source) {
		if (!id) return;
		var req =
			source === "issue"
				? fetchJson("/api/v1/issues/" + encodeURIComponent(id) + "/status", {
						method: "PATCH",
						body: { status: "Resolved" },
					})
				: fetchJson("/api/v1/punch-items/" + encodeURIComponent(id) + "/status", {
						method: "POST",
						body: { status: "closed" },
					});
		req.then(loadCrewPunch).catch(function () {
			window.alert("Could not resolve.");
		});
	}

	function deleteCrewItem(id, source) {
		if (!id || !window.confirm("Delete this crew punch item?")) return;
		var req =
			source === "issue"
				? fetchJson("/api/v1/issues/" + encodeURIComponent(id), { method: "DELETE" })
				: fetchJson("/api/v1/punch-items/" + encodeURIComponent(id), { method: "DELETE" });
		req.then(loadCrewPunch).catch(function (err) {
			window.alert((err && err.message) || "Could not delete item.");
		});
	}

	function loadOpenItems() {
		var tbody = document.getElementById("usis-openitems-tbody");
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/open-items"))
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					tbody.innerHTML = '<tr><td colspan="3" class="text-muted">Nothing open.</td></tr>';
					return;
				}
				tbody.innerHTML = items
					.map(function (it) {
						return "<tr><td>" + esc(it.kind) + "</td><td>" + esc(it.title) + "</td><td>" + esc(it.status) + "</td></tr>";
					})
					.join("");
			})
			.catch(function () {
				tbody.innerHTML = '<tr><td colspan="3" class="text-muted">Could not load open items.</td></tr>';
			});
		var inbox = document.getElementById("usis-wfinbox-tbody");
		if (!inbox) return;
		fetchJson("/api/v1/workflow-inbox")
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					inbox.innerHTML = '<tr><td colspan="3" class="text-muted">No pending approvals.</td></tr>';
					return;
				}
				inbox.innerHTML = items
					.map(function (it) {
						return (
							"<tr><td>" +
							esc(it.subject_type || "") +
							"</td><td>" +
							esc(it.status || "") +
							"</td><td>" +
							esc(it.created_at || "") +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				inbox.innerHTML = '<tr><td colspan="3" class="text-muted">Could not load inbox.</td></tr>';
			});
	}

	function onReady() {
		if (!projectId()) return;
		KINDS.forEach(loadKind);
		loadPhotos();
		loadOpenItems();
		loadCrewPunch();
		var punchAdd = document.getElementById("usis-punch-gc-add");
		if (punchAdd) punchAdd.setAttribute("href", punchHref());
		document.querySelectorAll("[data-usis-wave2-add]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var kind = btn.getAttribute("data-usis-wave2-add");
				var cfg = KINDS.filter(function (k) {
					return k.kind === kind && !k.customCreate;
				})[0];
				if (cfg) addKind(cfg);
			});
		});
		var form = document.getElementById("usis-wave2-create-form");
		if (form) form.addEventListener("submit", submitCreate);
		var crewAdd = document.getElementById("usis-punch-crew-add");
		if (crewAdd) crewAdd.addEventListener("click", openCrewModal);
		var crewForm = document.getElementById("usis-crew-punch-form");
		if (crewForm) crewForm.addEventListener("submit", submitCrewCreate);
		var crewTab = document.getElementById("usis-punch-subtab-crew");
		if (crewTab) crewTab.addEventListener("shown.bs.tab", loadCrewPunch);
		var modalRoot = document.getElementById("usis-modal-wave2-create");
		if (modalRoot) {
			modalRoot.addEventListener("shown.bs.modal", function () {
				var input = document.getElementById("usis-wave2-title");
				if (input) input.focus();
			});
		}
		document.body.addEventListener("click", function (e) {
			var openLink = e.target.closest(".usis-punch-crew-open");
			if (openLink) {
				e.preventDefault();
				openCrewDetail(openLink.getAttribute("data-id"), openLink.getAttribute("data-source"));
				return;
			}
			var btn = e.target.closest(".usis-w2-del");
			if (btn) delKind(btn.getAttribute("data-kind"), btn.getAttribute("data-id"));
			var resolveBtn = e.target.closest(".usis-punch-crew-resolve");
			if (resolveBtn) resolveCrewItem(resolveBtn.getAttribute("data-id"), resolveBtn.getAttribute("data-source"));
			var crewDel = e.target.closest(".usis-punch-crew-del");
			if (crewDel) {
				deleteCrewItem(crewDel.getAttribute("data-id"), crewDel.getAttribute("data-source"));
			}
		});
		var up = document.getElementById("usis-photo-upload");
		if (up) up.addEventListener("click", uploadPhoto);
		var gallery = document.getElementById("usis-photo-gallery");
		if (gallery) {
			gallery.addEventListener("click", function (e) {
				var btn = e.target.closest(".usis-photo-del");
				if (!btn) return;
				var pid = btn.getAttribute("data-id");
				if (!pid || !window.confirm("Delete this photo?")) return;
				fetchJson("/api/v1/photos/" + encodeURIComponent(pid), { method: "DELETE" })
					.then(loadPhotos)
					.catch(function (err) {
						window.alert((err && err.message) || "Could not delete photo.");
					});
			});
		}
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
})();
