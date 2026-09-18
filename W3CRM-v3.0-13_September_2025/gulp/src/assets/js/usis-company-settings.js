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
					(window.USISUi && window.USISUi.rowMenu
						? window.USISUi.rowMenu({
								id: o.id,
								editData: { "co-edit": o.id },
								createTarget: "#usis-co-add",
								deleteData: { "co-del": o.id },
								deleteClass: "",
							})
						: '<button type="button" class="btn btn-sm btn-outline-secondary me-1" data-co-edit="' +
							esc(o.id) +
							'">Edit</button>' +
							'<button type="button" class="btn btn-sm btn-outline-danger" data-co-del="' +
							esc(o.id) +
							'">Remove</button>') +
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

	function loadBcStatus() {
		var statusEl = $("usis-co-bc-status");
		var btn = $("usis-co-bc-connect");
		return fetchJson("/api/v1/integrations/buildingconnected/status")
			.then(function (d) {
				var connected = !!(d && d.connected);
				if (statusEl) {
					statusEl.textContent = connected
						? "Connected. Bid Board sync uses this company’s Autodesk account."
						: "Not connected. Connect BuildingConnected so leads pull into this company.";
					statusEl.className = "small mb-0 " + (connected ? "text-success" : "text-muted");
				}
				if (btn) btn.textContent = connected ? "Reconnect BuildingConnected" : "Connect BuildingConnected";
			})
			.catch(function (err) {
				if (statusEl) {
					statusEl.textContent = (err && err.message) || "Could not check BuildingConnected status.";
					statusEl.className = "small mb-0 text-danger";
				}
			});
	}

	function openBcOauth() {
		var width = 520;
		var height = 720;
		var left = Math.max(0, Math.round((window.screenX || 0) + ((window.outerWidth || 900) - width) / 2));
		var top = Math.max(0, Math.round((window.screenY || 0) + ((window.outerHeight || 700) - height) / 2));
		var url =
			(window.usisApiBase ? window.usisApiBase() : "") +
			"/api/v1/integrations/buildingconnected/oauth/start?return_to=" +
			encodeURIComponent("/usis-company-settings.html");
		var popup = window.open(
			url,
			"usisBcOauth",
			"popup=yes,width=" + width + ",height=" + height + ",left=" + left + ",top=" + top
		);
		if (!popup) {
			flash("Pop-up blocked. Allow pop-ups for this site, then try Connect BuildingConnected again.", "error");
			return;
		}
		try {
			popup.focus();
		} catch (e) {}
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
		var bcBtn = $("usis-co-bc-connect");
		if (bcBtn) bcBtn.addEventListener("click", openBcOauth);
		window.addEventListener("message", function (event) {
			if (event.origin !== window.location.origin) return;
			var data = event.data;
			if (!data || data.source !== "usis-bc-oauth") return;
			if (data.ok) {
				flash("BuildingConnected connected for this company.", "success");
			} else {
				flash(data.error || "BuildingConnected reconnect failed.", "error");
			}
			loadBcStatus();
		});
		load();
		loadBcStatus();
	});
})();
