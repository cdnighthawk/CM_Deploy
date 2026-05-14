(function ($) {
    "use strict"
	
	if(jQuery("#ckeditor").length>0) {
		ClassicEditor
		.create( document.querySelector( '#ckeditor' ), {
			simpleUpload: {
				uploadUrl: 'ckeditor-upload.php', 
			}
		} )
		.then( editor => {
			window.editor = editor;
		})
		.catch( err => {
			console.error( err.stack );
		});
	}
	
})(jQuery);