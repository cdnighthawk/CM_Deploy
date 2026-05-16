/**
 * Procore-parity RFI Detail page.
 *
 * Loads /api/v1/rfis/<id>, renders all panes, and wires every workflow
 * action (reply, official response, close/reopen, ball-in-court, add
 * assignee, forward, email, attachments, change history, revisions,
 * create change-event / PCO / instruction).
 */
(function () {
	"use strict";

	var U = window.USIS_RFI;

	var state = {
		rfi: null,
		users: [],
		lookupsByKind: { locations: {}, spec_sections: {}, cost_codes: {}, project_stages: {}, sub_jobs: {} },
	};

	function $(id) { return document.getElementById(id); }

	function rfiId() {
		var id = U.queryParam("id");
		return id ? id.trim() : null;
	}

	function applyStatusUi() {
		var r = state.rfi || {};
		var pill = $("usis-rfi-status-pill");
		if (pill) {
			pill.textContent = U.statusLabel(r.status).toUpperCase();
			pill.className = "usis-rfi-status-pill usis-rfi-status-" + (r.status || "draft");
		}
		var closeBtn = $("usis-rfi-btn-close");
		var reopenBtn = $("usis-rfi-btn-reopen");
		var reviseBtn = $("usis-rfi-btn-revise");
		var isClosed = r.status === "closed" || r.status === "closed_draft";
		if (closeBtn) closeBtn.classList.toggle("d-none", isClosed);
		if (reopenBtn) reopenBtn.classList.toggle("d-none", !isClosed);
		if (reviseBtn) reviseBtn.classList.toggle("d-none", !isClosed);

		var perms = r.permissions || {};
		[
			["usis-rfi-btn-reply", perms.can_reply],
			["usis-rfi-btn-add-assignee", perms.can_add_assignee],
			["usis-rfi-btn-forward", perms.can_forward],
			["usis-rfi-btn-bic", perms.can_shift_ball_in_court],
			["usis-rfi-btn-close", perms.can_close_or_reopen],
			["usis-rfi-btn-reopen", perms.can_close_or_reopen],
			["usis-rfi-btn-revise", perms.can_act_as_manager],
			["usis-rfi-btn-delete", perms.can_delete],
		].forEach(function (pair) {
			var el = $(pair[0]);
			if (!el || pair[1] === undefined) return;
			if (!pair[1]) el.setAttribute("disabled", "disabled");
			else el.removeAttribute("disabled");
		});
	}

	function lookupLabel(kind, id) {
		var map = state.lookupsByKind[kind] || {};
		return map[id] || "—";
	}

	function loadLookups(projectId) {
		var kinds = [
			["locations", "name"],
			["spec_sections", "code"],
			["cost_codes", "code"],
			["project_stages", "name"],
			["sub_jobs", "name"],
		];
		return Promise.all(kinds.map(function (k) {
			return U.loadLookup(projectId, k[0]).then(function (rows) {
				var map = {};
				rows.forEach(function (r) {
					var lbl = r[k[1]] || r.code || r.name;
					if (k[0] === "spec_sections" && r.title) lbl = r.code + " — " + r.title;
					if (k[0] === "cost_codes" && r.description) lbl = r.code + " — " + r.description;
					map[r.id] = lbl;
				});
				state.lookupsByKind[k[0]] = map;
			}).catch(function () {});
		}));
	}

	function loadUserList() {
		return U.loadUsers("").then(function (rows) {
			state.users = rows;
			var arr = rows.map(function (u) { return { id: u.id, label: u.name + " · " + (u.email || "") }; });
			fillSelect($("usis-rfi-dist-picker"), arr);
			fillSelect($("usis-rfi-forward-user"), arr, { emptyLabel: "Select user…", allowEmpty: false });
		});
	}

	function fillSelect(sel, items, opts) {
		opts = opts || {};
		if (!sel) return;
		sel.innerHTML = "";
		if (opts.allowEmpty !== false) {
			var blank = document.createElement("option");
			blank.value = "";
			blank.textContent = opts.emptyLabel || "—";
			sel.appendChild(blank);
		}
		items.forEach(function (it) {
			var opt = document.createElement("option");
			opt.value = it.id;
			opt.textContent = it.label;
			sel.appendChild(opt);
		});
	}

	function render() {
		var r = state.rfi;
		if (!r) return;
		$("usis-rfi-display-number").textContent = r.display_number || ("RFI-" + r.number);
		$("usis-rfi-subject").textContent = r.subject;
		$("usis-rfi-revision-tag").textContent = r.revision_index > 0 ? ("R" + r.revision_index) : "";
		$("usis-rfi-bic").textContent = r.ball_in_court || "—";
		$("usis-rfi-due").textContent = r.due_at ? U.fmtDate(r.due_at) : "—";
		$("usis-rfi-initiated").textContent = r.date_initiated_at ? U.fmtDate(r.date_initiated_at) : "—";
		if (r.closed_at) {
			$("usis-rfi-closed-line").classList.remove("d-none");
			$("usis-rfi-closed").textContent = U.fmtDate(r.closed_at);
		}

		$("usis-rfi-question").textContent = r.question || "—";
		$("usis-rfi-general-info").textContent = r.general_information || "—";
		$("usis-rfi-official-response").textContent = r.official_response || "— No official response yet —";

		$("usis-rfi-manager").textContent = r.rfi_manager ? r.rfi_manager.name : "—";
		$("usis-rfi-received-from").textContent = r.received_from ? r.received_from.name : "—";
		$("usis-rfi-responsible").textContent = r.responsible_contractor ? r.responsible_contractor.name : "—";
		$("usis-rfi-cost-impact").innerHTML =
			U.esc(U.impactLabel(r.cost_impact_choice)) +
			(r.cost_impact != null ? " · " + U.esc(U.fmtMoney(r.cost_impact)) : "");
		$("usis-rfi-sched-impact").innerHTML =
			U.esc(U.impactLabel(r.schedule_impact_choice)) +
			(r.schedule_impact_days != null ? " · " + U.esc(r.schedule_impact_days) + "d" : "");
		$("usis-rfi-drawing-number").textContent = r.drawing_number_text || "—";
		$("usis-rfi-location").textContent = lookupLabel("locations", r.location_id);
		$("usis-rfi-spec").textContent = lookupLabel("spec_sections", r.spec_section_id);
		$("usis-rfi-cost-code").textContent = lookupLabel("cost_codes", r.cost_code_id);
		$("usis-rfi-stage").textContent = lookupLabel("project_stages", r.project_stage_id);
		$("usis-rfi-sub-job").textContent = lookupLabel("sub_jobs", r.sub_job_id);
		$("usis-rfi-private").textContent = r.is_private ? "Yes" : "No";
		$("usis-rfi-reference").textContent = r.reference_text || "—";

		// Assignees list
		var assignees = r.assignees || [];
		var aWrap = $("usis-rfi-assignees-list");
		if (aWrap) {
			aWrap.innerHTML = assignees.length
				? assignees.map(function (a) {
					var dot = a.ball_in_court ? '<span class="usis-bic-pill">BIC</span> ' : "";
					return "<li>" + dot + U.esc(a.user ? a.user.name : "") +
						(a.is_required ? ' <small class="text-muted">(required)</small>' : "") +
						(a.responded_at ? ' <small class="text-success">replied</small>' : "") +
						"</li>";
				}).join("")
				: '<li class="text-muted">—</li>';
		}

		// Custom fields
		var cfWrap = $("usis-rfi-custom-fields-list");
		if (cfWrap) {
			var cfList = (r.custom_fields || []).filter(function (f) {
				return f.value_text != null || f.value_number != null || f.value_date || f.value_bool != null;
			});
			cfWrap.innerHTML = cfList.length
				? cfList.map(function (f) {
					var v = f.value_text != null ? f.value_text :
						f.value_number != null ? f.value_number :
						f.value_date ? U.fmtDate(f.value_date) :
						f.value_bool != null ? (f.value_bool ? "Yes" : "No") : "";
					return '<dt class="col-sm-5 text-muted">' + U.esc(f.label || f.key) + "</dt>" +
						'<dd class="col-sm-7">' + U.esc(v) + "</dd>";
				}).join("")
				: '<dt class="col-12 text-muted">No custom fields set.</dt>';
		}

		renderReplies();
		renderDistribution();
		renderAttachments();
		renderAudit();
		renderRevisions();
		renderRelated();
		applyStatusUi();
	}

	function renderReplies() {
		var r = state.rfi;
		var wrap = $("usis-rfi-replies-list");
		var cnt = $("usis-rfi-replies-count");
		if (!wrap) return;
		var replies = r.replies || [];
		if (cnt) cnt.textContent = replies.length;
		if (!replies.length) {
			wrap.innerHTML = '<div class="text-muted small">No replies yet. Click "Reply" to start the thread.</div>';
			return;
		}
		wrap.innerHTML = replies.map(function (rep) {
			var canMark = (state.rfi.permissions || {}).can_mark_official;
			var actions = [];
			if (canMark && !rep.is_official) {
				actions.push('<button type="button" class="btn btn-sm btn-outline-success" data-act="mark-official" data-id="' + U.escAttr(rep.id) + '">Mark Official</button>');
			}
			actions.push('<button type="button" class="btn btn-sm btn-outline-danger" data-act="delete-reply" data-id="' + U.escAttr(rep.id) + '">Delete</button>');
			return '<div class="usis-rfi-reply' + (rep.is_official ? " is-official" : "") + '">' +
				'<div class="meta d-flex justify-content-between align-items-center">' +
				'<span>' + U.esc(rep.author ? rep.author.name : "Unknown") + ' · ' + U.esc(U.fmtDateTime(rep.created_at)) +
				(rep.is_official ? ' · <strong class="text-success">Official Response</strong>' : "") +
				'</span>' +
				'<span>' + actions.join(" ") + '</span>' +
				'</div>' +
				'<div class="body mt-2">' + U.esc(rep.body) + '</div>' +
			'</div>';
		}).join("");
		Array.prototype.forEach.call(wrap.querySelectorAll("[data-act]"), function (btn) {
			btn.addEventListener("click", function () {
				var act = btn.dataset.act, rid = btn.dataset.id;
				if (act === "mark-official") markOfficial(rid);
				else if (act === "delete-reply") deleteReply(rid);
			});
		});
	}

	function renderDistribution() {
		var r = state.rfi;
		var wrap = $("usis-rfi-dist-list");
		if (!wrap) return;
		var list = r.distribution || [];
		wrap.innerHTML = list.length
			? list.map(function (d) {
				return '<li class="list-group-item d-flex justify-content-between align-items-center">' +
					U.esc(d.user ? d.user.name : "") +
					'<button type="button" class="btn btn-sm btn-outline-danger" data-rm-uid="' + U.escAttr(d.user.id) + '">Remove</button>' +
				'</li>';
			}).join("")
			: '<li class="list-group-item text-muted">No distribution members.</li>';
		Array.prototype.forEach.call(wrap.querySelectorAll("[data-rm-uid]"), function (btn) {
			btn.addEventListener("click", function () {
				var uid = btn.dataset.rmUid;
				U.fetchJson(
					"/api/v1/rfis/" + encodeURIComponent(state.rfi.id) + "/distribution/" + encodeURIComponent(uid),
					{ method: "DELETE" }
				).then(refresh).catch(function (err) { alert(err.message || String(err)); });
			});
		});
	}

	function renderAttachments() {
		var r = state.rfi;
		var wrap = $("usis-rfi-attach-list");
		var cnt = $("usis-rfi-attach-count");
		if (!wrap) return;
		var list = r.attachments || [];
		if (cnt) cnt.textContent = list.length;
		wrap.innerHTML = list.length
			? list.map(function (a) {
				var name = a.title || a.filename || a.file_url || "Attachment";
				var link = a.file_url ? ' <a href="' + U.escAttr(a.file_url) + '" target="_blank" rel="noopener">Open</a>' : "";
				return '<li class="list-group-item d-flex justify-content-between align-items-center">' +
					'<div>' + U.esc(name) + link +
					(a.file_size_bytes ? ' <small class="text-muted">(' + Math.round(a.file_size_bytes / 1024) + ' KB)</small>' : "") +
					'</div>' +
					'<button type="button" class="btn btn-sm btn-outline-danger" data-rm-doc="' + U.escAttr(a.id) + '">Remove</button>' +
				'</li>';
			}).join("")
			: '<li class="list-group-item text-muted">No attachments yet.</li>';
		Array.prototype.forEach.call(wrap.querySelectorAll("[data-rm-doc]"), function (btn) {
			btn.addEventListener("click", function () {
				var did = btn.dataset.rmDoc;
				U.fetchJson(
					"/api/v1/rfis/" + encodeURIComponent(state.rfi.id) + "/attachments/" + encodeURIComponent(did),
					{ method: "DELETE" }
				).then(refresh).catch(function (err) { alert(err.message || String(err)); });
			});
		});
	}

	function renderAudit() {
		var r = state.rfi;
		var wrap = $("usis-rfi-audit-list");
		if (!wrap) return;
		var list = r.audit || [];
		wrap.innerHTML = list.length
			? list.map(function (a) {
				return "<li>" +
					'<strong>' + U.esc(a.action) + '</strong> · ' +
					U.esc(a.actor ? a.actor.name : "system") +
					' · <span class="text-muted">' + U.esc(U.fmtDateTime(a.created_at)) + "</span>" +
					(a.summary ? '<div class="text-muted">' + U.esc(a.summary) + "</div>" : "") +
					"</li>";
			}).join("")
			: '<li class="text-muted">No audit entries yet.</li>';
	}

	function renderRevisions() {
		var r = state.rfi;
		var wrap = $("usis-rfi-revisions-list");
		if (!wrap) return;
		var list = r.revisions || [];
		wrap.innerHTML = list.length
			? list.map(function (v) {
				return "<li>R" + v.revision_index + " · " + U.esc(U.fmtDateTime(v.created_at)) +
					(v.reason ? ' · <span class="text-muted">' + U.esc(v.reason) + "</span>" : "") +
					"</li>";
			}).join("")
			: '<li class="text-muted">No revisions yet.</li>';
	}

	function renderRelated() {
		var r = state.rfi;
		var wrap = $("usis-rfi-related-list");
		var cnt = $("usis-rfi-related-count");
		if (!wrap) return;
		// Each cross-tool create writes a discriminated audit entry; the
		// ``_related_kind`` marker lives in the after-payload (the action
		// column is enum-constrained).
		var labels = {
			change_event: { label: "Change Event", icon: "fa-coins" },
			pco: { label: "Potential Change Order", icon: "fa-file-invoice-dollar" },
			instruction: { label: "Instruction", icon: "fa-clipboard-list" },
		};
		var list = (r.audit || []).filter(function (a) {
			var kind = (a.after || {})._related_kind;
			return kind && labels.hasOwnProperty(kind);
		});
		if (cnt) cnt.textContent = list.length;
		wrap.innerHTML = list.length
			? list.map(function (a) {
				var after = a.after || {};
				var meta = labels[after._related_kind];
				var title = after.title || "(no title)";
				return '<li class="list-group-item">' +
					'<i class="fa ' + meta.icon + ' me-2 text-muted"></i>' +
					'<strong>' + U.esc(meta.label) + '</strong> · ' + U.esc(title) +
					' <span class="text-muted small">— ' + U.esc(U.fmtDateTime(a.created_at)) + '</span>' +
				'</li>';
			}).join("")
			: '<li class="list-group-item text-muted">No related items yet. Use the Create dropdown to spawn a Change Event, PCO, or Instruction from this RFI.</li>';
	}

	function refresh() {
		var id = rfiId();
		if (!id) return Promise.resolve();
		return U.getRfi(id).then(function (data) {
			state.rfi = data.item;
			if (state.rfi && state.rfi.project_id) {
				return loadLookups(state.rfi.project_id).then(render);
			}
			render();
		}).catch(function (err) {
			U.flashError($("usis-rfi-detail-error"), err.message || String(err));
		});
	}

	// -------- Actions ------------------------------------------------------

	function notifyEmailResult(data) {
		var N = window.USISNotify;
		if (!N) return;
		if (data.errors && data.errors.length) {
			N.error("Some messages failed: " + data.errors.join("; "));
			return;
		}
		if (data.dry_run) {
			N.warning(
				"SMTP is not configured (MAIL_SERVER, MAIL_USERNAME, MAIL_FROM). " +
					"Message logged only — set MAIL_* on Render to deliver email."
			);
			return;
		}
		if (data.queued) {
			N.info("Email queued for delivery.");
			return;
		}
		var n = data.recipients || data.sent || 1;
		N.success("Email sent to " + n + " recipient(s).");
	}

	function postAction(suffix, body) {
		return U.fetchJson(
			"/api/v1/rfis/" + encodeURIComponent(state.rfi.id) + suffix,
			{ method: "POST", body: body || {} }
		).then(function (data) {
			if (suffix === "/email") notifyEmailResult(data || {});
			return refresh();
		}).catch(function (err) { alert(err.message || String(err)); });
	}

	function markOfficial(replyId) {
		return postAction("/official-response", { reply_id: replyId });
	}

	function deleteReply(replyId) {
		if (!confirm("Delete this reply?")) return;
		return U.fetchJson(
			"/api/v1/rfis/" + encodeURIComponent(state.rfi.id) + "/replies/" + encodeURIComponent(replyId),
			{ method: "DELETE" }
		).then(refresh).catch(function (err) { alert(err.message || String(err)); });
	}

	function wireActionButtons() {
		var rep = $("usis-rfi-reply-submit");
		if (rep) rep.addEventListener("click", function () {
			var body = ($("usis-rfi-reply-body").value || "").trim();
			if (!body) return;
			postAction("/replies", { body: body }).then(function () {
				$("usis-rfi-reply-body").value = "";
				if (window.bootstrap) bootstrap.Modal.getInstance($("usis-rfi-reply-modal")).hide();
			});
		});

		var close = $("usis-rfi-btn-close");
		if (close) close.addEventListener("click", function () { if (confirm("Close RFI?")) postAction("/close"); });
		var reopen = $("usis-rfi-btn-reopen");
		if (reopen) reopen.addEventListener("click", function () { postAction("/reopen"); });
		var del = $("usis-rfi-btn-delete");
		if (del) del.addEventListener("click", function () { if (confirm("Move to Recycle Bin?")) postAction(""); /* DELETE handled separately */ });
		if (del) del.addEventListener("click", function () {
			// override with proper DELETE
			U.deleteRfi(state.rfi.id).then(function () {
				alert("Moved to Recycle Bin.");
				window.location.href = "construction/rfis.html";
			}).catch(function (err) { alert(err.message || String(err)); });
		}, { once: false });

		var revise = $("usis-rfi-btn-revise");
		if (revise) revise.addEventListener("click", function () {
			var reason = window.prompt("Reason for revision?");
			if (reason === null) return;
			postAction("/revise", { reason: reason || "" });
		});

		var bicBtn = $("usis-rfi-btn-bic");
		if (bicBtn) bicBtn.addEventListener("click", function () {
			var uid = window.prompt("Shift Ball-in-Court to user UUID? Leave blank to give it to the Manager:");
			if (uid === null) return;
			postAction("/ball-in-court", uid ? { user_id: uid.trim() } : {});
		});

		var addA = $("usis-rfi-btn-add-assignee");
		if (addA) addA.addEventListener("click", function () {
			var uid = window.prompt("User UUID to add as assignee:");
			if (!uid) return;
			postAction("/assignees", { user_id: uid.trim(), is_required: false });
		});

		var fwdSubmit = $("usis-rfi-forward-submit");
		if (fwdSubmit) fwdSubmit.addEventListener("click", function () {
			var uid = $("usis-rfi-forward-user").value;
			var msg = $("usis-rfi-forward-msg").value;
			if (!uid) return;
			postAction("/forward-for-review", { user_id: uid, message: msg }).then(function () {
				if (window.bootstrap) bootstrap.Modal.getInstance($("usis-rfi-forward-modal")).hide();
			});
		});

		var emailSend = $("usis-rfi-email-send");
		if (emailSend) emailSend.addEventListener("click", function () {
			var to = $("usis-rfi-email-to").value.trim();
			if (!to) {
				if (window.USISNotify) USISNotify.error("Enter at least one recipient in To.");
				else alert("Enter at least one recipient in To.");
				return;
			}
			emailSend.disabled = true;
			postAction("/email", {
				to: to,
				cc: $("usis-rfi-email-cc").value.trim(),
				subject: $("usis-rfi-email-subject").value.trim(),
				message: $("usis-rfi-email-body").value,
			}).then(function () {
				if (window.bootstrap) bootstrap.Modal.getInstance($("usis-rfi-email-modal")).hide();
			}).finally(function () {
				emailSend.disabled = false;
			});
		});

		Array.prototype.forEach.call(document.querySelectorAll("[data-create]"), function (a) {
			a.addEventListener("click", function () {
				var kind = a.dataset.create;
				var path = {
					"change-event": "/create-change-event",
					"pco": "/create-pco",
					"instruction": "/create-instruction",
				}[kind];
				if (!path) return;
				postAction(path, {}).then(function () { alert((kind === "pco" ? "Potential Change Order" : kind) + " stub created. See change history."); });
			});
		});

		var addDist = $("usis-rfi-dist-add");
		if (addDist) addDist.addEventListener("click", function () {
			var uid = $("usis-rfi-dist-picker").value;
			if (!uid) return;
			postAction("/distribution", { user_id: uid });
		});

		var attachAdd = $("usis-rfi-attach-add");
		if (attachAdd) attachAdd.addEventListener("click", function () {
			var url = $("usis-rfi-attach-url").value.trim();
			var title = $("usis-rfi-attach-title").value.trim();
			if (!url) return;
			postAction("/attachments", { file_url: url, title: title }).then(function () {
				$("usis-rfi-attach-url").value = "";
				$("usis-rfi-attach-title").value = "";
			});
		});

		var drop = $("usis-rfi-attach-drop");
		var fileInput = $("usis-rfi-attach-file");
		if (drop && fileInput) {
			var queue = function (files) {
				Array.from(files || []).forEach(function (f) {
					postAction("/attachments", {
						file_url: "pending-upload://" + f.name,
						title: f.name,
						filename: f.name,
						mime_type: f.type || null,
						file_size_bytes: f.size,
					});
				});
			};
			fileInput.addEventListener("change", function () { queue(fileInput.files); fileInput.value = ""; });
			drop.addEventListener("click", function () { fileInput.click(); });
			drop.addEventListener("keydown", function (e) {
				if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
			});
			["dragenter", "dragover"].forEach(function (evt) {
				drop.addEventListener(evt, function (e) {
					e.preventDefault(); e.stopPropagation();
					drop.style.background = "#e7f5ff";
					drop.style.borderColor = "#1c7ed6";
				});
			});
			["dragleave", "drop"].forEach(function (evt) {
				drop.addEventListener(evt, function (e) {
					e.preventDefault(); e.stopPropagation();
					drop.style.background = "#f8f9fa";
					drop.style.borderColor = "#adb5bd";
				});
			});
			drop.addEventListener("drop", function (e) {
				var files = (e.dataTransfer && e.dataTransfer.files) || [];
				if (files.length) queue(files);
			});
		}
	}

	function init() {
		var id = rfiId();
		if (!id) {
			U.flashError($("usis-rfi-detail-error"), "Missing ?id= in URL.");
			return;
		}
		loadUserList();
		wireActionButtons();
		refresh();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
