(function ($) {
    "use strict"
	
	if(jQuery('.bs-maxlength').length > 0 ){
		$('.bs-maxlength').maxlength({
            alwaysShow: true,
            warningClass: "badge text-bg-success badge-xs",
            limitReachedClass: "badge text-bg-danger badge-xs",
        });
	}
	
	if(jQuery('.bs-maxlength-threshold').length > 0 ){
		$('.bs-maxlength-threshold').maxlength({
			threshold: 20,
            warningClass: "badge text-bg-success badge-xs",
            limitReachedClass: "badge text-bg-danger badge-xs",
		});
	}
	
	if(jQuery('.bs-maxlength-textarea').length > 0 ){
		$('.bs-maxlength-textarea').maxlength({
			alwaysShow: true,
			warningClass: "badge text-bg-success badge-xs",
            limitReachedClass: "badge text-bg-danger badge-xs",
		});
	}
	
	if(jQuery('.bs-maxlength-top-start').length > 0 ){
		$('.bs-maxlength-top-start').maxlength({
            alwaysShow: true,
            placement: 'top-left',
			warningClass: "badge text-bg-info badge-xs",
            limitReachedClass: "badge text-bg-danger badge-xs",
        });
	}
	
	if(jQuery('.bs-maxlength-top-end').length > 0 ){
		$('.bs-maxlength-top-end').maxlength({
            alwaysShow: true,
            placement: 'top-right',
			warningClass: "badge text-bg-success badge-xs",
            limitReachedClass: "badge text-bg-danger badge-xs",
        });
	}
	
	if(jQuery('.bs-maxlength-bottom-end').length > 0 ){
		$('.bs-maxlength-bottom-end').maxlength({
            alwaysShow: true,
            placement: 'bottom-right',
			warningClass: "badge text-bg-warning badge-xs",
            limitReachedClass: "badge text-bg-danger badge-xs",
        });
	}
	
	if(jQuery('.bs-maxlength-bottom-start').length > 0 ){
		$('.bs-maxlength-bottom-start').maxlength({
            alwaysShow: true,
            placement: 'bottom-left',
			warningClass: "badge text-bg-primary badge-xs",
            limitReachedClass: "badge text-bg-danger badge-xs",
        });
	}
	
	if(jQuery('.bs-maxlength-custom').length > 0 ){
		$('.bs-maxlength-custom').maxlength({
			alwaysShow: true,
			threshold: 10,
			warningClass: "badge text-bg-success badge-xs",
			limitReachedClass: "badge text-bg-danger badge-xs",
			separator: ' of ',
			preText: 'You have ',
			postText: ' chars remaining.',
			validate: true
        });
	}
	
})(jQuery);