/**
 * Drawing PDF upload: infer discipline from sheet #, preview selected files, POST one PDF at a time.
 */
(function (global) {
	"use strict";

	var DISC_PREFIXES = [
		[["ID", "AD", "I", "A"], "Architectural"],
		[["S"], "Structural"],
		[["MP", "MD", "M"], "Mechanical"],
		[["EL", "EP", "E"], "Electrical"],
		[["PL", "P"], "Plumbing"],
		[["CG", "CS", "C"], "Civil"],
		[["LA", "LS", "L"], "Landscape"],
		[["FA", "FP", "F"], "Fire Protection"],
		[["G"], "General"],
		[["T"], "Telecom"],
	];

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function disciplineFromSheetNumber(sheetNumber) {
		var raw = String(sheetNumber || "").trim().toUpperCase();
		if (!raw) return "";
		if (raw.charAt(0) === "P" && raw.indexOf("-") >= 0) {
			raw = raw.split("-").slice(1).join("-");
		}
		var m = raw.match(/^([A-Z]{1,3})/);
		if (!m) return "";
		var prefix = m[1];
		for (var i = 0; i < DISC_PREFIXES.length; i++) {
			if (DISC_PREFIXES[i][0].indexOf(prefix) !== -1) return DISC_PREFIXES[i][1];
		}
		return "";
	}

	function labelsFromFilename(filename) {
		var name = String(filename || "").split(/[/\\]/).pop() || "";
		var stem = name.replace(/\.[^.]+$/, "");
		var token = stem;
		var us = stem.indexOf("_");
		if (us >= 0) token = stem.slice(0, us).trim();
		else {
			var bits = stem.split(/\s+/);
			token = bits[0] || "";
		}
		token = token.trim();
		var sheet = "";
		if (token && /^[A-Za-z]{1,3}[-\s.]?\d/.test(token)) {
			sheet = token.toUpperCase().replace(/\s/g, "");
		}
		return {
			name: name,
			sheet: sheet,
			discipline: disciplineFromSheetNumber(sheet),
		};
	}

	function isPdfFile(f) {
		if (!f) return false;
		var n = String(f.name || "").toLowerCase();
		return n.slice(-4) === ".pdf" || f.type === "application/pdf";
	}

	function listPdfFiles(fileList) {
		return Array.prototype.slice.call(fileList || []).filter(isPdfFile);
	}

	function renderFilePreview(previewEl, files) {
		if (!previewEl) return;
		if (!files || !files.length) {
			previewEl.innerHTML = "";
			return;
		}
		var rows = files.map(function (f) {
			var lab = labelsFromFilename(f.name);
			var disc = lab.discipline || "Unassigned";
			var sheet = lab.sheet || "—";
			return (
				"<tr><td class=\"text-break\">" +
				esc(f.name) +
				"</td><td>" +
				esc(sheet) +
				"</td><td>" +
				esc(disc) +
				"</td></tr>"
			);
		});
		previewEl.innerHTML =
			'<p class="text-muted mb-1">Discipline is taken from each sheet number (A → Architectural, S → Structural, E → Electrical, …).</p>' +
			'<div class="table-responsive" style="max-height:220px;overflow:auto">' +
			'<table class="table table-sm table-bordered mb-0"><thead><tr><th>File</th><th>Sheet</th><th>Discipline</th></tr></thead><tbody>' +
			rows.join("") +
			"</tbody></table></div>";
	}

	function parseErrorBody(res, text) {
		var msg = res.status + " " + (text || res.statusText);
		try {
			var j = JSON.parse(text);
			if (j && (j.error || j.detail)) {
				msg = [j.error, j.detail].filter(Boolean).join(": ");
			}
		} catch (parseErr) {
			/* not JSON */
		}
		return msg;
	}

	function drawingFilePutUrl(postUrl, itemId) {
		var path = "/api/v1/drawings/" + encodeURIComponent(itemId) + "/file";
		try {
			var u = new URL(postUrl, typeof location !== "undefined" ? location.href : "http://localhost");
			var idx = u.pathname.indexOf("/api/v1/");
			if (idx >= 0) {
				u.pathname = u.pathname.slice(0, idx) + path;
				u.search = "";
				return u.toString();
			}
		} catch (e) {}
		return path;
	}

	function putDrawingThroughApi(postUrl, itemId, file, headers) {
		var fd = new FormData();
		fd.append("file", file, file.name || "drawing.pdf");
		return fetch(drawingFilePutUrl(postUrl, itemId), {
			method: "PUT",
			credentials: "include",
			headers: headers || {},
			body: fd,
		}).then(function (res) {
			return res.text().then(function (t) {
				if (res.ok) return;
				throw new Error(parseErrorBody(res, t) || "The website could not store the PDF (" + res.status + ").");
			});
		});
	}

	function postOne(url, file, drawingSet, headers) {
		var fd = new FormData();
		fd.append("file", file);
		fd.append("split_pages", "true");
		if (drawingSet) fd.append("drawing_set", drawingSet);
		return fetch(url, {
			method: "POST",
			body: fd,
			credentials: "include",
			headers: headers || {},
		}).then(function (res) {
			return res.text().then(function (t) {
				var j = null;
				try {
					j = t ? JSON.parse(t) : null;
				} catch (parseErr) {
					j = null;
				}
				if (j && j.file_pending && j.upload && j.item) {
					return putDrawingThroughApi(url, j.item.id, file, headers).then(function () {
						return j;
					});
				}
				if (!res.ok) {
					throw new Error(parseErrorBody(res, t));
				}
				return j;
			});
		});
	}

	function uploadFiles(opts) {
		var files = (opts && opts.files) || [];
		var url = opts && opts.url;
		var drawingSet = ((opts && opts.drawingSet) || "").trim();
		var headers = (opts && opts.headers) || {};
		var onProgress = opts && opts.onProgress;
		var i = 0;
		var ok = 0;
		var failed = [];

		function next() {
			if (i >= files.length) {
				return Promise.resolve({ ok: ok, failed: failed, total: files.length });
			}
			var file = files[i];
			var n = i + 1;
			i += 1;
			if (typeof onProgress === "function") onProgress(n, files.length, file);
			return postOne(url, file, drawingSet, headers)
				.then(function () {
					ok += 1;
					return next();
				})
				.catch(function (e) {
					failed.push({ name: file.name, message: (e && e.message) || String(e) });
					return next();
				});
		}

		if (!url || !files.length) {
			return Promise.resolve({ ok: 0, failed: failed, total: files.length });
		}
		return next();
	}

	function formatResultMessage(result) {
		if (!result) return "";
		if (!result.failed || !result.failed.length) {
			return result.ok === 1 ? "Uploaded 1 PDF." : "Uploaded " + result.ok + " PDFs.";
		}
		var lines = result.failed.map(function (f) {
			return (f.name || "file") + ": " + (f.message || "upload failed");
		});
		var head =
			result.ok > 0
				? "Uploaded " + result.ok + " of " + result.total + " PDFs. Could not upload:"
				: "Could not upload:";
		return head + "\n" + lines.join("\n");
	}

	global.USISDrawingUpload = {
		labelsFromFilename: labelsFromFilename,
		disciplineFromSheetNumber: disciplineFromSheetNumber,
		listPdfFiles: listPdfFiles,
		renderFilePreview: renderFilePreview,
		uploadFiles: uploadFiles,
		formatResultMessage: formatResultMessage,
	};
})(typeof window !== "undefined" ? window : this);
