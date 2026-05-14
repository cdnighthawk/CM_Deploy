(function($) {
	"use strict"
  
	// tempusDominus Default Picker
	if(jQuery('#w3-td-picker-default').length > 0 ){		
		new tempusDominus.TempusDominus(document.getElementById("w3-td-picker-default"));
	}
	
	// tempusDominus Picker with Button
	if(jQuery('#w3-td-picker-button').length > 0 ){		
		new tempusDominus.TempusDominus(document.getElementById("w3-td-picker-button"));
	}
	
	// tempusDominus Picker Only Day
	if(jQuery('#w3-td-picker-day').length > 0 ){		
		new tempusDominus.TempusDominus(document.getElementById("w3-td-picker-day"),{
			display: {
				viewMode: "calendar",
				components: {
					decades: true,
					year: true,
					month: true,
					date: true,
					hours: false,
					minutes: false,
					seconds: false
				}
			}
		});
	}
	
	// tempusDominus Picker Only Time
	if(jQuery('#w3-td-picker-time').length > 0 ){
		new tempusDominus.TempusDominus(document.getElementById("w3-td-picker-time"),{
			display: {
				viewMode: "clock",
				components: {
					decades: false,
					year: false,
					month: false,
					date: false,
					hours: true,
					minutes: true,
					seconds: true
				}
			}
		});
	}
	
	// tempusDominus Picker with Custom Icons
	if(jQuery('#w3-td-picker-custom-icons').length > 0 ){
		new tempusDominus.TempusDominus(document.getElementById("w3-td-picker-custom-icons"),{
			display: {
				icons: {
					time: "fa fa-clock",
					date: "fa fa-calendar",
					up: "fa fa-arrow-up",
					down: "fa fa-arrow-down",
					previous: "fa-solid fa-chevron-left",
					next: "fa-solid fa-chevron-right",
					today: "fa fa-check",
					clear: "fa fa-trash",
					close: "fa fa-close",
				},
				buttons: {
					today: true,
					clear: true,
					close: true,
				},
			}
		});
	}
	
	// tempusDominus Picker with Localization
	if(jQuery('#w3-td-picker-localization').length > 0 ){
		new tempusDominus.TempusDominus(document.getElementById("w3-td-picker-localization"),{
			localization: {
				locale: "ru",
				startOfTheWeek: 1,
				format: "dd/MM/yyyy"
			}
		});
	}
	
	// tempusDominus Picker Inline View
	if(jQuery('#w3-td-picker-inline').length > 0 ){
		new tempusDominus.TempusDominus(document.getElementById("w3-td-picker-inline"),{
			display: {
				inline: true
			}
		});
	}
	
	// tempusDominus Picker Inline View
	if(jQuery('#w3-td-linked-startDate').length > 0 ){
		const startPicker = new tempusDominus.TempusDominus(document.getElementById("w3-td-linked-startDate"), {
			useCurrent: false,
		});
		const endPicker = new tempusDominus.TempusDominus(document.getElementById("w3-td-linked-endDate"), {
			useCurrent: false,
		});
		startPicker.subscribe(tempusDominus.Namespace.events.change, (e) => {
			endPicker.updateOptions({
				restrictions: {
					minDate: e.date,
				},
			});
		});
		endPicker.subscribe(tempusDominus.Namespace.events.change, (e) => {
			startPicker.updateOptions({
				restrictions: {
					maxDate: e.date,
				},
			});
		});
	}
	
})(jQuery);