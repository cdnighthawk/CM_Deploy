/**
 * RFP comparison table — lowest price highlighted per row.
 */
(function () {
	"use strict";

	function esc(s) {
		var d = document.createElement("div");
		d.textContent = s == null ? "" : String(s);
		return d.innerHTML;
	}

	function fetchJson(path) {
		if (window.USIS_API && typeof window.USIS_API.fetchJson === "function") {
			return window.USIS_API.fetchJson(path);
		}
		return fetch(path, { credentials: "include", headers: { Accept: "application/json" } }).then(function (res) {
			return res.json().then(function (j) {
				if (!res.ok) throw new Error(j.error || res.statusText);
				return j;
			});
		});
	}

	document.addEventListener("DOMContentLoaded", function () {
		var id = new URLSearchParams(window.location.search).get("id");
		var back = document.getElementById("usis-rfp-compare-back");
		if (back && id) back.href = "usis-rfp-detail.html?id=" + encodeURIComponent(id);
		if (!id) return;
		fetchJson("/api/v1/rfps/" + encodeURIComponent(id) + "/compare").then(function (d) {
			var item = d.item || {};
			var vendors = item.vendors || [];
			var rows = item.rows || [];
			var head = document.getElementById("usis-rfp-compare-head");
			var body = document.getElementById("usis-rfp-compare-body");
			if (head) {
				head.innerHTML =
					"<tr><th>Line</th>" +
					vendors
						.map(function (v) {
							return "<th>" + esc(v.vendor_label) + "</th>";
						})
						.join("") +
					"</tr>";
			}
			if (!body) return;
			if (!rows.length || !vendors.length) {
				body.innerHTML =
					'<tr><td class="text-muted text-center py-4" colspan="' +
					(vendors.length + 1 || 3) +
					'">No vendor quotes to compare yet.</td></tr>';
				return;
			}
			body.innerHTML = rows
				.map(function (row) {
					var cells = vendors
						.map(function (v) {
							var val = row.prices ? row.prices[v.id] : null;
							var lowest = row.lowest != null && val === row.lowest;
							var shown = val == null ? "—" : Number(val).toLocaleString(undefined, { style: "currency", currency: "USD" });
							return (
								"<td" +
								(lowest ? ' class="table-success fw-semibold"' : "") +
								">" +
								esc(shown) +
								"</td>"
							);
						})
						.join("");
					return (
						"<tr><td>" +
						esc(row.description) +
						(row.quantity != null ? " <span class='text-muted'>(" + esc(row.quantity) + " " + esc(row.unit) + ")</span>" : "") +
						"</td>" +
						cells +
						"</tr>"
					);
				})
				.join("");
		});
	});
})();
