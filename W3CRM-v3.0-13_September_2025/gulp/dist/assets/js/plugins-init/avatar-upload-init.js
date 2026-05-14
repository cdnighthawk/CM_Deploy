(function ($) {
    "use strict"
	
	if ($('.upload-trigger').length > 0) {
		placeholderImage: 'assets/images/placeholder.jpg';
		
		initAvatarUpload();
	}

	// Initializes all avatar upload
	function initAvatarUpload() {
		$('.upload-trigger').on('click', triggerFileInput);
		$('.upload-input').on('change', function () {
			showPreview(this);
		});
		$('.remove-avatar').on('click', removeAvatar);
	}

	// Handle click on upload icon
	function triggerFileInput() {
		$(this).siblings('.upload-input').click();
	}

	// Show image preview when file is selected
	function showPreview(input) {
		const preview = $(input).siblings('.avatar-preview');

		if (input.files && input.files[0]) {
			const reader = new FileReader();
			reader.onload = function (e) {
				preview.hide().attr('src', e.target.result).fadeIn(650);
			};
			reader.readAsDataURL(input.files[0]);
		}
	}

	// reset to placeholder and clear input
	function removeAvatar() {
		const wrapper = $(this).closest('.avatar-input');
		const preview = wrapper.find('.avatar-preview');
		const input = wrapper.find('.upload-input');
		const placeholderImage = 'assets/images/placeholder.jpg';

		// Fade out and reset to placeholder
		preview.fadeOut(200, function () {
			preview.attr('src', placeholderImage).fadeIn(500);
		});

		// Replace input with a clean clone and rebind change
		const newInput = input.clone().val('');
		input.replaceWith(newInput);
		newInput.on('change', function () {
			showPreview(this);
		});
	}
	
})(jQuery);