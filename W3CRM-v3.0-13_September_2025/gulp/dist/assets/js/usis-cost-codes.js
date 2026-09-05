/**
 * Company-wide master cost codes (Admin → Cost codes).
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

	function el(id) {
		return document.getElementById(id);
	}

	function val(id) {
		var n = el(id);
		return n ? String(n.value || "").trim() : "";
	}

	function setVal(id, v) {
		var n = el(id);
		if (n) n.value = v == null ? "" : String(v);
	}

	var items = [];
	var keepOpen = false;

	function modal() {
		var node = el("usis-modal-cc");
		if (!node || !window.bootstrap || !window.bootstrap.Modal) return null;
		return window.bootstrap.Modal.getOrCreateInstance(node);
	}

	function setErr(msg) {
		var box = el("usis-cc-err");
		if (!box) return;
		box.textContent = msg || "";
		box.classList.toggle("d-none", !msg);
	}

	function nextOrder() {
		var max = 0;
		items.forEach(function (it) {
			var n = Number(it.order_number);
			if (!isNaN(n) && n > max) max = n;
		});
		return max + 1;
	}

	function payload() {
		return {
			code: val("usis-cc-code"),
			description: val("usis-cc-desc"),
			order_number: val("usis-cc-order") === "" ? 0 : Number(val("usis-cc-order")),
			units: val("usis-cc-units") || "LS",
			default_tax_code: val("usis-cc-tax"),
			ap_tax_code: val("usis-cc-ap-tax"),
			ar_tax_code: val("usis-cc-ar-tax"),
			division_code: val("usis-cc-div"),
			division_desc: val("usis-cc-div-desc"),
			major_code: val("usis-cc-maj"),
			major_desc: val("usis-cc-maj-desc"),
			minor_code: val("usis-cc-min"),
			minor_desc: val("usis-cc-min-desc"),
			subminor_code: val("usis-cc-submin"),
			subminor_desc: val("usis-cc-submin-desc"),
			owner_cost_code: val("usis-cc-owner"),
			owner_cost_code_desc: val("usis-cc-owner-desc"),
			workers_comp_code: val("usis-cc-wc"),
		};
	}

	function fillForm(row) {
		var form = el("usis-cc-form");
		if (form) form.reset();
		setVal("usis-cc-id", row && row.id ? row.id : "");
		setVal("usis-cc-order", row ? row.order_number : nextOrder());
		setVal("usis-cc-code", row ? row.code : "");
		setVal("usis-cc-desc", row ? row.description : "");
		setVal("usis-cc-units", row && row.units ? row.units : "LS");
		setVal("usis-cc-tax", row ? row.default_tax_code : "");
		setVal("usis-cc-ap-tax", row ? row.ap_tax_code : "");
		setVal("usis-cc-ar-tax", row ? row.ar_tax_code : "");
		setVal("usis-cc-div", row ? row.division_code : "");
		setVal("usis-cc-div-desc", row ? row.division_desc : "");
		setVal("usis-cc-maj", row ? row.major_code : "");
		setVal("usis-cc-maj-desc", row ? row.major_desc : "");
		setVal("usis-cc-min", row ? row.minor_code : "");
		setVal("usis-cc-min-desc", row ? row.minor_desc : "");
		setVal("usis-cc-submin", row ? row.subminor_code : "");
		setVal("usis-cc-submin-desc", row ? row.subminor_desc : "");
		setVal("usis-cc-owner", row ? row.owner_cost_code : "");
		setVal("usis-cc-owner-desc", row ? row.owner_cost_code_desc : "");
		setVal("usis-cc-wc", row ? row.workers_comp_code : "");
		var title = el("usis-modal-cc-title");
		if (title) title.textContent = row ? "Cost code" : "Add cost code";
		var saveNew = el("usis-cc-save-new");
		if (saveNew) saveNew.classList.toggle("d-none", !!row);
		setErr("");
	}

	function openForm(row) {
		fillForm(row || null);
		var m = modal();
		if (m) m.show();
		setTimeout(function () {
			var code = el("usis-cc-code");
			if (code) code.focus();
		}, 200);
	}

	function render() {
		var tbody = el("usis-cc-tbody");
		if (!tbody) return;
		var q = val("usis-cc-q").toLowerCase();
		var rows = items.filter(function (it) {
			if (!q) return true;
			return (it.code || "").toLowerCase().indexOf(q) >= 0 || (it.description || "").toLowerCase().indexOf(q) >= 0;
		});
		if (!rows.length) {
			tbody.innerHTML = '<tr><td colspan="5" class="text-muted">No cost codes yet.</td></tr>';
			return;
		}
		tbody.innerHTML = rows
			.map(function (it) {
				return (
					'<tr class="usis-cc-row" data-id="' +
					esc(it.id) +
					'" style="cursor:pointer"><td>' +
					esc(it.order_number != null ? it.order_number : "") +
					"</td><td>" +
					esc(it.code || "") +
					"</td><td>" +
					esc(it.description || "") +
					"</td><td>" +
					esc(it.units || "") +
					'</td><td class="text-end">' +
					(window.USISUi && window.USISUi.rowMenu
						? window.USISUi.rowMenu({
								id: it.id,
								editClass: "usis-cc-edit",
								deleteClass: "usis-cc-del",
								createTarget: "#usis-cc-add",
							})
						: '<button type="button" class="btn btn-link btn-sm p-0 usis-cc-del">Delete</button>') +
					"</td></tr>"
				);
			})
			.join("");
	}

	function load() {
		return fetchJson("/api/v1/cost-codes")
			.then(function (data) {
				items = (data && data.items) || [];
				render();
			})
			.catch(function () {
				items = [];
				var tbody = el("usis-cc-tbody");
				if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="text-muted">Could not load cost codes.</td></tr>';
			});
	}

	function save() {
		var body = payload();
		if (!body.code || !body.description) {
			setErr("Code and description are required.");
			return Promise.reject(new Error("required"));
		}
		var id = val("usis-cc-id");
		return fetchJson("/api/v1/cost-codes" + (id ? "/" + encodeURIComponent(id) : ""), {
			method: id ? "PATCH" : "POST",
			body: body,
		})
			.then(function () {
				return load();
			})
			.then(function () {
				if (keepOpen) {
					fillForm(null);
					var code = el("usis-cc-code");
					if (code) code.focus();
				} else {
					var m = modal();
					if (m) m.hide();
				}
			})
			.catch(function (err) {
				var msg = "Could not save cost code.";
				if (err && err.body) {
					try {
						var parsed = JSON.parse(err.body);
						msg = parsed.error || msg;
					} catch (e) {
						msg = String(err.body).slice(0, 240) || msg;
					}
				}
				setErr(msg);
				throw err;
			})
			.finally(function () {
				keepOpen = false;
			});
	}

	function importCsv(file) {
		if (!file) return Promise.resolve();
		return file.text().then(function (text) {
			return fetchJson("/api/v1/cost-codes/import", { method: "POST", body: { csv: text } });
		}).then(function (result) {
			var created = result && result.created != null ? result.created : 0;
			var updated = result && result.updated != null ? result.updated : 0;
			window.alert("Imported " + created + " new and updated " + updated + " existing cost codes.");
			return load();
		}).catch(function (err) {
			var msg = "Could not import cost codes.";
			if (err && err.body) {
				try {
					var parsed = JSON.parse(err.body);
					msg = parsed.error || msg;
				} catch (e) {
					msg = String(err.body).slice(0, 240) || msg;
				}
			}
			window.alert(msg);
		});
	}

	function onReady() {
		load();
		var add = el("usis-cc-add");
		if (add) add.addEventListener("click", function () {
			openForm(null);
		});
		var importBtn = el("usis-cc-import");
		var importFile = el("usis-cc-import-file");
		if (importBtn && importFile) {
			importBtn.addEventListener("click", function () {
				importFile.click();
			});
			importFile.addEventListener("change", function () {
				var file = importFile.files && importFile.files[0];
				importFile.value = "";
				importCsv(file);
			});
		}
		var q = el("usis-cc-q");
		if (q) q.addEventListener("input", render);
		var form = el("usis-cc-form");
		if (form) {
			form.addEventListener("submit", function (e) {
				e.preventDefault();
				keepOpen = false;
				save();
			});
		}
		var saveNew = el("usis-cc-save-new");
		if (saveNew) {
			saveNew.addEventListener("click", function () {
				if (form && typeof form.reportValidity === "function" && !form.reportValidity()) return;
				keepOpen = true;
				save();
			});
		}
		var tbody = el("usis-cc-tbody");
		if (tbody) {
			tbody.addEventListener("click", function (e) {
				var del = e.target.closest(".usis-cc-del");
				var edit = e.target.closest(".usis-cc-edit");
				var tr = e.target.closest("tr[data-id]");
				if (del) {
					e.preventDefault();
					e.stopPropagation();
					if (!tr || !window.confirm("Delete this cost code from the company list?")) return;
					fetchJson("/api/v1/cost-codes/" + encodeURIComponent(tr.getAttribute("data-id")), { method: "DELETE" })
						.then(load)
						.catch(function () {
							window.alert("Could not delete cost code.");
						});
					return;
				}
				if (edit) {
					e.preventDefault();
					e.stopPropagation();
					if (!tr) return;
					var foundEdit = null;
					items.forEach(function (it) {
						if (String(it.id) === String(tr.getAttribute("data-id"))) foundEdit = it;
					});
					if (foundEdit) openForm(foundEdit);
					return;
				}
				if (!tr) return;
				var found = null;
				items.forEach(function (it) {
					if (String(it.id) === String(tr.getAttribute("data-id"))) found = it;
				});
				if (found) openForm(found);
			});
		}
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
})();
