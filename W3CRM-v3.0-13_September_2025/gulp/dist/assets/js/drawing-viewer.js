/**
 * Full-page PDF drawing viewer with revision navigation (Procore-style).
 * Query: ?project_id=&drawing_id=  (drawing_id = any revision in the series)
 * Optional: &takeoff_line=<takeoff_line_items.id> — persist quantity / measurement via PATCH.
 */
(function () {
	"use strict";

	var pdfjsLib = window.pdfjsLib;
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

	function apiBase() {
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			var s = window.USIS_API_BASE.trim().replace(/\/$/, "");
			try {
				if (s && new URL(s).origin === window.location.origin) {
					/* use auto */
				} else if (s) {
					return s;
				}
			} catch (e) {
				if (s) return s;
			}
		}
		var loc = window.location;
		if (loc.protocol === "file:") {
			return "http://127.0.0.1:5000";
		}
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		var port = String(loc.port || "");
		var devPorts = { 3000: 1, 3001: 1, 3002: 1, 4173: 1, 5173: 1, 5174: 1, 5500: 1, 5501: 1, 8080: 1, 4200: 1, 4321: 1, 9630: 1, 1234: 1 };
		if (devPorts[port]) {
			return proto + "//" + host + ":5000";
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
		return fetch(base + path, { credentials: "omit" }).then(function (res) {
			if (!res.ok) {
				return res.text().then(function (t) {
					throw new Error(res.status + " " + (t || res.statusText));
				});
			}
			return res.json();
		});
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

	function setLoading(on) {
		var el = document.getElementById("usis-dv-loading");
		if (el) el.classList.toggle("d-none", !on);
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

	function loadPdfFromRevision() {
		var r = revisions[revIndex];
		if (!r || !r.file_url) {
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
			return;
		}
		showErr("");
		setLoading(true);
		if (pdfjsLib && pdfjsLib.GlobalWorkerOptions) {
			pdfjsLib.GlobalWorkerOptions.workerSrc =
				"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
		}
		var pdfSrc = (function () {
			var raw = r.file_url;
			if (raw == null || raw === "") return "";
			var s = String(raw).trim();
			if (!s) return "";
			if (/^https?:\/\//i.test(s)) return s;
			var b = apiBase();
			return b + (s.charAt(0) === "/" ? s : "/" + s);
		})();
		var loadingTask = pdfjsLib.getDocument({ url: pdfSrc, withCredentials: false });
		loadingTask.promise
			.then(function (doc) {
				pdfDoc = doc;
				pageNum = 1;
				setLoading(false);
				queueRenderPage();
				updatePageLabel();
				updateZoomLabel();
			})
			.catch(function (e) {
				setLoading(false);
				pdfDoc = null;
				showErr(
					"Could not load PDF (CORS or network). Open the PDF link instead. " +
						(e && e.message ? e.message : String(e))
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
		if (!strip) return;
		if (takeoffLineId) {
			strip.classList.remove("d-none");
			loadTakeoffLineSummary();
		} else {
			strip.classList.add("d-none");
		}
	}

	function loadTakeoffLineSummary() {
		var el = document.getElementById("usis-dv-takeoff-summary");
		if (!el || !takeoffLineId) return;
		if (!projectId) {
			el.textContent = takeoffLineId + " — add project_id to the URL to load line details.";
			return;
		}
		el.textContent = "Loading…";
		fetch(apiBase() + "/api/v1/projects/" + encodeURIComponent(projectId) + "/takeoff-lines", { credentials: "omit" })
			.then(function (res) {
				return res.json();
			})
			.then(function (d) {
				var line = (d.items || []).find(function (x) {
					return String(x.id) === String(takeoffLineId);
				});
				if (line) {
					el.textContent =
						(line.description || "(no description)") +
						" · qty " +
						line.quantity +
						" " +
						(line.unit || "") +
						" · ext " +
						(line.extended_total != null ? line.extended_total : "—");
				} else {
					el.textContent =
						"Line id not in this project's takeoff list — verify project_id matches the line's project.";
				}
			})
			.catch(function () {
				el.textContent = "Could not load takeoff lines.";
			});
	}

	function wireUi() {
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
					queueRenderPage();
				}
			});
		}
		if (pp) {
			pp.addEventListener("click", function () {
				if (pageNum > 1) {
					pageNum--;
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
					headers: { "Content-Type": "application/json" },
					credentials: "omit",
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
			takeoffSave.addEventListener("click", function () {
				if (!takeoffLineId) {
					if (window.USISNotify) window.USISNotify.info("Open the viewer with takeoff_line= in the URL.");
					return;
				}
				var did = currentRevisionDrawingId();
				if (!did) {
					if (window.USISNotify) window.USISNotify.error("No drawing revision loaded.");
					return;
				}
				var qStr = window.prompt("Quantity to store on this takeoff line", "10");
				if (qStr === null) return;
				var qty = parseFloat(String(qStr).replace(",", "."));
				if (isNaN(qty) || qty < 0) {
					if (window.USISNotify) window.USISNotify.error("Invalid quantity.");
					return;
				}
				var unit = window.prompt("Unit of measure (e.g. LF, SF, EA)", "LF");
				if (unit === null) return;
				unit = String(unit).trim().slice(0, 50) || "EA";
				var measurement_data = {
					tool: "viewer_stub",
					page: pageNum,
					viewer_scale: scale,
					revision_id: did,
				};
				fetch(apiBase() + "/api/v1/takeoff-lines/" + encodeURIComponent(takeoffLineId), {
					method: "PATCH",
					headers: { "Content-Type": "application/json" },
					credentials: "omit",
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
					})
					.catch(function (e) {
						if (window.USISNotify) window.USISNotify.error(String(e.message || e));
					});
			});
		}
		document.addEventListener("keydown", onKeyDown);
	}

	function init() {
		var q = new URLSearchParams(window.location.search);
		projectId = q.get("project_id");
		activeDrawingId = q.get("drawing_id");
		takeoffLineId = (q.get("takeoff_line") || "").trim();
		var back = document.getElementById("usis-dv-back");
		if (back && projectId) {
			back.setAttribute("href", "construction/project-detail.html?id=" + encodeURIComponent(projectId));
		}
		if (!pdfjsLib) {
			showErr("PDF.js failed to load from CDN.");
			return;
		}
		if (!activeDrawingId) {
			showErr("Missing drawing_id in URL.");
			return;
		}
		wireUi();
		refreshTakeoffStrip();
		setLoading(true);
		fetchJson("/api/v1/drawings/" + encodeURIComponent(activeDrawingId) + "/revisions")
			.then(function (data) {
				setLoading(false);
				revisions = data.revisions || [];
				if (!revisions.length) {
					showErr("No revisions returned.");
					return;
				}
				var ix = revisions.findIndex(function (r) {
					return r.id === activeDrawingId;
				});
				revIndex = ix >= 0 ? ix : 0;
				fillRevisionSelect();
				updateSheetLine();
				loadPdfFromRevision();
				loadAnnotations();
			})
			.catch(function (err) {
				setLoading(false);
				showErr(err.message || String(err));
			});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
