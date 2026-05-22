/**
 * Union card / dispatch photo upload for hire wizard.
 */
(function (global) {
	"use strict";

	var MAX_PER_KIND = 3;
	var docsByKind = { union_card: [], union_dispatch: [] };
	var locked = false;
	var apiBaseFn = function () {
		return "";
	};
	var onChange = null;

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function setDocuments(list) {
		docsByKind = { union_card: [], union_dispatch: [] };
		(list || []).forEach(function (d) {
			if (docsByKind[d.document_kind]) docsByKind[d.document_kind].push(d);
		});
		Object.keys(docsByKind).forEach(function (s) {
			docsByKind[s].sort(function (a, b) {
				return (a.sort_order || 0) - (b.sort_order || 0);
			});
		});
	}

	function fileUrl(item) {
		var path = item.file_url || "/api/v1/hr/me/hire-wizard/union-documents/" + item.id + "/file";
		var base = apiBaseFn();
		if (path.indexOf("http") === 0) return path;
		return base + path;
	}

	function notifyErr(msg) {
		if (global.USISNotify) global.USISNotify.error(msg);
	}

	function notifyOk(msg) {
		if (global.USISNotify) global.USISNotify.success(msg);
	}

	function upload(kind, file) {
		var fd = new FormData();
		fd.append("file", file);
		fd.append("kind", kind);
		return fetch(apiBaseFn() + "/api/v1/hr/me/hire-wizard/union-documents", {
			method: "POST",
			credentials: "include",
			body: fd,
		}).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error(j.error || "Upload failed");
				return j;
			});
		});
	}

	function remove(fileId) {
		return fetch(apiBaseFn() + "/api/v1/hr/me/hire-wizard/union-documents/" + encodeURIComponent(fileId), {
			method: "DELETE",
			credentials: "include",
			headers: { Accept: "application/json" },
		}).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error(j.error || "Delete failed");
				return j;
			});
		});
	}

	function renderKind(container, kind) {
		if (!container) return;
		var items = docsByKind[kind] || [];
		var canAdd = !locked && items.length < MAX_PER_KIND;
		var isCard = kind === "union_card";
		var html =
			'<p class="small fw-semibold mb-1">' +
			(isCard ? "Union card photos" : "Union dispatch photos") +
			"</p>" +
			'<p class="text-muted small mb-2">Take a photo or upload an image' +
			(isCard ? " (optional)" : "") +
			". Up to " +
			MAX_PER_KIND +
			" images.</p>";
		if (items.length) {
			html += '<div class="d-flex flex-wrap gap-2 mb-2 usis-union-doc-thumbs">';
			items.forEach(function (it, idx) {
				var label =
					kind === "union_card"
						? idx === 0
							? "Front"
							: idx === 1
								? "Back"
								: "Photo " + (idx + 1)
						: "Photo " + (idx + 1);
				html +=
					'<div class="usis-union-doc-thumb position-relative border rounded overflow-hidden">' +
					'<img src="' +
					esc(fileUrl(it)) +
					'" alt="' +
					esc(label) +
					'" class="d-block" width="96" height="96" style="object-fit:cover">' +
					'<span class="badge text-bg-secondary position-absolute top-0 start-0 m-1" style="font-size:0.65rem">' +
					esc(label) +
					"</span>";
				if (!locked) {
					html +=
						'<button type="button" class="btn btn-danger btn-sm position-absolute top-0 end-0 m-1 py-0 px-1 usis-union-doc-remove" data-file-id="' +
						esc(it.id) +
						'" title="Remove photo">&times;</button>';
				}
				html += "</div>";
			});
			html += "</div>";
		}
		if (canAdd) {
			html +=
				'<div class="d-flex flex-wrap gap-2 align-items-center">' +
				'<label class="btn btn-outline-primary btn-sm mb-0 usis-union-doc-add">' +
				"Add photo" +
				'<input type="file" class="d-none" accept="image/*" capture="environment" data-kind="' +
				esc(kind) +
				'">' +
				"</label>" +
				'<span class="text-muted small usis-union-doc-status"></span>' +
				"</div>";
		} else if (locked) {
			html += '<p class="text-muted small mb-0">Union document photos are locked after hire wizard is complete.</p>';
		}
		container.innerHTML = html;

		container.querySelectorAll(".usis-union-doc-remove").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var fid = btn.getAttribute("data-file-id");
				if (!fid || !window.confirm("Remove this photo?")) return;
				btn.disabled = true;
				remove(fid)
					.then(function () {
						docsByKind[kind] = (docsByKind[kind] || []).filter(function (d) {
							return d.id !== fid;
						});
						renderKind(container, kind);
						if (onChange) onChange();
						notifyOk("Photo removed.");
					})
					.catch(function (e) {
						btn.disabled = false;
						notifyErr(e.message || String(e));
					});
			});
		});

		var input = container.querySelector('input[type="file"][data-kind]');
		var statusEl = container.querySelector(".usis-union-doc-status");
		if (input) {
			input.addEventListener("change", function () {
				var file = input.files && input.files[0];
				input.value = "";
				if (!file) return;
				if (statusEl) statusEl.textContent = "Uploading…";
				var addBtn = container.querySelector(".usis-union-doc-add");
				if (addBtn) addBtn.classList.add("disabled");
				upload(kind, file)
					.then(function (j) {
						var item = j.item;
						if (item) {
							if (!docsByKind[kind]) docsByKind[kind] = [];
							docsByKind[kind].push(item);
							docsByKind[kind].sort(function (a, b) {
								return (a.sort_order || 0) - (b.sort_order || 0);
							});
						}
						renderKind(container, kind);
						if (onChange) onChange();
						notifyOk("Photo uploaded.");
					})
					.catch(function (e) {
						if (statusEl) statusEl.textContent = "";
						if (addBtn) addBtn.classList.remove("disabled");
						notifyErr(e.message || String(e));
					});
			});
		}
	}

	function getAll() {
		var out = [];
		Object.keys(docsByKind).forEach(function (k) {
			(docsByKind[k] || []).forEach(function (d) {
				out.push(d);
			});
		});
		return out;
	}

	function wire(root, opts) {
		if (!root) return;
		opts = opts || {};
		locked = !!opts.locked;
		if (typeof opts.apiBase === "function") apiBaseFn = opts.apiBase;
		if (opts.documents) setDocuments(opts.documents);
		onChange = opts.onChange || null;
		root.querySelectorAll("[data-union-doc-kind]").forEach(function (el) {
			var k = el.getAttribute("data-union-doc-kind");
			if (k) renderKind(el, k);
		});
	}

	global.USISHrUnionDocs = {
		setDocuments: setDocuments,
		getAll: getAll,
		wire: wire,
	};
})(typeof window !== "undefined" ? window : this);
