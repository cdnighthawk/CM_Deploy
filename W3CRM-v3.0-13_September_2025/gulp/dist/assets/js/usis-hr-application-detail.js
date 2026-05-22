(function () {
	"use strict";

	var state = { detail: null, userId: "" };

	function apiBase() {
		if (typeof window.usisApiBase === "function") return window.usisApiBase();
		if (typeof window.USIS_API_BASE === "string" && window.USIS_API_BASE.trim()) {
			return window.USIS_API_BASE.trim().replace(/\/$/, "");
		}
		var loc = window.location;
		if (loc.protocol === "file:") return "http://127.0.0.1:5000";
		var host = loc.hostname || "";
		var proto = loc.protocol || "http:";
		if (host === "localhost" || host === "127.0.0.1") return (proto + "//" + host + ":5000").replace(/\/$/, "");
		return "";
	}

	function esc(s) {
		if (s == null) return "";
		return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
	}

	function userIdFromQuery() {
		var id = new URLSearchParams(window.location.search).get("id");
		return id && String(id).trim() ? String(id).trim() : "";
	}

	function setStatus(msg, isErr) {
		var el = document.getElementById("usis-hr-appd-status");
		if (!el) return;
		el.textContent = msg || "";
		el.classList.toggle("text-danger", !!isErr);
	}

	function showErr(msg) {
		var el = document.getElementById("usis-hr-appd-err");
		if (!el) return;
		if (msg) {
			el.textContent = msg;
			el.classList.remove("d-none");
		} else {
			el.classList.add("d-none");
		}
	}

	function statusBadgeClass(status) {
		var s = status || "in_progress";
		if (s === "submitted") return "bg-primary";
		if (s === "under_review") return "bg-info text-dark";
		if (s === "hired") return "bg-success";
		if (s === "rejected") return "bg-danger";
		return "bg-secondary";
	}

	function patchStatus(body) {
		return fetch(apiBase() + "/api/v1/hr/applications/" + encodeURIComponent(state.userId) + "/status", {
			method: "PATCH",
			credentials: "include",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify(body),
		}).then(function (r) {
			return r.json().then(function (data) {
				if (!r.ok) throw new Error(data.error || "Request failed");
				return data;
			});
		});
	}

	function runDeleteApplicant(displayName) {
		var del = window.USISHrApplicantDelete;
		if (!del) {
			showErr("Delete helper not loaded.");
			return;
		}
		var reason = del.confirmDeleteApplicant(displayName);
		if (!reason) return;
		del.deleteApplicantAccount(state.userId, reason)
			.then(function () {
				if (window.USISNotify) window.USISNotify.success("Applicant account deleted.");
				window.location.href = "usis-hr-applications.html";
			})
			.catch(function (e) {
				showErr(e.message || String(e));
			});
	}

	function updateDeleteButtons(d) {
		var caps = (d && d.capabilities) || {};
		var name = (d && d.user && (d.user.name || d.user.email)) || "";
		var show = !!caps.can_delete_applicant;
		var header = document.getElementById("usis-hr-appd-delete-header");
		if (header) {
			header.classList.toggle("d-none", !show);
			if (show && !header._wired) {
				header._wired = true;
				header.addEventListener("click", function () {
					runDeleteApplicant(name);
				});
			}
		}
	}

	function renderDocThumbs(container, docs) {
		if (!container) return;
		if (!docs || !docs.length) {
			container.innerHTML = '<p class="text-muted small mb-0">No photos uploaded.</p>';
			return;
		}
		container.innerHTML =
			'<div class="d-flex flex-wrap gap-2">' +
			docs
				.map(function (d) {
					var url = d.staff_file_url || d.file_url;
					if (url && url.indexOf("http") !== 0) url = apiBase() + url;
					return (
						'<a href="' +
						esc(url) +
						'" target="_blank" rel="noopener" class="d-block border rounded overflow-hidden" style="width:120px;height:120px;">' +
						'<img src="' +
						esc(url) +
						'" alt="" class="w-100 h-100 object-fit-cover">' +
						"</a>"
					);
				})
				.join("") +
			"</div>";
	}

	function renderApplication(payload) {
		var dl = document.getElementById("usis-hr-appd-application-dl");
		if (!dl) return;
		payload = payload || {};
		var fields = [
			["Position", payload.position_applying_for],
			["Preferred start", payload.preferred_start_date],
			["Address", payload.address_line1],
			["City", payload.city],
			["State", payload.state],
			["Postal code", payload.postal_code],
			["Emergency contact", payload.emergency_contact_name],
			["Emergency phone", payload.emergency_contact_phone],
			["Prior employment", payload.prior_employer_summary],
		];
		dl.innerHTML = fields
			.map(function (pair) {
				return (
					'<dt class="col-sm-4 text-muted">' +
					esc(pair[0]) +
					'</dt><dd class="col-sm-8 mb-2">' +
					esc(pair[1] || "—") +
					"</dd>"
				);
			})
			.join("");
	}

	function renderActions(d) {
		var root = document.getElementById("usis-hr-appd-actions");
		if (!root) return;
		var review = d.review || {};
		var caps = d.capabilities || {};
		var status = review.hire_status || "in_progress";
		var html = "";
		if (status === "submitted" || status === "under_review") {
			if (status === "submitted") {
				html +=
					'<button type="button" class="btn btn-outline-info btn-sm" id="usis-hr-appd-under-review">Mark under review</button>';
			}
			html +=
				'<button type="button" class="btn btn-success btn-sm" id="usis-hr-appd-hire-open">Approve / hire</button>' +
				'<button type="button" class="btn btn-outline-danger btn-sm" id="usis-hr-appd-reject-open">Reject</button>';
		}
		if (caps.can_delete_applicant) {
			html +=
				'<button type="button" class="btn btn-outline-danger btn-sm" id="usis-hr-appd-delete">Delete applicant account</button>';
		} else if (status === "hired") {
			html +=
				'<p class="text-muted small mb-0">This applicant was hired and is now a staff account. To remove the user, use <a href="usis-user-directory.html">User admin</a>.</p>';
		}
		if (!html) {
			html = '<p class="text-muted small mb-0">No review actions for this status.</p>';
		}
		root.innerHTML = html;

		var under = document.getElementById("usis-hr-appd-under-review");
		if (under) {
			under.addEventListener("click", function () {
				patchStatus({ status: "under_review" })
					.then(function () {
						if (window.USISNotify) window.USISNotify.success("Marked under review.");
						loadDetail();
					})
					.catch(function (e) {
						showErr(e.message || String(e));
					});
			});
		}
		var hireOpen = document.getElementById("usis-hr-appd-hire-open");
		if (hireOpen && typeof bootstrap !== "undefined") {
			hireOpen.addEventListener("click", function () {
				var modalEl = document.getElementById("usis-hr-appd-hire-modal");
				if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show();
			});
		}
		var rejectOpen = document.getElementById("usis-hr-appd-reject-open");
		if (rejectOpen && typeof bootstrap !== "undefined") {
			rejectOpen.addEventListener("click", function () {
				var modalEl = document.getElementById("usis-hr-appd-reject-modal");
				if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show();
			});
		}
		var del = document.getElementById("usis-hr-appd-delete");
		if (del) {
			del.addEventListener("click", function () {
				var nameEl = document.getElementById("usis-hr-appd-name");
				runDeleteApplicant(nameEl ? nameEl.textContent : "");
			});
		}
	}

	function renderHireRoles(roles) {
		var root = document.getElementById("usis-hr-appd-hire-roles");
		if (!root) return;
		root.innerHTML = (roles || [])
			.map(function (r) {
				return (
					'<div class="form-check">' +
					'<input class="form-check-input usis-hr-appd-role-cb" type="checkbox" value="' +
					esc(r.id) +
					'" id="usis-hr-appd-role-' +
					esc(r.id) +
					'">' +
					'<label class="form-check-label small" for="usis-hr-appd-role-' +
					esc(r.id) +
					'"><code>' +
					esc(r.code) +
					"</code> — " +
					esc(r.name) +
					"</label></div>"
				);
			})
			.join("");
	}

	function renderDetail(d) {
		state.detail = d;
		var u = d.user || {};
		var review = d.review || {};
		document.getElementById("usis-hr-appd-name").textContent =
			[u.first_name, u.last_name].filter(Boolean).join(" ").trim() || u.email || "Applicant";
		document.getElementById("usis-hr-appd-email").textContent = u.email || "—";
		var badge = document.getElementById("usis-hr-appd-status-badge");
		if (badge) {
			badge.textContent = (review.hire_status || "in_progress").replace(/_/g, " ");
			badge.className = "badge " + statusBadgeClass(review.hire_status);
		}
		var notes = document.getElementById("usis-hr-appd-review-notes");
		if (notes) {
			notes.textContent = review.review_notes
				? "HR notes: " + review.review_notes
				: "No review notes yet.";
		}
		renderApplication((d.application && d.application.payload) || {});
		if (window.USISHrI9 && d.i9 && d.i9.draft) {
			window.USISHrI9.renderForm(document.getElementById("usis-hr-appd-i9-form"), d.i9.draft, { locked: true });
		}
		if (window.USISHrW4 && d.w4 && d.w4.draft) {
			window.USISHrW4.renderForm(document.getElementById("usis-hr-appd-w4-form"), d.w4.draft, { locked: true });
		}
		var union = d.union_documents || {};
		if (window.USISHrUnionDocs) {
			var unionList = (union.union_card || []).concat(union.union_dispatch || []);
			unionList.forEach(function (doc) {
				if (doc.staff_file_url) doc.file_url = doc.staff_file_url;
			});
			window.USISHrUnionDocs.wire(document.getElementById("usis-hr-appd-tab-union"), {
				locked: true,
				apiBase: apiBase,
				documents: unionList,
			});
		}
		renderDocThumbs(document.getElementById("usis-hr-appd-i9-docs"), d.i9 && d.i9.documents);
		renderDocThumbs(document.getElementById("usis-hr-appd-w4-docs"), d.w4 && d.w4.documents);
		renderHireRoles(d.staff_roles || []);
		renderActions(d);
		updateDeleteButtons(d);
		document.getElementById("usis-hr-appd-content").classList.remove("d-none");
		setStatus("");
	}

	function loadDetail() {
		state.userId = userIdFromQuery();
		if (!state.userId) {
			setStatus("Missing applicant id in URL (?id=).", true);
			return;
		}
		setStatus("Loading…");
		showErr("");
		fetch(apiBase() + "/api/v1/hr/applications/" + encodeURIComponent(state.userId), {
			credentials: "include",
			headers: { Accept: "application/json" },
		})
			.then(function (r) {
				return r.json().then(function (data) {
					return { ok: r.ok, data: data };
				});
			})
			.then(function (res) {
				if (!res.ok) throw new Error((res.data && res.data.error) || "Load failed");
				renderDetail(res.data);
			})
			.catch(function (err) {
				setStatus("Could not load application: " + (err.message || err), true);
			});
	}

	function wireModals() {
		var hireBtn = document.getElementById("usis-hr-appd-hire-confirm");
		if (hireBtn) {
			hireBtn.addEventListener("click", function () {
				var roleIds = [];
				document.querySelectorAll(".usis-hr-appd-role-cb:checked").forEach(function (cb) {
					roleIds.push(cb.value);
				});
				if (!roleIds.length) {
					showErr("Select at least one staff role.");
					return;
				}
				var notesEl = document.getElementById("usis-hr-appd-hire-notes");
				patchStatus({
					status: "hired",
					role_ids: roleIds,
					review_notes: notesEl ? notesEl.value : "",
				})
					.then(function () {
						if (typeof bootstrap !== "undefined") {
							var modalEl = document.getElementById("usis-hr-appd-hire-modal");
							if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide();
						}
						if (window.USISNotify) window.USISNotify.success("Applicant hired.");
						loadDetail();
					})
					.catch(function (e) {
						showErr(e.message || String(e));
					});
			});
		}
		var rejectBtn = document.getElementById("usis-hr-appd-reject-confirm");
		if (rejectBtn) {
			rejectBtn.addEventListener("click", function () {
				var notesEl = document.getElementById("usis-hr-appd-reject-notes");
				var notes = notesEl ? String(notesEl.value || "").trim() : "";
				if (!notes) {
					showErr("Rejection reason is required.");
					return;
				}
				patchStatus({ status: "rejected", review_notes: notes })
					.then(function () {
						if (typeof bootstrap !== "undefined") {
							var modalEl = document.getElementById("usis-hr-appd-reject-modal");
							if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide();
						}
						if (window.USISNotify) window.USISNotify.success("Application rejected.");
						loadDetail();
					})
					.catch(function (e) {
						showErr(e.message || String(e));
					});
			});
		}
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", function () {
			wireModals();
			loadDetail();
		});
	} else {
		wireModals();
		loadDetail();
	}
})();
