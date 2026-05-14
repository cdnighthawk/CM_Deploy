(function($) {
    "use strict"
	
	function escapeXml(string) {
		return string.replace(/[<>]/g, function (c) {
			switch (c) {
				case '<': return '\u003c';
				case '>': return '\u003e';
			}
		});
	}

	var dzVectorMap = function(){
		
		var pins = {
			mo: escapeXml('<div class="map-pin red"></div>'),
			or: escapeXml('<div class="map-pin purple"></div>')
		};
		
		var screenWidth = $(window).width();
		
		var handleWorldMap = function(trigger = 'load'){
			var vmapSelector = $('#jqvWorldMap');
			
			if(trigger == 'resize'){
				vmapSelector.empty();
				vmapSelector.removeAttr('style');
			}
			
			vmapSelector.delay( 500 ).unbind().vectorMap({
				map: 'world_en',
				backgroundColor: 'transparent',
				color: 'var(--bs-light)',
				hoverOpacity: 0.7,
				borderColor: 'var(--bs-body-color)',
				borderOpacity: 0.25,
				borderWidth: 1,
				enableZoom: true,
				showTooltip: true,
				selectedColor: 'rgba(13, 153, 255, 0.9)',
				normalizeFunction: 'polynomial'
			});
		}
		
		var handleMapPins = function(trigger = 'load'){
			var vmapSelector = $('#jqvMapPins');
			
			if(trigger == 'resize'){
				vmapSelector.empty();
				vmapSelector.removeAttr('style');
			}
			
			vmapSelector.delay( 500 ).unbind().vectorMap({
				backgroundColor: 'transparent',
				borderColor: 'var(--bs-border-color)',
				map: 'usa_en',
				pins: pins,
				color: 'var(--bs-light)',
				pinMode: 'content',
				borderColor: 'var(--bs-body-color)',
				hoverColor: null,
				selectedColor: 'var(--bs-success)',
				showTooltip: false,
				selectedRegions: ['MO', 'OR'],
				onRegionClick: function(event){
					event.preventDefault();
				}
			});
		}
		
		var handleMapLabels = function(trigger = 'load'){
			var vmapSelector = $('#jqvMapLabels');
			
			if(trigger == 'resize'){
				vmapSelector.empty();
				vmapSelector.removeAttr('style');
			}
			
			vmapSelector.delay( 500 ).unbind().vectorMap({
				backgroundColor: 'transparent',
				borderColor: 'var(--bs-border-color)',
				map: 'usa_en',
				color: 'var(--bs-light)',
				pinMode: 'content',
				borderColor: 'var(--bs-body-color)',
				hoverColor: null,
				selectedColor: 'var(--bs-success)',
				showTooltip: false,
				showLabels: true,
			});
		}
	
		return {
			init:function(){
				
			},
			
			load:function(){
				handleWorldMap();
				handleMapPins();
				handleMapLabels();
			},
			
			resize:function(){
				handleWorldMap();
				handleMapPins();
				handleMapLabels();
			}
		}
	
	}();

	jQuery(document).ready(function(){
		
	});
	
	jQuery(window).on('load',function(){
		setTimeout(function(){
			dzVectorMap.load();
		}, 1000); 
	});

	jQuery(window).on('resize',function(){
		setTimeout(function(){
			dzVectorMap.resize();
		}, 1000); 
	});

})(jQuery);	