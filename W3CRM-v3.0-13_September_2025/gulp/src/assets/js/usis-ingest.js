/**
 * Mass ingest: queue a folder of files and POST them one-by-one to /api/v1/ingest/files.
 */
(function () {
	"use strict";

	var MAX_BYTES = 52428800;
	var RETRY_STATUSES = { 429: 1, 502: 1, 503: 1, 504: 1 };
	var DISPLAY_CAP = 400;
	var SHEET_RE = /^(?:[A-Z]{1,3}\d{0,2}-)?[A-Z]{1,3}[-\s.]?\d{1,4}(?:[.\-]\d{1,4}){0,3}(?:-[A-Z0-9]{1,3})?[A-Z]?$/i;
	var DRAW_FOLDERS = {
		drawings: 1,
		drawing: 1,
		sheets: 1,
		sheet: 1,
		plans: 1,
		plan: 1,
		architectural: 1,
		architecture: 1,
		arch: 1,
		structural: 1,
		struct: 1,
		mechanical: 1,
		mech: 1,
		electrical: 1,
		elec: 1,
		plumbing: 1,
		plumb: 1,
		civil: 1,
		landscape: 1,
		general: 1,
		interiors: 1,
		telecom: 1,
	};
	var PHOTO_EXT = { ".jpg": 1, ".jpeg": 1, ".png": 1, ".gif": 1, ".webp": 1, ".heic": 1, ".tif": 1, ".tiff": 1, ".bmp": 1 };

	var state = {
		project: null,
		items: [],
		running: false,
		paused: false,
		inFlight: 0,
		searchTimer: null,
		batchId: "",
		queueFilter: "all",
		trackerItems: [],
		trackerTimer: null,
	};

	function el(id) {
		return document.getElementById(id);
	}

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function api() {
		return window.USIS_API || {};
	}

	function notify(kind, msg) {
		if (window.USISNotify && window.USISNotify[kind]) {
			window.USISNotify[kind](msg);
			return;
		}
		if (kind === "error") window.alert(msg);
	}

	function maybeSpecPackageToast(item, body) {
		try {
			if (window.localStorage.getItem("usis.specPackage.ingestToast") !== "1") return;
		} catch (e) {
			return;
		}
		var kind = String((item && item.documentType) || (body && body.kind) || "").toLowerCase();
		var name = String((item && item.file && item.file.name) || "").toLowerCase();
		var isSpec =
			kind === "specification" ||
			/\bspec(?:ification)?s?\b/.test(name) ||
			/project.?manual/.test(name) ||
			/addend/.test(name);
		if (!isSpec) return;
		var project = state.project || {};
		var job = project.project_number || project.name || "this job";
		notify("info", "New spec on " + job + ". Analyze for the open estimate?");
	}

	function newBatchId() {
		return window.crypto && crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + "-" + Math.random().toString(16).slice(2);
	}

	function batchId() {
		if (state.batchId) return state.batchId;
		try {
			state.batchId = sessionStorage.getItem("usis-ingest-batch-id") || "";
		} catch (e) {
			state.batchId = "";
		}
		if (!state.batchId) {
			state.batchId = newBatchId();
			try {
				sessionStorage.setItem("usis-ingest-batch-id", state.batchId);
			} catch (e) {}
		}
		return state.batchId;
	}

	function resetBatch() {
		state.batchId = newBatchId();
		try {
			sessionStorage.setItem("usis-ingest-batch-id", state.batchId);
		} catch (e) {}
	}

	function normalizeRel(path) {
		return String(path || "")
			.replace(/\\/g, "/")
			.replace(/^\/+/, "");
	}

	function extOf(name) {
		var i = String(name || "").lastIndexOf(".");
		return i >= 0 ? String(name).slice(i).toLowerCase() : "";
	}

	function guessDocType(rel) {
		var hay = normalizeRel(rel);
		var ext = extOf(hay);
		if (PHOTO_EXT[ext]) return "photo";
		if (/\brfi\b/i.test(hay)) return "rfi";
		if (/submittal/i.test(hay)) return "submittal";
		if (/\bspec(?:ification)?s?\b/i.test(hay) || /addend/i.test(hay)) return "specification";
		if (/contract/i.test(hay)) return "contract";
		if (/change[_\s-]?order|\bco[-_\s]/i.test(hay)) return "change_order";
		if (/invoice/i.test(hay)) return "invoice";
		if (/\bpermit/i.test(hay)) return "permit";
		if (/safety|iipp|js[ah]|toolbox/i.test(hay)) return "safety_doc";
		if (/\breport\b/i.test(hay)) return "report";
		return "other";
	}

	function folderLooksLikeDrawings(rel) {
		var parts = normalizeRel(rel).split("/");
		parts.pop();
		return parts.some(function (seg) {
			var token = String(seg || "")
				.toLowerCase()
				.replace(/^\d{1,2}-/, "");
			return !!DRAW_FOLDERS[token];
		});
	}

	function classify(rel, kindOverride) {
		var kind = (kindOverride || "auto").toLowerCase();
		if (kind === "drawing") return { kind: "drawing", documentType: "drawing" };
		if (kind === "document") return { kind: "document", documentType: guessDocType(rel) };
		var name = normalizeRel(rel).split("/").pop() || "";
		var stem = name.replace(/\.[^.]+$/, "");
		var token = stem.split(/[_\s]/)[0] || "";
		if (extOf(name) === ".pdf" && (SHEET_RE.test(token) || folderLooksLikeDrawings(rel))) {
			return { kind: "drawing", documentType: "drawing" };
		}
		return { kind: "document", documentType: guessDocType(rel) };
	}

	function shouldSkip(rel) {
		var n = normalizeRel(rel);
		if (!n) return true;
		var parts = n.split("/");
		var name = parts[parts.length - 1] || "";
		if (name.charAt(0) === ".") return true;
		if (/^(thumbs\.db|desktop\.ini|\.ds_store)$/i.test(name)) return true;
		return parts.slice(0, -1).some(function (p) {
			return p.charAt(0) === "." || /^(git|__pycache__|__macosx|svn|node_modules)$/i.test(p);
		});
	}

	function counts() {
		var c = { queued: 0, uploading: 0, created: 0, duplicate: 0, error: 0, skipped: 0 };
		state.items.forEach(function (item) {
			c[item.status] = (c[item.status] || 0) + 1;
		});
		c.total = state.items.length;
		c.done = (c.created || 0) + (c.duplicate || 0) + (c.error || 0) + (c.skipped || 0);
		return c;
	}

	function renderStats() {
		var c = counts();
		var stats = el("usis-ingest-stats");
		if (stats) {
			stats.textContent =
				c.total +
				" files · " +
				(c.queued || 0) +
				" queued · " +
				(c.uploading || 0) +
				" uploading · " +
				(c.created || 0) +
				" created · " +
				(c.duplicate || 0) +
				" duplicate · " +
				(c.error || 0) +
				" failed";
		}
		var bar = el("usis-ingest-bar");
		if (bar) {
			var pct = c.total ? Math.round((c.done / c.total) * 100) : 0;
			bar.style.width = pct + "%";
		}
		var start = el("usis-ingest-start");
		var pause = el("usis-ingest-pause");
		var retry = el("usis-ingest-retry");
		if (start) start.disabled = state.running || !(c.queued || 0);
		if (pause) pause.disabled = !state.running;
		if (retry) retry.disabled = state.running || !(c.error || 0);
	}

	function renderTable() {
		var tb = el("usis-ingest-tbody");
		if (!tb) return;
		var rows = state.items;
		if (state.queueFilter === "error") {
			rows = rows.filter(function (item) {
				return item.status === "error";
			});
		}
		var extra = "";
		var cap = state.queueFilter === "error" ? 1000 : DISPLAY_CAP;
		if (rows.length > cap) {
			extra =
				'<tr><td colspan="4" class="text-muted small">Showing first ' +
				cap +
				" of " +
				rows.length +
				" files.</td></tr>";
			rows = rows.slice(0, cap);
		}
		tb.innerHTML = rows
			.map(function (item) {
				return (
					"<tr data-id=\"" +
					esc(item.id) +
					'"><td class="text-break">' +
					esc(item.rel) +
					"</td><td>" +
					esc(item.kind) +
					"</td><td class=\"usis-ingest-status-" +
					esc(item.status) +
					'">' +
					esc(item.status) +
					"</td><td class=\"text-break small\">" +
					esc(item.note || "") +
					"</td></tr>"
				);
			})
			.join("") + extra;
		renderStats();
	}

	function addFiles(fileList, rootHint) {
		var kindSel = (el("usis-ingest-kind") || {}).value || "auto";
		var added = 0;
		Array.prototype.forEach.call(fileList || [], function (file) {
			var rel = normalizeRel(file.webkitRelativePath || file.relativePath || file.name);
			if (rootHint && rel.indexOf("/") === -1) rel = rootHint.replace(/\/$/, "") + "/" + file.name;
			if (shouldSkip(rel)) return;
			var classified = classify(rel, kindSel);
			var item = {
				id: String(state.items.length + 1) + "-" + rel,
				file: file,
				rel: rel,
				kind: classified.kind,
				documentType: classified.documentType,
				status: file.size > MAX_BYTES ? "error" : "queued",
				note: file.size > MAX_BYTES ? "file too large (max 50MB)" : "",
			};
			state.items.push(item);
			if (item.status === "error") reportClientError(item, { message: item.note, status: 413 });
			added += 1;
		});
		renderTable();
		if (added && window.USISNotify && window.USISNotify.info) {
			window.USISNotify.info("Queued " + added + " file" + (added === 1 ? "" : "s"));
		}
	}

	function walkEntry(entry, prefix) {
		return new Promise(function (resolve) {
			if (!entry) {
				resolve([]);
				return;
			}
			if (entry.isFile) {
				entry.file(
					function (file) {
						file.relativePath = (prefix ? prefix + "/" : "") + entry.name;
						resolve([file]);
					},
					function () {
						resolve([]);
					}
				);
				return;
			}
			if (!entry.isDirectory) {
				resolve([]);
				return;
			}
			var reader = entry.createReader();
			var all = [];
			function readBatch() {
				reader.readEntries(
					function (entries) {
						if (!entries.length) {
							resolve(all);
							return;
						}
						Promise.all(
							entries.map(function (child) {
								return walkEntry(child, (prefix ? prefix + "/" : "") + entry.name);
							})
						).then(function (chunks) {
							chunks.forEach(function (chunk) {
								all = all.concat(chunk);
							});
							readBatch();
						});
					},
					function () {
						resolve(all);
					}
				);
			}
			readBatch();
		});
	}

	function uploadOnce(item) {
		var fd = new FormData();
		fd.append("file", item.file, item.file.name);
		fd.append("kind", (el("usis-ingest-kind") || {}).value || "auto");
		var project = state.project || {};
		fd.append(
			"metadata",
			JSON.stringify({
				filename: item.file.name,
				relative_path: item.rel,
				project_id: project.job_id || project.project_id || project.id || "",
				lead_estimate_id: project.lead_estimate_id || "",
				project_number: project.project_number || "",
				folder_name: project.project_number || project.name || "",
				document_type: item.documentType,
				source: "mass_ingest",
				source_id: item.rel,
				batch_id: batchId(),
				split_pages: !!(el("usis-ingest-split") && el("usis-ingest-split").checked),
			})
		);
		var headers = Object.assign({ Accept: "application/json" }, api().actorHeaders ? api().actorHeaders() : {});
		var url = api().buildUrl ? api().buildUrl("/api/v1/ingest/files") : "/api/v1/ingest/files";
		return fetch(url, { method: "POST", body: fd, credentials: "include", headers: headers }).then(function (res) {
			return res.text().then(function (text) {
				var body = {};
				try {
					body = text ? JSON.parse(text) : {};
				} catch (e) {
					body = { error: text || res.statusText };
				}
				if (!res.ok) {
					var err = new Error(body.error || res.status + " " + (text || res.statusText));
					err.status = res.status;
					err.errorId = body.error_id || "";
					throw err;
				}
				return body;
			});
		});
	}

	function uploadWithRetry(item) {
		var attempt = 0;
		function once() {
			attempt += 1;
			return uploadOnce(item).catch(function (err) {
				if (attempt < 5 && RETRY_STATUSES[err.status]) {
					item.note = "retry " + attempt + "…";
					renderStats();
					return new Promise(function (resolve) {
						setTimeout(resolve, Math.min(30000, 800 * Math.pow(2, attempt - 1)));
					}).then(once);
				}
				throw err;
			});
		}
		return once();
	}

	function pump() {
		if (!state.running || state.paused) return;
		var workers = parseInt((el("usis-ingest-workers") || {}).value || "3", 10) || 3;
		var next = state.items.find(function (item) {
			return item.status === "queued";
		});
		if (!next) {
			if (state.inFlight === 0) {
				state.running = false;
				renderStats();
				var c = counts();
				if (c.error) notify("error", c.error + " file" + (c.error === 1 ? "" : "s") + " failed");
				else notify("success", "Ingest finished");
			}
			return;
		}
		if (state.inFlight >= workers) return;
		state.inFlight += 1;
		next.status = "uploading";
		next.note = "";
		renderTable();
		uploadWithRetry(next)
			.then(function (body) {
				next.status = body.duplicate ? "duplicate" : "created";
				next.kind = body.kind || next.kind;
				var doc = body.drawing || body.document || {};
				next.note = body.duplicate ? "already stored" : doc.filename || "";
				maybeSpecPackageToast(next, body);
			})
			.catch(function (err) {
				next.status = "error";
				next.note = err.message || String(err);
				if (!err.errorId) reportClientError(next, err);
				loadTracker();
			})
			.then(function () {
				state.inFlight -= 1;
				renderTable();
				pump();
				pump();
			});
	}

	function start() {
		if (state.running) return;
		batchId();
		state.paused = false;
		state.running = true;
		renderStats();
		loadTracker();
		if (state.trackerTimer) clearInterval(state.trackerTimer);
		state.trackerTimer = setInterval(function () {
			if (!state.running) {
				clearInterval(state.trackerTimer);
				state.trackerTimer = null;
				return;
			}
			loadTracker();
		}, 4000);
		pump();
		pump();
		pump();
		pump();
	}

	function reportClientError(item, err) {
		if (!api().fetchJson) return;
		var project = state.project || {};
		api()
			.fetchJson("/api/v1/ingest/errors", {
				method: "POST",
				body: {
					batch_id: batchId(),
					source: "mass_ingest",
					relative_path: item.rel,
					filename: item.file && item.file.name,
					kind: item.kind,
					project_id: project.job_id || project.project_id || project.id || "",
					project_number: project.project_number || "",
					http_status: err && err.status,
					message: (err && err.message) || "upload failed",
				},
			})
			.catch(function () {});
	}

	function formatWhen(iso) {
		if (!iso) return "";
		var d = new Date(iso);
		if (isNaN(d.getTime())) return iso;
		return d.toLocaleString();
	}

	function renderTracker() {
		var tb = el("usis-ingest-err-tbody");
		var stats = el("usis-ingest-err-stats");
		var rows = state.trackerItems || [];
		if (stats) {
			stats.textContent = rows.length
				? rows.length + " shown · open this filter: " + (state.trackerOpenCount || 0)
				: "No recorded failures yet.";
		}
		if (!tb) return;
		if (!rows.length) {
			tb.innerHTML = '<tr><td colspan="7" class="text-muted small">No errors recorded for this filter.</td></tr>';
			return;
		}
		tb.innerHTML = rows
			.map(function (row) {
				return (
					"<tr data-id=\"" +
					esc(row.id) +
					'"><td class="small text-nowrap">' +
					esc(formatWhen(row.created_at)) +
					'</td><td class="text-break">' +
					esc(row.relative_path || row.filename || "") +
					"</td><td>" +
					esc(row.project_number || "") +
					"</td><td>" +
					esc(row.http_status || "") +
					'</td><td class="text-break small">' +
					esc(row.message || "") +
					'</td><td class="usis-ingest-status-' +
					esc(row.status || "open") +
					'">' +
					esc(row.status || "open") +
					"</td><td>" +
					(row.status === "open"
						? '<button type="button" class="btn btn-link btn-sm p-0" data-resolve="' +
						  esc(row.id) +
						  '">Resolve</button>'
						: "") +
					"</td></tr>"
				);
			})
			.join("");
		tb.querySelectorAll("[data-resolve]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				resolveOne(btn.getAttribute("data-resolve"));
			});
		});
	}

	function trackerQuery() {
		var scope = (el("usis-ingest-err-scope") || {}).value || "batch";
		var params = { limit: 200 };
		if (scope === "batch") {
			params.batch_id = batchId();
			params.status = "";
		} else if (scope === "open") {
			params.status = "open";
		} else {
			params.status = "";
		}
		return params;
	}

	function loadTracker() {
		if (!api().fetchJson) return;
		api()
			.fetchJson("/api/v1/ingest/errors", { params: trackerQuery() })
			.then(function (data) {
				state.trackerItems = (data && data.items) || [];
				state.trackerOpenCount = (data && data.open_count) || 0;
				renderTracker();
			})
			.catch(function () {
				renderTracker();
			});
	}

	function resolveOne(id) {
		if (!id || !api().fetchJson) return;
		api()
			.fetchJson("/api/v1/ingest/errors/" + id, { method: "PATCH", body: { status: "resolved" } })
			.then(function () {
				loadTracker();
			})
			.catch(function (err) {
				notify("error", err.message || "Could not resolve error");
			});
	}

	function resolveBatch() {
		if (!api().fetchJson) return;
		api()
			.fetchJson("/api/v1/ingest/errors/resolve", { method: "POST", body: { batch_id: batchId() } })
			.then(function (data) {
				notify("success", (data && data.resolved ? data.resolved : 0) + " error(s) resolved");
				loadTracker();
			})
			.catch(function (err) {
				notify("error", err.message || "Could not resolve errors");
			});
	}

	function renderProjectList(projects) {
		var box = el("usis-ingest-project-list");
		if (!box) return;
		if (!projects.length) {
			box.classList.add("d-none");
			box.innerHTML = "";
			return;
		}
		box.classList.remove("d-none");
		box.innerHTML = projects
			.slice(0, 25)
			.map(function (p) {
				var label = (p.project_number ? p.project_number + " · " : "") + (p.name || p.id);
				return (
					'<button type="button" class="list-group-item list-group-item-action py-1 small" data-id="' +
					esc(p.id) +
					'">' +
					esc(label) +
					" <span class=\"text-muted\">" +
					esc(p.kind || "") +
					"</span></button>"
				);
			})
			.join("");
		box.querySelectorAll("button").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var id = btn.getAttribute("data-id");
				state.project = projects.find(function (p) {
					return p.id === id;
				});
				showSelected();
				box.classList.add("d-none");
			});
		});
	}

	function showSelected() {
		var node = el("usis-ingest-project-selected");
		if (!node) return;
		if (!state.project) {
			node.textContent = "No job selected — folder names will be used to match.";
			return;
		}
		node.innerHTML =
			"Selected <strong>" +
			esc((state.project.project_number ? state.project.project_number + " · " : "") + (state.project.name || "")) +
			'</strong> <button type="button" class="btn btn-link btn-sm p-0" id="usis-ingest-project-clear">Clear</button>';
		var clr = el("usis-ingest-project-clear");
		if (clr) {
			clr.addEventListener("click", function () {
				state.project = null;
				showSelected();
			});
		}
	}

	function searchProjects(q) {
		if (!api().fetchJson) return;
		api()
			.fetchJson("/api/v1/ingest/projects", { params: { q: q || "" } })
			.then(function (data) {
				renderProjectList((data && data.projects) || []);
			})
			.catch(function () {
				renderProjectList([]);
			});
	}

	function preselectFromQuery() {
		var params = new URLSearchParams(window.location.search);
		var pid = (params.get("project_id") || params.get("id") || "").trim();
		var job = (params.get("job") || params.get("project_number") || "").trim();
		var q = pid || job;
		if (!q || !api().fetchJson) return;
		api()
			.fetchJson("/api/v1/ingest/projects", { params: { q: q } })
			.then(function (data) {
				var rows = (data && data.projects) || [];
				state.project =
					rows.find(function (p) {
						return p.id === pid || p.project_id === pid || p.job_id === pid;
					}) ||
					rows.find(function (p) {
						return p.project_number === job;
					}) ||
					(rows.length === 1 ? rows[0] : null);
				showSelected();
			});
	}

	function bind() {
		var drop = el("usis-ingest-drop");
		var filesInput = el("usis-ingest-files-input");
		var folderInput = el("usis-ingest-folder-input");
		if (el("usis-ingest-pick-files") && filesInput) {
			el("usis-ingest-pick-files").addEventListener("click", function () {
				filesInput.click();
			});
			filesInput.addEventListener("change", function () {
				addFiles(filesInput.files);
				filesInput.value = "";
			});
		}
		if (el("usis-ingest-pick-folder") && folderInput) {
			el("usis-ingest-pick-folder").addEventListener("click", function () {
				folderInput.click();
			});
			folderInput.addEventListener("change", function () {
				addFiles(folderInput.files);
				folderInput.value = "";
			});
		}
		if (drop) {
			["dragenter", "dragover"].forEach(function (evt) {
				drop.addEventListener(evt, function (e) {
					e.preventDefault();
					drop.classList.add("is-over");
				});
			});
			["dragleave", "drop"].forEach(function (evt) {
				drop.addEventListener(evt, function () {
					drop.classList.remove("is-over");
				});
			});
			drop.addEventListener("drop", function (e) {
				e.preventDefault();
				var dt = e.dataTransfer;
				if (!dt) return;
				var items = dt.items;
				if (items && items.length && items[0].webkitGetAsEntry) {
					var jobs = [];
					for (var i = 0; i < items.length; i++) {
						var entry = items[i].webkitGetAsEntry();
						if (entry) jobs.push(walkEntry(entry, ""));
					}
					Promise.all(jobs).then(function (chunks) {
						var files = [];
						chunks.forEach(function (chunk) {
							files = files.concat(chunk);
						});
						addFiles(files);
					});
					return;
				}
				addFiles(dt.files);
			});
		}
		if (el("usis-ingest-start")) el("usis-ingest-start").addEventListener("click", start);
		if (el("usis-ingest-pause")) {
			el("usis-ingest-pause").addEventListener("click", function () {
				state.paused = true;
				state.running = false;
				renderStats();
			});
		}
		if (el("usis-ingest-retry")) {
			el("usis-ingest-retry").addEventListener("click", function () {
				state.items.forEach(function (item) {
					if (item.status === "error" && item.file && item.file.size <= MAX_BYTES) {
						item.status = "queued";
						item.note = "";
					}
				});
				renderTable();
				start();
			});
		}
		if (el("usis-ingest-clear")) {
			el("usis-ingest-clear").addEventListener("click", function () {
				if (state.running) return;
				state.items = [];
				resetBatch();
				renderTable();
				loadTracker();
			});
		}
		if (el("usis-ingest-errors-only")) {
			el("usis-ingest-errors-only").addEventListener("change", function () {
				state.queueFilter = el("usis-ingest-errors-only").checked ? "error" : "all";
				renderTable();
			});
		}
		if (el("usis-ingest-err-refresh")) el("usis-ingest-err-refresh").addEventListener("click", loadTracker);
		if (el("usis-ingest-err-resolve")) el("usis-ingest-err-resolve").addEventListener("click", resolveBatch);
		if (el("usis-ingest-err-scope")) {
			el("usis-ingest-err-scope").addEventListener("change", loadTracker);
		}
		var q = el("usis-ingest-project-q");
		if (q) {
			q.addEventListener("input", function () {
				clearTimeout(state.searchTimer);
				state.searchTimer = setTimeout(function () {
					searchProjects(q.value.trim());
				}, 250);
			});
			q.addEventListener("focus", function () {
				if (q.value.trim()) searchProjects(q.value.trim());
			});
		}
		showSelected();
		preselectFromQuery();
		renderStats();
		renderTracker();
		loadTracker();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", bind);
	} else {
		bind();
	}
})();
