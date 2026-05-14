document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    var quillEditor = document.getElementById("quillEditor");
    if (quillEditor) {
        var quill = new Quill("#quillEditor", {
            theme: "snow"
        });
    }
	
});