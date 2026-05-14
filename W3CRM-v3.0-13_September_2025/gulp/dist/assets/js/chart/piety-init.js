(function($) {
    "use strict"

	var W3CoreUIPiety = function(){
		
		var getGraphBlockSize = function (selector) {
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
		
		var handlePietyDataAttr = function(){
			if(jQuery('.piety-data-attr').length > 0 ){
				$(".piety-data-attr").peity("donut");
			}
		}
		
		var handlePietyBar = function(){
			if(jQuery('.piety-bar-chart').length > 0 ){
				$(".piety-bar-chart").peity("bar", {
					fill: ["var(--bs-primary)", "var(--bs-warning)", "var(--bs-info)"],
					width: "100%",
					height: "100",
				});
			}
		}
		
		var handlePietyLine = function(){
			if(jQuery('.peity-line-chart').length > 0 ){
				$(".peity-line-chart").peity("line", {
					fill: ["rgba(var(--bs-primary-rgb), 0.1)"], 
					stroke: 'var(--bs-primary)', 
					width: "100%",
					height: "100"
				});
			}
		}
		
		var handlePietyPie = function(){
			if(jQuery('.peity-pie-chart').length > 0 ){
				$(".peity-pie-chart").peity("pie", {
					fill: ['var(--bs-primary)', 'rgba(var(--bs-primary-rgb), .2)'], 
					width: "80",
					height: "80"
				});
			}
		}
		
		var handlePietyDonut = function(){
			if(jQuery('.peity-donut-chart').length > 0 ){
				$(".peity-donut-chart").peity("donut", {
					width: "100",
					height: "100"
				});
			}
		}
		
		var handlePietyUpdatingChart = function(){
			var t = $(".piety-updating-chart").peity("line", {
				fill: ['rgba(var(--bs-primary-rgb), 0.1)'],
				stroke: 'var(--bs-primary)', 
				width: "100%",
				height: 100
			});
			
			setInterval(function() {
				var e = Math.round(10 * Math.random()),
				i = t.text().split(",");
				i.shift(), i.push(e), t.text(i.join(",")).change()
			}, 1e3);
		}
		
		var handlePietyBarColours1 = function(){
			if(jQuery('.bar-colours-1').length > 0 ){
				$(".bar-colours-1").peity("bar", {
					colours: ["var(--bs-primary)", "var(--bs-success)", "var(--bs-info)"],
					width: "100",
					height: "100",
				});
			}
		}
		
		var handlePietyBarColours2 = function(){
			if(jQuery('.bar-colours-2').length > 0 ){
				$(".bar-colours-2").peity("bar", {
					colours: function(value) {
						return value > 0 ? "green" : "red"
					},
					width: "100",
					height: "100",
				});
			}
		}
		
		var handlePietyBarColours3 = function(){
			if(jQuery('.bar-colours-3').length > 0 ){
				$(".bar-colours-3").peity("bar", {
					fill: function(t, e, i) {
						return "rgb(16, " + parseInt(e / i.length * 202) + ", 147)"
					},
					width: "100",
					height: "100"
				});
			}
		}
		
		var handlePietyColours1 = function(){
			if(jQuery('.pie-colours-1').length > 0 ){
				$(".pie-colours-1").peity("pie", {
					colours: ["cyan", "magenta", "yellow", "black"],
					width: "80",
					height: "80"
				});
			}
		}
		
		/* Function ============ */
		return {
			init:function(){
				
			},			
			
			load:function(){
				handlePietyDataAttr();
				handlePietyBar();
				handlePietyLine();
				handlePietyPie();
				handlePietyUpdatingChart();
				handlePietyBarColours1();
				handlePietyBarColours2();
				handlePietyBarColours3();
				handlePietyColours1();
			},
			
			resize:function(){
				handlePietyDataAttr();
				handlePietyBar();
				handlePietyLine();
				handlePietyPie();
				handlePietyBarColours1();
				handlePietyBarColours2();
				handlePietyBarColours3();
				handlePietyColours1();
			}
		}
		
	}();
 
	jQuery(document).ready(function(){
		
	});
	
	jQuery(window).on('load',function(){
		setTimeout(function(){
			W3CoreUIPiety.load();
		}, 1000); 
		
	});

	jQuery(window).on('resize',function(){
		setTimeout(function(){
			W3CoreUIPiety.resize();
		}, 1000); 
		
	});      

})(jQuery);