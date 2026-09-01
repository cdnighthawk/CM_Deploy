(function () {
	"use strict";

	var selectedId = null;

	function esc(s) {
		if (s == null) return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function fetchJson(path, opts) {
		return window.USIS_API.fetchJson(path, opts || {});
	}

	function loadCompanies() {
		var q = ((document.getElementById("usis-co-q") || {}).value || "").trim();
		fetchJson("/api/v1/companies?limit=100&q=" + encodeURIComponent(q))
			.then(function (data) {
				var tbody = document.getElementById("usis-co-tbody");
				var items = data.items || [];
				if (!items.length) {
					tbody.innerHTML = '<tr><td colspan="2" class="text-muted">No companies.</td></tr>';
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
							"</td></tr>"
						);
					})
					.join("");
			})
			.catch(function () {
				document.getElementById("usis-co-tbody").innerHTML =
					'<tr><td colspan="2" class="text-muted">Could not load companies.</td></tr>';
			});
	}

	function loadDetail() {
		if (!selectedId) return;
		fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/contacts")
			.then(function (data) {
				var items = data.items || [];
				var tbody = document.getElementById("usis-ct-tbody");
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
				document.getElementById("usis-ins-tbody").innerHTML = items.length
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
				document.getElementById("usis-lic-tbody").innerHTML = items.length
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

	function onReady() {
		var qsId = new URLSearchParams(window.location.search).get("id");
		if (qsId) selectedId = qsId;
		loadCompanies();
		if (qsId) loadDetail();
		var q = document.getElementById("usis-co-q");
		if (q) q.addEventListener("input", loadCompanies);
		document.getElementById("usis-co-tbody").addEventListener("click", function (e) {
			var tr = e.target.closest("tr[data-id]");
			if (!tr) return;
			selectedId = tr.getAttribute("data-id");
			loadCompanies();
			loadDetail();
		});
		document.getElementById("usis-co-add").addEventListener("click", function () {
			var name = window.prompt("Company name");
			if (!name) return;
			var ctype = window.prompt("Type (vendor, subcontractor, owner, architect, other)", "vendor") || "other";
			fetchJson("/api/v1/companies", { method: "POST", body: { name: name.trim(), company_type: ctype.trim() } })
				.then(loadCompanies)
				.catch(function (err) {
					window.alert((err && err.body) || "Could not create company.");
				});
		});
		document.getElementById("usis-ct-add").addEventListener("click", function () {
			if (!selectedId) return;
			fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/contacts", {
				method: "POST",
				body: {
					first_name: document.getElementById("usis-ct-first").value,
					last_name: document.getElementById("usis-ct-last").value,
					email: document.getElementById("usis-ct-email").value,
				},
			}).then(loadDetail);
		});
		document.getElementById("usis-ins-add").addEventListener("click", function () {
			if (!selectedId) return;
			fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/insurance", {
				method: "POST",
				body: {
					policy_type: document.getElementById("usis-ins-type").value,
					carrier: document.getElementById("usis-ins-carrier").value,
					expires_on: document.getElementById("usis-ins-exp").value,
				},
			}).then(loadDetail);
		});
		document.getElementById("usis-lic-add").addEventListener("click", function () {
			if (!selectedId) return;
			fetchJson("/api/v1/companies/" + encodeURIComponent(selectedId) + "/licenses", {
				method: "POST",
				body: {
					license_type: document.getElementById("usis-lic-type").value,
					license_number: document.getElementById("usis-lic-num").value,
					expires_on: document.getElementById("usis-lic-exp").value,
				},
			}).then(loadDetail);
		});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
	else onReady();
})();
