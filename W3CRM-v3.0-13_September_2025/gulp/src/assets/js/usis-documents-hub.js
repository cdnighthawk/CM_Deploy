(function () {
	"use strict";

	function pid() {
		return new URLSearchParams(window.location.search).get("project_id");
	}

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function load() {
		var p = pid();
		var ul = document.getElementById("usis-doc-list");
		if (!ul) return;
		if (!p) {
			ul.innerHTML = '<li class="list-group-item text-muted">Pass project_id in URL</li>';
			return;
		}
		ul.innerHTML = '<li class="list-group-item">Loading…</li>';
		window.USIS_API.fetchJson("/api/v1/projects/" + encodeURIComponent(p) + "/documents")
			.then(function (data) {
				var items = data.items || [];
				if (!items.length) {
					ul.innerHTML = '<li class="list-group-item text-muted">No documents</li>';
					return;
				}
				ul.innerHTML = items
					.map(function (x) {
						return (
							'<li class="list-group-item d-flex justify-content-between align-items-center"><span>' +
							esc(x.title || x.document_type) +
							'</span><span class="badge bg-secondary">' +
							esc(x.document_type) +
							"</span></li>"
						);
					})
					.join("");
			})
			.catch(function () {
				ul.innerHTML = '<li class="list-group-item text-danger">Load failed</li>';
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		load();
		var btn = document.getElementById("usis-doc-add");
		if (btn) {
			btn.addEventListener("click", function () {
				var p = pid();
				if (!p) return;
				var title = window.prompt("Title", "Uploaded doc");
				if (!title) return;
				window.USIS_API.fetchJson("/api/v1/projects/" + encodeURIComponent(p) + "/documents", {
					method: "POST",
					body: { title: title, document_type: "other", file_url: "" },
				})
					.then(function () {
						load();
					})
					.catch(function (e) {
						alert(e.message || String(e));
					});
			});
		}
	});
})();
