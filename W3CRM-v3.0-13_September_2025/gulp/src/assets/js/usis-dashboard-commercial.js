/**
 * USIS Dark Dashboard — month-default chart periods (commercial layout).
 * Chart series labels are set in dashboard.js when #usis-dashboard-dark-page exists.
 */
(function () {
	"use strict";

	function isCommercialDash() {
		return !!document.getElementById("usis-dashboard-dark-page");
	}

	if (typeof jQuery !== "undefined") {
		jQuery(document).ready(function () {
			if (!isCommercialDash()) return;
			setTimeout(function () {
				jQuery("#pills-month-tab").trigger("click");
				jQuery("#pills-month-tab1").trigger("click");
			}, 2000);
		});
	}
})();
