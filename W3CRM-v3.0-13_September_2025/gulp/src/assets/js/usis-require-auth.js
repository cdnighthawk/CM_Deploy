/**

 * Redirects to Flask ``/auth/login`` when the API reports no session.

 * Set ``window.USIS_SKIP_AUTH_GUARD = true`` on a page to disable (debug only).

 */

(function () {

	"use strict";



	if (window.USIS_SKIP_AUTH_GUARD) return;

	if (location.protocol === "file:") return;



	var p = (location.pathname || "").replace(/\\/g, "/").toLowerCase();

	var authPages =

		p.indexOf("page-login") !== -1 ||

		p.indexOf("page-register") !== -1 ||

		p.indexOf("page-forgot-password") !== -1 ||

		p.indexOf("page-lock-screen") !== -1;

	if (authPages) return;



	function apiBase() {

		var raw = window.USIS_API_BASE;

		if (raw != null && String(raw).trim() !== "") {

			return String(raw).replace(/\/$/, "");

		}

		var h = window.location.hostname || "";

		var local = h === "localhost" || h === "127.0.0.1";

		if (local) {

			return (location.protocol + "//" + h + ":5000").replace(/\/$/, "");

		}

		return "http://127.0.0.1:5000";

	}



	var base = apiBase();

	var here = location.href.split("#")[0];

	var login = base + "/auth/login?next=" + encodeURIComponent(here);



	fetch(base + "/api/v1/auth/status", { credentials: "include", cache: "no-store" })

		.then(function (r) {

			return r.json();

		})

		.then(function (body) {

			if (body && body.authenticated) return;

			window.location.assign(login);

		})

		.catch(function () {

			/* offline / CORS: do not trap the user */

		});

})();

