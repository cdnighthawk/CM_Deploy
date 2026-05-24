/**
 * Submittal detail: General / History / Attachments + PDF.js viewer with markups.
 * ES module — requires ../vendor/pdfjs/*.mjs (copied from pdfjs-dist).
 */
import * as pdfjsLib from "../vendor/pdfjs/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL("../vendor/pdfjs/pdf.worker.min.mjs", import.meta.url).href;

function apiBase() {
	if (window.USIS_API) return window.USIS_API.apiBase();
	if (typeof window.usisApiBase === "function") return window.usisApiBase();
	return "";
}

function qs() {
	return new URLSearchParams(window.location.search);
}

async function fetchJson(path, opts) {
	var o = opts || {};
	if (window.USIS_API) {
		var body = o.body;
		if (typeof body === "string") {
			try {
				body = JSON.parse(body);
			} catch (e) {
				/* keep string body */
			}
		}
		return window.USIS_API.fetchJson(path, {
			method: o.method,
			headers: o.headers,
			body: body,
		});
	}
	var url = apiBase() + path;
	var res = await fetch(
		url,
		Object.assign({}, o, {
			credentials: "include",
			headers: Object.assign({ Accept: "application/json" }, o.headers || {}),
		})
	);
	if (!res.ok) {
		var t = await res.text();
		throw new Error(res.status + " " + (t || res.statusText));
	}
	return res.json();
}

function isoToDateInput(iso) {
	if (!iso) return "";
	var s = String(iso);
	return s.length >= 10 ? s.slice(0, 10) : "";
}

function dateInputToIso(el) {
	if (!el || !el.value) return null;
	return el.value + "T00:00:00+00:00";
}

const state = {
	projectId: "",
	submittalId: "",
	detail: null,
	canAnnotate: false,
	pdfDoc: null,
	pageNum: 1,
	scale: 1.2,
	tool: "pan",
	stampId: null,
	items: [],
	currentDocId: null,
	currentFileUrl: "",
	drawing: false,
	strokeNorm: [],
	renderToken: 0,
};

function esc(s) {
	if (s == null) return "";
	var d = document.createElement("div");
	d.textContent = String(s);
	return d.innerHTML;
}

function showErr(msg) {
	var el = document.getElementById("usis-sub-detail-error");
	if (!el) return;
	el.textContent = msg || "";
	el.classList.toggle("d-none", !msg);
}

function applyItemToForm(it) {
	document.getElementById("usis-sub-f-title").value = it.title || "";
	document.getElementById("usis-sub-f-spec").value = it.spec_section || "";
	document.getElementById("usis-sub-f-type").value = it.submittal_type || "";
	document.getElementById("usis-sub-f-status").value = it.status || "draft";
	document.getElementById("usis-sub-f-bic").value = it.ball_in_court || "";
	document.getElementById("usis-sub-f-contractor").value = it.responsible_contractor || "";
	document.getElementById("usis-sub-f-due").value = isoToDateInput(it.due_at);
	document.getElementById("usis-sub-f-submitby").value = isoToDateInput(it.submit_by_at);
	document.getElementById("usis-sub-f-received").value = isoToDateInput(it.received_at);
	document.getElementById("usis-sub-f-receivedfrom").value = it.received_from || "";
	document.getElementById("usis-sub-f-sent").value = isoToDateInput(it.sent_at);
	document.getElementById("usis-sub-f-returned").value = isoToDateInput(it.returned_at);
	document.getElementById("usis-sub-f-rev").value = it.revision || "";
	document.getElementById("usis-sub-f-response").value = it.response || "";
}

function collectFormPayload() {
	return {
		title: document.getElementById("usis-sub-f-title").value.trim(),
		spec_section: document.getElementById("usis-sub-f-spec").value.trim() || null,
		submittal_type: document.getElementById("usis-sub-f-type").value.trim() || null,
		status: document.getElementById("usis-sub-f-status").value,
		ball_in_court: document.getElementById("usis-sub-f-bic").value.trim() || null,
		responsible_contractor: document.getElementById("usis-sub-f-contractor").value.trim() || null,
		due_at: dateInputToIso(document.getElementById("usis-sub-f-due")),
		submit_by_at: dateInputToIso(document.getElementById("usis-sub-f-submitby")),
		received_at: dateInputToIso(document.getElementById("usis-sub-f-received")),
		received_from: document.getElementById("usis-sub-f-receivedfrom").value.trim() || null,
		sent_at: dateInputToIso(document.getElementById("usis-sub-f-sent")),
		returned_at: dateInputToIso(document.getElementById("usis-sub-f-returned")),
		revision: document.getElementById("usis-sub-f-rev").value.trim() || null,
		response: document.getElementById("usis-sub-f-response").value.trim() || null,
	};
}

function renderAudit(rows) {
	var tb = document.getElementById("usis-sub-audit-body");
	if (!tb) return;
	tb.innerHTML = "";
	if (!rows || !rows.length) {
		tb.innerHTML = '<tr><td colspan="4" class="text-muted">No history yet.</td></tr>';
		return;
	}
	rows.forEach(function (a) {
		var tr = document.createElement("tr");
		var fromTo = "";
		if (a.before_json || a.after_json) {
			fromTo =
				"<code class=\"small\">" +
				esc(JSON.stringify(a.before_json || {})) +
				"</code> → <code class=\"small\">" +
				esc(JSON.stringify(a.after_json || {})) +
				"</code>";
		} else fromTo = "—";
		tr.innerHTML =
			"<td>" +
			esc(a.created_at || "") +
			"</td><td>" +
			esc(a.action) +
			"</td><td>" +
			esc(a.summary || "") +
			"</td><td class=\"small\">" +
			fromTo +
			"</td>";
		tb.appendChild(tr);
	});
}

function renderAttachments(list) {
	var tb = document.getElementById("usis-sub-att-body");
	if (!tb) return;
	tb.innerHTML = "";
	if (!list || !list.length) {
		tb.innerHTML = '<tr><td colspan="4" class="text-muted">No attachments.</td></tr>';
		return;
	}
	list.forEach(function (a) {
		var tr = document.createElement("tr");
		var mime = (a.mime_type || "").toLowerCase();
		var isPdf = mime.indexOf("pdf") !== -1 || (a.file_url || "").toLowerCase().endsWith(".pdf");
		var btn = isPdf
			? '<button type="button" class="btn btn-sm btn-outline-primary usis-open-pdf" data-id="' +
			  esc(a.id) +
			  "\" data-url=\"" +
			  esc(a.file_url || "") +
			  '">View / mark up</button> <a class="btn btn-sm btn-link" href="' +
			  esc(a.file_url) +
			  '" target="_blank" rel="noopener">Open URL</a>'
			: '<a class="btn btn-sm btn-link" href="' + esc(a.file_url || "#") + '" target="_blank" rel="noopener">Open</a>';
		tr.innerHTML =
			"<td>" +
			esc(String(a.version)) +
			"</td><td>" +
			esc(a.title || a.original_filename || "") +
			"</td><td>" +
			esc(a.updated_at || "") +
			'</td><td class="text-end">' +
			btn +
			"</td>";
		tb.appendChild(tr);
	});
	tb.querySelectorAll(".usis-open-pdf").forEach(function (b) {
		b.addEventListener("click", function () {
			openViewer(b.getAttribute("data-id"), b.getAttribute("data-url"));
		});
	});
}

async function loadDetail() {
	showErr("");
	var path =
		"/api/v1/projects/" +
		encodeURIComponent(state.projectId) +
		"/submittals/" +
		encodeURIComponent(state.submittalId);
	var data = await fetchJson(path);
	state.detail = data;
	var it = data.item;
	state.canAnnotate = !!(data.permissions && data.permissions.can_annotate);
	document.getElementById("usis-sub-num").textContent = "#" + it.number;
	document.getElementById("usis-sub-title").textContent = it.title;
	document.getElementById("usis-sub-status").textContent = it.status;
	document.getElementById("usis-sub-bic").textContent = it.ball_in_court || "—";
	document.getElementById("usis-sub-perms").textContent =
		"Can edit: " +
		(data.permissions && data.permissions.can_edit ? "yes" : "no") +
		" · Can annotate: " +
		(state.canAnnotate ? "yes" : "no");
	applyItemToForm(it);
	renderAudit(data.audit || []);
	renderAttachments(data.attachments || []);
}

async function saveGeneral() {
	var path =
		"/api/v1/projects/" +
		encodeURIComponent(state.projectId) +
		"/submittals/" +
		encodeURIComponent(state.submittalId);
	var body = collectFormPayload();
	if (!body.title) {
		showErr("Title is required.");
		return;
	}
	var data = await fetchJson(path, {
		method: "PATCH",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
	state.detail = data;
	applyItemToForm(data.item);
	renderAudit(data.audit || []);
	var ok = document.getElementById("usis-sub-save-ok");
	if (ok) {
		ok.classList.remove("d-none");
		setTimeout(function () {
			ok.classList.add("d-none");
		}, 2000);
	}
}

async function addAttachment() {
	var url = document.getElementById("usis-sub-att-url").value.trim();
	if (!url) {
		showErr("file_url is required.");
		return;
	}
	var path =
		"/api/v1/projects/" +
		encodeURIComponent(state.projectId) +
		"/submittals/" +
		encodeURIComponent(state.submittalId) +
		"/attachments";
	var title = document.getElementById("usis-sub-att-title").value.trim() || null;
	var data = await fetchJson(path, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			file_url: url,
			title: title,
			mime_type: "application/pdf",
			original_filename: title || "attachment.pdf",
		}),
	});
	document.getElementById("usis-sub-att-url").value = "";
	await loadDetail();
	if (data && data.item && data.item.id) {
		openViewer(data.item.id, data.item.file_url);
	}
}

function syncMarkupCanvasSize() {
	var pdfCv = document.getElementById("usis-submittal-pdf-canvas");
	var mk = document.getElementById("usis-submittal-markup-canvas");
	if (!pdfCv || !mk) return;
	mk.width = pdfCv.width;
	mk.height = pdfCv.height;
	mk.style.width = pdfCv.style.width || pdfCv.width + "px";
	mk.style.height = pdfCv.style.height || pdfCv.height + "px";
	redrawMarkups();
}

function redrawMarkups() {
	var mk = document.getElementById("usis-submittal-markup-canvas");
	if (!mk) return;
	var ctx = mk.getContext("2d");
	ctx.clearRect(0, 0, mk.width, mk.height);
	var pageIndex = state.pageNum - 1;
	function drawStroke(points, color, width) {
		if (!points || points.length < 2) return;
		ctx.strokeStyle = color || "#ffcc00";
		ctx.lineWidth = Math.max(1, (width || 0.004) * mk.width);
		ctx.lineCap = "round";
		ctx.beginPath();
		points.forEach(function (pt, i) {
			var x = pt[0] * mk.width;
			var y = pt[1] * mk.height;
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		});
		ctx.stroke();
	}
	state.items.forEach(function (item) {
		if ((item.page || 0) !== pageIndex) return;
		if (item.type === "stroke" && item.points && item.points.length > 1) {
			drawStroke(item.points, item.color, item.width);
		}
		if (item.type === "stamp") {
			ctx.save();
			ctx.fillStyle = "#111";
			ctx.font = "bold " + Math.floor(mk.width * 0.06) + "px sans-serif";
			var tx = (item.x || 0) * mk.width;
			var ty = (item.y || 0) * mk.height;
			var label = String(item.stampId || "STAMP").toUpperCase();
			ctx.fillText(label, tx, ty);
			ctx.restore();
		}
	});
	if (state.drawing && state.tool === "ink" && state.strokeNorm.length > 1) {
		drawStroke(state.strokeNorm, "#ffcc00", 0.004);
	}
}

async function renderPdfPage() {
	var token = ++state.renderToken;
	if (!state.pdfDoc) return;
	var page = await state.pdfDoc.getPage(state.pageNum);
	if (token !== state.renderToken) return;
	var canvas = document.getElementById("usis-submittal-pdf-canvas");
	var wrap = document.getElementById("usis-submittal-pdf-wrap");
	var vp = page.getViewport({ scale: state.scale });
	canvas.width = vp.width;
	canvas.height = vp.height;
	canvas.style.width = vp.width + "px";
	canvas.style.height = vp.height + "px";
	var ctx = canvas.getContext("2d");
	await page.render({ canvasContext: ctx, viewport: vp }).promise;
	if (token !== state.renderToken) return;
	syncMarkupCanvasSize();
	document.getElementById("usis-pdf-hint").textContent =
		"Page " + state.pageNum + " / " + state.pdfDoc.numPages + (state.canAnnotate ? "" : " (read-only)");
}

async function openViewer(docId, fileUrl) {
	state.currentDocId = docId;
	state.currentFileUrl = fileUrl;
	document.getElementById("usis-sub-viewer-panel").classList.remove("d-none");
	document.getElementById("usis-sub-viewer-label").textContent = "Document " + docId;
	var ann = await fetchJson("/api/v1/documents/" + encodeURIComponent(docId) + "/submittal-annotations");
	state.items = Array.isArray(ann.items) ? ann.items.slice() : [];
	state.canAnnotate = !!(ann.permissions && ann.permissions.can_annotate);
	try {
		state.pdfDoc = await pdfjsLib.getDocument({ url: fileUrl, withCredentials: false }).promise;
	} catch (e) {
		showErr("Could not load PDF (CORS or invalid URL): " + (e.message || e));
		state.pdfDoc = null;
		return;
	}
	state.pageNum = 1;
	await renderPdfPage();
	updateToolUi();
}

function updateToolUi() {
	var stampRow = document.getElementById("usis-stamp-row");
	var mk = document.getElementById("usis-submittal-markup-canvas");
	if (stampRow) stampRow.classList.toggle("d-none", state.tool !== "stamp");
	if (mk) {
		mk.style.pointerEvents = state.tool === "pan" ? "none" : "auto";
		mk.style.cursor = state.tool === "ink" ? "crosshair" : state.tool === "stamp" ? "copy" : "default";
	}
	document.querySelectorAll("[data-tool]").forEach(function (b) {
		b.classList.toggle("active", b.getAttribute("data-tool") === state.tool);
	});
}

function normEvent(ev, canvas) {
	var r = canvas.getBoundingClientRect();
	var x = (ev.clientX - r.left) / r.width;
	var y = (ev.clientY - r.top) / r.height;
	return [Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))];
}

function wireViewer() {
	document.getElementById("usis-pdf-prev").addEventListener("click", async function () {
		if (!state.pdfDoc || state.pageNum <= 1) return;
		state.pageNum--;
		await renderPdfPage();
	});
	document.getElementById("usis-pdf-next").addEventListener("click", async function () {
		if (!state.pdfDoc || state.pageNum >= state.pdfDoc.numPages) return;
		state.pageNum++;
		await renderPdfPage();
	});
	document.getElementById("usis-pdf-zoom-in").addEventListener("click", async function () {
		state.scale *= 1.15;
		await renderPdfPage();
	});
	document.getElementById("usis-pdf-zoom-out").addEventListener("click", async function () {
		state.scale /= 1.15;
		await renderPdfPage();
	});
	document.getElementById("usis-pdf-fit").addEventListener("click", async function () {
		if (!state.pdfDoc) return;
		var page = await state.pdfDoc.getPage(state.pageNum);
		var wrap = document.getElementById("usis-submittal-pdf-wrap");
		var w = wrap.clientWidth - 24;
		var vp1 = page.getViewport({ scale: 1 });
		state.scale = w / vp1.width;
		await renderPdfPage();
	});

	document.querySelectorAll("[data-tool]").forEach(function (b) {
		b.addEventListener("click", function () {
			if (!state.canAnnotate) return;
			state.tool = b.getAttribute("data-tool");
			updateToolUi();
		});
	});
	document.querySelectorAll("[data-stamp]").forEach(function (b) {
		b.addEventListener("click", function () {
			state.stampId = b.getAttribute("data-stamp");
			state.tool = "stamp";
			updateToolUi();
		});
	});

	var mk = document.getElementById("usis-submittal-markup-canvas");
	mk.addEventListener("mousedown", function (ev) {
		if (!state.canAnnotate || state.tool !== "ink") return;
		state.drawing = true;
		state.strokeNorm = [normEvent(ev, mk)];
	});
	mk.addEventListener("mousemove", function (ev) {
		if (!state.drawing || state.tool !== "ink") return;
		state.strokeNorm.push(normEvent(ev, mk));
		redrawMarkups();
	});
	mk.addEventListener("mouseup", function () {
		if (!state.drawing || state.tool !== "ink") return;
		state.drawing = false;
		if (state.strokeNorm.length > 1) {
			state.items.push({
				type: "stroke",
				page: state.pageNum - 1,
				color: "#ffcc00",
				width: 0.004,
				points: state.strokeNorm.slice(),
			});
		}
		state.strokeNorm = [];
		redrawMarkups();
	});
	mk.addEventListener("click", function (ev) {
		if (!state.canAnnotate || state.tool !== "stamp" || !state.stampId) return;
		var pt = normEvent(ev, mk);
		state.items.push({
			type: "stamp",
			stampId: state.stampId,
			page: state.pageNum - 1,
			x: pt[0],
			y: pt[1],
		});
		redrawMarkups();
	});

	document.getElementById("usis-pdf-save-markups").addEventListener("click", async function () {
		if (!state.currentDocId || !state.canAnnotate) return;
		await fetchJson("/api/v1/documents/" + encodeURIComponent(state.currentDocId) + "/submittal-annotations", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ items: state.items }),
		});
		await loadDetail();
		var ok = document.getElementById("usis-sub-save-ok");
		if (ok) {
			ok.textContent = "Markups saved.";
			ok.classList.remove("d-none");
			setTimeout(function () {
				ok.classList.add("d-none");
				ok.textContent = "Saved.";
			}, 2000);
		}
	});

	window.addEventListener("resize", function () {
		if (state.pdfDoc) renderPdfPage();
	});
}

function init() {
	var q = qs();
	state.projectId = (q.get("id") || "").trim();
	state.submittalId = (q.get("submittal") || "").trim();
	var back = document.getElementById("usis-sub-back");
	if (back && state.projectId) {
		back.setAttribute("href", "construction/project-detail.html?id=" + encodeURIComponent(state.projectId));
	}
	if (!state.projectId || !state.submittalId) {
		showErr("Missing id or submittal in URL.");
		return;
	}
	document.getElementById("usis-sub-save-general").addEventListener("click", function () {
		saveGeneral().catch(function (e) {
			showErr(e.message || String(e));
		});
	});
	document.getElementById("usis-sub-att-add").addEventListener("click", function () {
		addAttachment().catch(function (e) {
			showErr(e.message || String(e));
		});
	});
	wireViewer();
	loadDetail().catch(function (e) {
		showErr(e.message || String(e));
	});
}

init();
