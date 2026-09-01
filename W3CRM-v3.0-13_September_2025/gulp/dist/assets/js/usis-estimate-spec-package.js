/**
 * Estimate detail — Spec package panel (BOD + alternates → draft RFPs).
 * Listens for usis-estimate-loaded. Does not send vendor mail.
 */
(function () {
	"use strict";

	var estimateId = null;
	var projectId = null;
	var payload = null;
	var showOut = false;
	var busy = false;

	function Api() {
		return window.USISEstimateApi;
	}

	function ui() {
		return window.USISUi || {};
	}

	function esc(s) {
		return String(s == null ? "" : s)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function notifyErr(msg) {
		if (window.USISNotify) window.USISNotify.error(String(msg));
		else alert(String(msg));
	}

	function notifyOk(msg) {
		if (window.USISNotify) window.USISNotify.success(String(msg));
	}

	function root() {
		return document.getElementById("usis-spec-pkg-root");
	}

	function chip(status, label) {
		var family = "draft";
		if (status === "review_sections") family = "warning";
		else if (status === "review_products" || status === "extracting") family = "info";
		else if (status === "vendors_ready") family = "success";
		else if (status === "rfp_drafted") family = "success";
		if (ui().statusChip) return ui().statusChip(status, { label: label, family: family });
		return '<span class="badge text-bg-secondary">' + esc(label) + "</span>";
	}

	function emptyHtml() {
		var body =
			"No specification files on this job yet. Upload a project manual under Files → Specs, then analyze.";
		if (ui().emptyState) {
			return ui().emptyState({
				icon: "icon-file-text",
				title: "No specs to analyze",
				body: body,
			});
		}
		return '<p class="text-muted mb-0">' + esc(body) + "</p>";
	}

	function confChip(v) {
		if (v == null || v === "") return "—";
		var n = Number(v);
		if (!isFinite(n)) return esc(v);
		var family = n >= 0.8 ? "success" : n >= 0.6 ? "info" : "warning";
		var label = n.toFixed(1);
		if (ui().statusChip) return ui().statusChip(label, { label: label, family: family, title: "Model confidence" });
		return esc(label);
	}

	function roleChip(role) {
		var map = {
			basis_of_design: { label: "BOD", family: "success" },
			listed_alternate: { label: "Alternate", family: "info" },
			or_equal: { label: "Or equal", family: "draft" },
			prohibited: { label: "Prohibited", family: "critical" },
			schedule_item: { label: "Schedule", family: "minor" },
		};
		var m = map[role] || { label: role, family: "draft" };
		if (ui().statusChip) return ui().statusChip(role, { label: m.label, family: m.family });
		return esc(m.label);
	}

	function matchChip(status) {
		if (!status || status === "unmatched") return '<span class="text-muted small">unmatched</span>';
		if (status === "needs_configurator") {
			return ui().statusChip
				? ui().statusChip(status, { label: "Family / configurator", family: "warning" })
				: "Family";
		}
		return esc(status.replace("_", " "));
	}

	function setBusy(on) {
		busy = !!on;
		var el = root();
		if (!el) return;
		el.querySelectorAll("[data-spec-act]").forEach(function (btn) {
			btn.disabled = !!on;
		});
	}

	function collectSections() {
		var rows = [];
		(root() || document)
			.querySelectorAll("[data-spec-section]")
			.forEach(function (tr) {
				rows.push({
					id: tr.getAttribute("data-spec-section"),
					in_scope: !!(tr.querySelector("[data-spec-inscope]") && tr.querySelector("[data-spec-inscope]").checked),
					shop_alternates: !(
						tr.querySelector("[data-spec-bod-only]") && tr.querySelector("[data-spec-bod-only]").checked
					),
					estimator_notes: (tr.querySelector("[data-spec-notes]") || {}).value || "",
				});
			});
		return rows;
	}

	function collectMentions() {
		var rows = [];
		(root() || document)
			.querySelectorAll("[data-spec-mention]")
			.forEach(function (card) {
				rows.push({
					id: card.getAttribute("data-spec-mention"),
					manufacturer: (card.querySelector("[data-m-mfr]") || {}).value || "",
					product_line: (card.querySelector("[data-m-line]") || {}).value || "",
					model_no: (card.querySelector("[data-m-model]") || {}).value || "",
					page_cite: (card.querySelector("[data-m-cite]") || {}).value || "",
					excerpt: (card.querySelector("[data-m-excerpt]") || {}).value || "",
					or_equal: !!(card.querySelector("[data-m-orequal]") && card.querySelector("[data-m-orequal]").checked),
				});
			});
		return rows;
	}

	function collectVendors() {
		var rows = [];
		(root() || document)
			.querySelectorAll("[data-spec-vendor]")
			.forEach(function (tr) {
				rows.push({
					id: tr.getAttribute("data-spec-vendor"),
					selected: !!(tr.querySelector("[data-v-sel]") && tr.querySelector("[data-v-sel]").checked),
				});
			});
		return rows;
	}

	function render(data) {
		payload = data || payload;
		var el = root();
		if (!el) return;
		var sources = (payload && payload.sources) || {};
		var item = (payload && payload.item) || null;
		var status = (payload && payload.status) || null;
		var label = (payload && payload.status_label) || "No scan";
		var canAnalyze = !!sources.analyze_enabled;
		var aiBtn = ui().aiReviewButton
			? ui().aiReviewButton({ id: "usis-spec-pkg-ai", label: "Review specs with Local AI", size: "small" })
			: '<button type="button" class="btn usis-ai-review btn-sm" id="usis-spec-pkg-ai">Review specs with Local AI</button>';

		var analyzeTitle = canAnalyze
			? "Analyze specs"
			: "Upload a project manual under Files → Specs, or add drawings, then analyze";

		var html = "";
		html += '<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">';
		html += "<div class=\"d-flex flex-wrap align-items-center gap-2\"><h5 class=\"mb-0\">Spec package</h5>";
		html += chip(status, label);
		if (item && item.progress_text) html += '<span class="text-muted small">' + esc(item.progress_text) + "</span>";
		html += "</div><div class=\"d-flex flex-wrap gap-1\">";
		html +=
			'<button type="button" class="btn btn-primary btn-sm" data-spec-act="analyze" title="' +
			esc(analyzeTitle) +
			'" ' +
			(canAnalyze ? "" : "disabled") +
			">Analyze specs</button>";
		html += aiBtn;
		html += "</div></div>";

		if (item && item.error_text) {
			html += '<div class="alert alert-warning py-2 small">' + esc(item.error_text) + "</div>";
		}

		if (!item && !canAnalyze) {
			html += emptyHtml();
			el.innerHTML = html;
			bind();
			return;
		}
		if (!item) {
			html +=
				'<p class="text-muted small mb-0">After drawings and the project manual are on the job, analyze specs, confirm BOD and listed alternates, then create draft RFPs. Send stays on the existing RFP page.</p>';
			el.innerHTML = html;
			bind();
			return;
		}

		html += renderSections(payload);
		html += renderMentions(payload);
		html += renderVendors(payload);
		el.innerHTML = html;
		bind();
	}

	function renderSections(data) {
		var sections = data.sections || [];
		var hidden = data.out_of_trade_count || 0;
		var status = data.status;
		var html = '<div class="mb-3">';
		html += '<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">';
		html += "<h6 class=\"mb-0\">Which specs are we bidding?</h6>";
		html += '<div class="form-check form-check-inline mb-0">';
		html +=
			'<input class="form-check-input" type="checkbox" id="usis-spec-pkg-out" ' +
			(showOut ? "checked" : "") +
			">";
		html +=
			'<label class="form-check-label small" for="usis-spec-pkg-out">Show sections outside USIS trades' +
			(hidden ? " (" + hidden + ")" : "") +
			"</label></div></div>";
		if (!sections.length) {
			html += '<p class="text-muted small mb-2">No in-trade sections yet. Turn on outside trades or re-analyze.</p>';
		} else {
			html += '<div class="table-responsive"><table class="table table-sm align-middle mb-2">';
			html +=
				"<thead><tr><th>In scope</th><th>CSI</th><th>Title</th><th>Pages</th><th>Confidence</th><th>Notes</th></tr></thead><tbody>";
			sections.forEach(function (s) {
				html += '<tr data-spec-section="' + esc(s.id) + '">';
				html +=
					'<td><input type="checkbox" class="form-check-input" data-spec-inscope ' +
					(s.in_scope ? "checked" : "") +
					"></td>";
				html += "<td class=\"text-nowrap\">" + esc(s.csi_code) + "</td>";
				html += "<td>" + esc(s.title) + (s.out_of_trade ? ' <span class="text-muted small">out of trade</span>' : "") + "</td>";
				html += "<td class=\"small\">" + esc(s.pages || "—") + "</td>";
				html += "<td>" + confChip(s.confidence) + "</td>";
				html +=
					'<td><input type="text" class="form-control form-control-sm" data-spec-notes value="' +
					esc(s.estimator_notes || "") +
					'"></td>';
				html += "</tr>";
			});
			html += "</tbody></table></div>";
		}
		if (status === "review_sections" || status === "detecting") {
			html +=
				'<button type="button" class="btn btn-outline-primary btn-sm" data-spec-act="confirm-sections">Confirm sections</button>';
		}
		html += "</div>";
		return html;
	}

	function renderMentions(data) {
		var status = data.status;
		var ready = ["extracting", "review_products", "vendors_ready", "rfp_drafted"].indexOf(status) >= 0;
		if (!ready) return "";
		var html = '<div class="mb-3">';
		html += "<h6 class=\"mb-2\">Basis of Design and listed alternates</h6>";
		html +=
			'<p class="text-muted small">Matching is informational. Confirm before seeding an RFP. Never auto-applies catalog prices to takeoff.</p>';
		(data.sections || []).forEach(function (s) {
			if (!s.in_scope) return;
			html += '<div class="card mb-2" data-spec-section-card="' + esc(s.id) + '">';
			html += '<div class="card-header py-2 d-flex flex-wrap justify-content-between gap-2">';
			html += "<span><strong>" + esc(s.csi_code) + "</strong> " + esc(s.title) + "</span>";
			html +=
				'<label class="small mb-0"><input type="checkbox" class="form-check-input me-1" data-spec-bod-only ' +
				(s.shop_alternates ? "" : "checked") +
				"> BOD only — do not shop alternates</label>";
			html += "</div><div class=\"card-body py-2\">";
			var mentions = s.mentions || [];
			if (!mentions.length) {
				html += '<p class="text-muted small mb-2">No product mentions yet. Add a BOD row or review with Local AI.</p>';
			}
			mentions.forEach(function (m) {
				html += mentionEditor(m);
			});
			html +=
				'<button type="button" class="btn btn-outline-secondary btn-sm" data-spec-act="add-mention" data-section="' +
				esc(s.id) +
				'">+ Add alternate</button>';
			html += "</div></div>";
		});
		if (status === "review_products" || status === "extracting") {
			html +=
				'<button type="button" class="btn btn-outline-primary btn-sm" data-spec-act="confirm-products">Confirm products</button>';
		}
		html += "</div>";
		return html;
	}

	function mentionEditor(m) {
		var html = '<div class="border rounded p-2 mb-2" data-spec-mention="' + esc(m.id) + '">';
		html += '<div class="d-flex flex-wrap gap-2 align-items-center mb-2">';
		html += roleChip(m.mention_role);
		html += matchChip(m.match_status);
		if (m.configurator_key) html += '<span class="small text-muted">' + esc(m.configurator_key) + " family</span>";
		if (m.confirmed) html += '<span class="small text-success">confirmed</span>';
		html += "</div>";
		html += '<div class="row g-2">';
		html +=
			'<div class="col-md-4"><label class="form-label small mb-0">Manufacturer</label><input class="form-control form-control-sm" data-m-mfr value="' +
			esc(m.manufacturer || "") +
			'"></div>';
		html +=
			'<div class="col-md-4"><label class="form-label small mb-0">Product line</label><input class="form-control form-control-sm" data-m-line value="' +
			esc(m.product_line || "") +
			'"></div>';
		html +=
			'<div class="col-md-4"><label class="form-label small mb-0">Model</label><input class="form-control form-control-sm" data-m-model value="' +
			esc(m.model_no || "") +
			'"></div>';
		html +=
			'<div class="col-md-4"><label class="form-label small mb-0">Page / paragraph</label><input class="form-control form-control-sm" data-m-cite value="' +
			esc(m.page_cite || "") +
			'"></div>';
		html +=
			'<div class="col-md-8"><label class="form-label small mb-0">Excerpt</label><input class="form-control form-control-sm" data-m-excerpt value="' +
			esc(m.excerpt || "") +
			'"></div>';
		html +=
			'<div class="col-12"><label class="small mb-0"><input type="checkbox" class="form-check-input me-1" data-m-orequal ' +
			(m.or_equal ? "checked" : "") +
			"> or equal</label></div>";
		html += "</div></div>";
		return html;
	}

	function renderVendors(data) {
		var status = data.status;
		var ready = ["vendors_ready", "rfp_drafted", "review_products"].indexOf(status) >= 0;
		if (!ready && status !== "vendors_ready") {
			if (status === "review_products") {
				/* still show after confirm */
			} else {
				return "";
			}
		}
		if (status !== "vendors_ready" && status !== "rfp_drafted" && status !== "review_products") return "";
		var vendors = data.vendors || [];
		var html = '<div class="mb-2">';
		html += '<div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">';
		html += "<h6 class=\"mb-0\">Vendors</h6>";
		html +=
			'<button type="button" class="btn btn-outline-secondary btn-sm" data-spec-act="suggest-vendors">Suggest vendors</button>';
		html += "</div>";
		html +=
			'<p class="text-muted small">Suggestions sort the list; they do not hide other companies. Default is one RFP per vendor.</p>';
		if (!vendors.length) {
			html += '<p class="text-muted small">No vendor matches yet. Confirm products, then suggest vendors.</p>';
		} else {
			html += '<div class="table-responsive"><table class="table table-sm align-middle">';
			html += "<thead><tr><th>Ask</th><th>Company</th><th>Why</th><th>Sections</th><th>RFP</th></tr></thead><tbody>";
			vendors.forEach(function (v) {
				html += '<tr data-spec-vendor="' + esc(v.id) + '">';
				html +=
					'<td><input type="checkbox" class="form-check-input" data-v-sel ' +
					(v.selected ? "checked" : "") +
					"></td>";
				html += "<td>" + esc(v.name) + "</td>";
				html += "<td class=\"small\">" + esc((v.suggested_reason || "").replace("_", " ")) + "</td>";
				html += "<td class=\"small\">" + esc((v.sections || []).join(", ") || "—") + "</td>";
				html +=
					"<td>" +
					(v.rfp_id
						? '<a href="usis-rfp-detail.html?id=' +
						  encodeURIComponent(v.rfp_id) +
						  '">Open draft</a>'
						: "—") +
					"</td>";
				html += "</tr>";
			});
			html += "</tbody></table></div>";
		}
		html += '<div class="d-flex flex-wrap gap-2 align-items-center">';
		html +=
			'<select class="form-select form-select-sm" style="max-width:16rem" id="usis-spec-pkg-group">';
		html += '<option value="per_vendor">One RFP per vendor</option>';
		html += '<option value="per_section">One RFP per spec section</option>';
		html += "</select>";
		html +=
			'<button type="button" class="btn btn-primary btn-sm" data-spec-act="draft-rfps">Create draft RFPs</button>';
		html += "</div></div>";
		return html;
	}

	function load() {
		if (!estimateId || !Api()) return;
		Api()
			.getSpecScan(estimateId, showOut)
			.then(render)
			.catch(function (err) {
				notifyErr(err.message || err);
			});
	}

	function act(name) {
		if (!estimateId || !Api() || busy) return;
		setBusy(true);
		var p;
		if (name === "analyze") {
			p = Api().analyzeSpecScan(estimateId, {});
		} else if (name === "confirm-sections") {
			p = Api().confirmSpecSections(estimateId, collectSections());
		} else if (name === "confirm-products") {
			p = Api()
				.patchSpecMentions(estimateId, collectMentions())
				.then(function () {
					return Api().patchSpecSections(estimateId, collectSections());
				})
				.then(function () {
					return Api().confirmSpecProducts(estimateId);
				});
		} else if (name === "suggest-vendors") {
			p = Api().suggestSpecVendors(estimateId);
		} else if (name === "draft-rfps") {
			p = Api()
				.patchSpecVendors(estimateId, collectVendors())
				.then(function () {
					var grouping = (document.getElementById("usis-spec-pkg-group") || {}).value || "per_vendor";
					return Api().draftSpecRfps(estimateId, { grouping: grouping });
				});
		} else {
			setBusy(false);
			return;
		}
		p.then(function (body) {
			render(body);
			if (name === "draft-rfps") {
				var first = (body.rfps && body.rfps[0]) || (body.rfp_ids && { id: body.rfp_ids[0] });
				notifyOk("Draft RFP created. Send stays on the RFP page.");
				if (first && first.id) {
					window.location.href = "usis-rfp-detail.html?id=" + encodeURIComponent(first.id);
				}
			}
		})
			.catch(function (err) {
				notifyErr((err && err.body && err.body.error) || err.message || err);
			})
			.then(function () {
				setBusy(false);
			});
	}

	function openChat() {
		var sources = (payload && payload.sources) || {};
		var docIds = (sources.spec_files || []).map(function (f) {
			return f.id;
		});
		var trades = (payload && payload.sections ? payload.sections : []).map(function (s) {
			return s.csi_code;
		});
		if (window.aiReviewBus) {
			window.aiReviewBus.emit("review-request", {
				mode: "spec_package_review",
				estimateId: estimateId,
				projectId: projectId,
				documentIds: docIds,
				context: { trades: trades, csiAllowList: trades, sheetIndex: sources.sheet_index || [] },
			});
		}
		if (window.USIS_AI_CHAT && window.USIS_AI_CHAT.setMode) {
			window.USIS_AI_CHAT.setMode("spec_package_review");
		}
	}

	function bind() {
		var el = root();
		if (!el) return;
		el.querySelectorAll("[data-spec-act]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var name = btn.getAttribute("data-spec-act");
				if (name === "add-mention") {
					var sid = btn.getAttribute("data-section");
					if (!Api()) return;
					setBusy(true);
					Api()
						.patchSpecMentions(estimateId, [
							{
								create: true,
								section_id: sid,
								role: "listed_alternate",
								manufacturer: "",
								page_cite: "",
							},
						])
						.then(render)
						.catch(function (err) {
							notifyErr(err.message || err);
						})
						.then(function () {
							setBusy(false);
						});
					return;
				}
				act(name);
			});
		});
		var out = document.getElementById("usis-spec-pkg-out");
		if (out) {
			out.addEventListener("change", function () {
				showOut = !!out.checked;
				load();
			});
		}
		var ai = document.getElementById("usis-spec-pkg-ai");
		if (ai) ai.addEventListener("click", openChat);
	}

	function onLoaded(ev) {
		var detail = (ev && ev.detail) || {};
		var item = detail.item;
		if (detail.missingEstimate || !item) {
			estimateId = null;
			return;
		}
		estimateId = item.id || item.current_estimate_id || estimateId;
		projectId = item.project_id || (item.lead && item.lead.project_id) || projectId;
		if (estimateId) load();
	}

	document.addEventListener("usis-estimate-loaded", onLoaded);
	document.addEventListener("usis-lead-estimate-loaded", onLoaded);
	if (window.aiReviewBus && window.aiReviewBus.on) {
		window.aiReviewBus.on("review-complete", function (msg) {
			if (msg && msg.mode === "spec_package_review" && estimateId) load();
		});
	}
})();
