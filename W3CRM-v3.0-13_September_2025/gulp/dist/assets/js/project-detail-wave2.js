/**
 * Wave 2 Sage CM: transmittals, punch, photos, WO, anticipated, PO CO,
 * sub invoices, meetings, incidents, QC, open items.
 */
(function () {
	"use strict";

	var KINDS = [
		{ kind: "punchlist", titleKey: "title", extra: "location", heading: "New GC punch item", submit: "Add item" },
		{ kind: "work-orders", titleKey: "subject", extra: "amount", heading: "New work order", submit: "Add work order" },
		{ kind: "meetings", titleKey: "subject", extra: "meeting_date", heading: "New meeting", submit: "Add meeting" },
		{ kind: "safety-incidents", titleKey: "subject", extra: "severity", heading: "New safety incident", submit: "Add incident" },
		{ kind: "transmittals", titleKey: "subject", extra: "due_date", heading: "New transmittal", submit: "Add transmittal" },
		{ kind: "anticipated-costs", titleKey: "subject", extra: "amount", heading: "New anticipated cost", submit: "Add cost" },
		{ kind: "po-change-orders", titleKey: "subject", extra: "amount", needCommitment: true, heading: "New PO change order", submit: "Add PO CO" },
		{ kind: "sub-invoices", titleKey: "subject", extra: "amount", heading: "New sub invoice", submit: "Add sub invoice" },
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

	function loadKind(cfg) {
		var tbody = document.getElementById("usis-w2-" + cfg.kind);
		if (!tbody || !projectId()) return;
		fetchJson(pidPath("/wave2/" + cfg.kind))
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					tbody.innerHTML = '<tr><td colspan="5" class="text-muted">None yet.</td></tr>';
					return;
				}
				tbody.innerHTML = items
					.map(function (it) {
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
							'</td><td><button type="button" class="btn btn-link btn-sm p-0 usis-w2-del" data-kind="' +
							esc(cfg.kind) +
							'" data-id="' +
							esc(it.id) +
							'">Delete</button></td></tr>'
						);
					})
					.join("");
			})
			.catch(function () {
				tbody.innerHTML = '<tr><td colspan="5" class="text-muted">Could not load.</td></tr>';
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
							'" class="card-img-top" alt="" style="height:8rem;object-fit:cover"><div class="card-body p-2 small">' +
							esc(ph.caption || ph.album || "Photo") +
							"</div></div></div>"
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

	function loadCrewPunch() {
		var tbody = crewEls().tbody;
		if (!tbody || !projectId()) return;
		fetchJson(crewIssuePath())
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					tbody.innerHTML = '<tr><td colspan="5" class="text-muted">None yet.</td></tr>';
					return;
				}
				tbody.innerHTML = items
					.map(function (it) {
						var closed = it.status === "Resolved" || it.status === "Closed";
						var action = closed
							? ""
							: '<button type="button" class="btn btn-link btn-sm p-0 usis-punch-crew-resolve" data-id="' +
							  esc(it.id) +
							  '">Resolve</button>';
						return (
							"<tr><td>" +
							esc(it.title || "") +
							"</td><td>" +
							esc(it.room || it.sheet_number || "") +
							"</td><td>" +
							esc(it.status || "") +
							"</td><td>" +
							esc(it.description || "") +
							"</td><td>" +
							action +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				tbody.innerHTML = '<tr><td colspan="5" class="text-muted">Could not load.</td></tr>';
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
					title: title,
					room: room,
					source_type: "crew_punch",
				};
				if (notes) body.description = notes;
				if (photoId) body.photo_id = photoId;
				return fetchJson(pidPath("/issues"), { method: "POST", body: body });
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

	function resolveCrewItem(id) {
		if (!id) return;
		fetchJson("/api/v1/issues/" + encodeURIComponent(id) + "/status", {
			method: "PATCH",
			body: { status: "Resolved" },
		})
			.then(loadCrewPunch)
			.catch(function () {
				window.alert("Could not resolve.");
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
		document.querySelectorAll("[data-usis-wave2-add]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var kind = btn.getAttribute("data-usis-wave2-add");
				var cfg = KINDS.filter(function (k) {
					return k.kind === kind;
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
			var btn = e.target.closest(".usis-w2-del");
			if (btn) delKind(btn.getAttribute("data-kind"), btn.getAttribute("data-id"));
			var resolveBtn = e.target.closest(".usis-punch-crew-resolve");
			if (resolveBtn) resolveCrewItem(resolveBtn.getAttribute("data-id"));
		});
		var up = document.getElementById("usis-photo-upload");
		if (up) up.addEventListener("click", uploadPhoto);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
})();
