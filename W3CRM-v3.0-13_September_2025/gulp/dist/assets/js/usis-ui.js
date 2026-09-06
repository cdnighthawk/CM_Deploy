/**
 * Shared chrome helpers: StatusChip, AiReviewButton, EmptyState.
 * Visual only — does not change API payloads or workflow data.
 */
(function (global) {
	"use strict";

	var FAMILY = {
		draft: "draft",
		new: "new",
		sent: "sent",
		"in progress": "progress",
		in_progress: "progress",
		progress: "progress",
		estimating: "estimating",
		invited: "progress",
		submitted: "progress",
		awarded: "awarded",
		approved: "approved",
		released: "approved",
		signed: "approved",
		won: "awarded",
		lost: "lost",
		rejected: "rejected",
		declined: "rejected",
		overdue: "overdue",
		warning: "warning",
		partial: "partial",
		"due soon": "warning",
		locked: "draft",
		critical: "critical",
		major: "major",
		minor: "minor",
		info: "info",
	};

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;");
	}

	function familyOf(status) {
		var key = String(status || "")
			.trim()
			.toLowerCase()
			.replace(/[_-]+/g, " ");
		if (FAMILY[key]) return FAMILY[key];
		if (FAMILY[key.replace(/\s+/g, "_")]) return FAMILY[key.replace(/\s+/g, "_")];
		if (/critical/.test(key)) return "critical";
		if (/major/.test(key)) return "major";
		if (/minor/.test(key)) return "minor";
		if (/award|approv|releas/.test(key)) return "awarded";
		if (/lost|reject|declin|overdue/.test(key)) return "lost";
		if (/warn|partial|due/.test(key)) return "warning";
		if (/sent|progress|estimat|invit|submit/.test(key)) return "progress";
		if (/draft|new|lock/.test(key)) return "draft";
		return "draft";
	}

	function chipClass(family, filled) {
		var map = {
			draft: "usis-status-chip--draft",
			new: "usis-status-chip--new",
			sent: "usis-status-chip--sent",
			progress: "usis-status-chip--progress",
			estimating: "usis-status-chip--estimating",
			awarded: "usis-status-chip--awarded",
			approved: "usis-status-chip--approved",
			lost: "usis-status-chip--lost",
			rejected: "usis-status-chip--rejected",
			overdue: "usis-status-chip--overdue",
			warning: "usis-status-chip--warning",
			partial: "usis-status-chip--partial",
			critical: "usis-status-chip--critical",
			major: "usis-status-chip--major",
			minor: "usis-status-chip--minor",
			info: "usis-status-chip--info",
		};
		var extra = map[family] || "usis-status-chip--draft";
		if (filled && (family === "critical" || family === "major" || family === "warning")) {
			extra += " usis-status-chip--filled";
		}
		return "usis-status-chip " + extra;
	}

	function statusChip(status, opts) {
		opts = opts || {};
		var label = opts.label != null ? opts.label : status || "—";
		var family = opts.family || familyOf(status);
		var filled = opts.filled === true || family === "critical" || family === "major";
		var title = opts.title || String(status || label);
		return (
			'<span class="' +
			chipClass(family, filled) +
			'" title="' +
			esc(title) +
			'">' +
			esc(label) +
			"</span>"
		);
	}

	function severityChip(sev) {
		var s = String(sev || "").toLowerCase();
		if (!s) return "—";
		var family = s === "critical" ? "critical" : s === "major" ? "major" : s === "minor" ? "minor" : "info";
		var label = s.charAt(0).toUpperCase() + s.slice(1);
		return (
			'<span class="' +
			chipClass(family, family === "critical" || family === "major") +
			'" title="' +
			esc(label) +
			'"><span class="usis-status-dot usis-status-dot--' +
			family +
			'" aria-hidden="true"></span>' +
			esc(label) +
			"</span>"
		);
	}

	function aiReviewButton(opts) {
		opts = opts || {};
		var label = opts.label || "Review with Local AI";
		var size = opts.size === "small" ? " btn-sm" : "";
		var id = opts.id ? ' id="' + esc(opts.id) + '"' : "";
		return (
			'<button type="button" class="btn usis-ai-review' +
			size +
			'"' +
			id +
			">" +
			'<i class="icon feather icon-star me-1" aria-hidden="true"></i>' +
			esc(label) +
			"</button>"
		);
	}

	function emptyState(opts) {
		opts = opts || {};
		var icon = opts.icon || "icon-inbox";
		var title = opts.title || "Nothing here yet";
		var body = opts.body || "";
		var action = opts.actionHtml || "";
		return (
			'<div class="usis-empty">' +
			'<div class="usis-empty__icon" aria-hidden="true"><i class="icon feather ' +
			esc(icon) +
			'"></i></div>' +
			'<div class="usis-empty__title">' +
			esc(title) +
			"</div>" +
			(body ? '<p class="usis-empty__body mb-0">' + esc(body) + "</p>" : "") +
			(action ? '<div class="mt-3">' + action + "</div>" : "") +
			"</div>"
		);
	}

	function restyleAiButtons(root) {
		var scope = root || global.document;
		if (!scope || !scope.querySelectorAll) return;
		scope.querySelectorAll("#usis-qc-ai, #usis-dv-ai-stub, [data-usis-ai-review]").forEach(function (btn) {
			btn.classList.add("usis-ai-review");
			btn.classList.remove("btn-primary", "btn-secondary");
			btn.style.background = "";
			btn.style.color = "";
			if (!btn.querySelector(".icon") && !btn.querySelector("i")) {
				btn.insertAdjacentHTML(
					"afterbegin",
					'<i class="icon feather icon-star me-1" aria-hidden="true"></i>'
				);
			}
		});
	}

	function notifyUi(kind, message) {
		if (global.USISNotify && typeof global.USISNotify[kind] === "function") {
			global.USISNotify[kind](message);
			return;
		}
		if (kind === "error") window.alert(message);
	}

	function safeFilename(name) {
		var s = String(name == null ? "" : name).replace(/[<>:"/\\|?*\u0000-\u001f]+/g, "-").trim();
		return s || "file";
	}

	function filenameFromDisposition(header, fallback) {
		if (!header) return fallback;
		var star = /filename\*=UTF-8''([^;]+)/i.exec(header);
		if (star && star[1]) {
			try {
				return safeFilename(decodeURIComponent(star[1]));
			} catch (e) {}
		}
		var plain = /filename=\"?([^\";]+)\"?/i.exec(header);
		if (plain && plain[1]) return safeFilename(plain[1]);
		return fallback;
	}

	function downloadFiles(jobs, opts) {
		opts = opts || {};
		var list = (jobs || []).filter(function (j) {
			return j && j.url;
		});
		if (!list.length) {
			notifyUi("info", opts.emptyMsg || "No files to download.");
			return Promise.resolve({ ok: 0, failed: 0 });
		}
		var failed = 0;
		var ok = 0;
		var chain = Promise.resolve();
		list.forEach(function (job) {
			chain = chain.then(function () {
				return fetch(job.url, { credentials: "include" }).then(function (res) {
					if (!res.ok) throw new Error("HTTP " + res.status);
					var name = filenameFromDisposition(
						res.headers.get("Content-Disposition"),
						safeFilename(job.name || "download.pdf")
					);
					if (!/\.[a-z0-9]{2,5}$/i.test(name)) name += ".pdf";
					return res.blob().then(function (blob) {
						var a = document.createElement("a");
						a.href = URL.createObjectURL(blob);
						a.download = name;
						document.body.appendChild(a);
						a.click();
						a.remove();
						setTimeout(function () {
							URL.revokeObjectURL(a.href);
						}, 4000);
						ok += 1;
					});
				}).catch(function () {
					failed += 1;
				}).then(function () {
					return new Promise(function (resolve) {
						setTimeout(resolve, 220);
					});
				});
			});
		});
		return chain.then(function () {
			if (failed) notifyUi("error", failed + " file" + (failed === 1 ? "" : "s") + " could not be downloaded.");
			else if (opts.successMsg) notifyUi("success", opts.successMsg);
			return { ok: ok, failed: failed };
		});
	}

	function dataAttrs(obj) {
		if (!obj) return "";
		return Object.keys(obj)
			.map(function (k) {
				var v = obj[k];
				if (v == null || v === "") return "";
				var name = String(k).replace(/_/g, "-");
				return " data-" + name + '="' + esc(v) + '"';
			})
			.join("");
	}

	function rowMenuHtml(items) {
		var lis = (items || [])
			.map(function (it) {
				if (!it || !it.label) return "";
				var cls =
					"dropdown-item" +
					(it.danger ? " text-danger" : "") +
					(it.className ? " " + it.className : "");
				var extra = dataAttrs(it.data);
				if (it.href) {
					return (
						'<a class="' +
						cls +
						'" href="' +
						esc(it.href) +
						'"' +
						(it.target ? ' target="' + esc(it.target) + '" rel="noopener"' : "") +
						extra +
						">" +
						esc(it.label) +
						"</a>"
					);
				}
				return (
					'<button type="button" class="' +
					cls +
					'"' +
					extra +
					">" +
					esc(it.label) +
					"</button>"
				);
			})
			.join("");
		return (
			'<div class="dropdown custom-dropdown mb-0 tbl-orders-style usis-row-menu">' +
			'<button type="button" class="btn btn-square btn-sm rounded" data-bs-toggle="dropdown" data-bs-boundary="viewport" data-bs-popper-config=\'{"strategy":"fixed"}\' aria-expanded="false" aria-label="Row actions">' +
			'<i class="fa-solid fa-ellipsis-vertical"></i></button>' +
			'<div class="dropdown-menu dropdown-menu-end">' +
			lis +
			"</div></div>"
		);
	}

	function rowMenu(opts) {
		opts = opts || {};
		var items = [];
		var editData = Object.assign({}, opts.editData || {});
		if (opts.id != null && opts.id !== "" && editData.id == null) editData.id = opts.id;
		items.push({
			label: opts.editLabel || "Edit",
			className: opts.editClass || "",
			href: opts.editHref || "",
			data: editData,
		});
		var createData = Object.assign({}, opts.createData || {});
		if (opts.createTarget && !createData.target) createData.target = opts.createTarget;
		items.push({
			label: opts.createLabel || "New",
			className: opts.createClass || "usis-row-new",
			href: opts.createHref || "",
			data: createData,
		});
		if (opts.extras && opts.extras.length) {
			items = items.concat(opts.extras);
		}
		if (opts.remove !== false) {
			var deleteData = Object.assign({}, opts.deleteData || {});
			if (opts.id != null && opts.id !== "" && deleteData.id == null) deleteData.id = opts.id;
			if (opts.deleteUrl && !deleteData.url) deleteData.url = opts.deleteUrl;
			if (opts.deleteMethod && !deleteData.method) deleteData.method = opts.deleteMethod;
			var delClass = opts.deleteClass || "usis-row-del";
			if (opts.adminDelete) delClass = (delClass ? delClass + " " : "") + "usis-admin-del";
			items.push({
				label: opts.deleteLabel || "Delete",
				className: delClass,
				danger: true,
				data: deleteData,
			});
		}
		return rowMenuHtml(items);
	}

	function bindRowMenuNew() {
		if (global.document.__usisRowMenuNewBound) return;
		global.document.__usisRowMenuNewBound = true;
		global.document.addEventListener(
			"click",
			function (ev) {
				var btn = ev.target && ev.target.closest && ev.target.closest(".usis-row-new");
				if (!btn) return;
				var sel = btn.getAttribute("data-target");
				if (!sel) return;
				var el = global.document.querySelector(sel);
				if (!el) return;
				ev.preventDefault();
				el.click();
			},
			true
		);
	}

	global.USISUi = {
		statusChip: statusChip,
		severityChip: severityChip,
		aiReviewButton: aiReviewButton,
		emptyState: emptyState,
		familyOf: familyOf,
		restyleAiButtons: restyleAiButtons,
		safeFilename: safeFilename,
		downloadFiles: downloadFiles,
		rowMenu: rowMenu,
		rowMenuHtml: rowMenuHtml,
	};

	bindRowMenuNew();

	if (global.document.readyState === "loading") {
		global.document.addEventListener("DOMContentLoaded", function () {
			restyleAiButtons();
		});
	} else {
		restyleAiButtons();
	}
})(window);

/**
 * Admin-only row delete for list tables, plus a shared confirm+DELETE helper.
 * Shown when /api/v1/me reports can_admin_delete (admin/superuser or any module admin).
 */
(function (global) {
	"use strict";

	var ready = false;
	var can = false;
	var waiters = [];
	var TABLES = {
		"usis-projects-table": { url: "/api/v1/projects/{id}", label: "project" },
		"usis-bc-leads-table": { url: "/api/v1/lead-estimates/{id}", label: "lead" },
		"usis-estimate-table": { url: "/api/v1/lead-estimates/{id}", label: "estimate" },
		"usis-lead-estimates-table": { url: "/api/v1/estimates/{id}", label: "estimate" },
	};

	(function injectHideUntilReady() {
		if (document.getElementById("usis-admin-delete-css")) return;
		var st = document.createElement("style");
		st.id = "usis-admin-delete-css";
		st.textContent = "html:not(.usis-can-admin-delete) .usis-admin-del, html:not(.usis-can-admin-delete) .usis-admin-bulk-del { display: none !important; }";
		(document.head || document.documentElement).appendChild(st);
	})();

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/"/g, "&quot;");
	}

	function apiBase() {
		if (typeof global.usisApiBase === "function") {
			return String(global.usisApiBase() || "").replace(/\/$/, "");
		}
		if (typeof global.USIS_API_BASE === "string") {
			return global.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		return "";
	}

	function notify(kind, message) {
		if (global.USISNotify && typeof global.USISNotify[kind] === "function") {
			global.USISNotify[kind](message);
			return;
		}
		if (kind === "error") global.alert(message);
	}

	function computeCan(caps) {
		if (!caps) return false;
		if (caps.can_admin_delete) return true;
		if (caps.is_superuser) return true;
		var roles = caps.role_codes || [];
		var i;
		for (i = 0; i < roles.length; i++) {
			if (roles[i] === "admin" || roles[i] === "superuser") return true;
		}
		var mods = caps.modules || {};
		var k;
		for (k in mods) {
			if (Object.prototype.hasOwnProperty.call(mods, k) && mods[k] === "admin") return true;
		}
		return false;
	}

	function whenReady(fn) {
		if (ready) {
			fn(can);
			return;
		}
		waiters.push(fn);
	}

	function setReady(value) {
		ready = true;
		can = !!value;
		document.documentElement.classList.toggle("usis-can-admin-delete", can);
		waiters.splice(0).forEach(function (fn) {
			try {
				fn(can);
			} catch (e) {}
		});
		injectAll();
		enhanceBulkBars();
	}

	function expandUrl(template, id) {
		return String(template || "").replace(/\{id\}/g, encodeURIComponent(id));
	}

	function menuItemHtml(id, url, opts) {
		opts = opts || {};
		if (ready && !can) return "";
		var hidden = ready && can ? "" : " d-none";
		var method = opts.method || "DELETE";
		var extra = "";
		if (opts.body) extra += " data-body=\"" + esc(JSON.stringify(opts.body)) + "\"";
		if (opts.reload) extra += " data-reload=\"" + esc(opts.reload) + "\"";
		return (
			'<button type="button" class="dropdown-item text-danger usis-admin-del' +
			hidden +
			'" data-id="' +
			esc(id) +
			'" data-url="' +
			esc(url) +
			'" data-method="' +
			esc(method) +
			'" data-label="' +
			esc(opts.label || "this item") +
			'"' +
			extra +
			">Delete</button>"
		);
	}

	function buttonHtml(id, url, opts) {
		opts = opts || {};
		if (ready && !can) return "";
		var hidden = ready && can ? "" : " d-none";
		var method = opts.method || "DELETE";
		return (
			'<button type="button" class="btn btn-sm btn-outline-danger py-0 usis-admin-del' +
			hidden +
			'" data-id="' +
			esc(id) +
			'" data-url="' +
			esc(url) +
			'" data-method="' +
			esc(method) +
			'" data-label="' +
			esc(opts.label || "this item") +
			'">Delete</button>'
		);
	}

	function tableConfig(table) {
		if (!table) return null;
		var id = table.id || "";
		if (TABLES[id]) return TABLES[id];
		var url = table.getAttribute("data-usis-admin-delete");
		if (!url) return null;
		return {
			url: url,
			label: table.getAttribute("data-usis-admin-delete-label") || "item",
			method: table.getAttribute("data-usis-admin-delete-method") || "DELETE",
		};
	}

	function rowHasDelete(tr) {
		return !!(
			tr.querySelector(".usis-admin-del") ||
			tr.querySelector(".usis-row-del") ||
			tr.querySelector("[class*='-del']")
		);
	}

	function injectRow(tr, cfg) {
		if (!can || !tr || rowHasDelete(tr)) return;
		var id = tr.getAttribute("data-id");
		if (!id) return;
		var url = expandUrl(cfg.url, id);
		var html = menuItemHtml(id, url, { label: cfg.label, method: cfg.method });
		if (!html) return;
		var menu = tr.querySelector(".dropdown-menu");
		if (menu) {
			menu.insertAdjacentHTML("beforeend", html);
			return;
		}
		var last = tr.querySelector("td:last-child");
		if (last) last.insertAdjacentHTML("beforeend", " " + buttonHtml(id, url, { label: cfg.label, method: cfg.method }));
	}

	function injectAll() {
		if (!can) return;
		document.querySelectorAll("table[id], table[data-usis-admin-delete]").forEach(function (table) {
			var cfg = tableConfig(table);
			if (!cfg) return;
			table.querySelectorAll("tbody tr[data-id]").forEach(function (tr) {
				injectRow(tr, cfg);
			});
		});
		document.querySelectorAll(".usis-admin-del.d-none").forEach(function (el) {
			el.classList.remove("d-none");
		});
	}

	function enhanceBulkBars() {
		if (!can) return;
		document.querySelectorAll("[data-usis-admin-bulk-delete]").forEach(function (bar) {
			if (bar.querySelector(".usis-admin-bulk-del")) {
				bar.querySelector(".usis-admin-bulk-del").classList.remove("d-none");
				return;
			}
			var url = bar.getAttribute("data-usis-admin-bulk-delete");
			if (!url) return;
			var btn = document.createElement("button");
			btn.type = "button";
			btn.className = "btn btn-sm btn-outline-danger usis-admin-bulk-del";
			btn.setAttribute("data-url-template", url);
			btn.setAttribute("data-label", bar.getAttribute("data-usis-admin-bulk-label") || "item");
			btn.textContent = "Delete";
			bar.appendChild(btn);
		});
	}

	function parseBody(el) {
		var raw = el.getAttribute("data-body");
		if (!raw) return undefined;
		try {
			return JSON.parse(raw);
		} catch (e) {
			return undefined;
		}
	}

	function requestDelete(url, opts) {
		opts = opts || {};
		var headers = { Accept: "application/json" };
		var body = opts.body;
		if (body != null) headers["Content-Type"] = "application/json";
		return fetch(apiBase() + url, {
			method: opts.method || "DELETE",
			credentials: "include",
			headers: headers,
			body: body != null ? JSON.stringify(body) : undefined,
		}).then(function (r) {
			return r.text().then(function (t) {
				var j = null;
				try {
					j = t ? JSON.parse(t) : null;
				} catch (e) {}
				if (!r.ok) throw new Error((j && (j.error || j.message)) || t || "HTTP " + r.status);
				return j;
			});
		});
	}

	function confirmDelete(label) {
		return global.confirm("Delete " + (label || "this item") + "? This cannot be undone from the list.");
	}

	function afterDelete(el) {
		var reloadSel = el && el.getAttribute("data-reload");
		if (reloadSel) {
			var reloadEl = document.querySelector(reloadSel);
			if (reloadEl) reloadEl.click();
			return;
		}
		global.dispatchEvent(new CustomEvent("usis:admin-deleted"));
		var tr = el && el.closest ? el.closest("tr") : null;
		if (tr && tr.parentNode) tr.parentNode.removeChild(tr);
	}

	function bindClicks() {
		if (document.__usisAdminDeleteBound) return;
		document.__usisAdminDeleteBound = true;
		document.addEventListener(
			"click",
			function (ev) {
				var bulk = ev.target.closest && ev.target.closest(".usis-admin-bulk-del");
				if (bulk) {
					ev.preventDefault();
					ev.stopPropagation();
					var ids =
						global.USISListBulk && typeof global.USISListBulk.ids === "function"
							? global.USISListBulk.ids()
							: [];
					if (!ids.length) return;
					var label = bulk.getAttribute("data-label") || "item";
					if (!global.confirm("Delete " + ids.length + " " + label + "(s)?")) return;
					var tmpl = bulk.getAttribute("data-url-template") || "";
					var chain = Promise.resolve();
					ids.forEach(function (id) {
						chain = chain.then(function () {
							return requestDelete(expandUrl(tmpl, id));
						});
					});
					chain
						.then(function () {
							notify("success", "Deleted " + ids.length + " " + label + "(s).");
							if (global.USISListBulk && global.USISListBulk.clear) global.USISListBulk.clear();
							global.dispatchEvent(new CustomEvent("usis:admin-deleted"));
							var reload = document.querySelector(
								"#usis-projects-reload, #usis-estimate-sync-stub, #usis-bc-leads-reload"
							);
							if (reload) reload.click();
						})
						.catch(function (err) {
							notify("error", err.message || "Delete failed");
						});
					return;
				}
				var btn = ev.target.closest && ev.target.closest(".usis-admin-del");
				if (!btn) return;
				ev.preventDefault();
				ev.stopPropagation();
				var url = btn.getAttribute("data-url");
				var id = btn.getAttribute("data-id");
				if (!url && id) {
					var table = btn.closest("table");
					var cfg = tableConfig(table);
					if (cfg) url = expandUrl(cfg.url, id);
				}
				if (!url) return;
				if (!confirmDelete(btn.getAttribute("data-label"))) return;
				requestDelete(url, { method: btn.getAttribute("data-method") || "DELETE", body: parseBody(btn) })
					.then(function () {
						notify("success", "Deleted.");
						afterDelete(btn);
					})
					.catch(function (err) {
						notify("error", err.message || "Delete failed");
					});
			},
			true
		);
	}

	function observeTables() {
		if (!global.MutationObserver || document.__usisAdminDeleteObs) return;
		document.__usisAdminDeleteObs = true;
		var obs = new MutationObserver(function () {
			if (!can) return;
			injectAll();
		});
		obs.observe(document.documentElement, { childList: true, subtree: true });
	}

	function loadCaps() {
		fetch(apiBase() + "/api/v1/me", { credentials: "include", headers: { Accept: "application/json" } })
			.then(function (r) {
				return r.json().then(function (j) {
					return { ok: r.ok, body: j };
				});
			})
			.then(function (res) {
				if (!res.ok) {
					setReady(false);
					return;
				}
				setReady(computeCan((res.body && res.body.capabilities) || {}));
			})
			.catch(function () {
				setReady(false);
			});
	}

	bindClicks();
	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", function () {
			observeTables();
			loadCaps();
		});
	} else {
		observeTables();
		loadCaps();
	}

	global.USISAdminDelete = {
		canDelete: function () {
			return can;
		},
		whenReady: whenReady,
		menuItemHtml: menuItemHtml,
		buttonHtml: buttonHtml,
		requestDelete: requestDelete,
		injectAll: injectAll,
	};
})(window);

