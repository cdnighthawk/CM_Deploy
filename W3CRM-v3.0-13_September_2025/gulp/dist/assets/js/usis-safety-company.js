(function () {
	"use strict";

	function api() {
		return window.USIS_API;
	}

	function show(el, msg, isErr) {
		if (!el) return;
		el.textContent = msg || "";
		el.classList.toggle("d-none", !msg);
		if (isErr) el.classList.add("alert-danger");
	}

	function val(id) {
		var el = document.getElementById(id);
		return el ? String(el.value || "").trim() : "";
	}

	function setVal(id, value) {
		var el = document.getElementById(id);
		if (el) el.value = value == null ? "" : String(value);
	}

	function fill(payload) {
		var p = payload || {};
		var admin = p.iippAdministrator || {};
		var phones = p.phones || {};
		var addr = (p.addresses && p.addresses.primary) || {};
		setVal("usis-safco-legal", p.legalName);
		setVal("usis-safco-dba", p.dba);
		setVal("usis-safco-short", p.shortName);
		setVal("usis-safco-admin-name", admin.name);
		setVal("usis-safco-admin-title", admin.title);
		setVal("usis-safco-admin-phone", admin.phone);
		setVal("usis-safco-admin-email", admin.email);
		setVal("usis-safco-phone-office", phones.office);
		setVal("usis-safco-phone-safety", phones.safety);
		setVal("usis-safco-phone-after", p.afterHoursPhone);
		setVal("usis-safco-addr1", addr.line1);
		setVal("usis-safco-city", addr.city);
		setVal("usis-safco-state", addr.state);
		setVal("usis-safco-zip", addr.zip);
	}

	function collect() {
		return {
			legalName: val("usis-safco-legal"),
			dba: val("usis-safco-dba"),
			shortName: val("usis-safco-short"),
			iippAdministrator: {
				name: val("usis-safco-admin-name"),
				title: val("usis-safco-admin-title"),
				phone: val("usis-safco-admin-phone"),
				email: val("usis-safco-admin-email"),
			},
			afterHoursPhone: val("usis-safco-phone-after"),
			phones: {
				office: val("usis-safco-phone-office"),
				safety: val("usis-safco-phone-safety"),
			},
			addresses: {
				primary: {
					line1: val("usis-safco-addr1"),
					city: val("usis-safco-city"),
					state: val("usis-safco-state"),
					zip: val("usis-safco-zip"),
				},
			},
		};
	}

	function renderDocs(items) {
		var box = document.getElementById("usis-safco-docs");
		if (!box) return;
		box.innerHTML = "";
		(items || []).forEach(function (doc) {
			var a = document.createElement("button");
			a.type = "button";
			a.className = "list-group-item list-group-item-action";
			a.textContent = doc.title || doc.slug;
			a.addEventListener("click", function () {
				preview(doc.slug);
			});
			box.appendChild(a);
		});
	}

	function preview(slug) {
		var frame = document.getElementById("usis-safco-preview");
		if (!frame || !api()) return;
		fetch(api().buildUrl("/api/v1/safety/company-docs/" + encodeURIComponent(slug)), {
			credentials: "include",
			headers: Object.assign({ Accept: "text/html" }, api().actorHeaders()),
		})
			.then(function (res) {
				if (!res.ok) throw new Error("Could not load document");
				return res.text();
			})
			.then(function (html) {
				frame.srcdoc = html;
			})
			.catch(function (err) {
				show(document.getElementById("usis-safco-err"), err.message || "Preview failed", true);
			});
	}

	function load() {
		var err = document.getElementById("usis-safco-err");
		var ok = document.getElementById("usis-safco-ok");
		show(err, "");
		show(ok, "");
		if (!api()) return;
		api()
			.fetchJson("/api/v1/safety/company-profile")
			.then(function (body) {
				fill(body.item && body.item.payload);
				return api().fetchJson("/api/v1/safety/company-docs");
			})
			.then(function (body) {
				renderDocs(body.items);
				if (body.items && body.items[0]) preview(body.items[0].slug);
			})
			.catch(function (e) {
				show(err, (e && e.body) || e.message || "Could not load company safety profile", true);
			});
	}

	function save(ev) {
		if (ev) ev.preventDefault();
		var err = document.getElementById("usis-safco-err");
		var ok = document.getElementById("usis-safco-ok");
		show(err, "");
		show(ok, "");
		api()
			.fetchJson("/api/v1/safety/company-profile", { method: "PUT", body: { payload: collect() } })
			.then(function () {
				show(ok, "Profile saved.", false);
				ok.classList.remove("alert-danger");
				ok.classList.add("alert-success");
			})
			.catch(function (e) {
				show(err, (e && e.body) || e.message || "Save failed", true);
			});
	}

	function regen() {
		var err = document.getElementById("usis-safco-err");
		var ok = document.getElementById("usis-safco-ok");
		show(err, "");
		api()
			.fetchJson("/api/v1/safety/company-docs/regenerate", { method: "POST", body: {} })
			.then(function () {
				return api().fetchJson("/api/v1/safety/company-docs");
			})
			.then(function (body) {
				renderDocs(body.items);
				if (body.items && body.items[0]) preview(body.items[0].slug);
				show(ok, "Company programs regenerated.", false);
				ok.classList.remove("alert-danger");
				ok.classList.add("alert-success");
			})
			.catch(function (e) {
				show(err, (e && e.body) || e.message || "Regenerate failed", true);
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		var form = document.getElementById("usis-safco-form");
		if (form) form.addEventListener("submit", save);
		var regenBtn = document.getElementById("usis-safco-regen");
		if (regenBtn) regenBtn.addEventListener("click", regen);
		load();
	});
})();
