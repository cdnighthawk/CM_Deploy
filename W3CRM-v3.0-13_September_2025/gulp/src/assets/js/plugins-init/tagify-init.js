(function ($) {
    "use strict"
	
	if(jQuery('.basic-tagify').length > 0 ){
		// The DOM element you wish to replace with Tagify
		var input = document.querySelector('.basic-tagify');

		// initialize Tagify on the above input node reference
		new Tagify(input)
	}
	
})(jQuery);