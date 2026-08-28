(function () {
	"use strict";

	function fetchJson(path, opts) {
		if (window.USIS_API) return window.USIS_API.fetchJson(path, opts || {});
		return fetch(path, Object.assign({ credentials: "include", headers: { Accept: "application/json" } }, opts || {})).then(function (r) {
			return r.json().then(function (j) {
				if (!r.ok) throw new Error(j.error || r.status);
				return j;
			});
		});
	}

	function qs() {
		return new URLSearchParams(window.location.search);
	}

	function renderStepper(wf) {
		var el = document.getElementById("usis-sub-workflow-stepper");
		if (!el) return;
		if (!wf || !wf.steps) {
			el.textContent = "";
			return;
		}
		el.innerHTML = (wf.steps || [])
			.map(function (s) {
				var cls = s.status === "complete" ? "text-success" : s.status === "ready" ? "fw-semibold text-primary" : "text-muted";
				return '<span class="' + cls + '">' + (s.label || s.stepKey) + "</span>";
			})
			.join(" → ");
	}

	function renderHolds(holds) {
		var el = document.getElementById("usis-sub-holds-banner");
		if (!el) return;
		var active = (holds || []).filter(function (h) {
			return h.isActive;
		});
		if (!active.length) {
			el.classList.add("d-none");
			return;
		}
		el.classList.remove("d-none");
		el.textContent = active
			.map(function (h) {
				return (h.holdType || "").replace(/^\w/, function (c) { return c.toUpperCase(); }) + " hold ON";
			})
			.join(" · ");
	}

	function renderChecklist(rev) {
		var box = document.getElementById("usis-qc-checklist");
		if (!box) return;
		box.innerHTML = "";
		(rev.checklist || []).forEach(function (item) {
			var wrap = document.createElement("div");
			wrap.className = "border-bottom py-2";
			wrap.dataset.id = item.id;
			wrap.innerHTML =
				'<div class="small fw-semibold">' +
				(item.label || "") +
				(item.required ? ' <span class="text-danger">*</span>' : "") +
				(item.source === "ai_finding" ? ' <span class="usis-status-chip usis-status-chip--progress">AI</span>' : "") +
				"</div>" +
				'<div class="d-flex flex-wrap gap-2 mt-1">' +
				'<select class="form-select form-select-sm usis-qc-result" style="max-width:8rem">' +
				["blank", "pass", "fail", "na"]
					.map(function (v) {
						return '<option value="' + v + '"' + ((item.result || "blank") === v ? " selected" : "") + ">" + v + "</option>";
					})
					.join("") +
				"</select>" +
				'<input class="form-control form-control-sm usis-qc-comment" placeholder="Comment" value="' +
				String(item.comment || "").replace(/"/g, "&quot;") +
				'">' +
				(item.source === "ai_finding"
					? '<select class="form-select form-select-sm usis-qc-disp" style="max-width:12rem"><option value="">Disposition</option><option value="accepted"' +
					  (item.disposition === "accepted" ? " selected" : "") +
					  ">accepted</option><option value=\"overridden\"" +
					  (item.disposition === "overridden" ? " selected" : "") +
					  ">overridden</option><option value=\"converted_to_comment\"" +
					  (item.disposition === "converted_to_comment" ? " selected" : "") +
					  ">converted_to_comment</option></select>"
					: "") +
				"</div>";
			box.appendChild(wrap);
		});
	}

	function collectChecklist() {
		return Array.prototype.map.call(document.querySelectorAll("#usis-qc-checklist [data-id]"), function (wrap) {
			var disp = wrap.querySelector(".usis-qc-disp");
			return {
				id: wrap.dataset.id,
				result: wrap.querySelector(".usis-qc-result").value,
				comment: wrap.querySelector(".usis-qc-comment").value,
				disposition: disp ? disp.value : undefined,
			};
		});
	}

	function applyStampGates(gates) {
		var btn = document.getElementById("usis-qc-stamp");
		var hint = document.getElementById("usis-qc-stamp-unmet");
		if (!btn || !hint) return;
		var unmet = (gates && gates.unmet) || [];
		btn.disabled = !gates || !gates.canStamp;
		btn.title = unmet.join("; ");
		hint.textContent = unmet.length ? "Stamp disabled: " + unmet.join("; ") : "Ready to stamp.";
	}

	var state = { detail: null };

	function load() {
		var sid = qs().get("submittal");
		if (!sid) return;
		fetchJson("/api/submittals/" + sid).then(function (body) {
			state.detail = body;
			var item = body.item || {};
			var num = document.getElementById("usis-sub-num");
			if (num) num.textContent = item.submittalNumber || item.submittal_number || item.number || "—";
			renderStepper(body.workflow);
			renderHolds(body.holds || []);
			var score = document.getElementById("usis-qc-complete-score");
			if (score && body.revision) {
				score.textContent =
					"Score " +
					(body.revision.completenessScore == null ? "—" : body.revision.completenessScore) +
					" · package " +
					(body.revision.packageComplete ? "complete" : "incomplete") +
					" · AI " +
					body.revision.aiStatus;
			}
			var ai = document.getElementById("usis-qc-ai-status");
			if (ai && body.revision) {
				ai.textContent = (body.revision.aiFindings || []).length + " findings";
			}
			if (body.revision) renderChecklist(body.revision);
			applyStampGates(body.stampGates || {});
		});
	}

	function revId() {
		return state.detail && state.detail.revision && state.detail.revision.id;
	}

	function sid() {
		return qs().get("submittal");
	}

	document.addEventListener("DOMContentLoaded", function () {
		load();
		var recompute = document.getElementById("usis-qc-recompute");
		if (recompute)
			recompute.addEventListener("click", function () {
				if (!sid() || !revId()) return;
				fetchJson("/api/submittals/" + sid() + "/revisions/" + revId() + "/completeness", { method: "POST", body: {} }).then(load);
			});
		var save = document.getElementById("usis-qc-checklist-save");
		if (save)
			save.addEventListener("click", function () {
				if (!sid() || !revId()) return;
				fetchJson("/api/submittals/" + sid() + "/revisions/" + revId() + "/checklist", {
					method: "PATCH",
					headers: { "Content-Type": "application/json" },
					body: { items: collectChecklist() },
				}).then(load);
			});
		var aiBtn = document.getElementById("usis-qc-ai");
		if (aiBtn)
			aiBtn.addEventListener("click", function () {
				var item = (state.detail && state.detail.item) || {};
				var payload = {
					mode: "submittal_review",
					submittalId: sid(),
					revisionId: revId(),
					documentIds: (state.detail.revision && state.detail.revision.documentIds) || [],
					drawingIds: item.linked_drawing_ids || [],
					context: {
						projectId: item.projectId || item.project_id,
						specSection: item.specSection || item.spec_section,
						trade: item.trade,
						californiaCodes: true,
					},
				};
				if (window.aiReviewBus) window.aiReviewBus.emit("review-request", payload);
				fetchJson("/api/ai/chat", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: {
						mode: "submittal_review",
						messages: [{ role: "user", content: "Review this submittal package against spec " + (payload.context.specSection || "") + " and return structured findings JSON." }],
					},
				})
					.then(function (chat) {
						var text = (chat && (chat.reply || chat.content || chat.message)) || JSON.stringify(chat || {});
						var findings = [];
						try {
							var parsed = typeof text === "string" ? JSON.parse(text) : text;
							if (parsed && parsed.findings) findings = parsed.findings;
						} catch (e) {
							findings = [];
						}
						return fetchJson("/api/submittals/" + sid() + "/revisions/" + revId() + "/ai-review", {
							method: "POST",
							headers: { "Content-Type": "application/json" },
							body: { ai_status: "complete", findings: findings, raw_response: typeof text === "string" ? text : JSON.stringify(text) },
						});
					})
					.then(function () {
						if (window.aiReviewBus) window.aiReviewBus.emit("review-complete", { submittalId: sid(), revisionId: revId() });
						load();
					})
					.catch(function (e) {
						if (window.USISNotify) window.USISNotify.error(String(e.message || e));
					});
			});
		var ov = document.getElementById("usis-qc-ai-override");
		if (ov)
			ov.addEventListener("click", function () {
				var reason = window.prompt("Written reason to override AI review");
				if (!reason) return;
				fetchJson("/api/submittals/" + sid() + "/revisions/" + revId() + "/ai-review", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: { ai_status: "overridden", ai_overridden_reason: reason },
				}).then(load);
			});
		var stamp = document.getElementById("usis-qc-stamp");
		if (stamp)
			stamp.addEventListener("click", function () {
				fetchJson("/api/submittals/" + sid() + "/revisions/" + revId() + "/stamp", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: {
						stamp: document.getElementById("usis-qc-stamp-value").value,
						comments: document.getElementById("usis-qc-stamp-comments").value,
						rush_exception: document.getElementById("usis-qc-rush").checked,
					},
				})
					.then(load)
					.catch(function (e) {
						if (window.USISNotify) window.USISNotify.error(String(e.message || e));
					});
			});
	});
})();
