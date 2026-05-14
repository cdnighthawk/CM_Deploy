(function ($) {
	
	$.fn.passwordMeter = function (options) {
		return this.each(function () {
			const $input = $(this);
			const $wrap = $input.parent().parent('.password-meter-wrap').find(".meter-wrap");

			const settings = $.extend({
				passwordLength: $input.data("password-length") == 8,
				withDigit: $input.data("digit") == true,
				toSymbol: $input.data("symbol") == true,
				upperCase: $input.data("uppercase") == true,
				lowerCase: $input.data("lowercase") == true
			}, options);

			const totalEnabled = Object.values(settings).filter(Boolean).length;

			// Create meter bars on load
			$wrap.empty();
			for (let i = 0; i < totalEnabled; i++) {
				$wrap.append("<div class='meter'></div>");
			}

			// Handle input change
			$input.on("keyup", function () {
				const password = $input.val();
				let activeCount = 0;

				if (settings.passwordLength && password.length >= 5) activeCount++;
				if (settings.withDigit && /[0-9]/.test(password)) activeCount++;
				if (settings.toSymbol && /[!,%,&,@,#,$,^,*,?,_,~,<,>]/.test(password)) activeCount++;
				if (settings.upperCase && /[A-Z]/.test(password)) activeCount++;
				if (settings.lowerCase && /[a-z]/.test(password)) activeCount++;

				$wrap.children(".meter").each(function (index) {
					$(this).toggleClass("active", index < activeCount);
				});
			});
		});
	}

	if(jQuery('.password-strength').length > 0 ){
		$(".password-strength").on("keyup", function () {
			const password = $(this).val();
			let strength = "Weak";
			let color = "red";

			if (password.length >= 8 && /[A-Z]/.test(password) && /[0-9]/.test(password) && /[!@#$%^&*]/.test(password)) {
				
				strength = "Strong";
				color = "green";
				
			} else if (password.length >= 6) {
			
				strength = "Medium";
				color = "orange";
				
			}

			$(this).parent().parent('.password-strength-wrap').find(".strength-message").text(`Strength: ${strength}`).css("color", color);
		});
	}
	
	if ($('.password-meter').length) {
		$('.password-meter').passwordMeter();
	}

})(jQuery);