/**
 * Admin: publish amendable workflow definitions (first-pass AI + office processes).
 */
(function () {
	"use strict";

	function fetchJson(path, opts) {
		if (window.USIS_API && typeof window.USIS_API.fetchJson === "function") {
			return window.USIS_API.fetchJson(path, opts || {});
		}
		var o = opts || {};
		var headers = Object.assign({ Accept: "application/json" }, o.headers || {});
		var init = { method: o.method || "GET", headers: headers, credentials: "include" };
		if (o.body !== undefined && o.body !== null) {
			if (!headers["Content-Type"]) headers["Content-Type"] = "application/json";
			init.headers = headers;
			init.body = typeof o.body === "string" ? o.body : JSON.stringify(o.body);
		}
		return fetch(path, init).then(function (res) {
			return res.json().then(function (j) {
				if (!res.ok) throw new Error((j && j.error) || res.statusText);
				return j;
			});
		});
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	var state = { processKey: "drawing_review", steps: [], name: "", notes: "" };

	function showErr(msg) {
		var el = document.getElementById("usis-wf-alert");
		if (!el) return;
		if (!msg) {
			el.classList.add("d-none");
			el.textContent = "";
			return;
		}
		el.classList.remove("d-none");
		el.textContent = msg;
	}

	function emptyStep(i) {
		return {
			step_key: "step_" + (i + 1),
			label: "Step " + (i + 1),
			sort_order: i + 1,
			queue_key: "estimator",
			required_actions: ["run_ai_review"],
			skippable: false,
			automation: { action: "run_ai_review", mode: "", prompt: "", system_hint: "", auto_complete: true },
		};
	}

	function normalizeStep(raw, i) {
		var a = raw.automation || {};
		return {
			step_key: raw.step_key || raw.stepKey || "step_" + (i + 1),
			label: raw.label || "Step " + (i + 1),
			sort_order: raw.sort_order || raw.sortOrder || i + 1,
			queue_key: raw.queue_key || raw.queueKey || "",
			required_actions: raw.required_actions || raw.requiredActions || [],
			skippable: !!raw.skippable,
			automation: {
				action: a.action || "",
				mode: a.mode || "",
				prompt: a.prompt || "",
				system_hint: a.system_hint || a.systemHint || "",
				auto_complete: a.auto_complete !== false && a.autoComplete !== false,
			},
		};
	}

	function readEditor() {
		var rows = document.querySelectorAll("#usis-wf-steps .usis-wf-step");
		state.steps = Array.prototype.map.call(rows, function (row, i) {
			var actions = (row.querySelector("[data-f=actions]").value || "")
				.split(",")
				.map(function (x) {
					return x.trim();
				})
				.filter(Boolean);
			return {
				step_key: row.querySelector("[data-f=key]").value.trim() || "step_" + (i + 1),
				label: row.querySelector("[data-f=label]").value.trim() || "Step " + (i + 1),
				sort_order: i + 1,
				queue_key: row.querySelector("[data-f=queue]").value.trim() || null,
				required_actions: actions,
				skippable: row.querySelector("[data-f=skip]").checked,
				automation: {
					action: row.querySelector("[data-f=action]").value.trim(),
					mode: row.querySelector("[data-f=mode]").value.trim(),
					prompt: row.querySelector("[data-f=prompt]").value,
					system_hint: row.querySelector("[data-f=hint]").value,
					auto_complete: row.querySelector("[data-f=auto]").checked,
				},
			};
		});
		state.name = (document.getElementById("usis-wf-name") || {}).value || state.processKey;
		state.notes = (document.getElementById("usis-wf-notes") || {}).value || "";
	}

	function renderSteps() {
		var host = document.getElementById("usis-wf-steps");
		if (!host) return;
		host.innerHTML = "";
		state.steps.forEach(function (s, i) {
			var a = s.automation || {};
			var card = document.createElement("div");
			card.className = "card border mb-2 usis-wf-step";
			card.innerHTML =
				'<div class="card-body py-2">' +
				'<div class="d-flex justify-content-between align-items-center mb-2">' +
				'<span class="small text-muted">Step ' +
				(i + 1) +
				"</span>" +
				'<div class="btn-group btn-group-sm">' +
				'<button type="button" class="btn btn-outline-secondary" data-move="-1">Up</button>' +
				'<button type="button" class="btn btn-outline-secondary" data-move="1">Down</button>' +
				'<button type="button" class="btn btn-outline-danger" data-del="1">Remove</button>' +
				"</div></div>" +
				'<div class="row g-2">' +
				'<div class="col-md-3"><label class="form-label small mb-0">step_key</label>' +
				'<input class="form-control form-control-sm" data-f="key" value="' +
				esc(s.step_key) +
				'"></div>' +
				'<div class="col-md-5"><label class="form-label small mb-0">Label</label>' +
				'<input class="form-control form-control-sm" data-f="label" value="' +
				esc(s.label) +
				'"></div>' +
				'<div class="col-md-2"><label class="form-label small mb-0">Queue</label>' +
				'<input class="form-control form-control-sm" data-f="queue" value="' +
				esc(s.queue_key) +
				'"></div>' +
				'<div class="col-md-2 d-flex align-items-end gap-2">' +
				'<div class="form-check"><input class="form-check-input" type="checkbox" data-f="skip"' +
				(s.skippable ? " checked" : "") +
				'><label class="form-check-label small">Skip OK</label></div>' +
				'<div class="form-check"><input class="form-check-input" type="checkbox" data-f="auto"' +
				(a.auto_complete !== false ? " checked" : "") +
				'><label class="form-check-label small">Auto</label></div>' +
				"</div>" +
				'<div class="col-md-3"><label class="form-label small mb-0">Action</label>' +
				'<input class="form-control form-control-sm" data-f="action" value="' +
				esc(a.action) +
				'" placeholder="run_ai_review"></div>' +
				'<div class="col-md-3"><label class="form-label small mb-0">AI mode</label>' +
				'<input class="form-control form-control-sm" data-f="mode" value="' +
				esc(a.mode) +
				'" placeholder="construction_review"></div>' +
				'<div class="col-md-6"><label class="form-label small mb-0">Required actions</label>' +
				'<input class="form-control form-control-sm" data-f="actions" value="' +
				esc((s.required_actions || []).join(", ")) +
				'"></div>' +
				'<div class="col-12"><label class="form-label small mb-0">Prompt (user message)</label>' +
				'<textarea class="form-control form-control-sm" data-f="prompt" rows="3">' +
				esc(a.prompt) +
				"</textarea></div>" +
				'<div class="col-12"><label class="form-label small mb-0">System hint (appended to system prompt)</label>' +
				'<textarea class="form-control form-control-sm" data-f="hint" rows="2">' +
				esc(a.system_hint) +
				"</textarea></div>" +
				"</div></div>";
			card.querySelector("[data-del]").addEventListener("click", function () {
				readEditor();
				state.steps.splice(i, 1);
				renderSteps();
			});
			card.querySelector("[data-move='-1']").addEventListener("click", function () {
				if (i === 0) return;
				readEditor();
				var tmp = state.steps[i - 1];
				state.steps[i - 1] = state.steps[i];
				state.steps[i] = tmp;
				renderSteps();
			});
			card.querySelector("[data-move='1']").addEventListener("click", function () {
				if (i >= state.steps.length - 1) return;
				readEditor();
				var tmp = state.steps[i + 1];
				state.steps[i + 1] = state.steps[i];
				state.steps[i] = tmp;
				renderSteps();
			});
			host.appendChild(card);
		});
	}

	function loadProcesses() {
		return fetchJson("/api/workflows/processes").then(function (body) {
			var sel = document.getElementById("usis-wf-process");
			if (!sel) return body;
			sel.innerHTML = "";
			(body.items || []).forEach(function (p) {
				var opt = document.createElement("option");
				opt.value = p.processKey;
				opt.textContent = p.name + " (" + p.processKey + ") v" + p.publishedVersion;
				sel.appendChild(opt);
			});
			if (state.processKey) sel.value = state.processKey;
			return body;
		});
	}

	function loadDefinition() {
		showErr("");
		state.processKey = document.getElementById("usis-wf-process").value || "drawing_review";
		return fetchJson("/api/workflows/definitions?process_key=" + encodeURIComponent(state.processKey)).then(
			function (body) {
				var items = body.items || [];
				var published = items.find(function (x) {
					return x.isPublished;
				}) || items[0];
				if (!published) {
					return loadSeed();
				}
				state.name = published.name || state.processKey;
				state.notes = "";
				state.steps = (published.steps || []).map(normalizeStep);
				var nameEl = document.getElementById("usis-wf-name");
				if (nameEl) nameEl.value = state.name;
				var ver = document.getElementById("usis-wf-version");
				if (ver) ver.textContent = "Published v" + published.version + " — new publish becomes v" + (published.version + 1) + ". Open work keeps the old snapshot.";
				renderSteps();
			}
		);
	}

	function loadSeed() {
		return fetchJson("/api/workflows/seeds/" + encodeURIComponent(state.processKey)).then(function (body) {
			state.name = body.name || state.processKey;
			state.steps = (body.steps || []).map(normalizeStep);
			var nameEl = document.getElementById("usis-wf-name");
			if (nameEl) nameEl.value = state.name;
			var ver = document.getElementById("usis-wf-version");
			if (ver) ver.textContent = "Showing seed defaults. Publish to make them live.";
			renderSteps();
		});
	}

	function renderScripts(items) {
		var tb = document.getElementById("usis-wf-scripts");
		if (!tb) return;
		tb.innerHTML = (items || [])
			.map(function (s) {
				return (
					"<tr><td><code>" +
					esc(s.scriptKey) +
					"</code></td><td>" +
					esc(s.name) +
					"</td><td>" +
					esc(s.kind) +
					"</td><td>" +
					esc((s.specPrefixes || []).join(", ")) +
					"</td><td><button type=\"button\" class=\"btn btn-link btn-sm p-0\" data-open=\"" +
					esc(s.scriptKey) +
					"\">Edit steps</button></td></tr>"
				);
			})
			.join("");
		tb.querySelectorAll("[data-open]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var sel = document.getElementById("usis-wf-process");
				if (sel) sel.value = btn.getAttribute("data-open");
				state.processKey = btn.getAttribute("data-open");
				loadDefinition().catch(function (e) {
					showErr(e.message || String(e));
				});
			});
		});
	}

	function loadScripts() {
		return fetchJson("/api/workflows/scripts?active_only=0").then(function (body) {
			renderScripts(body.items || []);
			return body;
		});
	}

	function loadStandards() {
		return fetchJson("/api/workflows/standard-specs").then(function (body) {
			var el = document.getElementById("usis-wf-standards");
			if (!el) return body;
			el.value = (body.items || [])
				.map(function (s) {
					return (s.specCode || "") + " " + (s.specTitle || "");
				})
				.join("\n");
			return body;
		});
	}

	function saveStandards() {
		var el = document.getElementById("usis-wf-standards");
		if (!el) return;
		var items = el.value
			.split("\n")
			.map(function (line, i) {
				var t = line.trim();
				if (!t) return null;
				var parts = t.split(/\s+/);
				var code = parts[0];
				if (parts.length >= 3 && /^\d{2}$/.test(parts[0]) && /^\d{2}$/.test(parts[1]) && /^\d{2}$/.test(parts[2])) {
					code = parts[0] + " " + parts[1] + " " + parts[2];
					return { spec_code: code, spec_title: parts.slice(3).join(" ") || code, sort_order: (i + 1) * 10 };
				}
				return { spec_code: code, spec_title: parts.slice(1).join(" ") || code, sort_order: (i + 1) * 10 };
			})
			.filter(Boolean);
		return fetchJson("/api/workflows/standard-specs", { method: "PUT", body: { items: items } })
			.then(function () {
				if (window.USISNotify) window.USISNotify.success("Standard specs saved.");
			})
			.catch(function (e) {
				showErr(e.message || String(e));
			});
	}

	function addScript() {
		var key = ((document.getElementById("usis-wf-new-key") || {}).value || "").trim();
		var name = ((document.getElementById("usis-wf-new-name") || {}).value || "").trim();
		var prefix = ((document.getElementById("usis-wf-new-prefix") || {}).value || "").trim();
		if (!key) {
			showErr("New script needs a key (e.g. spec.wallcovering).");
			return;
		}
		var prefixes = prefix
			.split(",")
			.map(function (x) {
				return x.trim();
			})
			.filter(Boolean);
		return fetchJson("/api/workflows/scripts", {
			method: "POST",
			body: { script_key: key, name: name || key, kind: "spec", spec_prefixes: prefixes },
		})
			.then(function () {
				if (window.USISNotify) window.USISNotify.success("Script added. Edit steps below and publish.");
				return loadScripts().then(loadProcesses).then(function () {
					var sel = document.getElementById("usis-wf-process");
					if (sel) sel.value = key;
					state.processKey = key;
					return loadDefinition();
				});
			})
			.catch(function (e) {
				showErr(e.message || String(e));
			});
	}

	function publish() {
		readEditor();
		showErr("");
		return fetchJson("/api/workflows/definitions", {
			method: "POST",
			body: {
				process_key: state.processKey,
				name: state.name,
				notes: state.notes,
				steps: state.steps,
			},
		})
			.then(function () {
				if (window.USISNotify) window.USISNotify.success("Published new workflow version.");
				return loadProcesses().then(loadDefinition);
			})
			.catch(function (e) {
				showErr(e.message || String(e));
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		loadProcesses()
			.then(loadDefinition)
			.then(loadScripts)
			.then(loadStandards)
			.catch(function (e) {
				showErr(e.message || String(e));
			});
		var addScriptBtn = document.getElementById("usis-wf-new-script");
		if (addScriptBtn) addScriptBtn.addEventListener("click", addScript);
		var saveStd = document.getElementById("usis-wf-save-standards");
		if (saveStd) saveStd.addEventListener("click", saveStandards);
		var sel = document.getElementById("usis-wf-process");
		if (sel)
			sel.addEventListener("change", function () {
				loadDefinition().catch(function (e) {
					showErr(e.message || String(e));
				});
			});
		var add = document.getElementById("usis-wf-add-step");
		if (add)
			add.addEventListener("click", function () {
				readEditor();
				state.steps.push(emptyStep(state.steps.length));
				renderSteps();
			});
		var seed = document.getElementById("usis-wf-reset-seed");
		if (seed)
			seed.addEventListener("click", function () {
				loadSeed().catch(function (e) {
					showErr(e.message || String(e));
				});
			});
		var pub = document.getElementById("usis-wf-publish");
		if (pub) pub.addEventListener("click", publish);
	});
})();
