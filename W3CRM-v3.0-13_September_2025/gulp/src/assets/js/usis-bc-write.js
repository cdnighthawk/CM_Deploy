/**
 * Push bid status to BuildingConnected (Will Not Bid / Will Bid / Undecided).
 */
(function () {
	"use strict";

	var DECLINE_REASONS = [
		["TOO_BUSY", "Too busy"],
		["LOCATION", "Location"],
		["TRADE", "Not our trade"],
		["CLIENT", "Client"],
		["BID_DUE_DATE", "Bid due date"],
		["PROJECT_SIZE", "Project size"],
		["MARKET_SECTOR", "Market sector"],
		["MISSING_INFO", "Missing information"],
		["UNION_STATUS", "Union status"],
		["PREVAILING_WAGE_STATUS", "Prevailing wage"],
		["OTHER", "Other"],
	];

	function apiBase() {
		if (typeof window.usisApiBase === "function") {
			return String(window.usisApiBase() || "").replace(/\/$/, "");
		}
		if (typeof window.USIS_API_BASE === "string") {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		return "";
	}

	function notify(kind, message) {
		if (window.USISNotify && typeof window.USISNotify[kind] === "function") {
			window.USISNotify[kind](message);
			return;
		}
		window.alert(message);
	}

	function ensureModal() {
		if (document.getElementById("usis-bc-write-modal")) return;
		var wrap = document.createElement("div");
		wrap.innerHTML =
			'<div class="modal fade" id="usis-bc-write-modal" tabindex="-1" aria-hidden="true">' +
			'<div class="modal-dialog modal-dialog-centered"><div class="modal-content">' +
			'<div class="modal-header"><h5 class="modal-title" id="usis-bc-write-title">Will Not Bid</h5>' +
			'<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>' +
			'<div class="modal-body">' +
			'<p class="mb-2" id="usis-bc-write-copy"></p>' +
			'<div id="usis-bc-write-decline-fields">' +
			'<label class="form-label small" for="usis-bc-write-reason">Reason</label>' +
			'<select class="form-select form-select-sm mb-3" id="usis-bc-write-reason"></select>' +
			'<label class="form-label small" for="usis-bc-write-note">Note (optional, stored in Hub)</label>' +
			'<textarea class="form-control" id="usis-bc-write-note" rows="3" placeholder="Optional internal note"></textarea>' +
			"</div></div>" +
			'<div class="modal-footer">' +
			'<button type="button" class="btn btn-light btn-sm" data-bs-dismiss="modal">Cancel</button>' +
			'<button type="button" class="btn btn-danger btn-sm" id="usis-bc-write-confirm">Update BuildingConnected</button>' +
			"</div></div></div></div>";
		document.body.appendChild(wrap.firstChild);
		var sel = document.getElementById("usis-bc-write-reason");
		DECLINE_REASONS.forEach(function (pair) {
			var opt = document.createElement("option");
			opt.value = pair[0];
			opt.textContent = pair[1];
			sel.appendChild(opt);
		});
	}

	function leadIdFromMenu(menu) {
		var text = menu.querySelector(".dropdown-item-text");
		if (!text) return null;
		var m = /id:\s*(\S+)/i.exec(text.textContent || "");
		return m ? m[1] : null;
	}

	function enhanceMenus(root) {
		var scope = root || document;
		scope.querySelectorAll(".dropdown-menu").forEach(function (menu) {
			if (menu.querySelector("[data-usis-bc-write]")) return;
			var id = leadIdFromMenu(menu);
			if (!id) return;
			var wnb = document.createElement("button");
			wnb.type = "button";
			wnb.className = "dropdown-item text-danger";
			wnb.setAttribute("data-usis-bc-write", "DECLINED");
			wnb.setAttribute("data-usis-bc-id", id);
			wnb.textContent = "Will Not Bid";
			var will = document.createElement("button");
			will.type = "button";
			will.className = "dropdown-item";
			will.setAttribute("data-usis-bc-write", "WILL_SUBMIT");
			will.setAttribute("data-usis-bc-id", id);
			will.textContent = "Will Bid";
			var und = document.createElement("button");
			und.type = "button";
			und.className = "dropdown-item";
			und.setAttribute("data-usis-bc-write", "UNDECIDED");
			und.setAttribute("data-usis-bc-id", id);
			und.textContent = "Undecided";
			var idLine = menu.querySelector(".dropdown-item-text");
			if (idLine) {
				menu.insertBefore(wnb, idLine);
				menu.insertBefore(will, idLine);
				menu.insertBefore(und, idLine);
			} else {
				menu.appendChild(wnb);
				menu.appendChild(will);
				menu.appendChild(und);
			}
		});
	}

	function asIdList(idOrIds) {
		if (Array.isArray(idOrIds)) {
			return idOrIds.map(function (id) { return String(id || "").trim(); }).filter(Boolean);
		}
		var one = String(idOrIds || "").trim();
		return one ? [one] : [];
	}

	function patchSubmission(id, body) {
		return fetch(apiBase() + "/api/v1/lead-estimates/" + encodeURIComponent(id) + "/buildingconnected", {
			method: "PATCH",
			credentials: "include",
			headers: { Accept: "application/json", "Content-Type": "application/json" },
			body: JSON.stringify(body),
		}).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error((j && j.error) || "HTTP " + r.status);
				return j;
			});
		});
	}

	function patchSubmissionBulk(ids, body) {
		return fetch(apiBase() + "/api/v1/lead-estimates/bulk/buildingconnected", {
			method: "POST",
			credentials: "include",
			headers: { Accept: "application/json", "Content-Type": "application/json" },
			body: JSON.stringify(Object.assign({ ids: ids }, body)),
		}).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error((j && j.error) || "HTTP " + r.status);
				return j;
			});
		});
	}

	function reloadLists() {
		var refresh =
			document.getElementById("usis-bc-sync-stub") ||
			document.getElementById("usis-estimate-sync-stub") ||
			document.getElementById("usis-crm-refresh");
		if (refresh) refresh.click();
	}

	function summarizeBulk(result, state) {
		var updated = (result && result.updated_count) || 0;
		var failed = (result && result.failed) || [];
		var label =
			state === "DECLINED" ? "Will Not Bid" : state === "WILL_SUBMIT" ? "Will Bid" : "Undecided";
		if (failed.length) {
			var first = failed[0].error || "update failed";
			notify(
				updated ? "warning" : "error",
				updated
					? "Updated " + updated + " to " + label + ". " + failed.length + " failed: " + first
					: "BuildingConnected update failed: " + first,
			);
			return;
		}
		notify(
			"success",
			updated > 1
				? "Marked " + updated + " opportunities " + label + " in BuildingConnected."
				: state === "DECLINED"
					? "Marked Will Not Bid in BuildingConnected."
					: "BuildingConnected status updated.",
		);
	}

	function openDialog(idOrIds, state, name) {
		var ids = asIdList(idOrIds);
		if (!ids.length) return;
		ensureModal();
		var modalEl = document.getElementById("usis-bc-write-modal");
		var title =
			state === "DECLINED" ? "Will Not Bid" : state === "WILL_SUBMIT" ? "Will Bid" : "Undecided";
		var target =
			ids.length > 1
				? ids.length + " selected opportunities"
				: name || "this opportunity";
		document.getElementById("usis-bc-write-title").textContent = title;
		document.getElementById("usis-bc-write-copy").textContent =
			"Push " + title + " to BuildingConnected for " + target + "?";
		document.getElementById("usis-bc-write-decline-fields").classList.toggle("d-none", state !== "DECLINED");
		document.getElementById("usis-bc-write-note").value = "";
		document.getElementById("usis-bc-write-reason").value = "TOO_BUSY";
		var confirmBtn = document.getElementById("usis-bc-write-confirm");
		confirmBtn.className = "btn btn-sm " + (state === "DECLINED" ? "btn-danger" : "btn-primary");
		confirmBtn.onclick = function () {
			var payload = { submissionState: state };
			if (state === "DECLINED") {
				payload.declineReasons = [document.getElementById("usis-bc-write-reason").value];
				payload.note = document.getElementById("usis-bc-write-note").value;
			}
			confirmBtn.disabled = true;
			var req = ids.length > 1 ? patchSubmissionBulk(ids, payload) : patchSubmission(ids[0], payload);
			req.then(function (result) {
					if (ids.length > 1) summarizeBulk(result, state);
					else {
						notify(
							"success",
							state === "DECLINED"
								? "Marked Will Not Bid in BuildingConnected."
								: "BuildingConnected status updated.",
						);
					}
					if (window.bootstrap && window.bootstrap.Modal) {
						window.bootstrap.Modal.getOrCreateInstance(modalEl).hide();
					}
					if (window.USISListBulk && typeof window.USISListBulk.clear === "function") {
						window.USISListBulk.clear();
					}
					document.dispatchEvent(
						new CustomEvent("usis-bc-write-done", { detail: { ids: ids, state: state } }),
					);
					reloadLists();
				})
				.catch(function (err) {
					notify("error", err.message || "BuildingConnected update failed");
				})
				.finally(function () {
					confirmBtn.disabled = false;
				});
		};
		if (window.bootstrap && window.bootstrap.Modal) {
			window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
		} else if (window.confirm(title + "?")) {
			confirmBtn.onclick();
		}
	}

	window.usisBcUpdateSubmission = function (id, state, name) {
		openDialog(id, state || "DECLINED", name);
	};

	window.usisBcUpdateSubmissionBulk = function (ids, state) {
		openDialog(ids, state || "DECLINED", null);
	};

	document.addEventListener("click", function (e) {
		var bulkBtn = e.target.closest("[data-usis-bulk-bc]");
		if (bulkBtn) {
			e.preventDefault();
			var selected = window.USISListBulk && typeof window.USISListBulk.ids === "function"
				? window.USISListBulk.ids()
				: [];
			if (!selected.length) {
				notify("error", "Select one or more rows first.");
				return;
			}
			openDialog(selected, bulkBtn.getAttribute("data-usis-bulk-bc"), null);
			return;
		}
		var btn = e.target.closest("[data-usis-bc-write]");
		if (!btn) return;
		e.preventDefault();
		openDialog(btn.getAttribute("data-usis-bc-id"), btn.getAttribute("data-usis-bc-write"), btn.getAttribute("data-usis-bc-name"));
	});

	function watchTables() {
		enhanceMenus(document);
		var tables = document.querySelectorAll("#usis-bc-leads-table tbody, #usis-estimate-table tbody, #usis-crm-tbody");
		tables.forEach(function (tb) {
			if (tb.getAttribute("data-usis-bc-write-watched")) return;
			tb.setAttribute("data-usis-bc-write-watched", "1");
			new MutationObserver(function () {
				enhanceMenus(tb.closest("table") || document);
			}).observe(tb, { childList: true, subtree: true });
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", watchTables);
	} else {
		watchTables();
	}
	document.addEventListener("usis-bc-write-done", function () {
		window.setTimeout(watchTables, 50);
	});
})();
