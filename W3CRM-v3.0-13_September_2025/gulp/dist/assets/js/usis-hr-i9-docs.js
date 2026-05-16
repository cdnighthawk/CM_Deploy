/**
 * I-9 supporting document photo upload (List A / B / C) for hire wizard.
 */
(function (global) {
	"use strict";

	var MAX_PER_SLOT = 3;
	var docsBySlot = { list_a: [], list_b: [], list_c: [] };
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
		docsBySlot = { list_a: [], list_b: [], list_c: [] };
		(list || []).forEach(function (d) {
			if (docsBySlot[d.slot]) docsBySlot[d.slot].push(d);
		});
		Object.keys(docsBySlot).forEach(function (s) {
			docsBySlot[s].sort(function (a, b) {
				return (a.sort_order || 0) - (b.sort_order || 0);
			});
		});
	}

	function fileUrl(item) {
		var path = item.file_url || "/api/v1/hr/me/i9-section1/documents/" + item.id + "/file";
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

	function upload(slot, file) {
		var fd = new FormData();
		fd.append("file", file);
		fd.append("slot", slot);
		return fetch(apiBaseFn() + "/api/v1/hr/me/i9-section1/documents", {
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
		return fetch(apiBaseFn() + "/api/v1/hr/me/i9-section1/documents/" + encodeURIComponent(fileId), {
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

	function renderSlot(container, slot) {
		if (!container) return;
		var items = docsBySlot[slot] || [];
		var canAdd = !locked && items.length < MAX_PER_SLOT;
		var html =
			'<p class="small fw-semibold mb-1">Photos of this document</p>' +
			'<p class="text-muted small mb-2">Take a photo or upload an image (front required; back optional). Up to ' +
			MAX_PER_SLOT +
			" images.</p>";
		if (items.length) {
			html += '<div class="d-flex flex-wrap gap-2 mb-2 usis-i9-doc-thumbs">';
			items.forEach(function (it, idx) {
				var label = idx === 0 ? "Front" : idx === 1 ? "Back" : "Photo " + (idx + 1);
				html +=
					'<div class="usis-i9-doc-thumb position-relative border rounded overflow-hidden">' +
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
						'<button type="button" class="btn btn-danger btn-sm position-absolute top-0 end-0 m-1 py-0 px-1 usis-i9-doc-remove" data-file-id="' +
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
				'<label class="btn btn-outline-primary btn-sm mb-0 usis-i9-doc-add">' +
				"Add photo" +
				'<input type="file" class="d-none" accept="image/*" capture="environment" data-slot="' +
				esc(slot) +
				'">' +
				"</label>" +
				'<span class="text-muted small usis-i9-doc-status"></span>' +
				"</div>";
		} else if (locked) {
			html += '<p class="text-muted small mb-0">Document photos are locked after I-9 signature.</p>';
		}
		container.innerHTML = html;

		container.querySelectorAll(".usis-i9-doc-remove").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var fid = btn.getAttribute("data-file-id");
				if (!fid || !window.confirm("Remove this photo?")) return;
				btn.disabled = true;
				remove(fid)
					.then(function () {
						docsBySlot[slot] = (docsBySlot[slot] || []).filter(function (d) {
							return d.id !== fid;
						});
						renderSlot(container, slot);
						if (onChange) onChange();
						notifyOk("Photo removed.");
					})
					.catch(function (e) {
						btn.disabled = false;
						notifyErr(e.message || String(e));
					});
			});
		});

		var input = container.querySelector('input[type="file"][data-slot]');
		var statusEl = container.querySelector(".usis-i9-doc-status");
		if (input) {
			input.addEventListener("change", function () {
				var file = input.files && input.files[0];
				input.value = "";
				if (!file) return;
				if (statusEl) statusEl.textContent = "Uploading…";
				var addBtn = container.querySelector(".usis-i9-doc-add");
				if (addBtn) addBtn.classList.add("disabled");
				upload(slot, file)
					.then(function (j) {
						var item = j.item;
						if (item) {
							if (!docsBySlot[slot]) docsBySlot[slot] = [];
							docsBySlot[slot].push(item);
							docsBySlot[slot].sort(function (a, b) {
								return (a.sort_order || 0) - (b.sort_order || 0);
							});
						}
						renderSlot(container, slot);
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
		Object.keys(docsBySlot).forEach(function (slot) {
			(docsBySlot[slot] || []).forEach(function (d) {
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
		root.querySelectorAll("[data-i9-doc-slot]").forEach(function (el) {
			var slot = el.getAttribute("data-i9-doc-slot");
			if (slot) renderSlot(el, slot);
		});
	}

	global.USISHrI9Docs = {
		setDocuments: setDocuments,
		getAll: getAll,
		wire: wire,
	};
})(typeof window !== "undefined" ? window : this);
