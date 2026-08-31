/**
 * Wave 2 Sage CM: transmittals, punch, photos, WO, anticipated, PO CO,
 * sub invoices, meetings, incidents, QC, open items.
 */
(function () {
	"use strict";

	var KINDS = [
		{ kind: "punchlist", titleKey: "title", extra: "location" },
		{ kind: "work-orders", titleKey: "subject", extra: "amount" },
		{ kind: "meetings", titleKey: "subject", extra: "meeting_date" },
		{ kind: "safety-incidents", titleKey: "subject", extra: "severity" },
		{ kind: "transmittals", titleKey: "subject", extra: "due_date" },
		{ kind: "anticipated-costs", titleKey: "subject", extra: "amount" },
		{ kind: "po-change-orders", titleKey: "subject", extra: "amount", needCommitment: true },
		{ kind: "sub-invoices", titleKey: "subject", extra: "amount" },
		{ kind: "qc-checklists", titleKey: "subject", extra: "review_date" },
	];

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

	function addKind(cfg) {
		var title = window.prompt((cfg.titleKey === "title" ? "Title" : "Subject"));
		if (!title) return;
		var body = {};
		body[cfg.titleKey] = title.trim();
		if (cfg.needCommitment) {
			var cid = window.prompt("Purchase order commitment UUID");
			if (!cid) return;
			body.commitment_id = cid.trim();
		}
		if (cfg.extra === "amount") {
			var amt = window.prompt("Amount (optional)");
			if (amt) body.amount = amt;
		}
		if (cfg.extra === "location") {
			var loc = window.prompt("Location (optional)");
			if (loc) body.location = loc;
		}
		if (cfg.extra === "severity") {
			var sev = window.prompt("Severity (optional)");
			if (sev) body.severity = sev;
		}
		fetchJson(pidPath("/wave2/" + cfg.kind), { method: "POST", body: body })
			.then(function () {
				loadKind(cfg);
			})
			.catch(function (err) {
				window.alert((err && err.body) || "Could not create.");
			});
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
		document.querySelectorAll("[data-usis-wave2-add]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var kind = btn.getAttribute("data-usis-wave2-add");
				var cfg = KINDS.filter(function (k) {
					return k.kind === kind;
				})[0];
				if (cfg) addKind(cfg);
			});
		});
		document.body.addEventListener("click", function (e) {
			var btn = e.target.closest(".usis-w2-del");
			if (btn) delKind(btn.getAttribute("data-kind"), btn.getAttribute("data-id"));
		});
		var up = document.getElementById("usis-photo-upload");
		if (up) up.addEventListener("click", uploadPhoto);
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
})();
