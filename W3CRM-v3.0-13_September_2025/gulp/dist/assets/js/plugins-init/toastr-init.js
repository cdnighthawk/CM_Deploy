(function ($) {
    "use strict"
	
	if(jQuery('#toastr-success-top-right').length > 0 ){
		$("#toastr-success-top-right").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": true,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-top-right",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "3000",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000"
			}
			toastr["success"]("This Is Success Message.", "Success Top Right");
		});
	}
	
	if(jQuery('#toastr-info-top-right').length > 0 ){
		$("#toastr-info-top-right").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": true,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-top-right",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "3000",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000"
			}
			toastr["info"]("This Is info Message", "Info Top Right");
		});
	}
	
	if(jQuery('#toastr-warning-top-right').length > 0 ){
		$("#toastr-warning-top-right").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": false,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-top-right",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "300",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000",
			}
			toastr["info"]("This Is warning Message", "Warning Top Right");
		});
	}
	
	if(jQuery('#toastr-error-top-right').length > 0 ){
		$("#toastr-error-top-right").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": false,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-top-right",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "300",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000",
			}
			toastr["error"]("This Is error Message", "Error Top Right");
		});
	}
	
	if(jQuery('#toastr-progress-top-right').length > 0 ){
		$("#toastr-progress-top-right").on("click", function () {
			toastr.options = {
				"closeButton": false,
				"debug": false,
				"newestOnTop": false,
				"progressBar": true,
				"positionClass": "toast-top-right",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "300",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000",
			}
			toastr["success"]("This Is Progress Bar", "Progress Top Right");
		});		
	}
	
	if(jQuery('#toastr-clear-top-right').length > 0 ){
		$("#toastr-clear-top-right").on("click", function () {
			toastr.options = {
				"closeButton": false,
				"debug": true,
				"newestOnTop": false,
				"progressBar": true,
				"positionClass": "toast-top-right",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "300",
				"hideDuration": "1000",
				"timeOut": 0,
				"extendedTimeOut": 0,
			}
			toastr["success"]('Add button to force clearing a toast, ignoring focus <br> <button type="button" class="btn btn-sm btn-light mt-2">Yes</button>');
		});
	}
	
	if(jQuery('#toastr-top-right').length > 0 ){
		$("#toastr-top-right").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": true,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-top-right",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "3000",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000"
			}
			toastr["success"]("This Is Success Message.", "Toastr Top Right");
		});
	}
	
	if(jQuery('#toastr-bottom-right').length > 0 ){
		$("#toastr-bottom-right").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": true,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-bottom-right",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "3000",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000"
			}
			toastr["success"]("This Is Success Message.", "Toastr Bottom Right");
		});
	}
	
	if(jQuery('#toastr-bottom-left').length > 0 ){
		$("#toastr-bottom-left").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": true,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-bottom-left",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "3000",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000"
			}
			toastr["success"]("This Is Success Message.", "Toastr Bottom Left");
		});
	}
	
	if(jQuery('#toastr-top-left').length > 0 ){
		$("#toastr-top-left").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": true,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-top-left",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "3000",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000"
			}
			toastr["success"]("This Is Success Message.", "Toastr Top Left");
		});
	}
	
	if(jQuery('#toastr-top-full-width').length > 0 ){
		$("#toastr-top-full-width").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": true,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-top-full-width",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "3000",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000"
			}
			toastr["success"]("This Is Success Message.", "Toastr Top Full Width");
		});
	}
	
	if(jQuery('#toastr-top-center').length > 0 ){
		$("#toastr-top-center").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": true,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-top-center",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "3000",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000"
			}
			toastr["success"]("This Is Success Message.", "Toastr Top Center");
		});
	}
	
	if(jQuery('#toastr-bottom-center').length > 0 ){
		$("#toastr-bottom-center").on("click", function () {
			toastr.options = {
				"closeButton": true,
				"debug": true,
				"newestOnTop": false,
				"progressBar": false,
				"positionClass": "toast-bottom-center",
				"preventDuplicates": false,
				"onclick": null,
				"showDuration": "3000",
				"hideDuration": "1000",
				"timeOut": "5000",
				"extendedTimeOut": "1000"
			}
			toastr["success"]("This Is Success Message.", "Toastr Bottom Center");
		});
	}
	
})(jQuery);