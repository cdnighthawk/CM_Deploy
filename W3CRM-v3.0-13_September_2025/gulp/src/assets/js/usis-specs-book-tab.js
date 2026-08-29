/**
 * Specs book as a drawing-style table. Click a section to open a PDF viewer
 * popup (zoom / pan / pages only — no takeoff tools).
 * Mount with USISSpecsBook.mount(containerElement, projectId, options?).
 */
(function (global) {
	"use strict";

	function metaApiBase() {
		var m = document.querySelector('meta[name="usis-api-base"]');
		if (!m) return null;
		var c = (m.getAttribute("content") || "").trim().replace(/\/$/, "");
		return c || null;
	}

	function apiBase() {
		var loc = global.location;
		var devPorts = {
			3000: 1,
			3001: 1,
			3002: 1,
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

		function isLoopbackHost(h) {
			return h === "localhost" || h === "127.0.0.1" || h === "[::1]" || h === "::1";
		}

		function flaskDevBase() {
			if (loc.protocol === "file:") {
				return "http://127.0.0.1:5000";
			}
			var host = loc.hostname || "";
			var proto = loc.protocol || "http:";
			var port = String(loc.port || "");
			if (devPorts[port]) {
				return proto + "//" + host + ":5000";
			}
			var loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
			if (loopback) {
				if (port === "5000") {
					return "";
				}
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

		function resolveOverride(s) {
			if (!s || !String(s).trim()) return null;
			var t = String(s).trim().replace(/\/$/, "");
			try {
				var u = new URL(t);
				if (u.origin === loc.origin) {
					return flaskDevBase();
				}
				if (isLoopbackHost(u.hostname) && devPorts[String(u.port || "")]) {
					var p = loc.protocol || "http:";
					return p + "//" + (loc.hostname || u.hostname) + ":5000";
				}
				return t;
			} catch (e) {
				return t;
			}
		}

		if (typeof global.USIS_API_BASE === "string" && global.USIS_API_BASE.trim()) {
			var w = resolveOverride(global.USIS_API_BASE);
			if (w !== null) return w;
		}
		var fromMeta = metaApiBase();
		if (fromMeta) {
			var m = resolveOverride(fromMeta);
			if (m !== null) return m;
		}
		return flaskDevBase();
	}

	function actorHeaders() {
		var id = null;
		try {
			id = global.localStorage.getItem("usisActorUserId");
		} catch (e) {}
		if (id && id.trim()) {
			return { "X-Usis-User-Id": id.trim() };
		}
		return {};
	}

	function jsonFetchHeaders() {
		return Object.assign(
			{ "Content-Type": "application/json", Accept: "application/json" },
			actorHeaders()
		);
	}

	function apiErrorText(res, bodyText) {
		var raw = (bodyText || "").trim();
		if (raw) {
			try {
				var parsed = JSON.parse(raw);
				if (parsed && parsed.error) return String(parsed.error);
				if (parsed && parsed.message) return String(parsed.message);
			} catch (e) {}
		}
		return raw || res.statusText || String(res.status);
	}

	function resolveUrl(u) {
		if (!u) return "";
		var s = String(u).trim();
		if (!s) return "";
		if (/^https?:\/\//i.test(s)) return s;
		var b = apiBase();
		return b + (s.charAt(0) === "/" ? s : "/" + s);
	}

	function resolveAgainstDocumentBase(relPath) {
		var rp = relPath == null ? "" : String(relPath).trim();
		if (!rp) return rp;
		try {
			return new URL(rp, document.baseURI).href;
		} catch (e) {
			return rp;
		}
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	var CSI_DIVISION_NAMES = {
		"00": "Procurement and Contracting Requirements",
		"01": "General Requirements",
		"02": "Existing Conditions",
		"03": "Concrete",
		"04": "Masonry",
		"05": "Metals",
		"06": "Wood, Plastics, and Composites",
		"07": "Thermal and Moisture Protection",
		"08": "Openings",
		"09": "Finishes",
		"10": "Specialties",
		"11": "Equipment",
		"12": "Furnishings",
		"13": "Special Construction",
		"14": "Conveying Equipment",
		"15": "Reserved for Future Expansion",
		"16": "Reserved for Future Expansion",
		"17": "Reserved for Future Expansion",
		"18": "Reserved for Future Expansion",
		"19": "Reserved for Future Expansion",
		"20": "Reserved for Future Expansion",
		"21": "Fire Suppression",
		"22": "Plumbing",
		"23": "Heating, Ventilating, and Air Conditioning (HVAC)",
		"24": "Reserved for Future Expansion",
		"25": "Integrated Automation",
		"26": "Electrical",
		"27": "Communications",
		"28": "Electronic Safety and Security",
		"29": "Reserved for Future Expansion",
		"30": "Reserved for Future Expansion",
		"31": "Earthwork",
		"32": "Exterior Improvements",
		"33": "Utilities",
		"34": "Transportation",
		"35": "Waterway and Marine Construction",
		"36": "Reserved for Future Expansion",
		"37": "Reserved for Future Expansion",
		"38": "Reserved for Future Expansion",
		"39": "Reserved for Future Expansion",
		"40": "Process Interconnections",
		"41": "Material Processing and Handling Equipment",
		"42": "Process Heating, Cooling, and Drying Equipment",
		"43": "Process Gas and Liquid Handling, Purification and Storage Equipment",
		"44": "Pollution and Waste Control Equipment",
		"45": "Industry-Specific Manufacturing Equipment",
		"46": "Water and Wastewater Equipment",
		"47": "Reserved for Future Expansion",
		"48": "Electrical Power Generation",
		"49": "Reserved for Future Expansion",
	};

	function csiDivisionMeta(code) {
		var c = String(code || "").trim();
		var m = c.match(/^(\d{2})/);
		if (!m) return { key: "other", num: "", name: "Other" };
		return {
			key: m[1],
			num: m[1],
			name: CSI_DIVISION_NAMES[m[1]] || "Division " + m[1],
		};
	}

	function divisionBoxLabel(meta, count) {
		var name = meta.name || "Other";
		if (meta.num) return meta.num + " - " + name + " (" + count + ")";
		return name + " (" + count + ")";
	}

	function sortDivisionKeys(keys) {
		return keys.slice().sort(function (a, b) {
			if (a === "other") return 1;
			if (b === "other") return -1;
			return String(a).localeCompare(String(b));
		});
	}

	function decorateSection(row) {
		var meta = csiDivisionMeta(row && row.code);
		var pdf = row && row.pdf_url ? String(row.pdf_url).trim() : "";
		return Object.assign({}, row, {
			division_key: meta.key,
			division_label: meta.num ? meta.num + " - " + meta.name : meta.name,
			has_pdf: !!pdf,
		});
	}

	function specDivisionGroup(data) {
		return (data && data.division_label) || "Other";
	}

	function pdfDocumentOptions(pdfSrc) {
		var opts = {
			url: pdfSrc,
			withCredentials: false,
			disableRange: true,
			disableStream: true,
		};
		try {
			var pageOrigin = global.location.origin;
			var docOrigin = new URL(pdfSrc, pageOrigin).origin;
			var b = apiBase();
			if (/\/api\/v1\/(spec-sections|documents|drawings)\//i.test(pdfSrc)) {
				opts.withCredentials = true;
			} else if (b) {
				var apiOrigin = new URL(b, pageOrigin).origin;
				if (docOrigin === apiOrigin || docOrigin === pageOrigin) opts.withCredentials = true;
			} else if (docOrigin === pageOrigin) {
				opts.withCredentials = true;
			}
		} catch (e) {
			if (/\/api\/v1\//i.test(String(pdfSrc))) opts.withCredentials = true;
		}
		return opts;
	}

	function ensurePdfJs() {
		return new Promise(function (resolve, reject) {
			if (global.pdfjsLib) {
				if (global.pdfjsLib.GlobalWorkerOptions) {
					global.pdfjsLib.GlobalWorkerOptions.workerSrc = resolveAgainstDocumentBase(
						"assets/vendor/pdfjs-3.11/pdf.worker.min.js"
					);
				}
				resolve(global.pdfjsLib);
				return;
			}
			var s = document.createElement("script");
			s.src = resolveAgainstDocumentBase("assets/vendor/pdfjs-3.11/pdf.min.js");
			s.onload = function () {
				if (!global.pdfjsLib) {
					reject(new Error("PDF.js failed to load."));
					return;
				}
				if (global.pdfjsLib.GlobalWorkerOptions) {
					global.pdfjsLib.GlobalWorkerOptions.workerSrc = resolveAgainstDocumentBase(
						"assets/vendor/pdfjs-3.11/pdf.worker.min.js"
					);
				}
				resolve(global.pdfjsLib);
			};
			s.onerror = function () {
				reject(new Error("PDF.js failed to load from assets/vendor/pdfjs-3.11."));
			};
			document.head.appendChild(s);
		});
	}

	function collapsedStoreKey(projectId) {
		return "usis-specs-div-collapsed:" + String(projectId || "");
	}

	function readCollapsedMap(projectId) {
		try {
			var raw = sessionStorage.getItem(collapsedStoreKey(projectId));
			return raw ? JSON.parse(raw) : {};
		} catch (e) {
			return {};
		}
	}

	function writeCollapsedMap(projectId, map) {
		try {
			sessionStorage.setItem(collapsedStoreKey(projectId), JSON.stringify(map || {}));
		} catch (e) {}
	}

	function viewerHref(projectId, specId) {
		var parts = ["project_id=" + encodeURIComponent(projectId || "")];
		if (specId) parts.push("spec_id=" + encodeURIComponent(specId));
		return "construction/specs-viewer.html?" + parts.join("&");
	}

	function mount(container, projectId, options) {
		if (!container || !projectId) return;
		var opts = options || {};
		var selectedId = null;
		var sections = [];
		var pendingAttachId = null;
		var table = null;
		var catalogItems = [];
		var catalogTimer = null;
		var autoSpecId = opts.specId || null;
		if (!autoSpecId) {
			try {
				autoSpecId = new URLSearchParams(global.location.search).get("spec_id");
			} catch (e) {
				autoSpecId = null;
			}
		}

		var overlayId = "usis-sv-overlay";
		var oldOverlay = document.getElementById(overlayId);
		if (oldOverlay && oldOverlay.parentNode) oldOverlay.parentNode.removeChild(oldOverlay);

		container.innerHTML =
			'<div class="usis-specs-book">' +
			'<div class="d-flex flex-wrap align-items-end gap-2 mb-2">' +
			'<button type="button" class="btn btn-sm btn-primary usis-specs-add">Add from CSI catalog</button>' +
			'<button type="button" class="btn btn-sm btn-outline-primary usis-specs-import-book">Import spec book PDF</button>' +
			'<input type="file" class="d-none usis-specs-book-file" accept="application/pdf,.pdf">' +
			'<input type="file" class="d-none usis-specs-file" accept="application/pdf,.pdf">' +
			'<div class="flex-grow-1" style="min-width:12rem;max-width:22rem;">' +
			'<label class="form-label small text-muted mb-0">Search</label>' +
			'<input type="search" class="form-control form-control-sm usis-specs-q" placeholder="CSI code or title…" autocomplete="off">' +
			"</div>" +
			"</div>" +
			'<div class="usis-draw-group-toolbar d-flex flex-wrap align-items-center gap-2 mb-2">' +
			'<button type="button" class="btn btn-link btn-sm p-0 usis-specs-expand-all">Expand all</button>' +
			'<span class="text-muted">·</span>' +
			'<button type="button" class="btn btn-link btn-sm p-0 usis-specs-collapse-all">Collapse all</button>' +
			'<div class="usis-specs-book-msg small ms-2 d-none"></div>' +
			"</div>" +
			'<div class="usis-specs-grid border rounded overflow-hidden bg-white" style="min-height:22rem;"></div>' +
			"</div>" +
			'<div class="usis-specs-modal d-none" style="position:fixed;inset:0;z-index:1080;background:rgba(15,23,42,.45);">' +
			'<div class="bg-white rounded shadow-lg m-3 mx-auto p-3" style="max-width:720px;max-height:calc(100vh - 2rem);display:flex;flex-direction:column;">' +
			'<div class="d-flex justify-content-between align-items-start gap-2 mb-2">' +
			"<div><h5 class=\"mb-1\">CSI MasterFormat catalog</h5>" +
			'<p class="text-muted small mb-0 usis-specs-cat-sub">All 50 MasterFormat divisions. Search or browse, then check the sections used on this job.</p></div>' +
			'<button type="button" class="btn-close usis-specs-modal-close" aria-label="Close"></button>' +
			"</div>" +
			'<input type="search" class="form-control form-control-sm mb-2 usis-specs-cat-q" placeholder="Search CSI code or title…" autocomplete="off">' +
			'<div class="usis-specs-cat-list border rounded overflow-auto small mb-2" style="min-height:220px;max-height:42vh;"></div>' +
			'<div class="row g-2 align-items-end mb-2">' +
			'<div class="col-sm-4"><label class="form-label small mb-0">Custom code</label>' +
			'<input class="form-control form-control-sm usis-specs-custom-code" placeholder="10 44 16"></div>' +
			'<div class="col-sm-8"><label class="form-label small mb-0">Custom title</label>' +
			'<input class="form-control form-control-sm usis-specs-custom-title" placeholder="Fire Extinguishers"></div>' +
			"</div>" +
			'<div class="d-flex flex-wrap gap-2 justify-content-end">' +
			'<button type="button" class="btn btn-sm btn-outline-secondary usis-specs-modal-close">Cancel</button>' +
			'<button type="button" class="btn btn-sm btn-primary usis-specs-cat-add">Add selected</button>' +
			"</div>" +
			'<div class="usis-specs-cat-err text-danger small mt-2 d-none"></div>' +
			"</div></div>";

		var overlay = document.createElement("div");
		overlay.id = overlayId;
		overlay.className = "usis-sv-overlay d-none";
		overlay.setAttribute("role", "dialog");
		overlay.setAttribute("aria-modal", "true");
		overlay.setAttribute("aria-label", "Specification viewer");
		overlay.innerHTML =
			'<div class="usis-sv-dialog">' +
			'<header class="usis-dv-chrome">' +
			'<div class="usis-dv-chrome__titlebar">' +
			'<div class="usis-dv-chrome__nav">' +
			'<button type="button" class="btn btn-outline-secondary btn-sm usis-sv-close">Close</button>' +
			"</div>" +
			'<div class="usis-dv-chrome__sheet">' +
			'<div class="usis-sv-title usis-dv-meta">Specification</div>' +
			"</div>" +
			'<div class="usis-dv-chrome__actions">' +
			'<a class="btn btn-outline-secondary btn-sm usis-sv-openfull d-none" target="_blank" rel="noopener">Open PDF</a>' +
			'<button type="button" class="btn btn-outline-secondary btn-sm usis-sv-attach">Attach PDF</button>' +
			'<button type="button" class="btn btn-outline-danger btn-sm usis-sv-delete">Delete</button>' +
			"</div>" +
			"</div>" +
			'<div class="usis-dv-chrome__alerts">' +
			'<div class="alert alert-danger d-none py-1 px-2 mb-0 small flex-grow-1 usis-sv-err" role="alert"></div>' +
			'<div class="alert alert-light border py-1 px-2 mb-0 small d-none usis-sv-loading" role="status">Loading PDF…</div>' +
			"</div>" +
			'<div class="usis-dv-toolbar">' +
			'<div class="usis-dv-toolgroup">' +
			'<span class="usis-overline">View</span>' +
			'<div class="usis-dv-toolgroup__row">' +
			'<div class="usis-seg" role="group" aria-label="Zoom">' +
			'<button type="button" class="btn btn-outline-secondary btn-sm usis-sv-zoom-out" title="Zoom out">−</button>' +
			'<button type="button" class="btn btn-outline-secondary btn-sm usis-sv-zoom-in" title="Zoom in">+</button>' +
			'<button type="button" class="btn btn-outline-secondary btn-sm usis-sv-fit-width">Width</button>' +
			'<button type="button" class="btn btn-outline-secondary btn-sm usis-sv-fit-page">Fit</button>' +
			"</div>" +
			'<span class="usis-dv-zoom-label usis-sv-zoom-label">100%</span>' +
			'<div class="usis-seg" role="group" aria-label="Page">' +
			'<button type="button" class="btn btn-outline-secondary btn-sm usis-sv-page-prev">−</button>' +
			'<span class="usis-dv-page-label usis-sv-page-label">1 / 1</span>' +
			'<button type="button" class="btn btn-outline-secondary btn-sm usis-sv-page-next">+</button>' +
			"</div>" +
			"</div>" +
			"</div>" +
			'<div class="usis-dv-toolgroup usis-dv-toolgroup--grow">' +
			'<span class="usis-overline">PDF URL</span>' +
			'<div class="input-group input-group-sm" style="max-width:28rem;">' +
			'<input type="url" class="form-control usis-sv-pdfurl" placeholder="https://… or /api/v1/…">' +
			'<button type="button" class="btn btn-primary usis-sv-saveurl">Save URL</button>' +
			"</div>" +
			"</div>" +
			"</div>" +
			"</header>" +
			'<div class="usis-sv-canvas-wrap">' +
			'<div class="usis-sv-empty">No PDF attached to this section.</div>' +
			'<canvas class="usis-sv-canvas" width="0" height="0"></canvas>' +
			"</div>" +
			'<p class="usis-dv-hint usis-sv-hint"><kbd>Wheel</kbd> zoom · drag to pan · <kbd>Esc</kbd> close</p>' +
			"</div>";
		document.body.appendChild(overlay);

		var gridEl = container.querySelector(".usis-specs-grid");
		var qEl = container.querySelector(".usis-specs-q");
		var addBtn = container.querySelector(".usis-specs-add");
		var importBookBtn = container.querySelector(".usis-specs-import-book");
		var bookFileInput = container.querySelector(".usis-specs-book-file");
		var fileInput = container.querySelector(".usis-specs-file");
		var bookMsg = container.querySelector(".usis-specs-book-msg");
		var modalEl = container.querySelector(".usis-specs-modal");
		var catList = container.querySelector(".usis-specs-cat-list");
		var catQ = container.querySelector(".usis-specs-cat-q");
		var catAdd = container.querySelector(".usis-specs-cat-add");
		var catErr = container.querySelector(".usis-specs-cat-err");
		var customCode = container.querySelector(".usis-specs-custom-code");
		var customTitle = container.querySelector(".usis-specs-custom-title");
		var expandAllBtn = container.querySelector(".usis-specs-expand-all");
		var collapseAllBtn = container.querySelector(".usis-specs-collapse-all");

		var closeBtn = overlay.querySelector(".usis-sv-close");
		var titleEl = overlay.querySelector(".usis-sv-title");
		var errEl = overlay.querySelector(".usis-sv-err");
		var loadingEl = overlay.querySelector(".usis-sv-loading");
		var canvas = overlay.querySelector(".usis-sv-canvas");
		var canvasWrap = overlay.querySelector(".usis-sv-canvas-wrap");
		var emptyEl = overlay.querySelector(".usis-sv-empty");
		var openFull = overlay.querySelector(".usis-sv-openfull");
		var attachBtn = overlay.querySelector(".usis-sv-attach");
		var deleteBtn = overlay.querySelector(".usis-sv-delete");
		var urlInput = overlay.querySelector(".usis-sv-pdfurl");
		var saveBtn = overlay.querySelector(".usis-sv-saveurl");
		var zoomInBtn = overlay.querySelector(".usis-sv-zoom-in");
		var zoomOutBtn = overlay.querySelector(".usis-sv-zoom-out");
		var fitWidthBtn = overlay.querySelector(".usis-sv-fit-width");
		var fitPageBtn = overlay.querySelector(".usis-sv-fit-page");
		var zoomLabel = overlay.querySelector(".usis-sv-zoom-label");
		var pagePrevBtn = overlay.querySelector(".usis-sv-page-prev");
		var pageNextBtn = overlay.querySelector(".usis-sv-page-next");
		var pageLabel = overlay.querySelector(".usis-sv-page-label");

		var pdfDoc = null;
		var pageNum = 1;
		var pageRendering = false;
		var pagePending = null;
		var scale = 1.25;
		var MIN_SCALE = 0.1;
		var MAX_SCALE = 10;
		var ZOOM_STEP = 1.25;
		var panState = null;

		function setBookMsg(text, isError) {
			if (!bookMsg) return;
			if (!text) {
				bookMsg.className = "usis-specs-book-msg small ms-2 d-none";
				bookMsg.textContent = "";
				return;
			}
			bookMsg.className = "usis-specs-book-msg small ms-2 " + (isError ? "text-danger" : "text-success");
			bookMsg.textContent = text;
		}

		function setCatErr(text) {
			if (!catErr) return;
			if (!text) {
				catErr.classList.add("d-none");
				catErr.textContent = "";
				return;
			}
			catErr.textContent = text;
			catErr.classList.remove("d-none");
		}

		function showViewerErr(msg) {
			if (!errEl) return;
			if (!msg) {
				errEl.classList.add("d-none");
				errEl.textContent = "";
				return;
			}
			errEl.textContent = msg;
			errEl.classList.remove("d-none");
		}

		function setViewerLoading(on) {
			if (loadingEl) loadingEl.classList.toggle("d-none", !on);
		}

		function updateZoomLabel() {
			if (zoomLabel) zoomLabel.textContent = Math.round(scale * 100) + "%";
		}

		function updatePageLabel() {
			var total = pdfDoc && pdfDoc.numPages ? pdfDoc.numPages : 1;
			if (pageLabel) pageLabel.textContent = pageNum + " / " + total;
		}

		function clampScale(n) {
			if (n < MIN_SCALE) return MIN_SCALE;
			if (n > MAX_SCALE) return MAX_SCALE;
			return n;
		}

		function queueRenderPage() {
			if (pageRendering) pagePending = pageNum;
			else renderPage(pageNum);
		}

		function renderPage(num) {
			if (!canvas || !pdfDoc) return;
			pageRendering = true;
			var ctx = canvas.getContext("2d");
			pdfDoc
				.getPage(num)
				.then(function (page) {
					var viewport = page.getViewport({ scale: scale });
					canvas.height = viewport.height;
					canvas.width = viewport.width;
					return page.render({ canvasContext: ctx, viewport: viewport }).promise;
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
					showViewerErr(e && e.message ? e.message : String(e));
				});
		}

		function fitToViewport(mode) {
			if (!pdfDoc || !canvasWrap) return;
			pdfDoc.getPage(pageNum).then(function (page) {
				var vp = page.getViewport({ scale: 1 });
				var pad = 24;
				var availW = Math.max(32, canvasWrap.clientWidth - pad);
				var availH = Math.max(32, canvasWrap.clientHeight - pad);
				scale = clampScale(mode === "page" ? Math.min(availW / vp.width, availH / vp.height) : availW / vp.width);
				updateZoomLabel();
				queueRenderPage();
			});
		}

		function clearPdf() {
			pdfDoc = null;
			pageNum = 1;
			if (canvas) {
				canvas.width = 0;
				canvas.height = 0;
			}
			if (emptyEl) emptyEl.classList.remove("d-none");
			if (openFull) {
				openFull.classList.add("d-none");
				openFull.removeAttribute("href");
			}
			updatePageLabel();
		}

		function loadPdf(url) {
			var full = resolveUrl(url);
			if (!full) {
				clearPdf();
				setViewerLoading(false);
				showViewerErr("");
				return;
			}
			if (emptyEl) emptyEl.classList.add("d-none");
			if (openFull) {
				openFull.href = full;
				openFull.classList.remove("d-none");
			}
			setViewerLoading(true);
			showViewerErr("");
			ensurePdfJs()
				.then(function (lib) {
					return lib.getDocument(pdfDocumentOptions(full)).promise;
				})
				.then(function (doc) {
					pdfDoc = doc;
					pageNum = 1;
					setViewerLoading(false);
					fitToViewport("width");
					updatePageLabel();
					updateZoomLabel();
				})
				.catch(function (e) {
					setViewerLoading(false);
					clearPdf();
					showViewerErr(e && e.message ? e.message : String(e));
				});
		}

		function findSection(id) {
			return sections.find(function (x) {
				return String(x.id) === String(id);
			});
		}

		function upsertSection(item) {
			if (!item || !item.id) return;
			var next = decorateSection(item);
			var idx = sections.findIndex(function (x) {
				return String(x.id) === String(item.id);
			});
			if (idx >= 0) sections[idx] = next;
			else sections.push(next);
			refreshTable();
			return next;
		}

		function applySectionToViewer(row) {
			if (!row) return;
			selectedId = row.id;
			if (titleEl) {
				titleEl.textContent = (row.code || "") + (row.title ? " — " + row.title : "");
			}
			if (urlInput) urlInput.value = row.pdf_url || "";
			loadPdf(row.pdf_url || "");
		}

		function openViewer(row) {
			if (!row) return;
			overlay.classList.remove("d-none");
			document.body.classList.add("usis-sv-open");
			applySectionToViewer(row);
		}

		function closeViewer() {
			overlay.classList.add("d-none");
			document.body.classList.remove("usis-sv-open");
			clearPdf();
			showViewerErr("");
		}

		function specNameLinkFormatter(field) {
			return function (cell) {
				var data = cell.getRow().getData();
				var text = data[field];
				if (text == null || String(text).trim() === "") text = "—";
				else text = String(text);
				var a = document.createElement("a");
				a.href = viewerHref(projectId, data.id);
				a.className = "usis-drawing-name-link usis-spec-name-link";
				a.textContent = text;
				a.addEventListener("click", function (ev) {
					if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey || ev.button) return;
					ev.preventDefault();
					openViewer(data);
				});
				return a;
			};
		}

		function filteredRows() {
			var qq = qEl && qEl.value ? qEl.value.trim().toLowerCase() : "";
			return sections.filter(function (r) {
				if (!qq) return true;
				var blob = (r.code || "") + " " + (r.title || "") + " " + (r.division_label || "");
				return blob.toLowerCase().indexOf(qq) !== -1;
			});
		}

		function setGroupsOpen(open) {
			if (!table || typeof table.getGroups !== "function") return;
			var map = {};
			table.getGroups().forEach(function (g) {
				if (open) g.show();
				else {
					g.hide();
					map[g.getKey()] = 1;
				}
			});
			writeCollapsedMap(projectId, open ? {} : map);
		}

		function bindGroupPersistence() {
			if (!table || table._usisGroupBound) return;
			table._usisGroupBound = true;
			table.on("groupVisibilityChanged", function (group, visible) {
				var map = readCollapsedMap(projectId);
				var key = group.getKey();
				if (visible) delete map[key];
				else map[key] = 1;
				writeCollapsedMap(projectId, map);
			});
		}

		function refreshTable() {
			var rows = filteredRows().slice().sort(function (a, b) {
				var da = String(a.division_key || "");
				var db = String(b.division_key || "");
				if (da === "other") return 1;
				if (db === "other") return -1;
				if (da !== db) return da.localeCompare(db);
				return String(a.code || "").localeCompare(String(b.code || ""), undefined, { numeric: true });
			});
			if (typeof Tabulator === "undefined") {
				if (gridEl) {
					gridEl.innerHTML =
						'<div class="alert alert-warning mb-0">Spec grid requires Tabulator (CDN). Check your network or CSP.</div>';
				}
				return;
			}
			if (table) {
				table.setData(rows);
				return;
			}
			table = new Tabulator(gridEl, {
				data: rows,
				layout: "fitColumns",
				pagination: false,
				movableColumns: true,
				placeholder: "No CSI sections on this project yet. Add them from the CSI catalog, or import a spec-book PDF.",
				columns: [
					{
						title: "CSI code",
						field: "code",
						headerFilter: "input",
						minWidth: 110,
						widthGrow: 1,
						formatter: specNameLinkFormatter("code"),
					},
					{
						title: "Title",
						field: "title",
						headerFilter: "input",
						minWidth: 180,
						widthGrow: 3,
						formatter: specNameLinkFormatter("title"),
					},
					{ title: "Division", field: "division_label", visible: false },
					{
						title: "PDF",
						field: "has_pdf",
						hozAlign: "center",
						width: 80,
						formatter: function (cell) {
							return cell.getValue() ? "Yes" : "—";
						},
					},
					{
						title: "",
						hozAlign: "right",
						headerSort: false,
						width: 220,
						formatter: function (cell) {
							var wrap = document.createElement("div");
							wrap.className = "d-flex gap-1 flex-wrap justify-content-end";
							var data = cell.getRow().getData();
							var view = document.createElement("button");
							view.type = "button";
							view.className = "btn btn-primary btn-sm py-0";
							view.textContent = "View";
							view.addEventListener("click", function () {
								openViewer(data);
							});
							wrap.appendChild(view);
							if (data.pdf_url) {
								var p = document.createElement("a");
								p.href = resolveUrl(data.pdf_url);
								p.target = "_blank";
								p.rel = "noopener noreferrer";
								p.className = "btn btn-outline-secondary btn-sm py-0";
								p.textContent = "PDF";
								wrap.appendChild(p);
							} else {
								var att = document.createElement("button");
								att.type = "button";
								att.className = "btn btn-outline-secondary btn-sm py-0";
								att.textContent = "Attach";
								att.addEventListener("click", function () {
									pendingAttachId = data.id;
									if (fileInput) fileInput.click();
								});
								wrap.appendChild(att);
							}
							var del = document.createElement("button");
							del.type = "button";
							del.className = "btn btn-outline-danger btn-sm py-0";
							del.textContent = "Delete";
							del.addEventListener("click", function () {
								deleteSection(data);
							});
							wrap.appendChild(del);
							return wrap;
						},
					},
				],
				groupBy: specDivisionGroup,
				groupToggleElement: "header",
				groupStartOpen: function (value) {
					return !readCollapsedMap(projectId)[value];
				},
				groupHeader: function (value, count) {
					return (
						'<span class="usis-doc-group-label">' +
						esc(value || "Other") +
						'</span> <span class="usis-doc-group-count">(' +
						count +
						")</span>"
					);
				},
			});
			bindGroupPersistence();
		}

		function load() {
			var base = apiBase();
			fetch(base + "/api/v1/projects/" + encodeURIComponent(projectId) + "/rfi-lookups/spec_sections", {
				credentials: "include",
				headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
			})
				.then(function (res) {
					if (!res.ok) {
						return res.text().then(function (t) {
							throw new Error(res.status + " " + (t || res.statusText));
						});
					}
					return res.json();
				})
				.then(function (data) {
					sections = (data.items || []).map(decorateSection);
					refreshTable();
					if (autoSpecId) {
						var row = findSection(autoSpecId);
						autoSpecId = null;
						if (row) openViewer(row);
					} else if (selectedId && !overlay.classList.contains("d-none")) {
						var cur = findSection(selectedId);
						if (cur) applySectionToViewer(cur);
					}
				})
				.catch(function (e) {
					if (gridEl) {
						gridEl.innerHTML = '<p class="text-danger small px-3 py-3 mb-0">' + esc(e.message || String(e)) + "</p>";
					}
				});
		}

		function applyGroupCollapsed(box, collapsed) {
			if (!box) return;
			box.classList.toggle("is-collapsed", !!collapsed);
			var btn = box.querySelector(".usis-doc-group-toggle");
			if (btn) btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
		}

		function renderCatalog(items, total) {
			catalogItems = items || [];
			var sub = container.querySelector(".usis-specs-cat-sub");
			if (sub && total) {
				sub.textContent =
					total +
					" sections across all 50 MasterFormat divisions. Search or browse, then check the sections used on this job.";
			}
			if (!catList) return;
			if (!catalogItems.length) {
				catList.innerHTML = '<p class="text-muted px-2 py-3 mb-0">No CSI sections match that search.</p>';
				return;
			}
			var groups = {};
			catalogItems.forEach(function (item) {
				var key = item.division || "other";
				if (!groups[key]) groups[key] = { name: item.division_name || "", items: [] };
				groups[key].items.push(item);
			});
			var searching = !!(catQ && catQ.value && catQ.value.trim());
			var html = "";
			sortDivisionKeys(Object.keys(groups)).forEach(function (div) {
				var g = groups[div];
				var meta = { key: div, num: div === "other" ? "" : div, name: g.name || "Other" };
				var collapsed = searching ? false : true;
				html +=
					'<div class="usis-doc-group' +
					(collapsed ? " is-collapsed" : "") +
					'" data-div="' +
					esc(div) +
					'">' +
					'<button type="button" class="usis-doc-group-toggle" aria-expanded="' +
					(collapsed ? "false" : "true") +
					'">' +
					'<span class="usis-doc-group-chevron" aria-hidden="true"></span>' +
					'<span class="usis-doc-group-label">' +
					esc(divisionBoxLabel(meta, g.items.length)) +
					"</span>" +
					"</button>" +
					'<div class="usis-doc-group-body"><div class="list-group list-group-flush">';
				g.items.forEach(function (item) {
					html +=
						'<label class="list-group-item list-group-item-action py-2 px-2 d-flex gap-2 align-items-start rounded-0">' +
						'<input type="checkbox" class="form-check-input mt-1 usis-specs-cat-check" value="' +
						esc(item.code) +
						'" data-title="' +
						esc(item.title) +
						'">' +
						'<div class="fw-medium">' +
						esc(item.code) +
						" · " +
						esc(item.title) +
						"</div></label>";
				});
				html += "</div></div></div>";
			});
			catList.innerHTML = html;
			Array.prototype.forEach.call(catList.querySelectorAll(".usis-doc-group-toggle"), function (btn) {
				btn.addEventListener("click", function () {
					var box = btn.closest(".usis-doc-group");
					if (!box) return;
					applyGroupCollapsed(box, !box.classList.contains("is-collapsed"));
				});
			});
		}

		function loadCatalog(q) {
			if (!catList) return;
			catList.innerHTML = '<p class="text-muted px-2 py-3 mb-0">Loading CSI catalog…</p>';
			var base = apiBase();
			var url = base + "/api/v1/csi-sections?limit=3000";
			if (q) url += "&q=" + encodeURIComponent(q);
			fetch(url, {
				credentials: "include",
				headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
			})
				.then(function (res) {
					if (!res.ok) {
						return res.text().then(function (t) {
							throw new Error(res.status + " " + (t || res.statusText));
						});
					}
					return res.json();
				})
				.then(function (data) {
					renderCatalog(data.items || [], data.total);
				})
				.catch(function (e) {
					catList.innerHTML = '<p class="text-danger small px-2">' + esc(e.message || String(e)) + "</p>";
				});
		}

		function openModal() {
			if (!modalEl) return;
			setCatErr("");
			modalEl.classList.remove("d-none");
			if (catQ) catQ.value = "";
			if (customCode) customCode.value = "";
			if (customTitle) customTitle.value = "";
			loadCatalog("");
			if (catQ) catQ.focus();
		}

		function closeModal() {
			if (modalEl) modalEl.classList.add("d-none");
		}

		function addFromCatalog() {
			var items = [];
			Array.prototype.forEach.call(container.querySelectorAll(".usis-specs-cat-check:checked"), function (box) {
				items.push({ code: box.value, title: box.getAttribute("data-title") || "" });
			});
			if (customCode && customCode.value.trim()) {
				items.push({
					code: customCode.value.trim(),
					title: customTitle && customTitle.value.trim() ? customTitle.value.trim() : "",
				});
			}
			if (!items.length) {
				setCatErr("Check at least one CSI section, or type a custom code.");
				return;
			}
			setCatErr("");
			var base = apiBase();
			fetch(base + "/api/v1/projects/" + encodeURIComponent(projectId) + "/spec-sections/from-catalog", {
				method: "POST",
				credentials: "include",
				headers: jsonFetchHeaders(),
				body: JSON.stringify({ items: items }),
			})
				.then(function (res) {
					if (!res.ok) {
						return res.text().then(function (t) {
							throw new Error(res.status + " " + (t || res.statusText));
						});
					}
					return res.json();
				})
				.then(function (data) {
					closeModal();
					load();
					var created = data.items || [];
					if (created.length) openViewer(decorateSection(created[0]));
					setBookMsg(
						created.length
							? "Added " + created.length + " CSI section" + (created.length === 1 ? "" : "s") + "."
							: "Those sections were already on this project."
					);
				})
				.catch(function (e) {
					setCatErr(e.message || String(e));
				});
		}

		function savePdfUrl() {
			if (!selectedId) return;
			var body = { pdf_url: urlInput && urlInput.value.trim() ? urlInput.value.trim() : null };
			var base = apiBase();
			fetch(
				base +
					"/api/v1/projects/" +
					encodeURIComponent(projectId) +
					"/rfi-lookups/spec_sections/" +
					encodeURIComponent(selectedId),
				{
					method: "PATCH",
					credentials: "include",
					headers: jsonFetchHeaders(),
					body: JSON.stringify(body),
				}
			)
				.then(function (res) {
					if (!res.ok) {
						return res.text().then(function (t) {
							throw new Error(res.status + " " + (t || res.statusText));
						});
					}
					return res.json();
				})
				.then(function (data) {
					var it = upsertSection(data.item);
					if (it) applySectionToViewer(it);
				})
				.catch(function (e) {
					showViewerErr(e.message || String(e));
				});
		}

		function attachPdfTo(sectionId, file) {
			if (!sectionId || !file) return;
			var base = apiBase();
			var fd = new FormData();
			fd.append("file", file, file.name || "spec.pdf");
			setViewerLoading(true);
			showViewerErr("");
			fetch(
				base +
					"/api/v1/projects/" +
					encodeURIComponent(projectId) +
					"/rfi-lookups/spec_sections/" +
					encodeURIComponent(sectionId) +
					"/file",
				{
					method: "POST",
					credentials: "include",
					headers: Object.assign({}, actorHeaders()),
					body: fd,
				}
			)
				.then(function (res) {
					if (!res.ok) {
						return res.text().then(function (t) {
							throw new Error(res.status + " " + (t || res.statusText));
						});
					}
					return res.json();
				})
				.then(function (data) {
					var it = upsertSection(data.item);
					if (it) {
						if (overlay.classList.contains("d-none")) openViewer(it);
						else applySectionToViewer(it);
					}
					setBookMsg("PDF attached.");
				})
				.catch(function (e) {
					setViewerLoading(false);
					showViewerErr(e.message || String(e));
					setBookMsg(e.message || String(e), true);
				});
		}

		function deleteSection(row) {
			if (!row || !row.id) return;
			var label = (row.code || "") + " " + (row.title || "this section");
			if (!window.confirm("Delete " + label.trim() + " from this project?")) return;
			var base = apiBase();
			fetch(
				base +
					"/api/v1/projects/" +
					encodeURIComponent(projectId) +
					"/rfi-lookups/spec_sections/" +
					encodeURIComponent(row.id),
				{
					method: "DELETE",
					credentials: "include",
					headers: Object.assign({ Accept: "application/json" }, actorHeaders()),
				}
			)
				.then(function (res) {
					if (!res.ok) {
						return res.text().then(function (t) {
							throw new Error(apiErrorText(res, t));
						});
					}
					return res.json();
				})
				.then(function () {
					if (String(selectedId) === String(row.id)) {
						selectedId = null;
						closeViewer();
					}
					setBookMsg("Section deleted.");
					load();
				})
				.catch(function (e) {
					var msg = e.message || String(e);
					showViewerErr(msg);
					setBookMsg(msg, true);
				});
		}

		if (qEl) {
			qEl.addEventListener("input", function () {
				refreshTable();
			});
		}
		if (expandAllBtn) {
			expandAllBtn.addEventListener("click", function () {
				setGroupsOpen(true);
			});
		}
		if (collapseAllBtn) {
			collapseAllBtn.addEventListener("click", function () {
				setGroupsOpen(false);
			});
		}
		if (addBtn) addBtn.addEventListener("click", openModal);
		Array.prototype.forEach.call(container.querySelectorAll(".usis-specs-modal-close"), function (btn) {
			btn.addEventListener("click", closeModal);
		});
		if (modalEl) {
			modalEl.addEventListener("click", function (ev) {
				if (ev.target === modalEl) closeModal();
			});
		}
		if (catAdd) catAdd.addEventListener("click", addFromCatalog);
		if (catQ) {
			catQ.addEventListener("input", function () {
				if (catalogTimer) global.clearTimeout(catalogTimer);
				catalogTimer = global.setTimeout(function () {
					loadCatalog(catQ.value);
				}, 220);
			});
		}
		if (saveBtn) saveBtn.addEventListener("click", savePdfUrl);
		if (attachBtn && fileInput) {
			attachBtn.addEventListener("click", function () {
				if (!selectedId) return;
				pendingAttachId = selectedId;
				fileInput.click();
			});
		}
		if (fileInput) {
			fileInput.addEventListener("change", function () {
				var f = fileInput.files && fileInput.files[0];
				var id = pendingAttachId || selectedId;
				fileInput.value = "";
				pendingAttachId = null;
				if (f && id) attachPdfTo(id, f);
			});
		}
		if (deleteBtn) {
			deleteBtn.addEventListener("click", function () {
				var row = findSection(selectedId);
				if (row) deleteSection(row);
			});
		}
		if (closeBtn) closeBtn.addEventListener("click", closeViewer);
		if (zoomInBtn) {
			zoomInBtn.addEventListener("click", function () {
				scale = clampScale(scale * ZOOM_STEP);
				updateZoomLabel();
				queueRenderPage();
			});
		}
		if (zoomOutBtn) {
			zoomOutBtn.addEventListener("click", function () {
				scale = clampScale(scale / ZOOM_STEP);
				updateZoomLabel();
				queueRenderPage();
			});
		}
		if (fitWidthBtn) fitWidthBtn.addEventListener("click", function () { fitToViewport("width"); });
		if (fitPageBtn) fitPageBtn.addEventListener("click", function () { fitToViewport("page"); });
		if (pagePrevBtn) {
			pagePrevBtn.addEventListener("click", function () {
				if (!pdfDoc || pageNum <= 1) return;
				pageNum--;
				queueRenderPage();
			});
		}
		if (pageNextBtn) {
			pageNextBtn.addEventListener("click", function () {
				if (!pdfDoc || pageNum >= pdfDoc.numPages) return;
				pageNum++;
				queueRenderPage();
			});
		}
		if (canvasWrap) {
			canvasWrap.addEventListener(
				"wheel",
				function (ev) {
					if (overlay.classList.contains("d-none") || !pdfDoc) return;
					ev.preventDefault();
					var factor = ev.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
					scale = clampScale(scale * factor);
					updateZoomLabel();
					queueRenderPage();
				},
				{ passive: false }
			);
			canvasWrap.addEventListener("mousedown", function (ev) {
				if (ev.button !== 0) return;
				panState = { x: ev.clientX, y: ev.clientY, sl: canvasWrap.scrollLeft, st: canvasWrap.scrollTop };
				canvasWrap.classList.add("is-panning");
			});
			canvasWrap.addEventListener("mousemove", function (ev) {
				if (!panState) return;
				canvasWrap.scrollLeft = panState.sl - (ev.clientX - panState.x);
				canvasWrap.scrollTop = panState.st - (ev.clientY - panState.y);
			});
			function endPan() {
				panState = null;
				canvasWrap.classList.remove("is-panning");
			}
			canvasWrap.addEventListener("mouseup", endPan);
			canvasWrap.addEventListener("mouseleave", endPan);
		}
		document.addEventListener("keydown", function onEsc(ev) {
			if (ev.key === "Escape" && overlay && !overlay.classList.contains("d-none")) {
				closeViewer();
			}
		});

		if (importBookBtn && bookFileInput) {
			importBookBtn.addEventListener("click", function () {
				bookFileInput.click();
			});
			bookFileInput.addEventListener("change", function () {
				var f = bookFileInput.files && bookFileInput.files[0];
				bookFileInput.value = "";
				if (!f) return;
				setBookMsg("Reading spec book…");
				var base = apiBase();
				var fd = new FormData();
				fd.append("file", f, f.name || "spec-book.pdf");
				fetch(base + "/api/v1/projects/" + encodeURIComponent(projectId) + "/spec-book/import", {
					method: "POST",
					credentials: "include",
					headers: Object.assign({}, actorHeaders()),
					body: fd,
				})
					.then(function (res) {
						if (!res.ok) {
							return res.text().then(function (t) {
								throw new Error(res.status + " " + (t || res.statusText));
							});
						}
						return res.json();
					})
					.then(function (data) {
						load();
						var created = data.items || [];
						if (created.length) openViewer(decorateSection(created[0]));
						setBookMsg(
							"Found " +
								(data.found || 0) +
								" CSI section" +
								((data.found || 0) === 1 ? "" : "s") +
								", added " +
								(data.created || 0) +
								((data.skipped || 0) ? ", skipped " + data.skipped + " already on the project" : "") +
								"."
						);
					})
					.catch(function (e) {
						setBookMsg(e.message || String(e), true);
					});
			});
		}

		load();
	}

	global.USISSpecsBook = { mount: mount, resolveAssetUrl: resolveUrl };
})(typeof window !== "undefined" ? window : globalThis);
