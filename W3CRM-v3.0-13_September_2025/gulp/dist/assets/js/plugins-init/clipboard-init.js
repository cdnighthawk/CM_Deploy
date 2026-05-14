document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    function changeText(e) {
		const originalText = e.trigger.innerText;
		
		if (originalText === 'Copied!') {
			return;
		}
		e.trigger.innerText = 'Copied!';
		
		setTimeout(() => {
			e.trigger.innerText = originalText;
		}, 5000);
	}
	

    // Clipboard for target
	const clipboardTarget = document.querySelectorAll('.clipboard-target');
	if(clipboardTarget.length > 0){
		const targetHandler = new ClipboardJS(clipboardTarget);
		
		targetHandler.on('success', function (e) {
			changeText(e);
		});
		
		targetHandler.on('error', function (e) {
			console.error('Clipboard copy failed', e);
		});			
	}
	
	// Clipboard for text
	const clipboardText = document.querySelectorAll('.clipboard-text');
	if(clipboardText.length > 0){
		const textHandler = new ClipboardJS(clipboardText);
		
		textHandler.on('success', function (e) {
			changeText(e);
		});
		
		textHandler.on('error', function (e) {
			console.error('Clipboard copy failed', e);
		});
	}
	
	// Data clipboard static
	const clipboardStatic = document.querySelectorAll('.clipboard-static');

	if (clipboardStatic.length > 0) {
		clipboardStatic.forEach(el => {
			const staticHandler = new ClipboardJS(el);

			staticHandler.on('success', function (e) {
				const targetSelector = el.getAttribute('data-clipboard-target');
				const targetElement = document.querySelector(targetSelector);
				const icon = e.trigger.querySelector('i');

				window.getSelection().removeAllRanges();

				// Add 'text-success' to target
				if (targetElement) {
					targetElement.classList.add('text-success');
				}

				// Update button style and icon
				e.trigger.classList.remove('btn-light');
				e.trigger.classList.add('btn-success');

				if (icon) {
					icon.classList.remove('fa-clone');
					icon.classList.add('fa-check');
				}

				// Revert after 5s
				setTimeout(() => {
					e.trigger.classList.remove('btn-success');
					e.trigger.classList.add('btn-light');

					if (icon) {
						icon.classList.remove('fa-check');
						icon.classList.add('fa-clone');
					}

					if (targetElement) {
						targetElement.classList.remove('text-success');
					}
				}, 5000);
			});

			staticHandler.on('error', function (e) {
				console.error('Clipboard copy failed', e);
			});
		});
	}
	
});