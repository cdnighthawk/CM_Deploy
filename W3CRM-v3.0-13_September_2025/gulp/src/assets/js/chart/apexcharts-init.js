(function () {
    "use strict";

    const apexChart = (function () {

        const ApexMixedCharts = function () {
			const mixedCharts = document.querySelector("#apexMixedCharts");
			
			if(mixedCharts) {
				var options = {
					series: [
						{
							name: 'Number of Projects',
							type: 'column',
							data: [75, 85, 72, 100, 50, 100, 80, 75, 95, 35, 75,100]
						},
						{
							name: 'Revenue',
							type: 'area',
							data: [44, 65, 55, 75, 45, 55, 40, 60, 75, 45, 50,42]
						},
						{
							name: 'Active Projects',
							type: 'line',
							data: [30, 25, 45, 30, 25, 35, 20, 45, 35, 20, 35,20]
						}
					],
					chart: {
						height: 350,
						type: 'line',
						stacked: false,
						toolbar: {
							show: false,
						},
					},
					grid: {
						borderColor: 'var(--bs-border-color)',
					},
					stroke: {
						width: [0, 1, 1],
						curve: 'straight',
						dashArray: [0, 0, 5],
						color: 'var(--bs-border-color)',
					},
					legend: {
						fontSize: '13px',
						fontFamily: 'var(--bs-body-font-family)',
						labels: {
							colors: 'var(--bs-body-color)',
						}
					},
					plotOptions: {
						bar: {
							columnWidth: '18%',
							borderRadius: 6,
						}
					},
					fill: {
						type : 'gradient',
						gradient: {
							inverseColors: false,
							shade: 'light',
							type: "vertical",
							colorStops : [[
								{
									offset: 0,
									color: 'var(--bs-info)',
									opacity: 1
								},{
									offset: 100,
									color: 'var(--bs-info)',
									opacity: 1
								}],
								[{
									offset: 0,
									color: 'var(--bs-success)',
									opacity: 1
								},{
									offset: 0.4,
									color: 'var(--bs-success)',
									opacity: .15
								},{
									offset: 100,
									color: 'var(--bs-success)',
									opacity: 0
								}],
								[{
									offset: 0,
									color: 'var(--bs-warning)',
									opacity: 1
								},{
									offset: 100,
									color: 'var(--bs-warning)',
									opacity: 1
								}],
							],
							stops: [0, 100, 100, 100]
						}
					},
					colors:[
						"var(--bs-info)", "var(--bs-success)", "var(--bs-warning)"
					],
					labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
					markers: {
						size: 0
					},
					xaxis: {
						type: 'month',
						labels: {
							style: {
							   fontSize: '12px',
							   colors: 'var(--bs-body-color)',
							},
						},
					},
					yaxis: {
						min: 0,
						max: 100,
						tickAmount: 4,
						labels: {
							style: {
								fontSize: '12px',
								colors: 'var(--bs-body-color)',
							},
						},
					},
					tooltip: {
						shared: true,
						intersect: false,
						y: {
							formatter: function (y) {
								if (typeof y !== "undefined") {
									return y.toFixed(0) + " points";
								}
								return y;
							}
						}
					}
				};

				var chart = new ApexCharts(mixedCharts, options);
				chart.render();
			}
        };
		
		const ApexAreaCharts = function () {
			const areaCharts = document.querySelector("#apexAreaCharts");
			
			if (areaCharts) {
				var options = {
					series: [{
						name: 'series1',
						data: [30, 50, 40, 50, 50, 40, 30, 45, 55, 65, 50]
					}, {
						name: 'series2',
						data: [20, 40, 30, 40, 40, 30, 20, 35, 45, 55, 40]
					}],
					chart: {
						height: 360,
						toolbar:{
							show:false
						},
						type: 'area'
					},
					colors:['#FFAB2D', '#AC4CBC'],
					legend:{
						show:false
					},
					dataLabels: {
						enabled: false
					},
					stroke: {
						width: 4,
						curve: 'smooth'
					},
					xaxis: {
						categories: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov'],
						labels: {
							style: {
								colors: 'var(--bs-body-color)',
								fontSize: '12px',
								fontFamily: 'var(--bs-body-font-family)',
							},
						},
					},
					yaxis: {
						show: false
					},
					fill:{
						opacity: 0.2,
						type: 'solid'
					},
					tooltip: {
						x: {
							format: 'dd/MM/yy HH:mm'
						},
					},
				};

				var chart = new ApexCharts(areaCharts, options);
				chart.render();
			}		
		}
		
		const ApexRangeBar = function () {
			const rangeBar = document.querySelector("#ApexRangeBar");
			if (rangeBar) {
				var options = {
					series: [{
						name: 'Buy',
						data: [{
							x: '2:00PM',
							y: [9200.00, 9600.00]
						}, {
							x: '2:30PM',
							y: [9300.00, 9600.00]
						}, {
							x: '3:00PM',
							y: [9150.00, 9500.00]
						}, {
							x: '3:30PM',
							y: [9300.00, 9700.00]
						}, {
							x: '4:00PM',
							y: [9200.00, 9600.00]
						}, {
							x: '4:30PM',
							y: [9400.00, 9700.00]
						}, {
							x: '5:00PM',
							y: [9400.00, 9600.00]
						}, {
							x: '5:30PM',
							y: [9300.00, 9600.00]
						}, {
							x: '6:00PM',
							y: [9300.00, 9500.00]
						}, {
							x: '6:30PM',
							y: [9200.00, 9500.00]
						}, {
							x: '7:00PM',
							y: [9450.00, 9650.00]
						}, {
							x: '7:30PM',
							y: [9400.00, 9700.00]
						}, {
							x: '8:00PM',
							y: [9300.00, 9700.00]
						}]
					},
					{
						name: 'Sell',
						data: [{
							x: '2:00PM',
							y: [9370.00, 9550.00]
						}, {
							x: '2:30PM',
							y: [9350.00, 9700.50]
						}, {
							x: '3:00PM',
							y: [9275.00, 9482.00]
						}, {
							x: '3:30PM',
							y: [9200.00, 9600.00]
						}, {
							x: '4:00PM',
							y: [9250.00, 9500.00]
						}, {
							x: '4:30PM',
							y: [9445.00, 9523.00]
						}, {
							x: '5:00PM',
							y: [9440.00, 9667.00]
						}, {
							x: '5:30PM',
							y: [9300.00, 9600.00]
						}, {
							x: '6:00PM',
							y: [9445.00, 9648.00]
						}, {
							x: '6:30PM',
							y: [9240.00, 9700.00]
						}, {
							x: '7:00PM',
							y: [9130.00, 9550.00]
						}, {
							x: '7:30PM',
							y: [9340.00, 9440.00]
						}, {
							x: '8:00PM',
							y: [9560.00, 9740.00]
						}]
					}],
					chart: {
						type: 'rangeBar',
						height: 370,
						toolbar: {
							show: false,
						},
					},
					plotOptions: {
						bar: {
							horizontal: false,
							columnWidth: '55%',
							endingShape: "rounded",
							startingShape: "rounded",
						},
					},
					colors:['#61C277', '#FF3E3E'],
					dataLabels: {
						enabled: false,
					},
					markers: {
						shape: "circle",
					},
					legend: {
						show: false,
						fontSize: '12px',
						labels: {
							colors: 'var(--bs-body-color)',
						},
						markers: {
							width: 18,
							height: 18,
							strokeWidth: 0,
							strokeColor: '#fff',
							fillColors: undefined,
							radius: 12,	
						}
					},
					stroke: {
						show: true,
						width: 6,
						colors: ['transparent']
					},
					grid: {
						borderColor: 'var(--bs-border-color)',
					},
					xaxis: {
						labels: {
							style: {
								colors: 'var(--bs-body-color)',
								fontSize: '13px',
								fontFamily: 'var(--bs-body-font-family)',
								cssClass: 'apexcharts-xaxis-label',
							},
						},
						crosshairs: {
							show: false,
						}
					},
					yaxis: {
						opposite: true,
						labels: {
							offsetX: 0,
							style: {
								colors: 'var(--bs-body-color)',
								fontSize: '12px',
								fontFamily: 'var(--bs-body-font-family)',
								cssClass: 'apexcharts-yaxis-label',
							},
						},
					},
					fill: {
						opacity: 1,
						colors:['#61C277', '#FF3E3E'],
					},
					tooltip: {
						x: {
							format: 'dd/MM/yy HH:mm'
						},
						y: {
							formatter: function (val) {
								return "$ " + val + " thousands"
							}
						}
					},
					responsive: [{
						breakpoint: 575,
						options: {
							series: [{
								name: 'Buy',
								data: [{
									x: '2:00PM',
									y: [9200.00, 9600.00]
								}, {
									x: '2:30PM',
									y: [9300.00, 9600.00]
								}, {
									x: '3:00PM',
									y: [9150.00, 9500.00]
								}, {
									x: '3:30PM',
									y: [9300.00, 9700.00]
								}, {
									x: '4:00PM',
									y: [9200.00, 9600.00]
								}, {
									x: '4:30PM',
									y: [9400.00, 9700.00]
								}, {
									x: '5:00PM',
									y: [9400.00, 9600.00]
								}, {
									x: '5:30PM',
									y: [9300.00, 9600.00]
								}]
							},
							{
								name: 'Sell',
								data: [{
									x: '2:00PM',
									y: [9370.00, 9550.00]
								}, {
									x: '2:30PM',
									y: [9350.00, 9700.50]
								}, {
									x: '3:00PM',
									y: [9275.00, 9482.00]
								}, {
									x: '3:30PM',
									y: [9200.00, 9600.00]
								}, {
									x: '4:00PM',
									y: [9250.00, 9500.00]
								}, {
									x: '4:30PM',
									y: [9445.00, 9523.00]
								}, {
									x: '5:00PM',
									y: [9440.00, 9667.00]
								}, {
									x: '5:30PM',
									y: [9300.00, 9600.00]
								}]
							}],
							plotOptions: {
								bar: {
									columnWidth: '40%',	
								},
							},
							chart:{
								height:250,
							},
							xaxis: {
								labels: {
									style: {
										fontSize: '10px',
									},
								},
							},
						}
					}]
				};

				var chart = new ApexCharts(rangeBar, options);
				chart.render();
			}
		}
		
		const ApexBubbleCharts = function () {
			const bubbleCharts = document.querySelector("#ApexBubbleCharts");
			if (bubbleCharts) {
				var options = {
					series: [
						{
							name: 'Bubble1',
							data: [
								[20, 30, 40],
								[50, 47, 23],
								[34, 30, 59],
								[98, 16, 57],
								[62, 30, 40],
								[42, 35, 30]
							]
						},
						{
							name: 'Bubble2',
							data: [
								[50, 55, 30],
								[12, 15, 23],
								[30, 10, 59],
								[15, 55, 57],
								[40, 35, 40],
								[60, 55, 30]
							]
						},
						{
							name: 'Bubble3',
							data: [
								[20, 45, 20],
								[10, 35, 70],
								[15, 35, 59],
								[65, 10, 57],
								[40, 55, 40],
								[20, 35, 30]
							]
						}
					],
					chart: {
						height: 350,
						type: 'bubble',
						toolbar: {
							show: false,
						},
					},
					dataLabels: {
						enabled: false
					},
					fill: {
						opacity: 0.8
					},
					xaxis: {
						tickAmount: 12,
						type: 'category',
						crosshairs: {
							show: false,
						}
					},
					yaxis: {
						max: 70
					}
				};

				var chart = new ApexCharts(bubbleCharts, options);
				chart.render();
			}
		}
		
		const ApexRadarCharts = function () {
			const radarCharts = document.querySelector("#ApexRadarCharts");
			if (radarCharts) {
				var options = {
					series: [
						{
							name: 'Series 1',
							data: [20, 100, 40, 30, 50, 80, 33],
						}
					],
					chart: {
						height: 350,
						type: 'radar',
						toolbar: {
							show: false,
						},
					},
					dataLabels: {
						enabled: true
					},
					plotOptions: {
						radar: {
							size: 140,
							polygons: {
								strokeColors: 'var(--bs-border-color)',
								fill: {
									colors: ['var(--bs-light)', 'var(--bs-body-bg)']
								}
							}
						}
					},
					colors: ['#F44336'],
					markers: {
						size: 4,
						colors: ['var(--bs-body-bg)'],
						strokeColor: 'var(--bs-border-color)',
						strokeWidth: 2,
					},
					tooltip: {
						y: {
							formatter: function(val) {
								return val
							}
						}
					},
					xaxis: {
						categories: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
					},
					yaxis: {
						labels: {
							formatter: function(val, i) {
								if (i % 2 === 0) {
									return val
								} else {
									return ''
								}
							}
						}
					}
				};

				var chart = new ApexCharts(radarCharts, options);
				chart.render();
			}
		}

        
        return {
            init: function () {
                ApexMixedCharts();
				ApexAreaCharts();
				ApexRangeBar();
				ApexBubbleCharts();
				ApexRadarCharts();
            },

            load: function () {
				
            },

            resize: function () {
				
            }
        };

    })();

    document.addEventListener('DOMContentLoaded', function () {
        apexChart.init();
    });

    window.addEventListener('load', function () {
        
    });

    window.addEventListener('resize', function () {
        
    });

})();