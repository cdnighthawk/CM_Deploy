/**
 * RFP detail — invite vendors from quotes@gousis.com and show returned quotes.
 */
(function () {
	"use strict";

	var state = {
		id: null,
		rfp: null,
		bidders: [],
		searchTimer: null,
		pendingCompany: null,
	};

	function $(id) {
		return document.getElementById(id);
	}

	function esc(s) {
		if (s == null || s === "") return "";
		var d = document.createElement("div");
		d.textContent = String(s);
		return d.innerHTML;
	}

	function fetchJson(path, opts) {
		if (window.USIS_API && typeof window.USIS_API.fetchJson === "function") {
			return window.USIS_API.fetchJson(path, opts || {});
		}
		return fetch(path, Object.assign({ credentials: "include", headers: { Accept: "application/json" } }, opts || {})).then(
			function (res) {
				return res.json().then(function (j) {
					if (!res.ok) throw new Error(j.error || res.statusText || String(res.status));
					return j;
				});
			}
		);
	}

	function flash(msg, kind) {
		var el = $("usis-rfp-flash");
		if (!el) return;
		el.className = "alert py-2 px-3 mb-3 " + (kind === "error" ? "alert-danger" : "alert-success");
		el.textContent = msg || "";
		el.classList.toggle("d-none", !msg);
	}

	function fmtWhen(iso) {
		if (!iso) return "—";
		var d = new Date(iso);
		if (isNaN(d.getTime())) return esc(iso);
		return d.toLocaleString();
	}

	function sourceLabel(src) {
		if (src === "email") return "Email";
		if (src === "portal") return "Portal";
		return "Invited";
	}

	function renderHeader(item) {
		var title = $("usis-rfp-title");
		if (title) title.textContent = item.title || "RFP";
		var status = $("usis-rfp-status");
		if (status) status.textContent = item.status || "Draft";
		var due = $("usis-rfp-due");
		if (due) due.textContent = item.due_at ? "Due " + String(item.due_at).slice(0, 10) : "No due date";
		var mailbox = $("usis-rfp-mailbox");
		if (mailbox) mailbox.textContent = item.quotes_mailbox || "quotes@gousis.com";
		var tag = $("usis-rfp-mail-tag");
		if (tag) tag.textContent = item.mail_tag ? "[RFP " + item.mail_tag + "]" : "";
	}

	function renderLines(item) {
		var tb = $("usis-rfp-lines-body");
		if (!tb) return;
		var lines = item.line_items || [];
		if (!lines.length) {
			tb.innerHTML = '<tr><td colspan="3" class="text-muted">No line items yet.</td></tr>';
			return;
		}
		tb.innerHTML = lines
			.map(function (ln) {
				return (
					"<tr><td>" +
					esc(ln.description) +
					"</td><td>" +
					esc(ln.quantity) +
					"</td><td>" +
					esc(ln.unit) +
					"</td></tr>"
				);
			})
			.join("");
	}

	function renderQuotes(item) {
		var tb = $("usis-rfp-quotes-body");
		if (!tb) return;
		var quotes = item.quotes || [];
		if (!quotes.length) {
			tb.innerHTML = '<tr><td colspan="6" class="text-muted">No invitations or quotes yet.</td></tr>';
			return;
		}
		tb.innerHTML = quotes
			.map(function (q) {
				var atts = (q.attachments || [])
					.map(function (a) {
						return esc(a.name || "attachment");
					})
					.join(", ");
				return (
					"<tr>" +
					"<td>" +
					esc(q.vendor_label) +
					"</td>" +
					"<td>" +
					esc(q.invited_email || q.from_email || "") +
					"</td>" +
					"<td>" +
					esc(sourceLabel(q.source)) +
					"</td>" +
					"<td>" +
					fmtWhen(q.sent_at) +
					"</td>" +
					"<td>" +
					fmtWhen(q.received_at) +
					"</td>" +
					"<td><div class='small'>" +
					esc(q.notes || "") +
					"</div>" +
					(atts ? "<div class='text-muted small mt-1'>" + atts + "</div>" : "") +
					"</td>" +
					"</tr>"
				);
			})
			.join("");
	}

	function renderBidders() {
		var wrap = $("usis-rfp-bidder-chips");
		if (!wrap) return;
		if (!state.bidders.length) {
			wrap.innerHTML = '<span class="text-muted small">Search the directory and add vendors to this send.</span>';
			return;
		}
		wrap.innerHTML = state.bidders
			.map(function (b, i) {
				return (
					'<span class="badge rounded-pill text-bg-light border me-1 mb-1">' +
					esc(b.label) +
					" &lt;" +
					esc(b.email) +
					"&gt; " +
					'<button type="button" class="btn btn-link btn-sm p-0 ms-1" data-remove="' +
					i +
					'" aria-label="Remove">×</button></span>'
				);
			})
			.join("");
		wrap.querySelectorAll("[data-remove]").forEach(function (btn) {
			btn.addEventListener("click", function () {
				state.bidders.splice(Number(btn.getAttribute("data-remove")), 1);
				renderBidders();
			});
		});
	}

	function addBidder(row) {
		var email = (row.email || "").trim().toLowerCase();
		if (!email) {
			flash("That company has no email on file. Add a contact email first.", "error");
			return;
		}
		var exists = state.bidders.some(function (b) {
			return b.email === email;
		});
		if (exists) return;
		state.bidders.push({
			company_id: row.company_id,
			contact_id: row.contact_id || null,
			email: email,
			label: row.label,
		});
		renderBidders();
		flash("");
	}

	function load() {
		flash("");
		return fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id)).then(function (d) {
			state.rfp = d.item || d;
			renderHeader(state.rfp);
			renderLines(state.rfp);
			renderQuotes(state.rfp);
			return state.rfp;
		});
	}

	function searchVendors(q) {
		var box = $("usis-rfp-vendor-results");
		if (!box) return;
		if (!q || q.length < 2) {
			box.innerHTML = "";
			box.classList.add("d-none");
			return;
		}
		fetchJson("/api/v1/rfi-companies?q=" + encodeURIComponent(q) + "&limit=12").then(function (d) {
			var items = d.items || [];
			if (!items.length) {
				box.innerHTML = '<div class="list-group-item text-muted small">No companies match.</div>';
				box.classList.remove("d-none");
				return;
			}
			box.innerHTML = items
				.map(function (c) {
					return (
						'<button type="button" class="list-group-item list-group-item-action py-2" data-company="' +
						esc(c.id) +
						'" data-name="' +
						esc(c.name) +
						'">' +
						esc(c.name) +
						' <span class="text-muted small">' +
						esc(c.company_type || "") +
						"</span></button>"
					);
				})
				.join("");
			box.classList.remove("d-none");
			box.querySelectorAll("[data-company]").forEach(function (btn) {
				btn.addEventListener("click", function () {
					var cid = btn.getAttribute("data-company");
					var name = btn.getAttribute("data-name") || "Vendor";
					box.classList.add("d-none");
					state.pendingCompany = { id: cid, name: name };
					fetchJson("/api/v1/companies/" + encodeURIComponent(cid) + "/contacts")
						.then(function (cd) {
							var contacts = (cd.items || []).filter(function (ct) {
								return ct.email;
							});
							if (contacts.length) {
								contacts.forEach(function (ct) {
									var label = [ct.first_name, ct.last_name].filter(Boolean).join(" ") || name;
									addBidder({
										company_id: cid,
										contact_id: ct.id,
										email: ct.email,
										label: label + " · " + name,
									});
								});
								state.pendingCompany = null;
								return;
							}
							var emailInput = $("usis-rfp-vendor-email");
							if (emailInput) {
								emailInput.placeholder = "Email for " + name;
								emailInput.focus();
							}
							flash("No contact email on file for " + name + ". Enter an address and click Add.", "error");
						})
						.catch(function (err) {
							flash(err.message || String(err), "error");
						});
				});
			});
		});
	}

	function sendInvites() {
		if (!state.bidders.length) {
			flash("Add at least one vendor with an email address.", "error");
			return;
		}
		var btn = $("usis-rfp-send");
		if (btn) btn.disabled = true;
		fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/send", {
			method: "POST",
			headers: { "Content-Type": "application/json", Accept: "application/json" },
			body: JSON.stringify({
				bidders: state.bidders.map(function (b) {
					return {
						company_id: b.company_id,
						contact_id: b.contact_id,
						email: b.email,
						vendor_label: b.label,
					};
				}),
			}),
		})
			.then(function (d) {
				var sends = d.sends || [];
				var dry = sends.some(function (s) {
					return s.dry_run;
				});
				var failed = sends.filter(function (s) {
					return !s.ok;
				});
				state.bidders = [];
				renderBidders();
				state.rfp = d.item || state.rfp;
				renderHeader(state.rfp);
				renderQuotes(state.rfp);
				if (failed.length) {
					flash("Some invitations failed: " + failed.map(function (s) { return s.error; }).join("; "), "error");
				} else if (dry) {
					flash("Invitations recorded (email dry-run — Graph is not sending yet).", "success");
				} else {
					flash("Invitations sent from quotes@gousis.com.", "success");
				}
			})
			.catch(function (err) {
				flash(err.message || String(err), "error");
			})
			.finally(function () {
				if (btn) btn.disabled = false;
			});
	}

	function syncMailbox() {
		var btn = $("usis-rfp-sync");
		if (btn) btn.disabled = true;
		fetchJson("/api/v1/rfps/mailbox/sync", { method: "POST", headers: { Accept: "application/json" } })
			.then(function (d) {
				var item = d.item || {};
				flash(
					"Synced " +
						(item.mailbox || "quotes@gousis.com") +
						": " +
						(item.updated || 0) +
						" updated, " +
						(item.created || 0) +
						" new, " +
						(item.unmatched || 0) +
						" unmatched.",
					"success"
				);
				return load();
			})
			.catch(function (err) {
				flash(err.message || String(err), "error");
			})
			.finally(function () {
				if (btn) btn.disabled = false;
			});
	}

	document.addEventListener("DOMContentLoaded", function () {
		state.id = new URLSearchParams(window.location.search).get("id");
		if (!state.id) {
			flash("Missing ?id= rfp uuid", "error");
			return;
		}
		load().catch(function (err) {
			flash(err.message || String(err), "error");
		});
		var search = $("usis-rfp-vendor-search");
		if (search) {
			search.addEventListener("input", function () {
				clearTimeout(state.searchTimer);
				state.searchTimer = setTimeout(function () {
					searchVendors(search.value.trim());
				}, 250);
			});
		}
		var addBtn = $("usis-rfp-vendor-add");
		if (addBtn) {
			addBtn.addEventListener("click", function () {
				var emailInput = $("usis-rfp-vendor-email");
				var email = emailInput ? emailInput.value.trim() : "";
				var pending = state.pendingCompany;
				if (!email) {
					flash("Enter a vendor email address.", "error");
					return;
				}
				addBidder({
					company_id: pending ? pending.id : null,
					contact_id: null,
					email: email,
					label: pending ? pending.name : email,
				});
				if (emailInput) emailInput.value = "";
				state.pendingCompany = null;
			});
		}
		var send = $("usis-rfp-send");
		if (send) send.addEventListener("click", sendInvites);
		var sync = $("usis-rfp-sync");
		if (sync) sync.addEventListener("click", syncMailbox);
		var preview = $("usis-rfp-email-preview");
		if (preview) {
			preview.addEventListener("click", function (ev) {
				ev.preventDefault();
				fetchJson("/api/v1/rfps/" + encodeURIComponent(state.id) + "/email-preview").then(function (d) {
					var body = $("usis-rfp-email-body");
					if (body) {
						body.textContent = (d.subject ? d.subject + "\n\n" : "") + (d.html || JSON.stringify(d, null, 2));
					}
					var modalEl = $("usis-rfp-email-modal");
					if (modalEl && window.bootstrap && window.bootstrap.Modal) {
						window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
					}
				});
			});
		}
	});
})();
