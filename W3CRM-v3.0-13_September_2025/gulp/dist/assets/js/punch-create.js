/**
 * Procore-style New Punch List Item page.
 */
(function () {
	"use strict";

	var state = {
		projectId: null,
		users: [],
		manager: "",
		approver: "",
		distribution: [],
		queuedFiles: [],
		busy: false,
		defaultApprover: "",
	};

	function $(id) {
		return document.getElementById(id);
	}

	function api() {
		return window.USIS_API;
	}

	function fetchJson(path, opts) {
		return api().fetchJson(path, opts || {});
	}

	function queryParam(name) {
		try {
			return new URLSearchParams(window.location.search).get(name) || "";
		} catch (e) {
			return "";
		}
	}

	function projectId() {
		return (
			queryParam("project_id") ||
			queryParam("projectId") ||
			queryParam("id") ||
			(window.USISProjectContext && window.USISProjectContext.getProjectId && window.USISProjectContext.getProjectId()) ||
			""
		).trim();
	}

	function projectDetailHref(pid) {
		var id = pid || state.projectId;
		if (!id) return "construction/project-detail.html";
		return "construction/project-detail.html?id=" + encodeURIComponent(id) + "&tab=punch";
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function setErr(msg) {
		var el = $("usis-punch-error");
		if (!el) return;
		if (msg) {
			el.textContent = String(msg);
			el.classList.remove("d-none");
			el.scrollIntoView({ behavior: "smooth", block: "center" });
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function errMessage(err) {
		if (!err) return "Could not save.";
		var body = err.body;
		if (typeof body === "string") {
			try {
				body = JSON.parse(body);
			} catch (e) {}
		}
		if (body && typeof body === "object") return body.error || body.message || err.message || "Could not save.";
		return err.message || "Could not save.";
	}

	function personLabel(u) {
		if (!u) return "";
		return (u.name || [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email || "").trim();
	}

	function userById(id) {
		return state.users.find(function (x) {
			return x.id === id;
		});
	}

	function chipHtml(id, kind) {
		return (
			'<span class="usis-punch-chip">' +
			esc(personLabel(userById(id)) || id) +
			' <button type="button" class="usis-punch-chip-x" data-people-kind="' +
			kind +
			'" data-id="' +
			esc(id) +
			'" aria-label="Remove">&times;</button></span>'
		);
	}

	function fillSelect(sel, excludeIds, emptyLabel) {
		if (!sel) return;
		excludeIds = excludeIds || [];
		sel.innerHTML = "";
		var blank = document.createElement("option");
		blank.value = "";
		blank.textContent = emptyLabel || "Select a Person";
		sel.appendChild(blank);
		state.users.forEach(function (u) {
			if (excludeIds.indexOf(u.id) !== -1) return;
			var opt = document.createElement("option");
			opt.value = u.id;
			opt.textContent = personLabel(u);
			sel.appendChild(opt);
		});
		sel.value = "";
	}

	function renderManager() {
		var chips = $("usis-punch-manager-chips");
		var sel = $("usis-punch-manager");
		if (chips) chips.innerHTML = state.manager ? chipHtml(state.manager, "manager") : "";
		if (sel) {
			sel.classList.toggle("d-none", !!state.manager);
			if (!state.manager) fillSelect(sel, [], "Select a Person");
		}
	}

	function renderApprover() {
		var chips = $("usis-punch-approver-chips");
		var sel = $("usis-punch-approver");
		if (chips) chips.innerHTML = state.approver ? chipHtml(state.approver, "approver") : "";
		if (sel) {
			sel.classList.toggle("d-none", !!state.approver);
			if (!state.approver) fillSelect(sel, [], "Select a Person");
		}
	}

	function renderDistribution() {
		var chips = $("usis-punch-dist-chips");
		var sel = $("usis-punch-dist");
		if (chips) {
			chips.innerHTML = state.distribution.map(function (id) {
				return chipHtml(id, "dist");
			}).join("");
		}
		fillSelect(sel, state.distribution, "Select a Person");
	}

	function renderPeople() {
		renderManager();
		renderApprover();
		renderDistribution();
	}

	function setPerson(kind, id) {
		if (kind === "manager") state.manager = id || "";
		else if (kind === "approver") state.approver = id || "";
		else if (kind === "dist" && id && state.distribution.indexOf(id) === -1) state.distribution.push(id);
		renderPeople();
	}

	function removePerson(kind, id) {
		if (kind === "manager") state.manager = "";
		else if (kind === "approver") state.approver = "";
		else if (kind === "dist") {
			state.distribution = state.distribution.filter(function (d) {
				return d !== id;
			});
		}
		renderPeople();
	}

	function descriptionHtml() {
		var el = $("usis-punch-description");
		if (!el) return "";
		var html = (el.innerHTML || "").replace(/&nbsp;/g, " ").trim();
		if (!html || html === "<br>" || html === "<div><br></div>") return "";
		return html;
	}

	function resetDescription() {
		var el = $("usis-punch-description");
		if (el) el.innerHTML = "";
	}

	function renderFiles() {
		var list = $("usis-punch-attach-list");
		if (!list) return;
		if (!state.queuedFiles.length) {
			list.innerHTML = "";
			return;
		}
		list.innerHTML = state.queuedFiles
			.map(function (f, i) {
				return (
					'<div class="usis-punch-attach-file"><span>' +
					esc(f.name) +
					'</span><button type="button" class="btn btn-link btn-sm p-0" data-file-i="' +
					i +
					'">Remove</button></div>'
				);
			})
			.join("");
	}

	function queueFiles(fileList) {
		if (!fileList || !fileList.length) return;
		Array.prototype.forEach.call(fileList, function (f) {
			if (f) state.queuedFiles.push(f);
		});
		renderFiles();
	}

	function val(id) {
		var el = $(id);
		return el ? String(el.value || "").trim() : "";
	}

	function collectPayload() {
		var title = val("usis-punch-title");
		var number = val("usis-punch-number");
		if (!title) return { error: "Title is required.", focus: "usis-punch-title" };
		if (!number) return { error: "Number is required.", focus: "usis-punch-number" };
		if (!state.manager) return { error: "Punch Item Manager is required.", focus: "usis-punch-manager" };
		if (!state.approver) return { error: "Final Approver is required.", focus: "usis-punch-approver" };
		var body = {
			title: title,
			number: number,
			manager_user_id: state.manager,
			final_approver_user_id: state.approver,
			distribution_user_ids: state.distribution.slice(),
		};
		var optional = {
			punch_type: val("usis-punch-type"),
			location: val("usis-punch-location"),
			priority: val("usis-punch-priority"),
			trade: val("usis-punch-trade"),
			reference: val("usis-punch-reference"),
			schedule_impact: val("usis-punch-schedule"),
			cost_impact: val("usis-punch-cost"),
			description: descriptionHtml(),
		};
		Object.keys(optional).forEach(function (k) {
			if (optional[k]) body[k] = optional[k];
		});
		return { body: body };
	}

	function uploadFiles(itemId) {
		if (!state.queuedFiles.length) return Promise.resolve([]);
		var headers = Object.assign({}, api().actorHeaders());
		var album = "Punch " + (val("usis-punch-number") || itemId);
		return state.queuedFiles.reduce(function (chain, file) {
			return chain.then(function (acc) {
				var fd = new FormData();
				fd.append("file", file, file.name || "attachment");
				fd.append("album", album);
				fd.append("caption", file.name || "");
				return fetch(api().apiBase() + "/api/v1/projects/" + encodeURIComponent(state.projectId) + "/photos", {
					method: "POST",
					credentials: "include",
					headers: headers,
					body: fd,
				}).then(function (res) {
					return res.json().then(function (data) {
						if (!res.ok) throw new Error((data && (data.error || data.message)) || "Attachment upload failed.");
						var photo = data.item || data;
						acc.push({
							photo_id: photo.id,
							name: file.name || photo.caption || "file",
							mime: file.type || "",
						});
						return acc;
					});
				});
			});
		}, Promise.resolve([]));
	}

	function setBusy(on) {
		state.busy = !!on;
		["usis-punch-save", "usis-punch-save-new"].forEach(function (id) {
			var el = $(id);
			if (el) el.disabled = state.busy;
		});
	}

	function save(createNew) {
		if (state.busy) return;
		if (!state.projectId) {
			setErr("Open this form from a project Punchlist.");
			return;
		}
		var collected = collectPayload();
		if (collected.error) {
			setErr(collected.error);
			var focus = $(collected.focus);
			if (focus) focus.focus();
			return;
		}
		setErr("");
		setBusy(true);
		fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/wave2/punchlist", {
			method: "POST",
			body: collected.body,
		})
			.then(function (data) {
				var item = (data && data.item) || {};
				return uploadFiles(item.id).then(function (attachments) {
					if (!attachments.length) return item;
					return fetchJson(
						"/api/v1/projects/" +
							encodeURIComponent(state.projectId) +
							"/wave2/punchlist/" +
							encodeURIComponent(item.id),
						{ method: "PATCH", body: { attachments: attachments } }
					).then(function () {
						return item;
					});
				});
			})
			.then(function (item) {
				if (createNew) {
					var savedNumber = item && item.number;
					resetForm(true);
					var num = $("usis-punch-number");
					if (num && savedNumber) {
						var n = parseInt(String(savedNumber).replace(/\D+/g, ""), 10);
						if (isFinite(n) && n > 0) {
							num.value = String(n + 1);
							num.setAttribute("data-next", String(n + 1));
						}
					}
					setBusy(false);
					var title = $("usis-punch-title");
					if (title) title.focus();
					return;
				}
				window.location.href = projectDetailHref();
			})
			.catch(function (err) {
				setBusy(false);
				setErr(errMessage(err));
			});
	}

	function resetForm(bumpNumber) {
		var form = $("usis-punch-form");
		if (form) form.reset();
		state.manager = "";
		state.approver = state.defaultApprover || "";
		state.distribution = [];
		state.queuedFiles = [];
		renderFiles();
		resetDescription();
		renderPeople();
		if (bumpNumber) {
			var num = $("usis-punch-number");
			if (num) {
				var n = parseInt(num.getAttribute("data-next") || num.value || "0", 10);
				if (!isFinite(n) || n < 1) n = 1;
				else n += 1;
				num.value = String(n);
				num.setAttribute("data-next", String(n));
			}
		}
	}

	function loadLookups() {
		var locSel = $("usis-punch-location");
		if (!locSel || !state.projectId) return Promise.resolve();
		return fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/rfi-lookups/locations")
			.then(function (data) {
				var items = data.items || [];
				items.forEach(function (row) {
					var opt = document.createElement("option");
					opt.value = row.name || row.path || "";
					opt.textContent = row.name || row.path || "";
					if (opt.value) locSel.appendChild(opt);
				});
			})
			.catch(function () {});
	}

	function loadUsers() {
		return fetchJson("/api/v1/rfi-users", { params: { limit: 200 } }).then(function (data) {
			state.users = data.items || [];
			renderPeople();
		});
	}

	function loadMeAndNumber() {
		var me = fetchJson("/api/v1/me")
			.then(function (data) {
				var item = (data && data.item) || {};
				if (item.id) {
					state.defaultApprover = item.id;
					if (!state.approver) {
						state.approver = item.id;
						renderApprover();
					}
				}
			})
			.catch(function () {});
		var nums = fetchJson("/api/v1/projects/" + encodeURIComponent(state.projectId) + "/wave2/punchlist")
			.then(function (data) {
				var next = data.next_number || "1";
				var num = $("usis-punch-number");
				if (num && !num.value) {
					num.value = String(next);
					num.setAttribute("data-next", String(next));
				}
			})
			.catch(function () {
				var num = $("usis-punch-number");
				if (num && !num.value) num.value = "1";
			});
		return Promise.all([me, nums]);
	}

	function focusRte() {
		var rte = $("usis-punch-description");
		if (rte) rte.focus();
	}

	function wireEditor() {
		document.querySelectorAll(".usis-punch-rte-toolbar [data-cmd]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var cmd = btn.getAttribute("data-cmd");
				if (!cmd) return;
				document.execCommand(cmd, false, null);
				focusRte();
			});
		});
		var link = $("usis-punch-link");
		if (link) {
			link.addEventListener("click", function () {
				var url = window.prompt("Link URL");
				if (url) document.execCommand("createLink", false, url);
				focusRte();
			});
		}
		var size = $("usis-punch-font-size");
		if (size) {
			size.addEventListener("change", function () {
				document.execCommand("fontSize", false, size.value);
				focusRte();
			});
		}
		var fore = $("usis-punch-fore-color");
		if (fore) {
			fore.addEventListener("input", function () {
				document.execCommand("foreColor", false, fore.value);
				focusRte();
			});
		}
		var hi = $("usis-punch-hilite-color");
		if (hi) {
			hi.addEventListener("input", function () {
				document.execCommand("hiliteColor", false, hi.value);
				focusRte();
			});
		}
		var imgBtn = $("usis-punch-insert-image");
		var imgFile = $("usis-punch-rte-image");
		if (imgBtn && imgFile) {
			imgBtn.addEventListener("click", function () {
				imgFile.click();
			});
			imgFile.addEventListener("change", function () {
				var file = imgFile.files && imgFile.files[0];
				imgFile.value = "";
				if (!file) return;
				var reader = new FileReader();
				reader.onload = function () {
					document.execCommand("insertImage", false, reader.result);
					focusRte();
				};
				reader.readAsDataURL(file);
			});
		}
		var tableBtn = $("usis-punch-insert-table");
		if (tableBtn) {
			tableBtn.addEventListener("click", function () {
				document.execCommand(
					"insertHTML",
					false,
					'<table style="width:100%;border-collapse:collapse"><tr><td style="border:1px solid #ced4da;padding:4px;">&nbsp;</td><td style="border:1px solid #ced4da;padding:4px;">&nbsp;</td></tr><tr><td style="border:1px solid #ced4da;padding:4px;">&nbsp;</td><td style="border:1px solid #ced4da;padding:4px;">&nbsp;</td></tr></table>'
				);
				focusRte();
			});
		}
	}

	function wireAttachments() {
		var drop = $("usis-punch-attach-drop");
		var input = $("usis-punch-attach-file");
		var btn = $("usis-punch-attach-btn");
		function openPicker(ev) {
			if (ev) ev.preventDefault();
			if (input) input.click();
		}
		if (btn) btn.addEventListener("click", openPicker);
		if (drop) {
			drop.addEventListener("click", function (ev) {
				if (ev.target && ev.target.closest("#usis-punch-attach-btn")) return;
				openPicker(ev);
			});
			drop.addEventListener("keydown", function (ev) {
				if (ev.key === "Enter" || ev.key === " ") openPicker(ev);
			});
			drop.addEventListener("dragover", function (ev) {
				ev.preventDefault();
				drop.classList.add("is-drag");
			});
			drop.addEventListener("dragleave", function () {
				drop.classList.remove("is-drag");
			});
			drop.addEventListener("drop", function (ev) {
				ev.preventDefault();
				drop.classList.remove("is-drag");
				queueFiles(ev.dataTransfer && ev.dataTransfer.files);
			});
		}
		if (input) {
			input.addEventListener("change", function () {
				queueFiles(input.files);
				input.value = "";
			});
		}
		var list = $("usis-punch-attach-list");
		if (list) {
			list.addEventListener("click", function (ev) {
				var rm = ev.target.closest("[data-file-i]");
				if (!rm) return;
				var i = parseInt(rm.getAttribute("data-file-i"), 10);
				if (!isFinite(i)) return;
				state.queuedFiles.splice(i, 1);
				renderFiles();
			});
		}
	}

	function wirePeople() {
		["usis-punch-manager", "usis-punch-approver", "usis-punch-dist"].forEach(function (id) {
			var sel = $(id);
			if (!sel) return;
			sel.addEventListener("change", function () {
				var kind = id === "usis-punch-manager" ? "manager" : id === "usis-punch-approver" ? "approver" : "dist";
				setPerson(kind, sel.value);
			});
		});
		document.addEventListener("click", function (ev) {
			var x = ev.target.closest("[data-people-kind]");
			if (!x || !x.closest("#usis-punch-form")) return;
			removePerson(x.getAttribute("data-people-kind"), x.getAttribute("data-id"));
		});
	}

	function init() {
		state.projectId = projectId();
		var cancel = $("usis-punch-cancel");
		var crumb = $("usis-punch-crumb-list");
		if (cancel) cancel.setAttribute("href", projectDetailHref());
		if (crumb) crumb.setAttribute("href", projectDetailHref());
		if (!state.projectId) {
			setErr("Open this form from a project Punchlist so a project id is in the URL.");
			return;
		}
		if (window.USISProjectContext && typeof window.USISProjectContext.setProjectId === "function") {
			window.USISProjectContext.setProjectId(state.projectId);
		}
		wireEditor();
		wireAttachments();
		wirePeople();
		var form = $("usis-punch-form");
		if (form) {
			form.addEventListener("submit", function (ev) {
				ev.preventDefault();
				save(true);
			});
		}
		var saveBtn = $("usis-punch-save");
		if (saveBtn) {
			saveBtn.addEventListener("click", function () {
				save(false);
			});
		}
		loadUsers()
			.then(loadLookups)
			.then(loadMeAndNumber)
			.catch(function (err) {
				setErr(errMessage(err));
			});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
	else init();
})();
