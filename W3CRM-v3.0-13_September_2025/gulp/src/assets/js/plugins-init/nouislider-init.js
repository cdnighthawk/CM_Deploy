"use strict"

// Basic Slider Start
var startSlider = document.getElementById('slider-start');
noUiSlider.create(startSlider, {
    start: [20, 80],
    connect: true,
	range: {
        'min': [0],
        'max': [100]
    }
});
// basic slider End

// Step Slider Start
var stepSlider = document.getElementById('slider-step');
noUiSlider.create(stepSlider, {
    start: [4000],
	step: 500,
    range: {
		'min': [2000],
		'max': [10000]
	}
});
var stepSliderValueElement = document.getElementById('slider-step-value');
stepSlider.noUiSlider.on('update', function (values, handle) {
	stepSliderValueElement.innerHTML = values[handle];
});
// Step Slider Start


// tooltip Slider Start
var tooltipSlider = document.getElementById('slider-tooltips');
noUiSlider.create(tooltipSlider, {
    start: [20, 80, 120],
    connect: true,
	tooltips: [false, wNumb({decimals: 1}), true],
    range: {
        'min': 0,
        'max': 200
    }
});
// Remove tooltips:
// tooltipSlider.noUiSlider.removeTooltips();
// tooltip Slider End


// limit Slider Start
var limitSlider = document.getElementById('slider-limit');
noUiSlider.create(limitSlider, {
    start: [10, 120],
    limit: 40,
    behaviour: 'drag',
    connect: true,
    range: {
        'min': 0,
        'max': 100
    }
});
var limitFieldMin = document.getElementById('slider-limit-value-min');
var limitFieldMax = document.getElementById('slider-limit-value-max');

limitSlider.noUiSlider.on('update', function (values, handle) {
    (handle ? limitFieldMax : limitFieldMin).innerHTML = values[handle];
});
// limit Slider End


// Colorpicker Slider Start
var resultElement = document.getElementById('result');
var sliders = document.querySelectorAll('.sliders');
var colors = [0, 0, 0];

sliders.forEach(function (slider, index) {
    noUiSlider.create(slider, {
        start: 127,
        connect: [true, false],
        orientation: "vertical",
        range: {
            'min': 0,
            'max': 255
        },
        format: wNumb({
            decimals: 0
        })
    });

    // Bind the color changing function to the update event.
    slider.noUiSlider.on('update', function () {
        colors[index] = slider.noUiSlider.get();
        var color = 'rgb(' + colors.join(',') + ')';
        resultElement.style.background = color;
        resultElement.style.color = color;
    });
});
// Colorpicker Slider End

// Soft Slider Start
var softSlider = document.getElementById('soft');
noUiSlider.create(softSlider, {
    start: 50,
    range: {
        min: 0,
        max: 100
    },
    pips: {
        mode: 'values',
        values: [20, 80],
        density: 4
    }
});
// Soft Slider End


// connect color Start
var slider = document.getElementById('slider-color');
noUiSlider.create(slider, {
	start: [4000, 8000, 12000, 16000],
	connect: [false, true, true, true, true],
	range: {
		'min': [2000],
		'max': [20000]
	}
});

var connect = slider.querySelectorAll('.noUi-connect');
var classes = ['c-1-color', 'c-2-color', 'c-3-color', 'c-4-color', 'c-5-color'];

for (var i = 0; i < connect.length; i++) {
    connect[i].classList.add(classes[i]);
}
// connect color End

// dateSlider color Start
var dateSlider = document.getElementById('slider-date');
function timestamp(str) {
    return new Date(str).getTime();
}
noUiSlider.create(dateSlider, {
	// Create two timestamps to define a range.
	connect: true,
	range: {
		min: timestamp('2010'),
		max: timestamp('2016')
	},

	// Steps of one week
	step: 7 * 24 * 60 * 60 * 1000,

	// Two more timestamps indicate the handle starting positions.
	start: [timestamp('2011'), timestamp('2015')],

	// No decimals
	format: wNumb({
		decimals: 0
	})
});
var dateValues = [
    document.getElementById('event-start'),
    document.getElementById('event-end')
];

var formatter = new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'full'
});

dateSlider.noUiSlider.on('update', function (values, handle) {
    dateValues[handle].innerHTML = formatter.format(new Date(+values[handle]));
});
// dateSlider color End


// activePips color Start
var pipsSlider = document.getElementById('active-pip');
noUiSlider.create(pipsSlider, {
    start: [20, 80],
    margin: 20,
    connect: true,
    range: {
        'min': 0,
        'max': 100
    },
    step: 20,
    pips: {
        mode: 'steps',
        density: 3
    }
});

var activePips = [null, null];

pipsSlider.noUiSlider.on('update', function (values, handle) {
    // Remove the active class from the current pip
    if (activePips[handle]) {
        activePips[handle].classList.remove('active-pip');
    }

    // Match the formatting for the pip
    var dataValue = Math.round(values[handle]);

    // Find the pip matching the value
    activePips[handle] = pipsSlider.querySelector('.noUi-value[data-value="' + dataValue + '"]');

    // Add the active class
    if (activePips[handle]) {
        activePips[handle].classList.add('active-pip');
    }
});
// activePips color End


// verticalSlider color Start
var verticalSlider = document.getElementById('slider-vertical');
noUiSlider.create(verticalSlider, {
    start: 40,
    orientation: 'vertical',
    range: {
        'min': 0,
        'max': 100
    },
	pips: {
        mode: 'values',
        values: [20, 80],
        density: 4
    }
});
// verticalSlider color End