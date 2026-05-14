var aikit = function(){
	"use strict"

	var multiplierSlider = function(){
		if($('#multiplierSlider').length > 0){
			var slider = document.getElementById('multiplierSlider');
			
			noUiSlider.create(slider, {
				start: [20],
				behaviour: 'snap',
				connect: [true, false],
				range: {
					'min': 0,
					'max': 100
				},
			});
		}
	}
	
	var multiplierSlider2 = function(){
		if($('#multiplierSlider2').length > 0){
			var slider = document.getElementById('multiplierSlider2');

			noUiSlider.create(slider, {
				start: [20],
				behaviour: 'snap',
				connect: [true, false],
				range: {
					'min': 0,
					'max': 100
				}
			});
		}
	}
	
	var multiplierSlider3 = function(){
		if($('#multiplierSlider3').length > 0){
			var slider = document.getElementById('multiplierSlider3');

			noUiSlider.create(slider, {
				start: [20],
				behaviour: 'snap',
				connect: [true, false],
				range: {
					'min': 0,
					'max': 100
				}
			});
		}
	}
	
	var multiplierSlider4 = function(){
		if($('#multiplierSlider4').length > 0){
			var slider = document.getElementById('multiplierSlider4');

			noUiSlider.create(slider, {
				start: [20],
				behaviour: 'snap',
				connect: [true, false],
				range: {
					'min': 0,
					'max': 100
				}
			});
		}
	}
	
	var multiplierSlider5 = function(){
		if($('#multiplierSlider5').length > 0){
			var slider = document.getElementById('multiplierSlider5');

			noUiSlider.create(slider, {
				start: [20],
				behaviour: 'snap',
				connect: [true, false],
				range: {
					'min': 0,
					'max': 100
				}
			});
		}
	}
	
	var chatbotSlider = function(){
		if($('#chatbotSlider').length > 0){
			var slider = document.getElementById('chatbotSlider');

			noUiSlider.create(slider, {
				start: [20],
				behaviour: 'snap',
				connect: [true, false],
				
				range: {
					'min': 0,
					'max': 100
				}
			});
		}
	}
	
	var complexColorpicker = function(){
		if($('.complex-colorpicker').length > 0){
			$(".complex-colorpicker").asColorPicker({
				mode: 'complex'
			});
		}
	}

	var aikitSchedulerTable = function(){		
		if(jQuery('#aikitSchedulerTable').length > 0){
			var empoloyeesTable = $('#aikitSchedulerTable').DataTable({
				dom: 'frtip',
				buttons: false,
				searching: false,
				select: false,
				lengthChange:false,
				language: {
					paginate: {
						next: '<i class="fa-solid fa-angle-right"></i>',
						previous: '<i class="fa-solid fa-angle-left"></i>' 
					}
				},
			});
		}
	}
	
	var aikitJobTable = function(){		
		if(jQuery('#aikitJobTable').length > 0){
			var empoloyeesTable = $('#aikitJobTable').DataTable({
				dom: 'frtip',
				buttons: false,
				searching: false,
				select: false,
				lengthChange:false ,
				language: {
					paginate: {
						next: '<i class="fa-solid fa-angle-right"></i>',
						previous: '<i class="fa-solid fa-angle-left"></i>' 
					}
				},
			});
		}
	}
	
	/* Function ============ */
	return {
		init:function(){
			multiplierSlider();
			multiplierSlider2();
			multiplierSlider3();
			multiplierSlider4();
			multiplierSlider5();
			chatbotSlider();
			complexColorpicker();
			aikitSchedulerTable();
			aikitJobTable();
		},
		
		load:function(){
			
		},
		
		resize:function(){
			
		},
	}
	
}();

/* Document.ready Start */	
jQuery(document).ready(function() {
	aikit.init();
});
/* Document.ready END */

/* Window Load START */
jQuery(window).on('load',function () {
	aikit.load();	
});
/*  Window Load END */

/* Window Resize START */
jQuery(window).on('resize',function () {
	aikit.resize();	
});
/*  Window Resize END */