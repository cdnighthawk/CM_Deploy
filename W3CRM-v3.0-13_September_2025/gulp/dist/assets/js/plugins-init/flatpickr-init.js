(function ($) {
    "use strict"
	
	if(jQuery('#defaultFlatpickr').length > 0 ){
		$("#defaultFlatpickr").flatpickr();
	}
	
	if(jQuery('#dateTimeFlatpickr').length > 0 ){
		$("#dateTimeFlatpickr").flatpickr({
			enableTime: true,
			dateFormat: "Y-m-d H:i",	
		});
	}
	
	if(jQuery('#timeFlatpickr').length > 0 ){
		$("#timeFlatpickr").flatpickr({
			enableTime: true,
			noCalendar: true,
			dateFormat: "H:i",
		});
	}
	
	if(jQuery('#localeFlatpickr').length > 0 ){
		$("#localeFlatpickr").flatpickr({
			enableTime: true,
			dateFormat: "Y-m-d H:i",	
			locale: "ru"
		});
	}
	
	if(jQuery('#weekNumbersFlatpickr').length > 0 ){
		$("#weekNumbersFlatpickr").flatpickr({
			weekNumbers: true,
		});
	}
	
	if(jQuery('#rangeCalendarFlatpickr').length > 0 ){
		$("#rangeCalendarFlatpickr").flatpickr({
			mode: "range",
		});
	}
	
	if(jQuery('#multipleDatesFlatpickr').length > 0 ){
		$("#multipleDatesFlatpickr").flatpickr({
			mode: "multiple",
			dateFormat: "Y-m-d"
		});
	}
	
})(jQuery);