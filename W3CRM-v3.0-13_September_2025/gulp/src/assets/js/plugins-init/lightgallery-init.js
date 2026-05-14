"use strict"

if (document.querySelector('#gallery-videos-demo')) {
    lightGallery(document.getElementById('animated-thumbnails-gallery'), {
        plugins: [lgZoom, lgThumbnail],
        selector: '.lg-item',
    });
}

if (document.querySelector('#gallery-videos-demo')) {
	lightGallery(document.getElementById('gallery-videos-demo'), {
		selector: '.lg-item',
		plugins: [lgVideo],
	});
}

if (document.querySelector('#bootstrap-gallery-carousel')) {
	// Get the carousel element by its ID
	let carouselEl = document.getElementById('bootstrap-gallery-carousel');

	// Create a new Bootstrap 5 Carousel instance with specified options
	const carousel = new bootstrap.Carousel(carouselEl, {
		interval: 2000,
		wrap: true,
	});

	// Add an event listener for the 'slide.bs.carousel' event, fires immediately when the slide instance method is invoked.
	carouselEl.addEventListener('slide.bs.carousel', (event) => {
		const container = document.querySelector('.carousel-inner');
		window.lightGallery(container, {
			plugins: [lgThumbnail],
			selector: '.lg-item',
		});
	});
}