/**
 * Procore-style drawings log chrome: Current Drawings / Drawing Sets tabs,
 * search + filter chips, list/thumbnail layouts, revision popovers.
 */
(function (global) {
	"use strict";

	var LAYOUT_KEY = "usis-draw-layout";
	var popEl = null;
	var popAnchor = null;

	function t(key) {
		return global.USISI18n && typeof global.USISI18n.tr === "function" ? global.USISI18n.tr(key) : key;
	}

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function qs(root, sel) {
		return root ? root.querySelector(sel) : null;
	}

	function qsa(root, sel) {
		return root ? Array.prototype.slice.call(root.querySelectorAll(sel)) : [];
	}

	function crOf(row) {
		return (row && row.current_revision) || {};
	}

	function fmtMDY(iso) {
		if (!iso) return "—";
		var d = new Date(iso);
		if (isNaN(d.getTime())) return "—";
		var m = d.getMonth() + 1;
		var day = d.getDate();
		var y = d.getFullYear();
		return (m < 10 ? "0" : "") + m + "/" + (day < 10 ? "0" : "") + day + "/" + y;
	}

	function revisionLabel(row) {
		var cr = crOf(row);
		if (cr.revision != null && String(cr.revision).trim() !== "") return String(cr.revision).trim();
		if (cr.version != null && cr.version !== "") return String(cr.version);
		if (row && row.revision_count != null) {
			var n = Number(row.revision_count);
			if (n > 0) return String(Math.max(0, n - 1));
		}
		return "0";
	}

	function drawingDate(row) {
		var cr = crOf(row);
		return fmtMDY(cr.updated_at || cr.created_at);
	}

	function receivedDate(row) {
		var cr = crOf(row);
		return fmtMDY(cr.created_at || cr.updated_at);
	}

	function isPublished(row) {
		var cr = crOf(row);
		return !!(cr.file_url || cr.id);
	}

	function statusLabel(row) {
		return isPublished(row) ? t("Published") : t("Draft");
	}

	function svg(path, size) {
		size = size || 16;
		return (
			'<svg width="' +
			size +
			'" height="' +
			size +
			'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
			path +
			"</svg>"
		);
	}

	function closePop() {
		if (popEl && popEl.parentNode) popEl.parentNode.removeChild(popEl);
		popEl = null;
		popAnchor = null;
		document.removeEventListener("mousedown", onPopOutside, true);
		document.removeEventListener("keydown", onPopKey, true);
	}

	function onPopOutside(ev) {
		if (!popEl) return;
		if (popEl.contains(ev.target) || (popAnchor && popAnchor.contains(ev.target))) return;
		closePop();
	}

	function onPopKey(ev) {
		if (ev.key === "Escape") closePop();
	}

	function showPop(anchor, html) {
		closePop();
		popAnchor = anchor;
		popEl = document.createElement("div");
		popEl.className = "usis-draw-pop";
		popEl.innerHTML = html;
		document.body.appendChild(popEl);
		var r = anchor.getBoundingClientRect();
		var w = popEl.offsetWidth || 280;
		var left = Math.min(window.scrollX + r.left, window.scrollX + window.innerWidth - w - 8);
		var top = window.scrollY + r.bottom + 6;
		popEl.style.left = Math.max(8, left) + "px";
		popEl.style.top = top + "px";
		document.addEventListener("mousedown", onPopOutside, true);
		document.addEventListener("keydown", onPopKey, true);
	}

	function viewerHref(opts, row, rev) {
		var pid = opts.getPid ? opts.getPid() : "";
		var id = (rev && rev.id) || (crOf(row) && crOf(row).id);
		if (!pid || !id || typeof opts.viewerHref !== "function") return "";
		return opts.viewerHref(pid, id);
	}

	function identityFormatter(field, opts) {
		return function (cell) {
			var data = cell.getRow().getData();
			var text = data[field];
			if (text == null || String(text).trim() === "") text = "—";
			else text = String(text);
			if (field === "sheet_title" && text !== "—") text = text.toUpperCase();
			var href = viewerHref(opts, data);
			var wrap = document.createElement("span");
			wrap.className = "usis-drawing-cell";
			if (href) {
				var a = document.createElement("a");
				a.href = href;
				a.className = "usis-drawing-name-link" + (field === "sheet_title" ? " usis-draw-title-link" : "");
				a.textContent = text;
				wrap.appendChild(a);
			} else {
				var span = document.createElement("span");
				if (field === "sheet_title") span.className = "usis-draw-title-link";
				span.textContent = text;
				wrap.appendChild(span);
			}
			var btn = document.createElement("button");
			btn.type = "button";
			btn.className = "btn btn-link btn-sm p-0 usis-drawing-rename";
			btn.title = field === "sheet_number" ? t("Change drawing #") : t("Change drawing name");
			btn.setAttribute("aria-label", btn.title);
			btn.innerHTML = svg('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>', 14);
			btn.addEventListener("click", function (ev) {
				ev.preventDefault();
				ev.stopPropagation();
				cell.edit(true);
			});
			wrap.appendChild(btn);
			return wrap;
		};
	}

	function iconsFormatter(opts) {
		return function (cell) {
			var data = cell.getRow().getData();
			var wrap = document.createElement("div");
			wrap.className = "usis-draw-row-icons";
			var info = document.createElement("button");
			info.type = "button";
			info.className = "usis-draw-icon-btn";
			info.title = t("Info");
			info.setAttribute("aria-label", t("Info"));
			info.innerHTML = svg('<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>');
			info.addEventListener("click", function (ev) {
				ev.preventDefault();
				ev.stopPropagation();
				var cr = crOf(data);
				var href = viewerHref(opts, data);
				var bits = [
					"<div class='usis-draw-pop__title'>" + esc(data.sheet_number || "—") + "</div>",
					"<div class='usis-draw-pop__meta'>" + esc((data.sheet_title || "").toUpperCase()) + "</div>",
					"<dl class='usis-draw-pop__dl'>",
					"<dt>" + esc(t("Discipline")) + "</dt><dd>" + esc(data.discipline || "—") + "</dd>",
					"<dt>" + esc(t("Set")) + "</dt><dd>" + esc(data.drawing_set || "—") + "</dd>",
					"<dt>" + esc(t("Revision")) + "</dt><dd>" + esc(revisionLabel(data)) + "</dd>",
					"<dt>" + esc(t("File")) + "</dt><dd>" + esc(cr.original_filename || "—") + "</dd>",
					"</dl>",
				];
				if (href) {
					bits.push(
						"<a class='usis-draw-pop__open' href='" + esc(href) + "'>" + esc(t("Open drawing")) + "</a>"
					);
				}
				showPop(info, bits.join(""));
			});
			wrap.appendChild(info);
			var href = viewerHref(opts, data);
			if (href) {
				var open = document.createElement("a");
				open.href = href;
				open.className = "usis-draw-icon-btn";
				open.title = t("Open drawing");
				open.setAttribute("aria-label", t("Open drawing"));
				open.innerHTML = svg(
					'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>'
				);
				wrap.appendChild(open);
			}
			return wrap;
		};
	}

	function revisionFormatter(opts) {
		return function (cell) {
			var data = cell.getRow().getData();
			var wrap = document.createElement("div");
			wrap.className = "usis-draw-rev";
			var num = document.createElement("span");
			num.className = "usis-draw-rev__num";
			num.textContent = revisionLabel(data);
			wrap.appendChild(num);
			var revs = data.revisions || [];
			if (revs.length > 1) {
				var btn = document.createElement("button");
				btn.type = "button";
				btn.className = "usis-draw-see-all";
				btn.textContent = t("See All");
				btn.addEventListener("click", function (ev) {
					ev.preventDefault();
					ev.stopPropagation();
					var rows = revs
						.map(function (r) {
							var href = viewerHref(opts, data, r);
							var label = r.revision != null && String(r.revision).trim() !== "" ? r.revision : r.version;
							var line =
								"<span class='usis-draw-pop__rev'>" +
								esc(String(label == null ? "—" : label)) +
								"</span> " +
								"<span class='usis-draw-pop__meta'>" +
								esc(r.drawing_set || "—") +
								" · " +
								esc(fmtMDY(r.updated_at || r.created_at)) +
								"</span>";
							if (href) {
								return "<a class='usis-draw-pop__row' href='" + esc(href) + "'>" + line + "</a>";
							}
							return "<div class='usis-draw-pop__row'>" + line + "</div>";
						})
						.join("");
					showPop(
						btn,
						"<div class='usis-draw-pop__title'>" +
							esc(t("Revisions")) +
							"</div>" +
							"<div class='usis-draw-pop__list'>" +
							rows +
							"</div>"
					);
				});
				wrap.appendChild(btn);
			}
			return wrap;
		};
	}

	function setFormatter(opts) {
		return function (cell) {
			var name = cell.getValue();
			if (name == null || String(name).trim() === "") return "—";
			name = String(name);
			var a = document.createElement("button");
			a.type = "button";
			a.className = "usis-draw-set-link";
			a.textContent = name;
			a.title = name;
			a.addEventListener("click", function (ev) {
				ev.preventDefault();
				ev.stopPropagation();
				if (opts.onSelectSet) opts.onSelectSet(name);
			});
			return a;
		};
	}

	function statusFormatter() {
		return function (cell) {
			var data = cell.getRow().getData();
			var span = document.createElement("span");
			span.className = "usis-draw-status" + (isPublished(data) ? "" : " usis-draw-status--draft");
			span.textContent = statusLabel(data);
			return span;
		};
	}

	function columns(opts) {
		opts = opts || {};
		var cols = [];
		if (opts.checkboxColumn) cols.push(opts.checkboxColumn);
		cols.push(
			{
				title: "",
				field: "_icons",
				headerSort: false,
				resizable: false,
				width: 72,
				minWidth: 64,
				hozAlign: "center",
				formatter: iconsFormatter(opts),
			},
			{
				title: t("Drawing Number"),
				field: "sheet_number",
				minWidth: 110,
				widthGrow: 1,
				editor: "input",
				formatter: identityFormatter("sheet_number", opts),
			},
			{
				title: t("Drawing Title"),
				field: "sheet_title",
				minWidth: 180,
				widthGrow: 3,
				editor: "input",
				formatter: identityFormatter("sheet_title", opts),
			},
			{
				title: t("Revision"),
				field: "revision_count",
				width: 120,
				minWidth: 100,
				headerSort: false,
				formatter: revisionFormatter(opts),
			},
			{
				title: t("Drawing Date"),
				field: "_ddate",
				width: 120,
				minWidth: 110,
				formatter: function (cell) {
					return drawingDate(cell.getRow().getData());
				},
			},
			{
				title: t("Received Date"),
				field: "_rdate",
				width: 120,
				minWidth: 110,
				formatter: function (cell) {
					return receivedDate(cell.getRow().getData());
				},
			},
			{
				title: t("Set"),
				field: "drawing_set",
				minWidth: 140,
				widthGrow: 2,
				formatter: setFormatter(opts),
			},
			{
				title: t("Status"),
				field: "_status",
				width: 110,
				minWidth: 100,
				hozAlign: "center",
				headerSort: false,
				formatter: statusFormatter(),
			},
			{ title: t("Discipline"), field: "discipline", visible: false }
		);
		return cols;
	}

	function paneOf(el) {
		return el && el.closest ? el.closest(".usis-draw-log") || el : el;
	}

	function activeView(pane) {
		var tab = qs(pane, ".usis-draw-log__tab.is-active");
		return (tab && tab.getAttribute("data-usis-draw-view")) || "current";
	}

	function activeLayout(pane) {
		var btn = qs(pane, ".usis-draw-log__layout.is-active");
		return (btn && btn.getAttribute("data-usis-draw-layout")) || "list";
	}

	function setView(pane, view) {
		qsa(pane, ".usis-draw-log__tab").forEach(function (btn) {
			var on = btn.getAttribute("data-usis-draw-view") === view;
			btn.classList.toggle("is-active", on);
			if (on) btn.setAttribute("aria-current", "page");
			else btn.removeAttribute("aria-current");
		});
		var current = qs(pane, ".usis-draw-log__current");
		var sets = qs(pane, ".usis-draw-log__sets");
		if (current) current.classList.toggle("d-none", view !== "current");
		if (sets) sets.classList.toggle("d-none", view !== "sets");
	}

	function setLayout(pane, layout) {
		try {
			sessionStorage.setItem(LAYOUT_KEY, layout);
		} catch (e) {}
		qsa(pane, ".usis-draw-log__layout").forEach(function (btn) {
			var on = btn.getAttribute("data-usis-draw-layout") === layout;
			btn.classList.toggle("is-active", on);
			btn.setAttribute("aria-pressed", on ? "true" : "false");
		});
	}

	function renderChips(pane) {
		var host = qs(pane, ".usis-draw-log__chips");
		if (!host) return;
		var discSel = qs(pane, "[id$='filter-drawing-discipline']") || qs(pane, "select.usis-draw-discipline");
		if (!discSel) {
			var all = pane.querySelectorAll("select");
			for (var i = 0; i < all.length; i++) {
				if ((all[i].id || "").indexOf("filter-drawing-discipline") !== -1) discSel = all[i];
			}
		}
		var setSel = qs(pane, "[id$='filter-drawing-set']");
		host.innerHTML = "";
		function addChip(label, onClear) {
			var chip = document.createElement("button");
			chip.type = "button";
			chip.className = "usis-draw-chip";
			chip.innerHTML = esc(label) + '<span class="usis-draw-chip__x" aria-hidden="true">×</span>';
			chip.addEventListener("click", onClear);
			host.appendChild(chip);
		}
		if (discSel && discSel.value) {
			addChip(t("Discipline") + ": " + discSel.value, function () {
				discSel.value = "";
				discSel.dispatchEvent(new Event("change", { bubbles: true }));
			});
		}
		if (setSel && setSel.value) {
			addChip(t("Set") + ": " + setSel.value, function () {
				setSel.value = "";
				setSel.dispatchEvent(new Event("change", { bubbles: true }));
			});
		}
		host.classList.toggle("d-none", !host.childNodes.length);
	}

	function collectSets(sheets) {
		var map = {};
		(sheets || []).forEach(function (s) {
			var names = {};
			if (s && s.drawing_set) names[s.drawing_set] = 1;
			(s && s.sets ? s.sets : []).forEach(function (n) {
				if (n) names[n] = 1;
			});
			(s && s.revisions ? s.revisions : []).forEach(function (r) {
				if (r && r.drawing_set) names[r.drawing_set] = 1;
			});
			Object.keys(names).forEach(function (name) {
				if (!map[name]) map[name] = { name: name, count: 0, latest: null };
				map[name].count += 1;
				var revs = (s.revisions || []).filter(function (r) {
					return String(r.drawing_set || "").toLowerCase() === name.toLowerCase();
				});
				if (!revs.length && s.current_revision) revs = [s.current_revision];
				revs.forEach(function (r) {
					var ts = r.updated_at || r.created_at;
					if (ts && (!map[name].latest || String(ts) > String(map[name].latest))) map[name].latest = ts;
				});
			});
		});
		return Object.keys(map)
			.map(function (k) {
				return map[k];
			})
			.sort(function (a, b) {
				return a.name.localeCompare(b.name, undefined, { numeric: true });
			});
	}

	function renderSets(pane, sheets, opts) {
		var host = qs(pane, ".usis-draw-sets-table-wrap");
		if (!host) return;
		var rows = collectSets(sheets);
		if (!rows.length) {
			host.innerHTML = '<div class="text-muted text-center py-5">' + esc(t("No drawing sets yet.")) + "</div>";
			return;
		}
		var html =
			'<table class="table table-sm mb-0 usis-draw-sets-table"><thead><tr>' +
			"<th>" +
			esc(t("Set")) +
			"</th><th>" +
			esc(t("Drawings")) +
			"</th><th>" +
			esc(t("Received Date")) +
			"</th></tr></thead><tbody>";
		rows.forEach(function (row) {
			html +=
				"<tr><td><button type='button' class='usis-draw-set-link' data-set='" +
				esc(row.name) +
				"'>" +
				esc(row.name) +
				"</button></td><td>" +
				esc(String(row.count)) +
				"</td><td>" +
				esc(fmtMDY(row.latest)) +
				"</td></tr>";
		});
		html += "</tbody></table>";
		host.innerHTML = html;
		qsa(host, "[data-set]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				if (opts.onSelectSet) opts.onSelectSet(btn.getAttribute("data-set"));
			});
		});
	}

	function rowId(row) {
		return row && row.series_id ? String(row.series_id) : "";
	}

	function renderCards(pane, rows, opts) {
		var host = qs(pane, ".usis-draw-log__cards");
		if (!host) return;
		host.innerHTML = "";
		if (!rows.length) {
			host.innerHTML = '<div class="text-muted text-center py-5">' + esc(t("No drawings for this project yet.")) + "</div>";
			return;
		}
		var groups = {};
		var order = [];
		rows.forEach(function (row) {
			var key = (row.discipline && String(row.discipline).trim()) || t("Unassigned");
			if (!groups[key]) {
				groups[key] = [];
				order.push(key);
			}
			groups[key].push(row);
		});
		order.forEach(function (key) {
			var box = document.createElement("div");
			box.className = "usis-draw-card-group";
			var h = document.createElement("div");
			h.className = "usis-draw-card-group__h";
			h.textContent = key + " (" + groups[key].length + ")";
			box.appendChild(h);
			var grid = document.createElement("div");
			grid.className = "usis-draw-cards";
			groups[key].forEach(function (row) {
				var id = rowId(row);
				var href = viewerHref(opts, row);
				var card = document.createElement("div");
				card.className = "usis-draw-card";
				var top = document.createElement("div");
				top.className = "usis-draw-card__top";
				var cb = document.createElement("input");
				cb.type = "checkbox";
				cb.className = "form-check-input m-0";
				cb.checked = !!(opts.selected && id && opts.selected.has(id));
				cb.setAttribute("aria-label", t("Select drawing"));
				cb.addEventListener("change", function () {
					if (opts.onToggleSelect) opts.onToggleSelect(id, cb.checked);
				});
				top.appendChild(cb);
				var badge = document.createElement("span");
				badge.className = "usis-draw-status" + (isPublished(row) ? "" : " usis-draw-status--draft");
				badge.textContent = statusLabel(row);
				top.appendChild(badge);
				card.appendChild(top);
				var num = href ? document.createElement("a") : document.createElement("div");
				num.className = "usis-draw-card__num usis-drawing-name-link";
				if (href) num.href = href;
				num.textContent = row.sheet_number || "—";
				card.appendChild(num);
				var title = document.createElement("div");
				title.className = "usis-draw-card__title";
				title.textContent = (row.sheet_title || "—").toUpperCase();
				card.appendChild(title);
				var meta = document.createElement("div");
				meta.className = "usis-draw-card__meta";
				meta.textContent =
					t("Rev") +
					" " +
					revisionLabel(row) +
					" · " +
					drawingDate(row) +
					(row.drawing_set ? " · " + row.drawing_set : "");
				card.appendChild(meta);
				grid.appendChild(card);
			});
			box.appendChild(grid);
			host.appendChild(box);
		});
	}

	function refresh(pane, opts) {
		opts = opts || {};
		if (!pane) return;
		pane = paneOf(pane);
		renderChips(pane);
		var view = activeView(pane);
		if (view === "sets") {
			renderSets(pane, opts.allSheets || opts.rows || [], opts);
			return;
		}
		var layout = activeLayout(pane);
		var table = qs(pane, ".usis-draw-log__table") || qs(pane, "[id$='grid-drawings']");
		var cards = qs(pane, ".usis-draw-log__cards");
		var toolbar = qs(pane, ".usis-draw-group-toolbar");
		if (layout === "grid") {
			if (table) table.classList.add("d-none");
			if (toolbar) toolbar.classList.add("d-none");
			if (cards) {
				cards.classList.remove("d-none");
				renderCards(pane, opts.rows || [], opts);
			}
			return;
		}
		if (cards) cards.classList.add("d-none");
		if (table) table.classList.remove("d-none");
		if (toolbar) toolbar.classList.remove("d-none");
		if (opts.buildTable) opts.buildTable(opts.rows || []);
	}

	function wire(pane, opts) {
		opts = opts || {};
		if (!pane || pane.dataset.usisDrawLogWired === "1") return;
		if (!pane.classList.contains("usis-draw-log") && !qs(pane, ".usis-draw-log")) return;
		pane.dataset.usisDrawLogWired = "1";
		var root = pane.classList.contains("usis-draw-log") ? pane : qs(pane, ".usis-draw-log") || pane;
		var saved = "";
		try {
			saved = sessionStorage.getItem(LAYOUT_KEY) || "";
		} catch (e) {}
		if (saved === "grid" || saved === "list") setLayout(root, saved);
		qsa(root, ".usis-draw-log__tab").forEach(function (btn) {
			btn.addEventListener("click", function () {
				setView(root, btn.getAttribute("data-usis-draw-view") || "current");
				if (opts.onChange) opts.onChange();
			});
		});
		qsa(root, ".usis-draw-log__layout").forEach(function (btn) {
			btn.addEventListener("click", function () {
				setLayout(root, btn.getAttribute("data-usis-draw-layout") || "list");
				if (opts.onChange) opts.onChange();
			});
		});
		var allBtn = qs(root, ".usis-draw-log__all-filters");
		var panel = qs(root, ".usis-draw-log__filter-panel");
		if (allBtn && panel) {
			allBtn.addEventListener("click", function () {
				var open = panel.classList.contains("d-none");
				panel.classList.toggle("d-none", !open);
				allBtn.classList.toggle("is-open", open);
				allBtn.setAttribute("aria-expanded", open ? "true" : "false");
			});
		}
		var exportBtn = qs(root, ".usis-draw-export");
		if (exportBtn && opts.onExport) {
			exportBtn.addEventListener("click", opts.onExport);
		}
		setView(root, "current");
	}

	function selectSetIn(pane, name) {
		var root = paneOf(pane);
		var setSel = qs(root, "[id$='filter-drawing-set']");
		if (setSel) {
			var found = false;
			Array.prototype.forEach.call(setSel.options, function (o) {
				if (o.value === name) found = true;
			});
			if (!found && name) {
				var o = document.createElement("option");
				o.value = name;
				o.textContent = name;
				setSel.appendChild(o);
			}
			setSel.value = name || "";
		}
		setView(root, "current");
		if (setSel) setSel.dispatchEvent(new Event("change", { bubbles: true }));
	}

	global.USISDrawingsLog = {
		t: t,
		esc: esc,
		fmtMDY: fmtMDY,
		revisionLabel: revisionLabel,
		drawingDate: drawingDate,
		receivedDate: receivedDate,
		columns: columns,
		wire: wire,
		refresh: refresh,
		renderChips: renderChips,
		selectSetIn: selectSetIn,
		activeView: activeView,
		activeLayout: activeLayout,
		closePop: closePop,
		paneOf: paneOf,
	};
})(window);
