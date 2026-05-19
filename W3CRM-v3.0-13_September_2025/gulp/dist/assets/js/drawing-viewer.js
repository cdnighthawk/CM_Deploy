/**
 * Full-page PDF drawing viewer with revision navigation (Procore-style).
 * Query: ?project_id=&drawing_id=  (drawing_id = any revision in the series)
 * Optional: &takeoff_line=<takeoff_line_items.id> — persist quantity / measurement via PATCH.
 * Measure: Fabric overlay — calibrate (2 pts + known LF), linear polyline, polygon area, axis-aligned rectangle + deductions, count markers.
 */
(function () {
	"use strict";

	// #region agent log
	function _usisDbg(hypothesisId, location, message, data) {
		try {
			var payload = {
				sessionId: "ff8612",
				hypothesisId: hypothesisId,
				location: location,
				message: message,
				data: data || {},
				timestamp: Date.now(),
			};
			var body = JSON.stringify(payload);
			var b = apiBase();
			fetch(b + "/api/v1/__debug/client-log", {
				method: "POST",
				credentials: "include",
				headers: { "Content-Type": "application/json", Accept: "application/json" },
				body: body,
			}).catch(function () {});
			fetch("http://127.0.0.1:7866/ingest/7eb18b08-6c99-452b-b32e-e84826b81e7a", {
				method: "POST",
				headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "ff8612" },
				body: body,
			}).catch(function () {});
		} catch (e) {
			/* never break viewer on debug */
		}
	}
	// #endregion

	var pdfjsLib = window.pdfjsLib;
	var fabricLib = window.fabric;
	var pdfDoc = null;
	var pageNum = 1;
	var pageRendering = false;
	var pagePending = null;
	var scale = 1.25;
	var revisions = [];
	var revIndex = 0;
	var projectId = null;
	var activeDrawingId = null;
	var takeoffLineId = null;
	var takeoffListCache = [];
	var fab = null;
	var measureMode = "none";
	var pixelsPerLf = null;
	var calPoints = [];
	var linePoints = [];
	var polyPoints = [];
	var countMarkers = [];
	var lastMeasurement = null;
	var measurementShapes = [];
	var lastGrossShapeIndex = -1;
	var rectPoints = [];
	var deductPoints = [];
	var measurePreviewRect = null;

	/** Resolve a path like ``assets/vendor/...`` using ``document.baseURI`` (includes ``<base href>``) so the worker URL matches ``pdf.min.js``. */
	function resolveAgainstDocumentBase(relPath) {
		var rp = relPath == null ? "" : String(relPath).trim();
		if (!rp) return rp;
		try {
			return new URL(rp, document.baseURI).href;
		} catch (e) {
			return rp;
		}
	}

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") {
			return "http://127.0.0.1:5000";
		}
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		var devPorts = {
			3000: 1,
			3001: 1,
			3002: 1,
			3003: 1,
			4173: 1,
			5173: 1,
			5174: 1,
			5500: 1,
			5501: 1,
			8080: 1,
			4200: 1,
			4321: 1,
			9630: 1,
			1234: 1,
		};
		if (devPorts[port]) {
			return "";
		}
		var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
		if (loopback) {
			if (port === "5000") return "";
			return proto + "//" + host + ":5000";
		}
		var ipv4 = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
		if (ipv4 && port && port !== "5000" && port !== "80" && port !== "443") {
			return proto + "//" + host + ":5000";
		}
		if ((host === "host.docker.internal" || host.endsWith(".local")) && port && port !== "5000") {
			return proto + "//" + host + ":5000";
		}
		return "";
	}

	function fetchJson(path) {
		var base = apiBase();
		return fetch(base + path, {
			credentials: "include",
			headers: { Accept: "application/json" },
		}).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					if (res.status === 401) {
						throw new Error("Sign in required — log in and reopen this drawing.");
					}
					if (res.status === 404) {
						throw new Error("Drawing not found (404). Check the link or pick another sheet.");
					}
					throw new Error(res.status + " " + (t || res.statusText));
				});
			}
			return res.json();
		});
	}

	function probePdfAccessible(pdfSrc) {
		return fetch(pdfSrc, {
			method: "GET",
			credentials: "include",
			headers: { Range: "bytes=0-0" },
		}).then(function (res) {
			if (res.status === 401) {
				throw new Error("Sign in required — log in and reopen this drawing.");
			}
			if (res.status === 404) {
				throw new Error(
					"PDF not found on server. Re-upload the drawing from Project → Drawings."
				);
			}
			if (!res.ok && res.status !== 206) {
				throw new Error("PDF unavailable (HTTP " + res.status + ").");
			}
		});
	}

	function pdfDocumentOptions(pdfSrc) {
		var opts = {
			url: pdfSrc,
			withCredentials: false,
			disableRange: true,
			disableStream: true,
		};
		try {
			var pageOrigin = window.location.origin;
			var docOrigin = new URL(pdfSrc, pageOrigin).origin;
			var b = apiBase();
			if (/\/api\/v1\/drawings\//i.test(pdfSrc)) {
				opts.withCredentials = true;
			} else if (b) {
				var apiOrigin = new URL(b, pageOrigin).origin;
				if (docOrigin === apiOrigin || docOrigin === pageOrigin) opts.withCredentials = true;
			} else if (docOrigin === pageOrigin) {
				opts.withCredentials = true;
			}
		} catch (e) {
			if (/\/api\/v1\/drawings\//i.test(String(pdfSrc))) opts.withCredentials = true;
		}
		return opts;
	}

	function withTimeout(promise, ms, label) {
		return new Promise(function (resolve, reject) {
			var t = setTimeout(function () {
				reject(new Error(label || "Request timed out."));
			}, ms);
			promise.then(
				function (v) {
					clearTimeout(t);
					resolve(v);
				},
				function (e) {
					clearTimeout(t);
					reject(e);
				}
			);
		});
	}

	function setOverlayPointerEvents(on) {
		var o = document.getElementById("usis-dv-overlay");
		if (o) o.style.pointerEvents = on ? "auto" : "none";
	}

	function showErr(msg) {
		var el = document.getElementById("usis-dv-error");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.textContent = "";
			el.classList.add("d-none");
		}
	}

	function setLoading(on, phase) {
		var el = document.getElementById("usis-dv-loading");
		var tx = document.getElementById("usis-dv-loading-text");
		if (el) el.classList.toggle("d-none", !on);
		if (tx && on) {
			if (phase === "pdf") tx.textContent = "Loading PDF…";
			else if (phase === "revisions") tx.textContent = "Loading sheet / revisions…";
			else tx.textContent = "Loading drawing…";
		}
	}

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function currentRevisionDrawingId() {
		var r = revisions[revIndex];
		return r && r.id ? r.id : null;
	}

	function loadAnnotations() {
		var ul = document.getElementById("usis-dv-annotations-list");
		if (!ul) return;
		var did = currentRevisionDrawingId();
		if (!did) {
			ul.innerHTML = "";
			return;
		}
		ul.innerHTML = '<li class="text-muted">Loading…</li>';
		fetchJson("/api/v1/drawings/" + encodeURIComponent(did) + "/annotations")
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					ul.innerHTML = '<li class="text-muted">No annotations yet.</li>';
					return;
				}
				ul.innerHTML = items
					.map(function (a) {
						return (
							"<li><span class=\"badge bg-light text-dark me-1\">" +
							esc(a.type) +
							"</span>" +
							esc(JSON.stringify(a.data || {}).slice(0, 120)) +
							"</li>"
						);
					})
					.join("");
			})
			.catch(function () {
				ul.innerHTML = '<li class="text-danger">Could not load annotations.</li>';
			});
	}

	function updateZoomLabel() {
		var el = document.getElementById("usis-dv-zoom-label");
		if (el) el.textContent = Math.round(scale * 100) + "%";
	}

	function updatePageLabel() {
		var el = document.getElementById("usis-dv-page-label");
		if (!el || !pdfDoc) {
			if (el) el.textContent = "—";
			return;
		}
		el.textContent = pageNum + " / " + pdfDoc.numPages;
	}

	function queueRenderPage() {
		if (pageRendering) {
			pagePending = pageNum;
		} else {
			renderPage(pageNum);
		}
	}

	function renderPage(num) {
		pageRendering = true;
		var canvas = document.getElementById("usis-dv-canvas");
		if (!canvas || !pdfDoc) {
			pageRendering = false;
			return;
		}
		var ctx = canvas.getContext("2d");
		pdfDoc
			.getPage(num)
			.then(function (page) {
				var viewport = page.getViewport({ scale: scale });
				canvas.height = viewport.height;
				canvas.width = viewport.width;
				var renderContext = {
					canvasContext: ctx,
					viewport: viewport,
				};
				return page.render(renderContext).promise;
			})
			.then(function () {
				pageRendering = false;
				if (pagePending !== null) {
					var pending = pagePending;
					pagePending = null;
					renderPage(pending);
				}
				updatePageLabel();
				resizeFabricOverlay();
			})
			.catch(function (e) {
				pageRendering = false;
				showErr(e && e.message ? e.message : String(e));
			});
	}

	function fillRevisionSelect() {
		var sel = document.getElementById("usis-dv-revision");
		if (!sel) return;
		sel.innerHTML = "";
		revisions.forEach(function (r, i) {
			var o = document.createElement("option");
			o.value = String(i);
			var label =
				"Rev " +
				(r.revision != null ? String(r.revision) : "?") +
				" · v" +
				(r.version != null ? String(r.version) : "?");
			if (r.updated_at) {
				try {
					label += " · " + new Date(r.updated_at).toLocaleDateString();
				} catch (e2) {
					label += " · " + r.updated_at;
				}
			}
			o.textContent = label;
			sel.appendChild(o);
		});
		sel.value = String(revIndex);
	}

	function updateSheetLine() {
		var el = document.getElementById("usis-dv-sheetline");
		if (!el) return;
		var r = revisions[revIndex];
		if (!r) {
			el.innerHTML = "";
			return;
		}
		var parts = [];
		if (r.sheet_number) parts.push("<span class='fw-semibold'>" + esc(r.sheet_number) + "</span>");
		if (r.sheet_title) parts.push(esc(r.sheet_title));
		if (r.discipline) parts.push(esc(r.discipline));
		if (r.drawing_set) parts.push("Set " + esc(r.drawing_set));
		el.innerHTML = parts.join(" · ");
	}

	function renderSheetsList() {
		var wrap = document.getElementById("usis-dv-sheets-wrap");
		var ul = document.getElementById("usis-dv-thumb-list");
		if (!wrap || !ul) return;
		if (!revisions.length) {
			wrap.classList.add("d-none");
			return;
		}
		wrap.classList.remove("d-none");
		ul.innerHTML = revisions
			.map(function (r, i) {
				var lab = (r.sheet_number || "?") + " — " + (r.sheet_title || r.id);
				return (
					'<li class="mb-1"><button type="button" class="btn btn-link btn-sm p-0 text-start usis-dv-jump-rev" data-rev-idx="' +
					i +
					'">' +
					esc(lab) +
					"</button></li>"
				);
			})
			.join("");
		ul.querySelectorAll(".usis-dv-jump-rev").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var ix = parseInt(btn.getAttribute("data-rev-idx"), 10);
				if (!isNaN(ix)) setRevIndex(ix, false);
			});
		});
	}

	function loadPdfFromRevision() {
		var r = revisions[revIndex];
		if (!r) {
			_usisDbg("B", "drawing-viewer.js:loadPdfFromRevision", "no_revision_row", { revIndex: revIndex });
			showErr("No revision selected.");
			pdfDoc = null;
			updatePageLabel();
			disposeFabric();
			return;
		}
		var pdfSrc = (function () {
			var raw = r.file_url;
			if (raw != null && String(raw).trim() !== "") {
				var s = String(raw).trim();
				if (/^https?:\/\//i.test(s)) return s;
				var b0 = apiBase();
				return b0 + (s.charAt(0) === "/" ? s : "/" + s);
			}
			var rid = r.id || currentRevisionDrawingId();
			if (rid) {
				var bb = apiBase();
				return bb + "/api/v1/drawings/" + encodeURIComponent(rid) + "/file";
			}
			return "";
		})();
		_usisDbg("B", "drawing-viewer.js:loadPdfFromRevision", "pdfSrc_resolved", {
			pdfSrcLen: pdfSrc ? pdfSrc.length : 0,
			pdfSrcHead: pdfSrc ? String(pdfSrc).slice(0, 160) : "",
			apiBaseVal: apiBase(),
			revId: r && r.id,
			hasRawFileUrl: !!(r && r.file_url != null && String(r.file_url).trim() !== ""),
		});
		if (!pdfSrc) {
			_usisDbg("B", "drawing-viewer.js:loadPdfFromRevision", "empty_pdfSrc", {});
			showErr("No PDF file URL for this revision.");
			var canvas = document.getElementById("usis-dv-canvas");
			if (canvas) {
				var ctx = canvas.getContext("2d");
				canvas.width = 400;
				canvas.height = 120;
				ctx.fillStyle = "#f8f9fa";
				ctx.fillRect(0, 0, canvas.width, canvas.height);
				ctx.fillStyle = "#6c757d";
				ctx.font = "14px sans-serif";
				ctx.fillText("No PDF attached", 24, 64);
			}
			pdfDoc = null;
			updatePageLabel();
			disposeFabric();
			return;
		}
		showErr("");
		setLoading(true, "pdf");
		withTimeout(
			probePdfAccessible(pdfSrc).then(function () {
				return pdfjsLib.getDocument(pdfDocumentOptions(pdfSrc)).promise;
			}),
			120000,
			"PDF load timed out (network, auth, or worker)."
		)
			.then(function (doc) {
				_usisDbg("D", "drawing-viewer.js:getDocument", "pdf_open_ok", {
					numPages: doc && doc.numPages,
				});
				pdfDoc = doc;
				pageNum = 1;
				setLoading(false);
				queueRenderPage();
				updatePageLabel();
				updateZoomLabel();
			})
			.catch(function (e) {
				_usisDbg("D", "drawing-viewer.js:getDocument", "pdf_open_fail", {
					err: e && e.message ? e.message : String(e),
				});
				setLoading(false);
				pdfDoc = null;
				var msg = e && e.message ? e.message : String(e);
				showErr(
					msg.indexOf("Sign in") !== -1 || msg.indexOf("not found") !== -1
						? msg
						: "Could not load PDF. " + msg
				);
				updatePageLabel();
			});
	}

	function setRevIndex(i, skipSelect) {
		if (!revisions.length) return;
		if (i < 0) i = 0;
		if (i >= revisions.length) i = revisions.length - 1;
		revIndex = i;
		if (!skipSelect) {
			var sel = document.getElementById("usis-dv-revision");
			if (sel) sel.value = String(revIndex);
		}
		updateSheetLine();
		pageNum = 1;
		clearMeasureGeometry();
		loadPdfFromRevision();
		loadAnnotations();
	}

	function goOlder() {
		setRevIndex(revIndex + 1);
	}

	function goNewer() {
		setRevIndex(revIndex - 1);
	}

	function onKeyDown(e) {
		if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "SELECT" || e.target.tagName === "TEXTAREA")) {
			return;
		}
		if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
			e.preventDefault();
			goOlder();
		} else if (e.key === "ArrowRight" || e.key === "ArrowUp") {
			e.preventDefault();
			goNewer();
		} else if (e.key === "+" || e.key === "=") {
			e.preventDefault();
			scale = Math.min(scale * 1.15, 4);
			updateZoomLabel();
			queueRenderPage();
		} else if (e.key === "-" || e.key === "_") {
			e.preventDefault();
			scale = Math.max(scale / 1.15, 0.35);
			updateZoomLabel();
			queueRenderPage();
		}
	}

	function refreshTakeoffStrip() {
		var strip = document.getElementById("usis-dv-takeoff-strip");
		var empty = document.getElementById("usis-dv-takeoff-empty");
		if (!strip) return;
		if (takeoffLineId) {
			strip.classList.remove("d-none");
			if (empty) empty.classList.add("d-none");
			loadTakeoffLineSummary();
		} else {
			strip.classList.add("d-none");
			if (empty) empty.classList.remove("d-none");
			currentTakeoffLine = null;
		}
	}

	function syncTakeoffLineInUrl() {
		try {
			var u = new URL(window.location.href);
			if (takeoffLineId) u.searchParams.set("takeoff_line", String(takeoffLineId));
			else u.searchParams.delete("takeoff_line");
			window.history.replaceState({}, "", u.toString());
		} catch (e) {
			/* ignore */
		}
	}

	function selectTakeoffLine(id, opts) {
		opts = opts || {};
		takeoffLineId = id ? String(id).trim() : "";
		if (!takeoffLineId) takeoffLineId = null;
		if (opts.prefetchLine && takeoffLineId && String(opts.prefetchLine.id) === String(takeoffLineId)) {
			currentTakeoffLine = opts.prefetchLine;
		}
		syncTakeoffLineInUrl();
		renderTakeoffList();
		refreshTakeoffStrip();
		if (opts.openModal) {
			openTakeoffLineModal();
		}
	}

	function renderTakeoffList() {
		var listEl = document.getElementById("usis-dv-takeoff-list");
		var ph = document.getElementById("usis-dv-takeoff-list-placeholder");
		if (!listEl) return;
		listEl.querySelectorAll("button.usis-dv-takeoff-row").forEach(function (n) {
			n.remove();
		});
		if (!projectId) {
			if (ph) {
				ph.classList.remove("d-none");
				ph.textContent = "Add project_id to the URL to list takeoffs for this job.";
			}
			return;
		}
		if (!takeoffListCache.length) {
			if (ph) {
				ph.classList.remove("d-none");
				ph.textContent = "No takeoffs yet. Use New takeoff below.";
			}
			return;
		}
		if (ph) ph.classList.add("d-none");
		takeoffListCache.forEach(function (line) {
			var btn = document.createElement("button");
			btn.type = "button";
			btn.className =
				"usis-dv-takeoff-row btn btn-light border w-100 mb-1 py-2 px-2 small text-start";
			btn.setAttribute("data-takeoff-id", String(line.id));
			if (takeoffLineId && String(line.id) === String(takeoffLineId)) {
				btn.classList.add("active");
			}
			var t1 = (line.description || "(no description)").trim() || "(no description)";
			var t2 =
				"Qty " +
				(line.quantity != null ? line.quantity : "—") +
				" " +
				(line.unit || "").trim();
			btn.innerHTML =
				'<span class="fw-semibold d-block text-truncate">' +
				escapeHtml(t1) +
				"</span>" +
				'<span class="text-muted">' +
				escapeHtml(t2) +
				"</span>";
			btn.addEventListener("click", function () {
				selectTakeoffLine(line.id, { openModal: true, prefetchLine: line });
			});
			listEl.appendChild(btn);
		});
	}

	function escapeHtml(s) {
		return String(s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function loadProjectTakeoffList() {
		var listEl = document.getElementById("usis-dv-takeoff-list");
		var ph = document.getElementById("usis-dv-takeoff-list-placeholder");
		if (!listEl) return Promise.resolve();
		if (!projectId) {
			takeoffListCache = [];
			renderTakeoffList();
			return Promise.resolve();
		}
		if (ph) {
			ph.classList.remove("d-none");
			ph.textContent = "Loading takeoffs…";
		}
		return fetch(apiBase() + "/api/v1/projects/" + encodeURIComponent(projectId) + "/takeoff-lines", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.status);
					return j;
				});
			})
			.then(function (d) {
				takeoffListCache = d.items || [];
				renderTakeoffList();
			})
			.catch(function () {
				takeoffListCache = [];
				if (ph) {
					ph.classList.remove("d-none");
					ph.textContent = "Could not load takeoffs for this project.";
				}
			});
	}

	function createNewTakeoffLine() {
		if (!projectId) {
			if (window.USISNotify) window.USISNotify.warning("Add project_id to the URL first.");
			return;
		}
		var did = currentRevisionDrawingId();
		var body = {
			description: "New takeoff",
			quantity: 0,
			unit: "EA",
			unit_cost: 0,
			cost_type: "M",
		};
		if (did) body.drawing_id = did;
		fetch(apiBase() + "/api/v1/projects/" + encodeURIComponent(projectId) + "/takeoff-lines", {
			method: "POST",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			credentials: "include",
			body: JSON.stringify(body),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.status);
					return j;
				});
			})
			.then(function (j) {
				var item = j.item;
				return loadProjectTakeoffList().then(function () {
					if (item && item.id) {
						selectTakeoffLine(item.id, { openModal: true, prefetchLine: item });
						if (window.USISNotify) window.USISNotify.success("Takeoff line created");
					}
				});
			})
			.catch(function (e) {
				if (window.USISNotify) window.USISNotify.error(String(e.message || e));
			});
	}

	function formatTakeoffStripSummary(line) {
		if (!line) return "(not found)";
		var parts = [line.description && String(line.description).trim() ? line.description : "(no description)"];
		if (line.takeoff_location && String(line.takeoff_location).trim()) {
			parts.push("Loc: " + String(line.takeoff_location).trim());
		}
		if (line.material_catalog && line.material_catalog.item) {
			var mc = line.material_catalog;
			var mfg = String(mc.manufacturer || "");
			var it = String(mc.item || "");
			parts.push((mfg && it ? mfg + " · " + it : mfg || it) || "Catalog");
		}
		parts.push(
			"qty " +
				line.quantity +
				" " +
				(line.unit || "") +
				(line.extended_total != null ? " · ext " + line.extended_total : "")
		);
		return parts.join(" · ");
	}

	function loadTakeoffLineSummary() {
		var el = document.getElementById("usis-dv-takeoff-summary");
		if (!el || !takeoffLineId) return;
		if (!projectId) {
			currentTakeoffLine = null;
			el.textContent =
				"Line " +
				takeoffLineId +
				" — set quantity/unit below; add project_id to the URL to match this line to a project list.";
			return;
		}
		el.textContent = "Loading…";
		fetch(apiBase() + "/api/v1/projects/" + encodeURIComponent(projectId) + "/takeoff-lines", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (res) {
				return res.json();
			})
			.then(function (d) {
				var line = (d.items || []).find(function (x) {
					return String(x.id) === String(takeoffLineId);
				});
				if (line) {
					currentTakeoffLine = line;
					el.textContent = formatTakeoffStripSummary(line);
					var qIn = document.getElementById("usis-dv-takeoff-qty");
					var uIn = document.getElementById("usis-dv-takeoff-unit");
					if (qIn && line.quantity != null) qIn.value = String(line.quantity);
					if (uIn && line.unit) uIn.value = String(line.unit);
				} else {
					currentTakeoffLine = null;
					el.textContent =
						"Line id not in this project's takeoff list — verify project_id matches the line's project.";
				}
			})
			.catch(function () {
				currentTakeoffLine = null;
				el.textContent = "Could not load takeoff lines.";
			});
	}

	function setTakeoffModalErr(msg) {
		var err = document.getElementById("usis-dv-takeoff-modal-err");
		if (!err) return;
		if (msg) {
			err.textContent = msg;
			err.classList.remove("d-none");
		} else {
			err.textContent = "";
			err.classList.add("d-none");
		}
	}

	function applyMaterialFilterToSelect(filterRaw) {
		var sel = document.getElementById("usis-dv-takeoff-modal-material");
		if (!sel) return;
		var prev = sel.value;
		var needle = (filterRaw || "").toLowerCase().trim();
		sel.innerHTML = "";
		var o0 = document.createElement("option");
		o0.value = "";
		o0.textContent = "— None (no catalog link) —";
		sel.appendChild(o0);
		var rows = allMaterialsCache.filter(function (m) {
			if (!needle) return true;
			var blob = (
				(m.manufacturer || "") +
				" " +
				(m.item || "") +
				" " +
				(m.description || "") +
				" " +
				(m.category || "")
			).toLowerCase();
			return blob.indexOf(needle) >= 0;
		});
		rows.forEach(function (m) {
			var o = document.createElement("option");
			o.value = String(m.id);
			o.textContent = (m.manufacturer || "?") + " — " + (m.item || "?");
			sel.appendChild(o);
		});
		if (prev && Array.prototype.some.call(sel.options, function (x) { return x.value === prev; })) {
			sel.value = prev;
		}
	}

	function syncTakeoffModalFromLine() {
		var labelIn = document.getElementById("usis-dv-takeoff-modal-label");
		var locIn = document.getElementById("usis-dv-takeoff-modal-loc");
		var sel = document.getElementById("usis-dv-takeoff-modal-material");
		var line = currentTakeoffLine;
		if (labelIn) labelIn.value = line && line.description != null ? String(line.description) : "";
		if (locIn) locIn.value = line && line.takeoff_location != null ? String(line.takeoff_location) : "";
		if (sel) {
			if (line && line.material_pricing_id) {
				sel.dataset.pendingMat = String(line.material_pricing_id);
			} else {
				sel.dataset.pendingMat = "";
				sel.value = "";
			}
		}
	}

	function loadTakeoffMaterialCatalogAndFill() {
		var noCat = document.getElementById("usis-dv-takeoff-modal-no-catalog");
		var wrap = document.getElementById("usis-dv-takeoff-modal-mat-wrap");
		setTakeoffModalErr("");
		return fetch(apiBase() + "/api/v1/material-prices?limit=300", {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.status);
					return j;
				});
			})
			.then(function (d) {
				allMaterialsCache = d.items || [];
				if (allMaterialsCache.length === 0) {
					if (noCat) noCat.classList.remove("d-none");
					if (wrap) wrap.classList.add("d-none");
				} else {
					if (noCat) noCat.classList.add("d-none");
					if (wrap) wrap.classList.remove("d-none");
					applyMaterialFilterToSelect("");
				}
				var sel = document.getElementById("usis-dv-takeoff-modal-material");
				var pending = sel && sel.dataset ? sel.dataset.pendingMat : "";
				if (sel && pending) {
					if (Array.prototype.some.call(sel.options, function (x) { return x.value === pending; })) {
						sel.value = pending;
					} else if (currentTakeoffLine && currentTakeoffLine.material_catalog) {
						var mc = currentTakeoffLine.material_catalog;
						var o = document.createElement("option");
						o.value = pending;
						o.textContent = (mc.manufacturer || "?") + " — " + (mc.item || "?") + " (current)";
						sel.appendChild(o);
						sel.value = pending;
					}
					sel.dataset.pendingMat = "";
				}
			})
			.catch(function (e) {
				allMaterialsCache = [];
				if (noCat) noCat.classList.add("d-none");
				if (wrap) wrap.classList.remove("d-none");
				applyMaterialFilterToSelect("");
				setTakeoffModalErr(
					"Could not load material catalog. You can still save label and location. (" + String(e.message || e) + ")"
				);
			});
	}

	function openTakeoffLineModal() {
		var modalEl = document.getElementById("usis-dv-modal-takeoff-line");
		if (!modalEl) return;
		if (!takeoffLineId) {
			if (window.USISNotify) window.USISNotify.info("Select a takeoff on the left, or create New takeoff.");
			return;
		}
		syncTakeoffModalFromLine();
		var fil = document.getElementById("usis-dv-takeoff-modal-mat-filter");
		if (fil) fil.value = "";
		loadTakeoffMaterialCatalogAndFill().then(function () {
			if (typeof bootstrap !== "undefined" && bootstrap.Modal) {
				bootstrap.Modal.getOrCreateInstance(modalEl).show();
			} else {
				modalEl.classList.add("show");
				modalEl.style.display = "block";
			}
		});
	}

	function saveTakeoffLineModal() {
		if (!takeoffLineId) return;
		var labelIn = document.getElementById("usis-dv-takeoff-modal-label");
		var locIn = document.getElementById("usis-dv-takeoff-modal-loc");
		var sel = document.getElementById("usis-dv-takeoff-modal-material");
		var desc = labelIn && labelIn.value != null ? String(labelIn.value).trim().slice(0, 500) : "";
		var loc = locIn && locIn.value != null ? String(locIn.value).trim().slice(0, 500) : "";
		var mid = sel && sel.value ? String(sel.value).trim() : null;
		setTakeoffModalErr("");
		fetch(apiBase() + "/api/v1/takeoff-lines/" + encodeURIComponent(takeoffLineId), {
			method: "PATCH",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			credentials: "include",
			body: JSON.stringify({
				description: desc,
				takeoff_location: loc === "" ? null : loc,
				material_pricing_id: mid,
			}),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.status);
					return j;
				});
			})
			.then(function (j) {
				if (j.item) currentTakeoffLine = j.item;
				if (window.USISNotify) window.USISNotify.success("Takeoff line saved");
				var mEl = document.getElementById("usis-dv-modal-takeoff-line");
				if (mEl && typeof bootstrap !== "undefined" && bootstrap.Modal) {
					bootstrap.Modal.getOrCreateInstance(mEl).hide();
				}
				loadTakeoffLineSummary();
				loadProjectTakeoffList();
			})
			.catch(function (e) {
				var msg = String(e.message || e);
				setTakeoffModalErr(msg);
				if (window.USISNotify) window.USISNotify.error(msg);
			});
	}

	function wireTakeoffLineModal() {
		var newBare = document.getElementById("usis-dv-takeoff-modal-new-bare");
		if (newBare && !newBare.dataset.usisWired) {
			newBare.dataset.usisWired = "1";
			newBare.addEventListener("click", function () {
				var noCat = document.getElementById("usis-dv-takeoff-modal-no-catalog");
				if (noCat) noCat.classList.add("d-none");
				if (window.USISNotify) {
					window.USISNotify.info("Enter label and location, then Save. Quantity and measure tools stay in the rail.");
				}
				var locIn = document.getElementById("usis-dv-takeoff-modal-loc");
				if (locIn) locIn.focus();
			});
		}
		var fil = document.getElementById("usis-dv-takeoff-modal-mat-filter");
		if (fil && !fil.dataset.usisWired) {
			fil.dataset.usisWired = "1";
			fil.addEventListener("input", function () {
				applyMaterialFilterToSelect(fil.value);
			});
		}
		var saveBtn = document.getElementById("usis-dv-takeoff-modal-save");
		if (saveBtn && !saveBtn.dataset.usisWired) {
			saveBtn.dataset.usisWired = "1";
			saveBtn.addEventListener("click", saveTakeoffLineModal);
		}
		var sum = document.getElementById("usis-dv-takeoff-summary");
		if (sum && !sum.dataset.usisWired) {
			sum.dataset.usisWired = "1";
			sum.addEventListener("click", openTakeoffLineModal);
			sum.addEventListener("keydown", function (e) {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					openTakeoffLineModal();
				}
			});
		}
		var openBtn = document.getElementById("usis-dv-takeoff-open-modal");
		if (openBtn && !openBtn.dataset.usisWired) {
			openBtn.dataset.usisWired = "1";
			openBtn.addEventListener("click", openTakeoffLineModal);
		}
	}

	function disposeFabric() {
		if (fab) {
			try {
				fab.dispose();
			} catch (e) {}
			fab = null;
		}
		measurePreviewRect = null;
	}

	function clearMeasureGeometry() {
		linePoints = [];
		polyPoints = [];
		calPoints = [];
		countMarkers = [];
		lastMeasurement = null;
		pixelsPerLf = null;
		measurementShapes = [];
		lastGrossShapeIndex = -1;
		resetRectDraft();
		disposeFabric();
		updateMeasureStatus();
	}

	function updateMeasureStatus() {
		var el = document.getElementById("usis-dv-m-status");
		if (!el) return;
		var cal =
			pixelsPerLf != null && pixelsPerLf > 0
				? "1 LF ≈ " + pixelsPerLf.toFixed(2) + " px"
				: "none";
		var lm = lastMeasurement
			? lastMeasurement.tool + " · " + (lastMeasurement.summary || "")
			: "—";
		el.textContent = "Calibration: " + cal + " · Measured: " + lm;
	}

	function setMeasureMode(mode) {
		measureMode = mode || "none";
		if (measureMode === "none") resetRectDraft();
		setOverlayPointerEvents(measureMode !== "none");
		updateMeasureStatus();
	}

	function resizeFabricOverlay() {
		var pdfCv = document.getElementById("usis-dv-canvas");
		var ovl = document.getElementById("usis-dv-overlay");
		if (!pdfCv || !ovl || !fabricLib) return;
		ovl.width = pdfCv.width;
		ovl.height = pdfCv.height;
		ovl.style.width = pdfCv.width + "px";
		ovl.style.height = pdfCv.height + "px";
		if (!fab) {
			try {
				fab = new fabricLib.Canvas("usis-dv-overlay", {
					width: pdfCv.width,
					height: pdfCv.height,
					selection: false,
				});
			} catch (e) {
				return;
			}
			fab.on("mouse:down", onFabricMouseDown);
			fab.on("mouse:move", onFabricMouseMove);
			fab.on("mouse:dblclick", onFabricDblClick);
		} else {
			fab.setWidth(pdfCv.width);
			fab.setHeight(pdfCv.height);
			fab.calcOffset();
		}
		setOverlayPointerEvents(measureMode !== "none");
	}

	function dist(a, b) {
		return Math.sqrt(Math.pow(b.x - a.x, 2) + Math.pow(b.y - a.y, 2));
	}

	function polylineLengthPx(points) {
		var t = 0;
		for (var i = 1; i < points.length; i++) t += dist(points[i - 1], points[i]);
		return t;
	}

	function polygonAreaPx(pts) {
		var n = pts.length;
		if (n < 3) return 0;
		var a = 0;
		for (var i = 0; i < n; i++) {
			var j = (i + 1) % n;
			a += pts[i].x * pts[j].y - pts[j].x * pts[i].y;
		}
		return Math.abs(a) / 2;
	}

	function boundsFromCorners(a, b) {
		return {
			minX: Math.min(a.x, b.x),
			minY: Math.min(a.y, b.y),
			maxX: Math.max(a.x, b.x),
			maxY: Math.max(a.y, b.y),
		};
	}

	function rectAreaPx(bounds) {
		if (!bounds) return 0;
		var w = bounds.maxX - bounds.minX;
		var h = bounds.maxY - bounds.minY;
		if (w <= 0 || h <= 0) return 0;
		return w * h;
	}

	function intersectBounds(A, B) {
		var minX = Math.max(A.minX, B.minX);
		var minY = Math.max(A.minY, B.minY);
		var maxX = Math.min(A.maxX, B.maxX);
		var maxY = Math.min(A.maxY, B.maxY);
		if (maxX <= minX || maxY <= minY) return null;
		return { minX: minX, minY: minY, maxX: maxX, maxY: maxY };
	}

	function intersectAreaPx(A, B) {
		var ix = intersectBounds(A, B);
		return ix ? rectAreaPx(ix) : 0;
	}

	function sumDeductionsPx(grossBounds, grossShapeIndex) {
		var t = 0;
		for (var i = 0; i < measurementShapes.length; i++) {
			var s = measurementShapes[i];
			if (s && s.type === "deduction" && s.grossShapeIndex === grossShapeIndex && s.bounds) {
				t += intersectAreaPx(grossBounds, s.bounds);
			}
		}
		return t;
	}

	function pxToSf(areaPx) {
		if (pixelsPerLf == null || pixelsPerLf <= 0) return null;
		return areaPx / (pixelsPerLf * pixelsPerLf);
	}

	function removeMeasurePreviewRect() {
		if (measurePreviewRect && fab) {
			try {
				fab.remove(measurePreviewRect);
				fab.requestRenderAll();
			} catch (e1) {}
		}
		measurePreviewRect = null;
	}

	function updateMeasurePreviewRect(bounds, isDeduct) {
		if (!fab || !fabricLib || !bounds) return;
		var w = bounds.maxX - bounds.minX;
		var h = bounds.maxY - bounds.minY;
		if (w < 1 || h < 1) return;
		var stroke = isDeduct ? "#dc3545" : "#198754";
		var fill = isDeduct ? "rgba(220,53,69,0.12)" : "rgba(25,135,84,0.12)";
		if (!measurePreviewRect) {
			measurePreviewRect = new fabricLib.Rect({
				left: bounds.minX,
				top: bounds.minY,
				width: w,
				height: h,
				fill: fill,
				stroke: stroke,
				strokeWidth: 2,
				strokeDashArray: [6, 4],
				selectable: false,
				evented: false,
			});
			fab.add(measurePreviewRect);
		} else {
			measurePreviewRect.set({
				left: bounds.minX,
				top: bounds.minY,
				width: w,
				height: h,
				stroke: stroke,
				fill: fill,
			});
			measurePreviewRect.setCoords();
		}
		fab.requestRenderAll();
	}

	function resetRectDraft() {
		rectPoints = [];
		deductPoints = [];
		removeMeasurePreviewRect();
	}

	function recomputeRectAreaSummary() {
		if (lastGrossShapeIndex < 0 || lastGrossShapeIndex >= measurementShapes.length) return;
		var g = measurementShapes[lastGrossShapeIndex];
		if (!g || g.type !== "rect" || !g.bounds) return;
		var grossPx = rectAreaPx(g.bounds);
		var deductPx = sumDeductionsPx(g.bounds, lastGrossShapeIndex);
		var netPx = Math.max(0, grossPx - deductPx);
		var grossSf = pxToSf(grossPx);
		var netSf = pxToSf(netPx);
		var dlist = [];
		for (var i = 0; i < measurementShapes.length; i++) {
			var s = measurementShapes[i];
			if (s && s.type === "deduction" && s.grossShapeIndex === lastGrossShapeIndex && s.bounds) {
				dlist.push(s.bounds);
			}
		}
		var summary;
		if (grossSf != null) {
			summary =
				"Gross " +
				grossSf.toFixed(3) +
				" SF" +
				(dlist.length ? " · Net " + (netSf != null ? netSf.toFixed(3) : "?") + " SF" : "");
		} else {
			summary =
				"Gross " +
				grossPx.toFixed(0) +
				" px²" +
				(dlist.length ? " · Net " + netPx.toFixed(0) + " px² (calibrate for SF)" : " (calibrate for SF)");
		}
		lastMeasurement = {
			tool: "rect_area",
			gross: g.bounds,
			deductions: dlist,
			grossSf: grossSf,
			netSf: netSf,
			grossPx: grossPx,
			netPx: netPx,
			summary: summary,
			page: pageNum,
			viewer_scale: scale,
		};
		updateMeasureStatus();
		var qIn = document.getElementById("usis-dv-takeoff-qty");
		var uIn = document.getElementById("usis-dv-takeoff-unit");
		if (qIn && netSf != null) qIn.value = String(netSf.toFixed(4));
		if (uIn && netSf != null) uIn.value = "SF";
	}

	function finalizeRectGross(bounds) {
		var areaPx = rectAreaPx(bounds);
		var sf = pxToSf(areaPx);
		if (fab && fabricLib) {
			var gr = new fabricLib.Rect({
				left: bounds.minX,
				top: bounds.minY,
				width: bounds.maxX - bounds.minX,
				height: bounds.maxY - bounds.minY,
				fill: "rgba(25,135,84,0.22)",
				stroke: "#198754",
				strokeWidth: 2,
				selectable: false,
				evented: false,
			});
			fab.add(gr);
		}
		measurementShapes.push({
			type: "rect",
			bounds: bounds,
			areaPx: areaPx,
			areaSf: sf,
			page: pageNum,
			viewer_scale: scale,
		});
		lastGrossShapeIndex = measurementShapes.length - 1;
		rectPoints = [];
		recomputeRectAreaSummary();
		if (window.USISNotify) window.USISNotify.info("Gross rectangle set — use Deduction for openings, then Apply to line.");
		setMeasureMode("none");
	}

	function finalizeDeduction(bounds) {
		var g = measurementShapes[lastGrossShapeIndex];
		if (!g || g.type !== "rect" || !g.bounds) return;
		var subPx = intersectAreaPx(g.bounds, bounds);
		var subSf = pxToSf(subPx);
		if (fab && fabricLib) {
			var dr = new fabricLib.Rect({
				left: bounds.minX,
				top: bounds.minY,
				width: bounds.maxX - bounds.minX,
				height: bounds.maxY - bounds.minY,
				fill: "rgba(220,53,69,0.22)",
				stroke: "#dc3545",
				strokeWidth: 2,
				strokeDashArray: [5, 4],
				selectable: false,
				evented: false,
			});
			fab.add(dr);
		}
		measurementShapes.push({
			type: "deduction",
			bounds: bounds,
			grossShapeIndex: lastGrossShapeIndex,
			subtractedAreaPx: subPx,
			subtractedAreaSf: subSf,
			page: pageNum,
			viewer_scale: scale,
		});
		deductPoints = [];
		recomputeRectAreaSummary();
		if (window.USISNotify) window.USISNotify.info("Deduction added — net SF updated.");
		setMeasureMode("none");
	}

	function onFabricMouseMove(opt) {
		if (!fab || (measureMode !== "rect" && measureMode !== "deduct")) return;
		var pts = measureMode === "rect" ? rectPoints : deductPoints;
		if (pts.length !== 1) {
			removeMeasurePreviewRect();
			return;
		}
		var p = fab.getPointer(opt.e);
		var b = boundsFromCorners(pts[0], p);
		updateMeasurePreviewRect(b, measureMode === "deduct");
	}

	function onFabricMouseDown(opt) {
		if (!fab || measureMode === "none") return;
		var p = fab.getPointer(opt.e);

		if (measureMode === "cal") {
			calPoints.push({ x: p.x, y: p.y });
			var c = new fabricLib.Circle({
				radius: 5,
				left: p.x,
				top: p.y,
				originX: "center",
				originY: "center",
				fill: "#ffc107",
				selectable: false,
				evented: false,
			});
			fab.add(c);
			if (calPoints.length >= 2) {
				var dPx = dist(calPoints[0], calPoints[1]);
				var lfStr = window.prompt("Known distance between the two marks (LF)", "10");
				if (lfStr == null) {
					setMeasureMode("none");
					return;
				}
				var lf = parseFloat(String(lfStr).replace(",", "."));
				if (isNaN(lf) || lf <= 0 || dPx <= 0) {
					if (window.USISNotify) window.USISNotify.error("Invalid calibration.");
					calPoints = [];
					fab.clear();
					setMeasureMode("none");
					return;
				}
				pixelsPerLf = dPx / lf;
				var ln = new fabricLib.Line([calPoints[0].x, calPoints[0].y, calPoints[1].x, calPoints[1].y], {
					stroke: "#ffc107",
					strokeWidth: 2,
					selectable: false,
					evented: false,
				});
				fab.add(ln);
				lastMeasurement = { tool: "calibration", summary: lf + " LF · " + dPx.toFixed(1) + " px", lf: lf, dPx: dPx };
				updateMeasureStatus();
				if (lastGrossShapeIndex >= 0) recomputeRectAreaSummary();
				if (window.USISNotify) window.USISNotify.success("Calibrated");
				setMeasureMode("none");
			}
			return;
		}

		if (measureMode === "line") {
			linePoints.push({ x: p.x, y: p.y });
			var dot = new fabricLib.Circle({
				radius: 3,
				left: p.x,
				top: p.y,
				originX: "center",
				originY: "center",
				fill: "#20c997",
				selectable: false,
				evented: false,
			});
			fab.add(dot);
			if (linePoints.length >= 2) {
				var a = linePoints[linePoints.length - 2];
				var b = linePoints[linePoints.length - 1];
				var seg = new fabricLib.Line([a.x, a.y, b.x, b.y], { stroke: "#20c997", strokeWidth: 2, selectable: false, evented: false });
				fab.add(seg);
			}
			return;
		}

		if (measureMode === "poly") {
			var closeThr = 14;
			if (polyPoints.length >= 3) {
				var first = polyPoints[0];
				if (dist(p, first) <= closeThr) {
					finalizePolygon();
					return;
				}
			}
			polyPoints.push({ x: p.x, y: p.y });
			var dotp = new fabricLib.Circle({
				radius: 3,
				left: p.x,
				top: p.y,
				originX: "center",
				originY: "center",
				fill: "#fd7e14",
				selectable: false,
				evented: false,
			});
			fab.add(dotp);
			if (polyPoints.length >= 2) {
				var ap = polyPoints[polyPoints.length - 2];
				var bp = polyPoints[polyPoints.length - 1];
				var segp = new fabricLib.Line([ap.x, ap.y, bp.x, bp.y], {
					stroke: "#fd7e14",
					strokeWidth: 2,
					selectable: false,
					evented: false,
				});
				fab.add(segp);
			}
			return;
		}

		if (measureMode === "rect") {
			if (rectPoints.length === 0) {
				rectPoints.push({ x: p.x, y: p.y });
				var cr0 = new fabricLib.Circle({
					radius: 4,
					left: p.x,
					top: p.y,
					originX: "center",
					originY: "center",
					fill: "#198754",
					selectable: false,
					evented: false,
				});
				fab.add(cr0);
				return;
			}
			var r0 = rectPoints[0];
			removeMeasurePreviewRect();
			var rbx = boundsFromCorners(r0, { x: p.x, y: p.y });
			var rmin = Math.min(rbx.maxX - rbx.minX, rbx.maxY - rbx.minY);
			if (rmin < 3) {
				if (window.USISNotify) window.USISNotify.warning("Rectangle too small — click two diagonal corners.");
				rectPoints = [];
				setMeasureMode("none");
				return;
			}
			finalizeRectGross(rbx);
			return;
		}

		if (measureMode === "deduct") {
			if (lastGrossShapeIndex < 0) {
				if (window.USISNotify) window.USISNotify.warning("Draw a gross Rectangle first, then add deductions.");
				setMeasureMode("none");
				return;
			}
			if (deductPoints.length === 0) {
				deductPoints.push({ x: p.x, y: p.y });
				var ddr = new fabricLib.Circle({
					radius: 4,
					left: p.x,
					top: p.y,
					originX: "center",
					originY: "center",
					fill: "#dc3545",
					selectable: false,
					evented: false,
				});
				fab.add(ddr);
				return;
			}
			var d0 = deductPoints[0];
			removeMeasurePreviewRect();
			var dbx = boundsFromCorners(d0, { x: p.x, y: p.y });
			var dmin = Math.min(dbx.maxX - dbx.minX, dbx.maxY - dbx.minY);
			if (dmin < 3) {
				if (window.USISNotify) window.USISNotify.warning("Deduction too small — try again.");
				deductPoints = [];
				setMeasureMode("none");
				return;
			}
			finalizeDeduction(dbx);
			return;
		}

		if (measureMode === "count") {
			var m = new fabricLib.Circle({
				radius: 6,
				left: p.x,
				top: p.y,
				originX: "center",
				originY: "center",
				fill: "rgba(13,110,253,0.35)",
				stroke: "#0d6efd",
				strokeWidth: 2,
				selectable: false,
				evented: false,
			});
			fab.add(m);
			countMarkers.push({ x: p.x, y: p.y });
			lastMeasurement = { tool: "count", summary: countMarkers.length + " EA", count: countMarkers.length };
			updateMeasureStatus();
		}
	}

	function onFabricDblClick() {
		if (measureMode === "line" && linePoints.length >= 2) {
			finalizeLinear();
		} else if (measureMode === "poly" && polyPoints.length >= 3) {
			finalizePolygon();
		}
	}

	function finalizeLinear() {
		var lenPx = polylineLengthPx(linePoints);
		var lf = null;
		if (pixelsPerLf != null && pixelsPerLf > 0) {
			lf = lenPx / pixelsPerLf;
		}
		lastMeasurement = {
			tool: "linear",
			summary: lf != null ? lf.toFixed(3) + " LF (from cal.)" : lenPx.toFixed(1) + " px (calibrate for LF)",
			points: linePoints.slice(),
			lengthPx: lenPx,
			lengthLf: lf,
			page: pageNum,
			scale: scale,
		};
		measurementShapes.push({
			type: "line",
			points: linePoints.slice(),
			lengthPx: lenPx,
			lengthLf: lf,
			page: pageNum,
			viewer_scale: scale,
		});
		updateMeasureStatus();
		var qIn = document.getElementById("usis-dv-takeoff-qty");
		if (qIn && lf != null) qIn.value = String(lf.toFixed(4));
		if (window.USISNotify) window.USISNotify.info("Linear path finished — review qty/unit, then Apply to line.");
		setMeasureMode("none");
	}

	function finalizePolygon() {
		if (polyPoints.length < 3) return;
		var areaPx = polygonAreaPx(polyPoints);
		var sf = null;
		if (pixelsPerLf != null && pixelsPerLf > 0) {
			sf = areaPx / (pixelsPerLf * pixelsPerLf);
		}
		var closed = polyPoints.slice();
		if (fab && fabricLib) {
			var minX = Infinity;
			var minY = Infinity;
			for (var i = 0; i < closed.length; i++) {
				if (closed[i].x < minX) minX = closed[i].x;
				if (closed[i].y < minY) minY = closed[i].y;
			}
			var rel = closed.map(function (pt) {
				return { x: pt.x - minX, y: pt.y - minY };
			});
			var polyShape = new fabricLib.Polygon(rel, {
				left: minX,
				top: minY,
				fill: "rgba(253,126,20,0.15)",
				stroke: "#fd7e14",
				strokeWidth: 2,
				selectable: false,
				evented: false,
			});
			fab.add(polyShape);
		}
		lastMeasurement = {
			tool: "area",
			summary: sf != null ? sf.toFixed(3) + " SF (from cal.)" : areaPx.toFixed(1) + " px² (calibrate for SF)",
			polygon: closed,
			areaPx: areaPx,
			areaSf: sf,
			page: pageNum,
			scale: scale,
		};
		measurementShapes.push({
			type: "poly",
			polygon: closed.slice(),
			areaPx: areaPx,
			areaSf: sf,
			page: pageNum,
			viewer_scale: scale,
		});
		updateMeasureStatus();
		var qIn = document.getElementById("usis-dv-takeoff-qty");
		if (qIn && sf != null) qIn.value = String(sf.toFixed(4));
		var uIn = document.getElementById("usis-dv-takeoff-unit");
		if (uIn && sf != null) uIn.value = "SF";
		if (window.USISNotify) window.USISNotify.info("Area closed — review qty/unit, then Apply to line.");
		polyPoints = [];
		setMeasureMode("none");
	}

	function wireMeasureToolbar() {
		var bNone = document.getElementById("usis-dv-m-none");
		var bCal = document.getElementById("usis-dv-m-cal");
		var bLine = document.getElementById("usis-dv-m-line");
		var bPoly = document.getElementById("usis-dv-m-poly");
		var bRect = document.getElementById("usis-dv-m-rect");
		var bDeduct = document.getElementById("usis-dv-m-deduct");
		var bCount = document.getElementById("usis-dv-m-count");
		var bClr = document.getElementById("usis-dv-m-clear");
		var bDone = document.getElementById("usis-dv-m-done");
		if (bNone)
			bNone.addEventListener("click", function () {
				setMeasureMode("none");
			});
		if (bCal)
			bCal.addEventListener("click", function () {
				if (!fabricLib) {
					if (window.USISNotify) window.USISNotify.error("Fabric.js not loaded.");
					return;
				}
				resetRectDraft();
				calPoints = [];
				setMeasureMode("cal");
				if (window.USISNotify) window.USISNotify.info("Calibration: click two points along a known length.");
			});
		if (bLine)
			bLine.addEventListener("click", function () {
				if (!fabricLib) return;
				resetRectDraft();
				linePoints = [];
				polyPoints = [];
				setMeasureMode("line");
				if (window.USISNotify) window.USISNotify.info("Linear: click vertices; double-click or Done to finish.");
			});
		if (bPoly)
			bPoly.addEventListener("click", function () {
				if (!fabricLib) return;
				resetRectDraft();
				polyPoints = [];
				linePoints = [];
				setMeasureMode("poly");
				if (window.USISNotify)
					window.USISNotify.info("Area: click corners; double-click, Done, or click near first point to close.");
			});
		if (bRect)
			bRect.addEventListener("click", function () {
				if (!fabricLib) return;
				resetRectDraft();
				linePoints = [];
				polyPoints = [];
				setMeasureMode("rect");
				if (window.USISNotify)
					window.USISNotify.info("Rectangle: first corner, then opposite diagonal (live preview while you move).");
			});
		if (bDeduct)
			bDeduct.addEventListener("click", function () {
				if (!fabricLib) return;
				if (lastGrossShapeIndex < 0) {
					if (window.USISNotify) window.USISNotify.warning("Place a gross Rectangle first.");
					return;
				}
				resetRectDraft();
				setMeasureMode("deduct");
				if (window.USISNotify)
					window.USISNotify.info("Deduction: two clicks for inner rectangle (subtracted from last gross).");
			});
		if (bCount)
			bCount.addEventListener("click", function () {
				if (!fabricLib) return;
				countMarkers = [];
				if (fab) fab.clear();
				setMeasureMode("count");
			});
		if (bClr)
			bClr.addEventListener("click", function () {
				linePoints = [];
				polyPoints = [];
				calPoints = [];
				countMarkers = [];
				pixelsPerLf = null;
				lastMeasurement = null;
				measurementShapes = [];
				lastGrossShapeIndex = -1;
				resetRectDraft();
				if (fab) fab.clear();
				setMeasureMode("none");
				updateMeasureStatus();
			});
		if (bDone)
			bDone.addEventListener("click", function () {
				if (measureMode === "line" && linePoints.length >= 2) finalizeLinear();
				else if (measureMode === "poly" && polyPoints.length >= 3) finalizePolygon();
			});
	}

	function canDeleteDrawings() {
		return window.__usisDvCanDeleteDrawings === true;
	}

	function setDeleteButtonsVisible(show) {
		["usis-dv-delete-revision", "usis-dv-delete-sheet"].forEach(function (id) {
			var el = document.getElementById(id);
			if (el) el.classList.toggle("d-none", !show);
		});
	}

	function loadDeletePermission() {
		fetch(apiBase() + "/api/v1/me", { credentials: "include", headers: { Accept: "application/json" } })
			.then(function (res) {
				return res.json().then(function (j) {
					return { ok: res.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) return;
				var caps = (res.body && res.body.capabilities) || {};
				var mods = caps.modules || {};
				var level = mods.projects || "none";
				var rank = { none: 0, read: 1, write: 2, admin: 3 };
				window.__usisDvCanDeleteDrawings =
					!!caps.is_superuser || (rank[level] || 0) >= rank.write;
				setDeleteButtonsVisible(canDeleteDrawings());
			})
			.catch(function () {});
	}

	function afterDrawingDeleted(scope, deletedId) {
		if (scope === "revision" && revisions.length > 1) {
			var remaining = revisions.filter(function (r) {
				return r.id !== deletedId;
			});
			if (remaining.length) {
				var nextIx = Math.min(revIndex, remaining.length - 1);
				activeDrawingId = remaining[nextIx].id;
				var u = new URL(window.location.href);
				u.searchParams.set("drawing_id", activeDrawingId);
				window.history.replaceState({}, "", u.pathname + u.search);
				loadRevisionsAndPdf();
				return;
			}
		}
		activeDrawingId = null;
		revisions = [];
		revIndex = 0;
		if (pdfDoc) {
			try {
				pdfDoc.destroy();
			} catch (e) {}
			pdfDoc = null;
		}
		var u2 = new URL(window.location.href);
		u2.searchParams.delete("drawing_id");
		window.history.replaceState({}, "", u2.pathname + u2.search);
		showErr("Drawing deleted. Select another sheet to open.");
		showPicker();
	}

	function deleteDrawing(scope) {
		var did = currentRevisionDrawingId();
		if (!did) {
			if (window.USISNotify) window.USISNotify.error("No drawing loaded.");
			return;
		}
		var r = revisions[revIndex];
		var label =
			scope === "series"
				? "Delete this entire sheet and all " +
				  revisions.length +
				  " revision(s)? This cannot be undone."
				: "Delete revision " +
				  (r && r.revision != null ? String(r.revision) : "?") +
				  " only? Other revisions for this sheet will remain.";
		if (!window.confirm(label)) return;
		fetch(apiBase() + "/api/v1/drawings/" + encodeURIComponent(did) + "/delete", {
			method: "POST",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify({ scope: scope, confirm: true }),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					return { ok: res.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					var msg = (res.body && res.body.error) || "Delete failed (" + res.status + ").";
					if (window.USISNotify) window.USISNotify.error(msg);
					else showErr(msg);
					return;
				}
				if (window.USISNotify) {
					window.USISNotify.success(
						scope === "series"
							? "Sheet deleted (" + (res.body.deleted || 0) + " revision(s))."
							: "Revision deleted."
					);
				}
				afterDrawingDeleted(scope, did);
			})
			.catch(function () {
				if (window.USISNotify) window.USISNotify.error("Network error deleting drawing.");
			});
	}

	function wireUi() {
		loadDeletePermission();
		var sel = document.getElementById("usis-dv-revision");
		if (sel) {
			sel.addEventListener("change", function () {
				var v = parseInt(sel.value, 10);
				if (!isNaN(v)) setRevIndex(v, true);
			});
		}
		var bNew = document.getElementById("usis-dv-rev-newer");
		var bOld = document.getElementById("usis-dv-rev-older");
		if (bNew) bNew.addEventListener("click", goNewer);
		if (bOld) bOld.addEventListener("click", goOlder);
		var bDelRev = document.getElementById("usis-dv-delete-revision");
		var bDelSheet = document.getElementById("usis-dv-delete-sheet");
		if (bDelRev) {
			bDelRev.addEventListener("click", function () {
				deleteDrawing("revision");
			});
		}
		if (bDelSheet) {
			bDelSheet.addEventListener("click", function () {
				deleteDrawing("series");
			});
		}
		var zIn = document.getElementById("usis-dv-zoom-in");
		var zOut = document.getElementById("usis-dv-zoom-out");
		if (zIn) {
			zIn.addEventListener("click", function () {
				scale = Math.min(scale * 1.15, 4);
				updateZoomLabel();
				queueRenderPage();
			});
		}
		if (zOut) {
			zOut.addEventListener("click", function () {
				scale = Math.max(scale / 1.15, 0.35);
				updateZoomLabel();
				queueRenderPage();
			});
		}
		var pn = document.getElementById("usis-dv-page-next");
		var pp = document.getElementById("usis-dv-page-prev");
		if (pn) {
			pn.addEventListener("click", function () {
				if (!pdfDoc) return;
				if (pageNum < pdfDoc.numPages) {
					pageNum++;
					clearMeasureGeometry();
					queueRenderPage();
				}
			});
		}
		if (pp) {
			pp.addEventListener("click", function () {
				if (pageNum > 1) {
					pageNum--;
					clearMeasureGeometry();
					queueRenderPage();
				}
			});
		}
		var annAdd = document.getElementById("usis-dv-ann-add");
		if (annAdd) {
			annAdd.addEventListener("click", function () {
				var did = currentRevisionDrawingId();
				if (!did) return;
				var text = window.prompt("Note text", "");
				if (text == null || !String(text).trim()) return;
				fetch(apiBase() + "/api/v1/drawings/" + encodeURIComponent(did) + "/annotations", {
					method: "POST",
					headers: { "Content-Type": "application/json", Accept: "application/json" },
					credentials: "include",
					body: JSON.stringify({ type: "user_note", data: { text: String(text).trim() } }),
				})
					.then(function (res) {
						return res.json().then(function (j) {
							if (!res.ok) throw new Error(j.error || res.status);
							return j;
						});
					})
					.then(function () {
						loadAnnotations();
						if (window.USISNotify) window.USISNotify.success("Note saved");
					})
					.catch(function (e) {
						if (window.USISNotify) window.USISNotify.error(String(e.message || e));
					});
			});
		}
		var aiStub = document.getElementById("usis-dv-ai-stub");
		if (aiStub) {
			aiStub.addEventListener("click", function () {
				var did = currentRevisionDrawingId();
				if (window.aiReviewBus && did) {
					window.aiReviewBus.emit("review_requested", {
						mode: "construction_review",
						drawing_id: did,
					});
				}
				if (window.USISNotify) window.USISNotify.info("AI review requested (stub — Plan 12).");
			});
		}
		var takeoffSave = document.getElementById("usis-dv-takeoff-save");
		if (takeoffSave) {
			takeoffSave.addEventListener("click", applyTakeoffPatch);
		}
		var takeoffNew = document.getElementById("usis-dv-takeoff-new");
		if (takeoffNew) {
			takeoffNew.addEventListener("click", createNewTakeoffLine);
		}
		wireTakeoffLineModal();
		var fsClose = document.getElementById("usis-dv-fs-close");
		if (fsClose) {
			fsClose.addEventListener("click", function () {
				var backEl = document.getElementById("usis-dv-back");
				var href = backEl && backEl.getAttribute("href");
				if (href && href.indexOf("javascript:") !== 0) {
					try {
						window.location.href = new URL(href, document.baseURI).href;
						return;
					} catch (e) {
						window.location.href = href;
						return;
					}
				}
				if (window.history.length > 1) window.history.back();
			});
		}
		document.addEventListener("keydown", onKeyDown);
		wireMeasureToolbar();
	}

	function buildMeasurementShapesForPatch() {
		var out = measurementShapes.slice();
		if (countMarkers.length) {
			out.push({
				type: "count",
				markers: countMarkers.map(function (m) {
					return { x: m.x, y: m.y };
				}),
				count: countMarkers.length,
				page: pageNum,
				viewer_scale: scale,
			});
		}
		return out;
	}

	function buildMeasurementPayload() {
		var did = currentRevisionDrawingId();
		return {
			version: 1,
			calibration: { pixels_per_lf: pixelsPerLf },
			shapes: buildMeasurementShapesForPatch(),
			tool: "fabric_mvp",
			page: pageNum,
			viewer_scale: scale,
			revision_id: did,
			pixels_per_lf: pixelsPerLf,
			last: lastMeasurement,
		};
	}

	function applyTakeoffPatch() {
		if (!takeoffLineId) {
			if (window.USISNotify)
				window.USISNotify.info("Select a takeoff in the left list, or click New takeoff.");
			return;
		}
		var did = currentRevisionDrawingId();
		if (!did) {
			if (window.USISNotify) window.USISNotify.error("No drawing revision loaded.");
			return;
		}
		var qIn = document.getElementById("usis-dv-takeoff-qty");
		var uIn = document.getElementById("usis-dv-takeoff-unit");
		var qStr = qIn && qIn.value != null ? String(qIn.value).trim() : "";
		var qty = parseFloat(qStr.replace(",", "."));
		if (isNaN(qty) || qty < 0) {
			if (window.USISNotify) window.USISNotify.error("Enter a valid quantity.");
			return;
		}
		var unit = uIn && uIn.value ? String(uIn.value).trim().slice(0, 50) : "EA";
		if (!unit) unit = "EA";
		var measurement_data = buildMeasurementPayload();
		fetch(apiBase() + "/api/v1/takeoff-lines/" + encodeURIComponent(takeoffLineId), {
			method: "PATCH",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			credentials: "include",
			body: JSON.stringify({
				drawing_id: did,
				quantity: qty,
				unit: unit,
				measurement_data: measurement_data,
			}),
		})
			.then(function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.status);
					return j;
				});
			})
			.then(function () {
				if (window.USISNotify) window.USISNotify.success("Takeoff line updated");
				loadTakeoffLineSummary();
				loadProjectTakeoffList();
			})
			.catch(function (e) {
				if (window.USISNotify) window.USISNotify.error(String(e.message || e));
			});
	}

	function loadRevisionsAndPdf() {
		_usisDbg("A", "drawing-viewer.js:loadRevisionsAndPdf", "fetch_revisions_start", {
			activeDrawingId: activeDrawingId,
		});
		setLoading(true, "revisions");
		withTimeout(
			fetchJson("/api/v1/drawings/" + encodeURIComponent(activeDrawingId) + "/revisions"),
			60000,
			"Loading revisions timed out — check API and network."
		)
			.then(function (data) {
				revisions = data.revisions || [];
				_usisDbg("A", "drawing-viewer.js:loadRevisionsAndPdf", "revisions_response", {
					count: revisions.length,
					firstId: revisions[0] && revisions[0].id,
					firstHasFileUrl: !!(revisions[0] && revisions[0].file_url),
				});
				setLoading(false);
				if (!revisions.length) {
					_usisDbg("A", "drawing-viewer.js:loadRevisionsAndPdf", "revisions_empty", {});
					showErr("No revisions returned.");
					return;
				}
				var ix = revisions.findIndex(function (r) {
					return r.id === activeDrawingId;
				});
				revIndex = ix >= 0 ? ix : 0;
				fillRevisionSelect();
				updateSheetLine();
				renderSheetsList();
				loadPdfFromRevision();
				loadAnnotations();
				loadProjectTakeoffList();
			})
			.catch(function (err) {
				_usisDbg("A", "drawing-viewer.js:loadRevisionsAndPdf", "revisions_fetch_fail", {
					err: err && err.message ? err.message : String(err),
				});
				setLoading(false);
				showErr(err.message || String(err));
			});
	}

	function showPicker() {
		var wrap = document.getElementById("usis-dv-picker-wrap");
		var card = document.getElementById("usis-dv-picker");
		var sel = document.getElementById("usis-dv-pick-drawing");
		if (!card || !sel || !projectId) return;
		if (wrap) wrap.classList.remove("d-none");
		card.classList.remove("d-none");
		sel.innerHTML = '<option value="">Loading…</option>';
		fetchJson("/api/v1/projects/" + encodeURIComponent(projectId) + "/drawings?limit=500&offset=0")
			.then(function (data) {
				var items = data.items || [];
				sel.innerHTML = "";
				if (!items.length) {
					sel.innerHTML = '<option value="">No drawings in project</option>';
					return;
				}
				items.forEach(function (row) {
					var cur = row.current_revision || {};
					var id = cur.id || row.id || row.drawing_id;
					if (!id) return;
					var o = document.createElement("option");
					o.value = String(id);
					o.textContent = (row.sheet_number || "?") + " — " + (row.sheet_title || row.title || id);
					sel.appendChild(o);
				});
			})
			.catch(function () {
				sel.innerHTML = '<option value="">Could not load drawings</option>';
			});
	}

	function wirePickerOnce() {
		var openBtn = document.getElementById("usis-dv-pick-open");
		var sel = document.getElementById("usis-dv-pick-drawing");
		if (!openBtn || openBtn.dataset.usisWired) return;
		openBtn.dataset.usisWired = "1";
		openBtn.addEventListener("click", function () {
			var card = document.getElementById("usis-dv-picker");
			if (!sel || !card) return;
			var v = sel.value;
			if (!v) {
				if (window.USISNotify) window.USISNotify.warning("Select a drawing first.");
				return;
			}
			activeDrawingId = v;
			card.classList.add("d-none");
			var wrap = document.getElementById("usis-dv-picker-wrap");
			if (wrap) wrap.classList.add("d-none");
			showErr("");
			loadRevisionsAndPdf();
		});
	}

	function init() {
		var q = new URLSearchParams(window.location.search);
		projectId = q.get("project_id");
		activeDrawingId = q.get("drawing_id");
		takeoffLineId = (q.get("takeoff_line") || "").trim() || null;
		_usisDbg("E", "drawing-viewer.js:init", "init_query", {
			projectId: projectId,
			activeDrawingId: activeDrawingId,
			hasPdfjsLib: !!window.pdfjsLib,
			origin: window.location && window.location.origin,
		});
		var back = document.getElementById("usis-dv-back");
		if (back && projectId) {
			back.setAttribute("href", "construction/project-detail.html?id=" + encodeURIComponent(projectId));
		}
		if (!pdfjsLib) {
			_usisDbg("C", "drawing-viewer.js:init", "pdfjsLib_missing", {});
			showErr("PDF.js failed to load from CDN.");
			return;
		}
		if (pdfjsLib.GlobalWorkerOptions) {
			pdfjsLib.GlobalWorkerOptions.workerSrc = resolveAgainstDocumentBase(
				"assets/vendor/pdfjs-3.11/pdf.worker.min.js"
			);
		}
		wireUi();
		wirePickerOnce();
		loadProjectTakeoffList();
		refreshTakeoffStrip();
		setMeasureMode("none");

		if (!activeDrawingId) {
			_usisDbg("E", "drawing-viewer.js:init", "no_drawing_id_branch", { hasProjectId: !!projectId });
			if (projectId) {
				showErr("");
				showPicker();
			} else {
				showErr(
					"Add drawing_id to the URL (from Project detail → Drawings → open a sheet), or add project_id to pick a drawing here."
				);
			}
			return;
		}
		_usisDbg("E", "drawing-viewer.js:init", "calling_loadRevisionsAndPdf", {});
		loadRevisionsAndPdf();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
