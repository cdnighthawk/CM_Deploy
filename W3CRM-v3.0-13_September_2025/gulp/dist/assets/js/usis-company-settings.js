/**
 * Company settings — named office locations for shipping and lead distance.
 */
(function () {
	"use strict";

	function api() {
		return window.USIS_API || {};
	}

	function fetchJson(path, opts) {
		return api().fetchJson(path, opts || {});
	}

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function $(id) {
		return document.getElementById(id);
	}

	function flash(msg, kind) {
		var el = $("usis-co-flash");
		if (!el) return;
		el.className = "alert py-2 px-3 mb-3 " + (kind === "error" ? "alert-danger" : "alert-success");
		el.textContent = msg || "";
		el.classList.toggle("d-none", !msg);
	}

	function setErr(msg) {
		var el = $("usis-co-err");
		if (!el) return;
		el.textContent = msg || "";
		el.classList.toggle("d-none", !msg);
	}

	function modal() {
		var node = $("usis-co-modal");
		if (!node || !window.bootstrap || !window.bootstrap.Modal) return null;
		return window.bootstrap.Modal.getOrCreateInstance(node);
	}

	var items = [];

	function render() {
		var tbody = $("usis-co-tbody");
		if (!tbody) return;
		if (!items.length) {
			tbody.innerHTML =
				'<tr><td colspan="4" class="text-muted">No offices yet. Add the shops and yards vendors should ship to.</td></tr>';
			return;
		}
		tbody.innerHTML = items
			.map(function (o) {
				return (
					"<tr>" +
					"<td>" +
					esc(o.name || o.label || "Office") +
					"</td>" +
					"<td class='small' style='white-space:pre-wrap'>" +
					esc(o.address || "—") +
					"</td>" +
					"<td>" +
					(o.is_default ? '<span class="badge bg-primary">Default</span>' : "") +
					"</td>" +
					'<td class="text-end text-nowrap">' +
					'<button type="button" class="btn btn-sm btn-outline-secondary me-1" data-co-edit="' +
					esc(o.id) +
					'">Edit</button>' +
					'<button type="button" class="btn btn-sm btn-outline-danger" data-co-del="' +
					esc(o.id) +
					'">Remove</button>' +
					"</td>" +
					"</tr>"
				);
			})
			.join("");
	}

	function load() {
		return fetchJson("/api/v1/office-locations")
			.then(function (d) {
				items = (d && d.items) || [];
				render();
			})
			.catch(function (err) {
				flash(err.message || "Could not load offices.", "error");
			});
	}

	function openForm(row) {
		setErr("");
		$("usis-co-id").value = row && row.id ? row.id : "";
		$("usis-co-name").value = (row && row.name) || "";
		$("usis-co-addr1").value = (row && row.address_line1) || "";
		$("usis-co-addr2").value = (row && row.address_line2) || "";
		$("usis-co-city").value = (row && row.city) || "";
		$("usis-co-state").value = (row && row.state) || "";
		$("usis-co-zip").value = (row && row.postal_code) || "";
		$("usis-co-default").checked = !!(row && row.is_default) || (!row && !items.length);
		$("usis-co-modal-title").textContent = row ? "Edit office" : "Add office";
		var m = modal();
		if (m) m.show();
	}

	function save() {
		setErr("");
		var id = $("usis-co-id").value;
		var payload = {
			name: $("usis-co-name").value.trim() || "Office",
			address_line1: $("usis-co-addr1").value.trim() || null,
			address_line2: $("usis-co-addr2").value.trim() || null,
			city: $("usis-co-city").value.trim() || null,
			state: $("usis-co-state").value.trim() || null,
			postal_code: $("usis-co-zip").value.trim() || null,
			is_default: !!$("usis-co-default").checked,
		};
		var path = id ? "/api/v1/office-locations/" + encodeURIComponent(id) : "/api/v1/office-locations";
		var method = id ? "PATCH" : "POST";
		fetchJson(path, { method: method, body: payload })
			.then(function () {
				var m = modal();
				if (m) m.hide();
				flash("Office saved.", "success");
				return load();
			})
			.catch(function (err) {
				setErr(err.message || "Could not save office.");
			});
	}

	function remove(id) {
		if (!id) return;
		if (!window.confirm("Remove this office?")) return;
		fetchJson("/api/v1/office-locations/" + encodeURIComponent(id), { method: "DELETE" })
			.then(function () {
				flash("Office removed.", "success");
				return load();
			})
			.catch(function (err) {
				flash(err.message || "Could not remove office.", "error");
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		var add = $("usis-co-add");
		if (add) add.addEventListener("click", function () {
			openForm(null);
		});
		var saveBtn = $("usis-co-save");
		if (saveBtn) saveBtn.addEventListener("click", save);
		var tbody = $("usis-co-tbody");
		if (tbody) {
			tbody.addEventListener("click", function (ev) {
				var edit = ev.target.closest("[data-co-edit]");
				if (edit) {
					var row = items.filter(function (o) {
						return o.id === edit.getAttribute("data-co-edit");
					})[0];
					openForm(row || null);
					return;
				}
				var del = ev.target.closest("[data-co-del]");
				if (del) remove(del.getAttribute("data-co-del"));
			});
		}
		load();
	});
})();
