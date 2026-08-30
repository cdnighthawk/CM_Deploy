/**
 * Run amendable first-pass AI workflows (drawing_review, takeoff).
 * Step order, prompts, and auto_complete live on the published definition.
 */
(function (global) {
	"use strict";

	if (global.USIS_AI_WORKFLOW) return;

	function fetchJson(path, opts) {
		if (global.USIS_API && typeof global.USIS_API.fetchJson === "function") {
			return global.USIS_API.fetchJson(path, opts || {});
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
			return res.text().then(function (t) {
				var data = null;
				try {
					data = t ? JSON.parse(t) : null;
				} catch (e) {
					data = t;
				}
				if (!res.ok) {
					var err = new Error((data && data.error) || t || res.statusText);
					err.status = res.status;
					err.body = data;
					throw err;
				}
				return data;
			});
		});
	}

	function automationOf(step) {
		var a = (step && (step.automation || step.Automation)) || {};
		return {
			action: a.action || "",
			mode: a.mode || "",
			prompt: a.prompt || "",
			systemHint: a.system_hint || a.systemHint || "",
			provider: a.provider || "",
			autoComplete: a.auto_complete !== false && a.autoComplete !== false,
		};
	}

	function currentStep(instance) {
		if (!instance || !instance.steps) return null;
		var key = instance.currentStepKey || instance.current_step_key;
		var ready = (instance.steps || []).filter(function (s) {
			return s.status === "ready" || s.stepKey === key || s.step_key === key;
		});
		if (ready.length) {
			return ready.sort(function (a, b) {
				return (a.sortOrder || a.sort_order || 0) - (b.sortOrder || b.sort_order || 0);
			})[0];
		}
		return null;
	}

	function renderStepper(el, instance) {
		if (!el) return;
		if (!instance || !instance.steps) {
			el.textContent = "";
			return;
		}
		el.innerHTML = (instance.steps || [])
			.map(function (s) {
				var cls =
					s.status === "complete"
						? "text-success"
						: s.status === "ready"
							? "fw-semibold text-primary"
							: s.status === "skipped"
								? "text-decoration-line-through text-muted"
								: "text-muted";
				return '<span class="' + cls + '">' + (s.label || s.stepKey) + "</span>";
			})
			.join(" → ");
	}

	function ensure(opts) {
		var o = opts || {};
		return fetchJson("/api/workflows/instances", {
			method: "POST",
			body: {
				process_key: o.processKey,
				subject_type: o.subjectType,
				subject_id: o.subjectId,
				project_id: o.projectId || null,
			},
		}).then(function (body) {
			return body && body.item ? body.item : body;
		});
	}

	function complete(instanceId, stepKey, skip) {
		return fetchJson("/api/workflows/instances/" + encodeURIComponent(instanceId) + "/complete", {
			method: "POST",
			body: { step_key: stepKey, skip: !!skip },
		}).then(function (body) {
			return body && body.item ? body.item : body;
		});
	}

	function extractReply(data) {
		if (!data) return "";
		var msg = data.message;
		if (msg && typeof msg === "object") return msg.content || "";
		if (typeof msg === "string") return msg;
		return data.reply || data.content || "";
	}

	function runAction(step, ctx) {
		var auto = automationOf(step);
		var action = auto.action || (step.requiredActions || step.required_actions || [])[0] || "";
		if (action === "capture_canvas") {
			var url = ctx.captureCanvas ? ctx.captureCanvas() : null;
			if (url && ctx.attachments) ctx.attachments.push({ kind: "file", name: "sheet.png", mime: "image/png", data: url });
			return Promise.resolve({ ok: true, skippedChat: true });
		}
		if (action === "persist_findings") {
			if (typeof ctx.persistFindings === "function") {
				return Promise.resolve(ctx.persistFindings(ctx.lastReply || "")).then(function () {
					return { ok: true, skippedChat: true };
				});
			}
			return Promise.resolve({ ok: true, skippedChat: true });
		}
		if (action === "enqueue_spec_scripts") {
			if (!ctx.estimateId) return Promise.resolve({ ok: true, skippedChat: true });
			return fetchJson("/api/v1/estimates/" + encodeURIComponent(ctx.estimateId) + "/bid-scope/enqueue", {
				method: "POST",
				body: {},
			}).then(function () {
				return { ok: true, skippedChat: true };
			});
		}
		if (action === "human_accept") {
			return Promise.resolve({ ok: true, waitForHuman: true });
		}
		if (action === "run_ai_review" || !action) {
			var prompt = auto.prompt || ctx.fallbackPrompt || "Review the current work and list leftovers for the estimator.";
			if (ctx.subjectNote) prompt += "\n\n" + ctx.subjectNote;
			var chatOpts = { mode: auto.mode || ctx.mode || "", open: true };
			if (auto.systemHint) chatOpts.system_hint = auto.systemHint;
			if (ctx.attachments && ctx.attachments.length) chatOpts.attachments = ctx.attachments.slice();
			if (global.aiReviewBus) {
				global.aiReviewBus.emit("review-request", {
					mode: chatOpts.mode,
					processKey: ctx.processKey,
					stepKey: step.stepKey || step.step_key,
				});
			}
			if (!global.USIS_AI_CHAT || typeof global.USIS_AI_CHAT.ask !== "function") {
				return Promise.reject(new Error("ChatBot is not loaded."));
			}
			return global.USIS_AI_CHAT.ask(prompt, chatOpts).then(function (data) {
				ctx.lastReply = extractReply(data);
				ctx.attachments = [];
				return { ok: true, data: data };
			});
		}
		return Promise.resolve({ ok: true, skippedChat: true });
	}

	function runUntilHuman(opts) {
		var o = opts || {};
		var ctx = {
			processKey: o.processKey,
			mode: o.mode,
			fallbackPrompt: o.fallbackPrompt,
			subjectNote: o.subjectNote || "",
			captureCanvas: o.captureCanvas,
			persistFindings: o.persistFindings,
			estimateId: o.estimateId || o.subjectId,
			attachments: [],
			lastReply: o.lastReply || "",
		};
		var stepperEl = o.stepperEl || null;
		var maxSteps = 12;

		function loop(instance, n) {
			if (!instance || instance.status === "complete") return Promise.resolve(instance);
			renderStepper(stepperEl, instance);
			var step = currentStep(instance);
			if (!step) return Promise.resolve(instance);
			var auto = automationOf(step);
			if (!auto.autoComplete || auto.action === "human_accept") {
				return Promise.resolve(instance);
			}
			if (n >= maxSteps) return Promise.resolve(instance);
			return runAction(step, ctx).then(function (result) {
				if (result && result.waitForHuman) return instance;
				return complete(instance.id, step.stepKey || step.step_key, false).then(function (next) {
					if (typeof o.onStep === "function") o.onStep(next, step, result);
					return loop(next, n + 1);
				});
			});
		}

		return ensure(o).then(function (inst) {
			return loop(inst, 0);
		});
	}

	global.USIS_AI_WORKFLOW = {
		ensure: ensure,
		complete: complete,
		currentStep: currentStep,
		automationOf: automationOf,
		renderStepper: renderStepper,
		runUntilHuman: runUntilHuman,
	};
})(typeof window !== "undefined" ? window : this);
