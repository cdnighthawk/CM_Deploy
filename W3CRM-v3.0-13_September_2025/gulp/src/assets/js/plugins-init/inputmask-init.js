(function($) {
	"use strict"
  
	if(jQuery('.mask-phone').length > 0 ){
		Inputmask({
			"mask": "(999) 999-9999" 
		}).mask(".mask-phone");
	}
	
	if(jQuery('.mask-date').length > 0 ){
		Inputmask("datetime", {
			inputFormat: "dd/mm/yyyy",
			placeholder: "dd/mm/yyyy",
		}).mask(".mask-date");
	}
	
	if(jQuery('.mask-email').length > 0 ){		
		Inputmask("email").mask(".mask-email");
	}
	
	if(jQuery('.mask-ip').length > 0 ){		
		Inputmask("ip").mask(".mask-ip");
	}
	
	if(jQuery('.mask-currency').length > 0 ){		
		Inputmask("€ 999.999,99", {
			numericInput: true,
			placeholder: "0",
			rightAlign: false,
		}).mask(".mask-currency");
	}
	
	if(jQuery('.mask-percentage').length > 0 ){		
		Inputmask("percentage", {
			suffix: " %",
			rightAlign: true,
		}).mask(".mask-percentage");
	}
	
	if(jQuery('.mask-zipcode').length > 0 ){
		Inputmask("99999").mask(".mask-zipcode");
	}
	
	if(jQuery('.mask-mac').length > 0 ){		
		Inputmask("**:**:**:**:**:**", {
			definitions: {
				"*": {
					validator: "[0-9A-Fa-f]",
					casing: "upper",
				},
			},
		}).mask(".mask-mac");
	}
	
	if(jQuery('.mask-repeating').length > 0 ){		
		Inputmask({ 
			mask: "9{1,10}", 
			greedy: false 
		}).mask(".mask-repeating");
	}
	
	if(jQuery('.mask-placeholder').length > 0 ){		
		Inputmask({
			mask: "(999) 999-9999",
			placeholder: "(999) 999-9999"
		}).mask(".mask-placeholder");
	}
	
	if(jQuery('.mask-cc').length > 0 ){		
		Inputmask("9999 9999 9999 9999").mask(".mask-cc");
	}
	
	if(jQuery('.mask-decimal').length > 0 ){		
		Inputmask("decimal", {
			digits: 2,
			rightAlign: false,
			autoGroup: true,
		}).mask(".mask-decimal");
	}
	
	if(jQuery('.mask-ssn').length > 0 ){		
		Inputmask("999-99-9999").mask(".mask-ssn");
	}
	
})(jQuery);