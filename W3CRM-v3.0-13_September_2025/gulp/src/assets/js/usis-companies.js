(function () {
	"use strict";

	var selectedId = null;

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function $(id) {
		return document.getElementById(id);
	}

	function fetchJson(path, opts) {
		return window.USIS_API.fetchJson(path, opts || {});
	}

	function roleLabel(role) {
		if (role === "manufacturer") return "Manufacturer";
		if (role === "distributor") return "Distributor";
		if (role === "both") return "Both";
		return "";
	}

	function buyLabel(buy) {
		if (buy === "manufacturer") return "Manufacturer (direct)";
		if (buy === "distributor") return "Distributor / vendor";
		return buy || "";
	}

	function selectedRole() {
		var el = document.querySelector('input[name="usis-supply-role"]:checked');
		return el ? el.value : "";
	}

	function setRole(role) {
		var val = role || "";
		var el = document.querySelector('input[name="usis-supply-role"][value="' + val + '"]');
		if (el) el.checked = true;
		else {
			var unset = $("usis-role-unset");
			if (unset) unset.checked = true;
		}
	}

	function fillDatalist(id, values) {
		var list = $(id);
		if (!list) return;
		list.innerHTML = (values || [])
			.map(function (v) {
				if (typeof v === "string") {
					return '<option value="' + esc(v) + '"></option>';
				}
				var value = v.value || v.display || v.code || v.name || "";
				var label = v.label || v.title || value;
				return '<option value="' + esc(value) + '">' + esc(label) + "</option>";
			})
			.join("");
	}

	function loadOptions() {
		fetchJson("/api/v1/companies/line-card-options")
			.then(function (data) {
				var sections = data.csi_sections || [];
				fillDatalist(
					"usis-csi-list",
					sections.map(function (s) {
						var code = s.code || s.display || s.csi_spec_section || "";
						var title = s.title || s.name || "";
						return { value: code, label: title ? code + " — " + title : code };
					})
				);
				fillDatalist("usis-mfr-list", data.manufacturers || []);
			})
			.catch(function () {});
	}

	function loadBuyChannels() {
		var tbody = $("usis-buy-tbody");
		if (!tbody) return;
		fetchJson("/api/v1/csi-buy-channels")
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					tbody.innerHTML = '<tr><td colspan="4" class="text-muted">No buy paths yet. Example: 10 26 00 manufacturer, 10 28 00 distributor.</td></tr>';
					return;
				}
				tbody.innerHTML = items
					.map(function (row) {
						return (
							"<tr><td>" +
							esc(row.csi_display || row.csi_spec_section) +
							"</td><td>" +
							esc(row.csi_title || "") +
							"</td><td>" +
							esc(buyLabel(row.buy_from)) +
							'</td><td class="text-end">' +
							(window.USISUi && window.USISUi.rowMenu
								? window.USISUi.rowMenu({
										id: row.csi_spec_section,
										createTarget: "#usis-buy-add",
										deleteClass: "",
										deleteData: { "buy-del": row.csi_spec_section },
									})
								: '<button type="button" class="btn btn-link btn-sm text-danger p-0" data-buy-del="' +
									esc(row.csi_spec_section) +
									'">Remove</button>') +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Could not load buy paths.</td></tr>';
			});
	}

	function loadCompanies() {
		var q = (($("usis-co-q") || {}).value || "").trim();
		fetchJson("/api/v1/companies?limit=200&q=" + encodeURIComponent(q))
			.then(function (data) {
				var tbody = $("usis-co-tbody");
				var items = data.items || [];
				if (!items.length) {
					tbody.innerHTML = '<tr><td colspan="4" class="text-muted">No companies.</td></tr>';
					return;
				}
				tbody.innerHTML = items
					.map(function (c) {
						var on = selectedId === c.id ? " table-active" : "";
						return (
							'<tr class="' +
							on +
							'" data-id="' +
							esc(c.id) +
							'"><td>' +
							esc(c.name) +
							"</td><td>" +
							esc(c.company_type || "") +
							"</td><td>" +
							esc(roleLabel(c.supply_role)) +
							'</td><td class="text-end">' +
							(window.USISUi && window.USISUi.rowMenu
								? window.USISUi.rowMenu({
										id: c.id,
										editClass: "usis-co-select",
										createTarget: "#usis-co-add",
										deleteClass: "usis-co-del",
									})
								: "") +
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				var tbody = $("usis-co-tbody");
				if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="text-muted">Could not load companies.</td></tr>';
			});
	}

	function renderLineCard(data) {
		var box = $("usis-lc-specs");
		if (!box) return;
		setRole(data.supply_role);
		var specs = data.specs || [];
		if (!specs.length) {
			box.innerHTML = '<p class="text-muted small mb-0">No specs on this line card yet.</p>';
			return;
		}
		box.innerHTML = specs
			.map(function (spec) {
				var csi = spec.csi_spec_section;
				var brands = spec.manufacturers || [];
				var chips = brands.length
					? brands
							.map(function (row) {
								return (
									'<span class="badge text-bg-light border me-1 mb-1">' +
									esc(row.manufacturer) +
									' <button type="button" class="btn-close btn-close-sm ms-1" data-lc-row="' +
									esc(row.id) +
									'" aria-label="Remove ' +
									esc(row.manufacturer) +
									'"></button></span>'
								);
							})
							.join("")
					: '<span class="text-muted small">Covers this spec (any brand).</span>';
				return (
					'<div class="border rounded p-2 mb-2" data-lc-csi="' +
					esc(csi) +
					'"><div class="d-flex justify-content-between align-items-start gap-2 mb-1"><div><strong>' +
					esc(spec.csi_display || csi) +
					"</strong> <span class=\"text-muted small\">" +
					esc(spec.csi_title || "") +
					'</span></div><button type="button" class="btn btn-link btn-sm text-danger p-0" data-lc-spec="' +
					esc(csi) +
					'">Remove spec</button></div><div class="mb-2">' +
					chips +
					'</div><div class="d-flex gap-2"><input class="form-control form-control-sm" data-lc-add-mfr="' +
					esc(csi) +
					'" list="usis-mfr-list" placeholder="Add manufacturer"><button type="button" class="btn btn-outline-secondary btn-sm" data-lc-add-mfr-btn="' +
					esc(csi) +
					'">Add</button></div></div>'
				);
			})
			.join("");
	}

	function loadLineCard() {
		var box = $("usis-lc-specs");
		if (!selectedId) {
			setRole("");
			if (box) box.innerHTML = '<p class="text-muted small mb-0">Select a company.</p>';
			return;
		}
		fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/line-card")
			.then(renderLineCard)
			.catch(function () {
				if (box) box.innerHTML = '<p class="text-muted small mb-0">Could not load line card.</p>';
			});
	}

	function loadDetail() {
		loadLineCard();
		if (!selectedId) return;
		fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/contacts")
			.then(function (data) {
				var items = data.items || [];
				var tbody = $("usis-ct-tbody");
				if (!tbody) return;
				tbody.innerHTML = items.length
					? items
							.map(function (c) {
								return (
									"<tr><td>" +
									esc([c.first_name, c.last_name].filter(Boolean).join(" ")) +
									"</td><td>" +
									esc(c.email || "") +
									"</td><td>" +
									esc(c.phone || "") +
									"</td></tr>"
								);
							})
							.join("")
					: '<tr><td colspan="3" class="text-muted">No contacts.</td></tr>';
			})
			.catch(function () {});
		fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/insurance")
			.then(function (data) {
				var items = data.items || [];
				var tbody = $("usis-ins-tbody");
				if (!tbody) return;
				tbody.innerHTML = items.length
					? items
							.map(function (p) {
								return (
									"<tr><td>" +
									esc(p.policy_type || "") +
									"</td><td>" +
									esc(p.carrier || "") +
									"</td><td>" +
									esc(p.expires_on || "") +
									"</td></tr>"
								);
							})
							.join("")
					: '<tr><td colspan="3" class="text-muted">No policies.</td></tr>';
			})
			.catch(function () {});
		fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/licenses")
			.then(function (data) {
				var items = data.items || [];
				var tbody = $("usis-lic-tbody");
				if (!tbody) return;
				tbody.innerHTML = items.length
					? items
							.map(function (p) {
								return (
									"<tr><td>" +
									esc(p.license_type || "") +
									"</td><td>" +
									esc(p.license_number || "") +
									"</td><td>" +
									esc(p.expires_on || "") +
									"</td></tr>"
								);
							})
							.join("")
					: '<tr><td colspan="3" class="text-muted">No licenses.</td></tr>';
			})
			.catch(function () {});
	}

	function saveRole() {
		if (!selectedId) return;
		fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId), {
			method: "PATCH",
			body: { supply_role: selectedRole() || null },
		})
			.then(loadCompanies)
			.catch(function (err) {
				window.alert((err && err.body && err.body.error) || (err && err.message) || "Could not save supply role.");
			});
	}

	function addLineCard(csi, manufacturer) {
		if (!selectedId) {
			window.alert("Select a company first.");
			return Promise.resolve();
		}
		var body = { csi_spec_section: csi };
		if (manufacturer) body.manufacturer = manufacturer;
		return fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/line-card", {
			method: "POST",
			body: body,
		}).then(renderLineCard);
	}

	function onReady() {
		var qsId = new URLSearchParams(window.location.search).get("id");
		if (qsId) selectedId = qsId;
		loadOptions();
		loadBuyChannels();
		loadCompanies();
		if (qsId) loadDetail();
		else loadLineCard();

		var q = $("usis-co-q");
		if (q) q.addEventListener("input", loadCompanies);

		var tbody = $("usis-co-tbody");
		if (tbody) {
			tbody.addEventListener("click", function (e) {
				var del = e.target.closest(".usis-co-del");
				if (del) {
					e.preventDefault();
					e.stopPropagation();
					var id = del.getAttribute("data-id");
					if (!id || !window.confirm("Delete this company?")) return;
					fetchJson("/api/v1/companies/" + encodeURIComponent(id), { method: "DELETE" })
						.then(function () {
							if (selectedId === id) selectedId = "";
							loadCompanies();
							loadDetail();
						})
						.catch(function () {
							window.alert("Could not delete company.");
						});
					return;
				}
				var tr = e.target.closest("tr[data-id]");
				if (!tr) return;
				selectedId = tr.getAttribute("data-id");
				loadCompanies();
				loadDetail();
			});
		}

		document.querySelectorAll('input[name="usis-supply-role"]').forEach(function (el) {
			el.addEventListener("change", saveRole);
		});

		var buyAdd = $("usis-buy-add");
		if (buyAdd) {
			buyAdd.addEventListener("click", function () {
				var csi = (($("usis-buy-csi") || {}).value || "").trim();
				var buyEl = document.querySelector('input[name="usis-buy-from"]:checked');
				if (!csi) {
					window.alert("Enter a CSI section, for example 10 26 00.");
					return;
				}
				fetchJson("/api/v1/csi-buy-channels", {
					method: "POST",
					body: { csi_spec_section: csi, buy_from: buyEl ? buyEl.value : "manufacturer" },
				})
					.then(function () {
						$("usis-buy-csi").value = "";
						loadBuyChannels();
					})
					.catch(function (err) {
						window.alert((err && err.body && err.body.error) || "Could not save buy path.");
					});
			});
		}

		var buyBody = $("usis-buy-tbody");
		if (buyBody) {
			buyBody.addEventListener("click", function (e) {
				var btn = e.target.closest("[data-buy-del]");
				if (!btn) return;
				var csi = btn.getAttribute("data-buy-del");
				fetchJson("/api/v1/csi-buy-channels/" + encodeURIComponent(csi), { method: "DELETE" })
					.then(loadBuyChannels)
					.catch(function (err) {
						window.alert((err && err.body && err.body.error) || "Could not remove buy path.");
					});
			});
		}

		var addSpec = $("usis-lc-add-spec");
		if (addSpec) {
			addSpec.addEventListener("click", function () {
				var csi = (($("usis-lc-csi") || {}).value || "").trim();
				var mfr = (($("usis-lc-mfr") || {}).value || "").trim();
				if (!csi) {
					window.alert("Enter a CSI section, for example 10 21 00.");
					return;
				}
				addLineCard(csi, mfr)
					.then(function () {
						$("usis-lc-csi").value = "";
						$("usis-lc-mfr").value = "";
					})
					.catch(function (err) {
						window.alert((err && err.body && err.body.error) || "Could not add spec.");
					});
			});
		}

		var specs = $("usis-lc-specs");
		if (specs) {
			specs.addEventListener("click", function (e) {
				var rowBtn = e.target.closest("[data-lc-row]");
				if (rowBtn && selectedId) {
					fetchJson(
						"/api/v1/companies/" +
							encodeURIComponent(selectedId) +
							"/line-card/" +
							encodeURIComponent(rowBtn.getAttribute("data-lc-row")),
						{ method: "DELETE" }
					)
						.then(renderLineCard)
						.catch(function (err) {
							window.alert((err && err.body && err.body.error) || "Could not remove manufacturer.");
						});
					return;
				}
				var specBtn = e.target.closest("[data-lc-spec]");
				if (specBtn && selectedId) {
					fetchJson(
						"/api/v1/companies/" +
							encodeURIComponent(selectedId) +
							"/line-card/specs/" +
							encodeURIComponent(specBtn.getAttribute("data-lc-spec")),
						{ method: "DELETE" }
					)
						.then(renderLineCard)
						.catch(function (err) {
							window.alert((err && err.body && err.body.error) || "Could not remove spec.");
						});
					return;
				}
				var addBtn = e.target.closest("[data-lc-add-mfr-btn]");
				if (addBtn) {
					var csi = addBtn.getAttribute("data-lc-add-mfr-btn");
					var inp = specs.querySelector('[data-lc-add-mfr="' + csi + '"]');
					var name = ((inp || {}).value || "").trim();
					if (!name) {
						window.alert("Enter a manufacturer name.");
						return;
					}
					addLineCard(csi, name)
						.then(function () {
							if (inp) inp.value = "";
						})
						.catch(function (err) {
							window.alert((err && err.body && err.body.error) || "Could not add manufacturer.");
						});
				}
			});
			specs.addEventListener("keydown", function (e) {
				if (e.key !== "Enter") return;
				var inp = e.target.closest("[data-lc-add-mfr]");
				if (!inp) return;
				e.preventDefault();
				var csi = inp.getAttribute("data-lc-add-mfr");
				var btn = specs.querySelector('[data-lc-add-mfr-btn="' + csi + '"]');
				if (btn) btn.click();
			});
		}

		var addCo = $("usis-co-add");
		if (addCo) {
			addCo.addEventListener("click", function () {
				var name = window.prompt("Company name");
				if (!name) return;
				var ctype = window.prompt("Type (vendor, subcontractor, owner, architect, other)", "vendor") || "other";
				fetchJson("/api/v1/companies", { method: "POST", body: { name: name.trim(), company_type: ctype.trim() } })
					.then(function (data) {
						selectedId = data.item && data.item.id;
						loadCompanies();
						loadDetail();
					})
					.catch(function (err) {
						window.alert((err && err.body) || "Could not create company.");
					});
			});
		}

		var ctAdd = $("usis-ct-add");
		if (ctAdd) {
			ctAdd.addEventListener("click", function () {
				if (!selectedId) return;
				fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/contacts", {
					method: "POST",
					body: {
						first_name: $("usis-ct-first").value,
						last_name: $("usis-ct-last").value,
						email: $("usis-ct-email").value,
					},
				}).then(loadDetail);
			});
		}
		var insAdd = $("usis-ins-add");
		if (insAdd) {
			insAdd.addEventListener("click", function () {
				if (!selectedId) return;
				fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/insurance", {
					method: "POST",
					body: {
						policy_type: $("usis-ins-type").value,
						carrier: $("usis-ins-carrier").value,
						expires_on: $("usis-ins-exp").value,
					},
				}).then(loadDetail);
			});
		}
		var licAdd = $("usis-lic-add");
		if (licAdd) {
			licAdd.addEventListener("click", function () {
				if (!selectedId) return;
				fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/licenses", {
					method: "POST",
					body: {
						license_type: $("usis-lic-type").value,
						license_number: $("usis-lic-num").value,
						expires_on: $("usis-lic-exp").value,
					},
				}).then(loadDetail);
			});
		}
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
})();
