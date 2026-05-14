(function ($) {
    "use strict"
	
	if(jQuery('.touchspin-input').length > 0 ){
		$('.touchspin-input').TouchSpin({
			step: 1,
			buttondown_class: 'btn',
			buttonup_class: 'btn'
		});
	}
	
	if(jQuery("input[name='touchspinStep']").length > 0 ){
		$("input[name='touchspinStep']").TouchSpin({
			buttondown_class: 'btn',
			buttonup_class: 'btn'
		});
	}
	
})(jQuery);