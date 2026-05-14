(function($) {
    "use strict"
	
	var W3CoreUISparkLine = function(){
    
		var screenWidth = $(window).width();
	
		function getSparkLineGraphBlockSize(selector){
			var screenWidth = $(window).width();
			var graphBlockSize = '100%';
			
			if(screenWidth <= 768){
				screenWidth = (screenWidth < 300 )?screenWidth:300;
				
				var blockWidth  = jQuery(selector).parent().innerWidth() - jQuery(selector).parent().width();
		
				blockWidth = Math.abs(blockWidth);
				
				var graphBlockSize = screenWidth - blockWidth - 10;	
			}
			
			return graphBlockSize;
		}
	
		var sparkLineDash = function(){
			if(jQuery('#sparklineDash').length > 0 ){	 
				 $("#sparklineDash").sparkline([10, 15, 26, 27, 28, 31, 34, 40, 41, 44, 49, 64, 68, 69, 72], {
					type: "bar",
					height: "50",
					barWidth: "4",
					resize: !0,
					barSpacing: "5",
					barColor: "#0d99ff"
				});
			}
		}
	
		var sparklineTraffic1 = function(){
			if(jQuery('#sparklineTraffic1').length > 0 ){	
				$("#sparklineTraffic1").sparkline([79, 72, 29, 6, 52, 32, 73, 40, 14, 75, 77, 39, 9, 15, 10], {
					type: "line",
					width: getSparkLineGraphBlockSize('#sparklineTraffic1'),
					height: "50",
					lineColor: "#0d99ff",
					fillColor: "rgba(13, 153, 255, 1)",
					minSpotColor: "#0d99ff",
					maxSpotColor: "#0d99ff",
					highlightLineColor: "#0d99ff",
					highlightSpotColor: "#0d99ff",
				});
			}
		}
	
		var sparklineTraffic2 = function(){
			if(jQuery('#sparklineTraffic2').length > 0 ){	
				$("#sparklineTraffic2").sparkline([27, 31, 35, 28, 45, 52, 24, 4, 50, 11, 54, 49, 72, 59, 75], {
					type: "line",
					//width: "100%",
					width: getSparkLineGraphBlockSize('#sparklineTraffic2'),
					height: "50",
					lineColor: "#ff5c00",
					fillColor: "rgba(255, 92, 0, .5)",
					minSpotColor: "#ff5c00",
					maxSpotColor: "#ff5c00",
					highlightLineColor: "rgb(255, 159, 0)",
					highlightSpotColor: "#ff5c00"
				});
			}
		}

		var sparklineBar = function(){
			if(jQuery('#sparklineBar').length > 0 ){	
				$("#sparklineBar").sparkline([33, 22, 68, 54, 8, 30, 74, 7, 36, 5, 41, 19, 43, 29, 38], {
					type: "bar",
					height: "200",
					barWidth: 6,
					barSpacing: 7,
					barColor: "#ffaa2b"
				});
			}	
		}
		
		var sparklineStacked = function(){
			if(jQuery('#sparklineStacked').length > 0 ){	
				$('#sparklineStacked').sparkline([
					[1, 4, 2],
					[2, 3, 2],
					[3, 2, 2],
					[4, 1, 2]
				], {
					type: "bar",
					height: "200",
					barWidth: 10,
					barSpacing: 7, 
					stackedBarColor: ['#0d99ff', '#ffaa2b', '#ff5c00']
				});
			}
		}
		
		var sparklineTriState = function(){
			if(jQuery('#sparklineTriState').length > 0 ){
				$("#sparklineTriState").sparkline([1, 1, 0, 1, -1, -1, 1, -1, 0, 0, 1, 1], {
					type: 'tristate',
					height: "200",
					barWidth: 10,
					barSpacing: 7, 
					colorMap: ['#0d99ff', '#ffaa2b', '#ff5c00'], 
					negBarColor: '#ff5c00'
				});
			}
		}
		
		var sparklineCompositeChart = function(){
			if(jQuery('#sparklineCompositeChart').length > 0 ){
				$("#sparklineCompositeChart").sparkline([5, 6, 7, 2, 0, 3, 6, 8, 1, 2, 2, 0, 3, 6], {
					type: 'line',
					width: '100%',
					height: '200', 
					barColor: '#ffaa2b', 
					colorMap: ['#ffaa2b', '#ff5c00']
				});
			}
			if(jQuery('#sparklineCompositeChart').length > 0 ){
				$("#sparklineCompositeChart").sparkline([5, 6, 7, 2, 0, 3, 6, 8, 1, 2, 2, 0, 3, 6], {
					type: 'bar',
					height: '150px',
					width: '100%',
					barWidth: 10,
					barSpacing: 5,
					barColor: '#34C73B',
					negBarColor: '#34C73B',
					composite: true,
				});
			}
		}
		
		var sparklineCompositeBar = function(){
			if(jQuery('#sparklineCompositeBar').length > 0 ){
				$("#sparklineCompositeBar").sparkline([73, 53, 50, 67, 3, 56, 19, 59, 37, 32, 40, 26, 71, 19, 4, 53, 55, 31, 37], {
					type: "bar",
					height: "200",
					barWidth: "10",
					resize: true,
					// barSpacing: "7",
					barColor: "#0d99ff", 
					width: '100%',
					
				});
			}	
		}
		
		var sparklineBulletChart = function(){
			if(jQuery('#sparklineBulletChart').length > 0 ){
				$("#sparklineBulletChart").sparkline([10, 12, 12, 9, 7], {
					type: 'bullet',
					height: '100',
					width: '100%',
					targetOptions: {		  // Options related with look and position of targets 
						width: '100%',        // The width of the target 
						height: 3,            // The height of the target 
						borderWidth: 0,       // The border width of the target 
						borderColor: 'black', // The border color of the target 
						color: 'black'        // The color of the target 
					}
				});
			}
		}
		
		var sparklinePieChart = function(){
			if(jQuery('#sparklinePieChart').length > 0 ){
				$("#sparklinePieChart").sparkline([24, 61, 51], {
					type: "pie",
					height: "100px",
					resize: !0,
					sliceColors: ["rgba(192, 10, 39, .5)", "rgba(0, 0, 128, .5)", "rgba(44, 44, 44,1)"]
				});
			}	
		}
		
		var sparklineBoxPlot = function(){
			if(jQuery('#sparklineBoxPlot').length > 0 ){
				$("#sparklineBoxPlot").sparkline([4,27,34,52,54,59,61,68,78,82,85,87,91,93,100], {
					type: 'box'
				});
			}
		}
		
		/* Function ============ */
		return {
			init:function(){
				
			},
			
			load:function(){
				sparkLineDash();	
				sparklineTraffic1();
				sparklineTraffic2();
				sparklineBar();	
				sparklineStacked();
				sparklineTriState();
				sparklineCompositeChart();
				sparklineCompositeBar();
				sparklineBulletChart();
				sparklinePieChart();
				sparklineBoxPlot();
			},
			
			resize:function(){
				sparkLineDash();	
				sparklineTraffic1();
				sparklineTraffic2();
				sparklineBar();	
				sparklineStacked();
				sparklineTriState();
				sparklineCompositeChart();
				sparklineCompositeBar();
				sparklineBulletChart();
				sparklinePieChart();
				sparklineBoxPlot();
			}
		}
	
	}();

	jQuery(document).ready(function(){
		
	});
	
	jQuery(window).on('load',function(){
		setTimeout(function(){
			W3CoreUISparkLine.resize();	
		}, 1000);
	});

	jQuery(window).on('resize',function(){
		setTimeout(function(){
			W3CoreUISparkLine.resize();	
		}, 1000);
	});     

})(jQuery);