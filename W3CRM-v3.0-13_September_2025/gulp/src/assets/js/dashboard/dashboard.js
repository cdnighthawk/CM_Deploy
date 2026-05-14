(function($) {
	
    /* "use strict" */
	var dzDashboard = function(){
		
		var screenWidth = $(window).width();
	
		var NewCustomers = function(){
			if(jQuery("#NewCustomers").length>0) {
				var options = {
					series: [{
						name: 'Net Profit',
						data: [100,300, 200, 250, 200, 240, 180,230,200, 250, 300],
					},],
					chart: {
						type: 'area',
						height: 40,
						toolbar: {
							show: false,
						},
						zoom: {
							enabled: false
						},
						sparkline: {
							enabled: true
						}
					},
					colors:['var(--bs-primary)'],
					dataLabels: {
						enabled: false,
					},
					legend: {
						show: false,
					},
					stroke: {
						show: true,
						width: 2,
						curve:'straight',
						colors:['var(--bs-primary)'],
					},
					grid: {
						show:false,
						borderColor: '#eee',
						padding: {
							top: 0,
							right: 0,
							bottom: 0,
							left: -1
						}
					},
					states: {
						normal: {
							filter: {
								type: 'none',
								value: 0
							}
						},
						hover: {
							filter: {
								type: 'none',
								value: 0
							}
						},
						active: {
							allowMultipleDataPointsSelection: false,
							filter: {
								type: 'none',
								value: 0
							}
						}
					},
					xaxis: {
						categories: ['Jan', 'feb', 'Mar', 'Apr', 'May', 'June', 'July','August', 'Sept','Oct'],
						axisBorder: {
							show: false,
						},
						axisTicks: {
							show: false
						},
						labels: {
							show: false,
							style: {
								fontSize: '12px',

							}
						},
						crosshairs: {
							show: false,
							position: 'front',
							stroke: {
								width: 1,
								dashArray: 3
							}
						},
						tooltip: {
							enabled: true,
							formatter: undefined,
							offsetY: 0,
							style: {
								fontSize: '12px',
							}
						}
					},
					yaxis: {
						show: false,
					},
					fill: {
						opacity: 0.9,
						colors:'var(--bs-primary)',
						type: 'gradient', 
						gradient: {
							colorStops:[{
								offset: 0,
								color: 'var(--bs-primary)',
								opacity: .4
							},
							{
								offset: 0.6,
								color: 'var(--bs-primary)',
								opacity: .4
							},
							{
								offset: 100,
								color: 'white',
								opacity: 0
							}
						],}
					},
					tooltip: {
						enabled:false,
						style: {
							fontSize: '12px',
						},
						y: {
							formatter: function(val) {
								return "$" + val + " thousands"
							}
						}
					}
				};

				var chartBar1 = new ApexCharts(document.querySelector("#NewCustomers"), options);
				chartBar1.render();
			}
		}
		
		var NewExperience = function(){
			if(jQuery("#NewExperience").length>0) {
				var options = {
					series: [
						{
							name: 'Net Profit',
							data: [100,300, 200, 250, 200, 240, 180,230,200, 250, 300],
						}, 				
					],
					chart: {
						type: 'area',
						height: 40,
						toolbar: {
							show: false,
						},
						zoom: {
							enabled: false
						},
						sparkline: {
							enabled: true
						}
						
					},
					colors:['var(--bs-danger)'],
					dataLabels: {
						enabled: false,
					},
					legend: {
						show: false,
					},
					stroke: {
						show: true,
						width: 2,
						curve:'straight',
						colors:['var(--bs-danger)'],
					},
					grid: {
						show:false,
						borderColor: '#eee',
						padding: {
							top: 0,
							right: 0,
							bottom: 0,
							left: -1
						}
					},
					states: {
						normal: {
							filter: {
								type: 'none',
								value: 0
							}
						},
						hover: {
							filter: {
								type: 'none',
								value: 0
							}
						},
						active: {
							allowMultipleDataPointsSelection: false,
							filter: {
								type: 'none',
								value: 0
							}
						}
					},
					xaxis: {
						categories: ['Jan', 'feb', 'Mar', 'Apr', 'May', 'June', 'July','August', 'Sept','Oct'],
						axisBorder: {
							show: false,
						},
						axisTicks: {
							show: false
						},
						labels: {
							show: false,
							style: {
								fontSize: '12px',
							}
						},
						crosshairs: {
							show: false,
							position: 'front',
							stroke: {
								width: 1,
								dashArray: 3
							}
						},
						tooltip: {
							enabled: true,
							formatter: undefined,
							offsetY: 0,
							style: {
								fontSize: '12px',
							}
						}
					},
					yaxis: {
						show: false,
					},
					fill: {
						opacity: 0.9,
						colors:'var(--bs-danger)',
						type: 'gradient', 
						gradient: {
						colorStops:[	
							{
								offset: 0,
								color: 'var(--bs-danger)',
								opacity: .5
							},
							{
								offset: 0.6,
								color: 'var(--bs-danger)',
								opacity: .5
							},
							{
								offset: 100,
								color: 'white',
								opacity: 0
							}
						],}
					},
					tooltip: {
						enabled:false,
						style: {
							fontSize: '12px',
						},
						y: {
							formatter: function(val) {
								return "$" + val + " thousands"
							}
						}
					}
				};

				var chartBar1 = new ApexCharts(document.querySelector("#NewExperience"), options);
				chartBar1.render();	
			}
		}
	
		var AllProject = function(){
			if(jQuery("#AllProject").length>0) {
				var options = {
					series: [12, 30, 20],
					chart: {
						type: 'donut',
						width: 150,
					},
					plotOptions: {
						pie: {
							donut: {
								size: '80%',
								labels: {
									show: true,
									name: {
										show: true,
										offsetY: 12,
										color: 'var(--bs-body-color)',
									},
									value: {
										show: true,
										fontSize: '22px',
										fontFamily:'Arial',
										fontWeight:'500',
										offsetY: -17,
										color: 'var(--bs-body-color)'
									},
									total: {
										show: true,
										fontSize: '11px',
										fontWeight:'500',
										fontFamily:'Arial',
										label: 'Compete',
										color: 'var(--bs-body-color)',
									   
										formatter: function (w) {
											return w.globals.seriesTotals.reduce((a, b) => {
												return a + b
											}, 0)
										}
									}
								}
							}
						}
					},
					stroke: {
						show: true,
						width: 2,
						colors: ['var(--bs-body-bg)'],
					},
					legend: {
						show: false,
					},
					colors: ['var(--bs-success)', 'var(--bs-primary)', 'var(--bs-secondary)'],
					labels: ["Compete", "Pending", "Not Start"],
					dataLabels: {
						enabled: false,
					},
				};
				var chartBar1 = new ApexCharts(document.querySelector("#AllProject"), options);
				chartBar1.render();
			}
		}
	
		var overviewChart = function(){
			if(jQuery("#overiewChart").length>0) {
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
						height: 300,
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
						fontFamily: 'poppins',
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
									color: 'var(--bs-primary)',
									opacity: 1
								},{
									offset: 100,
									color: 'var(--bs-primary)',
									opacity: 1
								}],
								[{
									offset: 0,
									color: '#3AC977',
									opacity: 1
								},{
									offset: 0.4,
									color: '#3AC977',
									opacity: .15
								},{
									offset: 100,
									color: '#3AC977',
									opacity: 0
								}],
								[{
									offset: 0,
									color: '#FF5E5E',
									opacity: 1
								},{
									offset: 100,
									color: '#FF5E5E',
									opacity: 1
								}],
							],
							stops: [0, 100, 100, 100]
						}
					},
					colors:[
						"var(--bs-primary)", "var(--bs-success)", "var(--bs-danger)"
					],
					labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
					markers: {
						size: 0
					},
					xaxis: {
						type: 'month',
						labels: {
							style: {
							   fontSize: '13px',
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
								fontSize: '13px',
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

				var chart = new ApexCharts(document.querySelector("#overiewChart"), options);
				chart.render();
				
				$(".mix-chart-tab .nav-link").on('click',function(){
					var seriesType = $(this).attr('data-series');
					var columnData = [];
					var areaData = [];
					var lineData = [];
					switch(seriesType) {
						case "week":
							columnData = [75, 85, 72, 100, 50, 100, 80, 75, 95, 35, 75,100];
							areaData = [44, 65, 55, 75, 45, 55, 40, 60, 75, 45, 50,42];
							lineData = [30, 25, 45, 30, 25, 35, 20, 45, 35, 20, 35,20];
							break;
						case "month":
							columnData = [20, 50, 80, 52, 10, 80, 50, 30, 95, 10, 60,85];
							areaData = [40, 25, 85, 45, 85, 25, 95, 65, 45, 45, 20,12];
							lineData = [65, 45, 25, 65, 45, 25, 75, 35, 65, 75, 15,65];
							
							break;
						case "year":
							columnData = [30, 20, 80, 52, 10, 90, 50, 30, 95, 20, 60,85];
							areaData = [40, 25, 40, 45, 85, 25, 50, 65, 45, 60, 20,12];
							lineData = [65, 45, 30, 65, 45, 25, 75, 40, 65, 50, 15,65];
							break;
						case "all":
							columnData = [20, 50, 80, 60, 10, 80, 50, 40, 95, 20, 60,85];
							areaData = [40, 25, 30, 45, 85, 25, 95, 65, 50, 45, 20,12];
							lineData = [65, 45, 25, 65, 45, 25, 30, 35, 65, 75, 15,65];
							break;
						default:
							columnData = [75, 80, 72, 100, 50, 100, 80, 30, 95, 35, 75,100];
							areaData = [44, 65, 55, 75, 45, 55, 40, 60, 75, 45, 50,42];
							lineData = [30, 25, 45, 30, 25, 35, 20, 45, 35, 30, 35,20];
					}
					chart.updateSeries([
						{
							name: "Number of Projects",
							type: 'column',
							data: columnData
						},{
							name: 'Revenue',
							type: 'area',
							data: areaData
						},{
							name: 'Active Projects',
							type: 'line',
							data: lineData
						}
					]);
				})
			}
		}
	
		var earningChart = function(){
			if(jQuery("#earningChart").length>0) {
				var chartWidth = $("#earningChart").width();
			
				var options = {
					series: [
						{
							name: 'Net Profit',
							data: [700, 650, 680, 600, 700, 610, 710, 620],
						},
					],
					chart: {
						type: 'area',
						height: 350,
						width: chartWidth + 60,
						toolbar: {
							show: false,
						},
						offsetX: -50,
						zoom: {
							enabled: false
						},
					},
					colors: ['var(--bs-primary)'],
					dataLabels: {
						enabled: false,
					},
					legend: {
						show: false,
					},
					stroke: {
						show: true,
						width: 2,
						curve: 'straight',
						colors: ['var(--bs-primary)'],
					},
					grid: {
						show: true,
						borderColor: 'var(--bs-border-color)',

						xaxis: {
							lines: {
								show: true
							}
						},
						yaxis: {
							lines: {
								show: false
							}
						},
					},
					yaxis: {
						show: true,
						tickAmount: 4,
						min: 0,
						max: 800,
						labels: {
							offsetX: 50,
							style: {
								colors: 'var(--bs-body-color)',
								fontSize: '12px'
							}
						}
					},
					xaxis: {
						categories: ['', 'May', 'June', 'July', 'Aug', 'Sep', 'Oct'],
						overwriteCategories: undefined,
						
						axisBorder: {
							show: false,
						},
						axisTicks: {
							show: false
						},
						labels: {
							show: true,
							offsetX: 5,
							style: {
								fontSize: '12px',
								colors: 'var(--bs-body-color)' // X-axis label color
							}
						},
					},
					fill: {
						opacity: 0.5,
						colors: 'var(--bs-primary)',
						type: 'gradient',
						gradient: {
							colorStops: [
								{
									offset: 0.6,
									color: 'var(--bs-primary)',
									opacity: 0.2
								},
								{
									offset: 0.6,
									color: 'var(--bs-primary)',
									opacity: 0.15
								},
								{
									offset: 100,
									color: 'white',
									opacity: 0
								}
							],
						}
					},
					tooltip: {
						enabled: true,
						style: {
							fontSize: '12px',
						},
						y: {
							formatter: function (val) {
								return "$" + val + ""
							}
						}
					}
				};

				var chartBar1 = new ApexCharts(document.querySelector("#earningChart"), options);
				chartBar1.render();
				
				$(".earning-chart .nav-link").on('click',function(){
					var seriesType = $(this).attr('data-series');
					var columnData = [];
					switch(seriesType) {
						case "day":
							columnData = [700,650, 680, 650, 700, 610,710,620];
							break;
						case "week":
							columnData = [700,700, 680, 600, 700, 620,710,620];
							break;
						case "month":
							columnData = [700,650, 690, 640, 700, 670,710,620];
							break;
						case "year":
							columnData = [700,650, 590, 650, 700, 610,710,630];
							break;
						default:
							columnData = [700,650, 680, 650, 700, 610,710,620];
					}
					chartBar1.updateSeries([
						{
							name: "Net Profit",
							data: columnData
						}
					]);
				})
			}
		}
		
		var projectChart = function(){
			if(jQuery("#projectChart").length>0) {
				var options = {
					series: [30, 40, 20, 10],
					chart: {
						type: 'donut',
						width: 250,
					},
					plotOptions: {
						pie: {
							donut: {
								size: '90%',
								labels: {
									show: true,
									name: {
										show: true,
										offsetY: 12,
										color: 'var(--bs-body-color)',
									},
									value: {
										show: true,
										fontSize: '24px',
										fontFamily:'Arial',
										fontWeight:'500',
										offsetY: -17,
										color: 'var(--bs-heading-color)',
									},
									total: {
										show: true,
										fontSize: '11px',
										fontWeight:'500',
										fontFamily:'Arial',
										label: 'Total projects',
										color: 'var(--bs-body-color)',
									   
										formatter: function (w) {
											return w.globals.seriesTotals.reduce((a, b) => {
												return a + b
											}, 0)
										}
									}
								}
							}
						}
					},
					stroke: {
						show: true,
						width: 2,
						colors: ['var(--bs-body-bg)'],
					},
					legend: {
						show: false,
					},
					colors: ['var(--bs-warning)', 'var(--bs-primary)', 'var(--bs-success)', 'var(--bs-danger)'],
					labels: ["Pending", "Completed", "Progress", "Cancelled"],
					dataLabels: {
						enabled: false,
					},
				};
				var chartBar1 = new ApexCharts(document.querySelector("#projectChart"), options);
				chartBar1.render();
			}
		}
		
		var handleWorldMap = function(trigger = 'load'){
			if(jQuery("#world-map").length>0) {
				var vmapSelector = $('#world-map');
				if(trigger == 'resize')
				{
					vmapSelector.empty();
					vmapSelector.removeAttr('style');
				}
				
				vmapSelector.delay( 500 ).unbind().vectorMap({ 
					map: 'world_en',
					backgroundColor: 'transparent',
					borderColor: 'rgb(239, 242, 244)',
					borderOpacity: 0.25,
					borderWidth: 1,
					color: 'rgb(239, 242, 244)',
					enableZoom: true,
					hoverColor: 'rgba(239, 242, 244 0.9)',
					hoverOpacity: null,
					normalizeFunction: 'linear',
					scaleColors: ['#b6d6ff', '#005ace'],
					selectedColor: 'rgba(239, 242, 244 0.9)',
					selectedRegions: null,
					showTooltip: true,
					onRegionClick: function(element, code, region)
					{
						var message = 'You clicked "'
							+ region
							+ '" which has the code: '
							+ code.toUpperCase();
				 
						alert(message);
					}
				});
			}
		}
	
		var tableEempoloyees = function(){
			if(jQuery("#empoloyees-tbl").length>0) {				
				var table = $('#empoloyees-tbl').DataTable({
					'dom': 'ZBfrltip',
					buttons: [{
						extend: 'excel',
						text: '<i class="fa-solid fa-file-excel"></i> Export Report',
						className: 'btn btn-primary light btn-sm'
					}],
					searching: false,
					select: false,   
					pageLength: 5,			
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}
					},
					initComplete: function() {
						var btns = $('#empoloyees-tbl_wrapper .dt-buttons').detach();
						$('#tableEmpoloyeesExcelBTN').append(btns);
					}
				});
			}
		}
		
		var handleDateTimePicker = function(){
			if(jQuery("#datetimepicker").length>0) {
				$('#datetimepicker').datetimepicker({
					inline: true,
				});
			}
		}
		
		var handleReportsTable = function(){
			if(jQuery("#reportsTable").length>0) {				
				var reportsTable = $('#reportsTable').DataTable({
					'dom': 'frtip',
					buttons: false,
					searching: false,
					select: false,   
					lengthChange: false,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}
					},
				});
			}
		}
		
		var handleFinanceTable = function(){
			if(jQuery('#financeTable').length > 0){				
				var table = $('#financeTable').DataTable({
					'dom': 'ZBfrltip',
					buttons: [{
						extend: 'excel',
						text: '<i class="fa-solid fa-file-excel"></i> Export Report',
						className: 'btn btn-primary light btn-sm'
					}],
					searching: false,
					select: false,   
					pageLength: 10,
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}
						
					},
					initComplete: function() {
						var btns = $('#financeTable_wrapper .dt-buttons').detach();
						$('#financeTableExcelBTN').append(btns);
					}
				});
			}
		}
		
		var handlePerformanceTable = function(){
			if(jQuery('#performanceTable').length > 0){
				var empoloyeesTable = $('#performanceTable').DataTable({
					'dom': 'frtip',
					buttons: false,
					searching: false,
					select: false,
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}
					},
				});
			}
		}
		
		var handleManagementTable = function(){
			if(jQuery('#managementTable').length > 0){
				var empoloyeesTable = $('#managementTable').DataTable({
					'dom': 'frtip',
					buttons: false,
					searching: false,
					pageLength:5,
					select: false,            
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}			
					},
				});
			}
		}
		
		var handleRejectionsTable = function(){
			if(jQuery('#rejectionsTable').length > 0){
				var empoloyeesTable = $('#rejectionsTable').DataTable({
					'dom': 'frtip',
					buttons: false,
					searching: false,
					pageLength:5,
					select: false,            
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}			
					},
				});
			}
		}
		
		var handlePaymentHistoryTable = function(){
			if(jQuery('#paymentHistoryTable').length > 0){
				var table = $('#paymentHistoryTable').DataTable({
					'dom': 'frtip',
					buttons: false,
					searching: false,
					select: false,   
					pageLength: 6,			
					lengthChange: false,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}
					},
				});
			}
		}
		
		var handleContactsTable = function(){
			if(jQuery('#contactsTable').length > 0){
				var table = $('#contactsTable').DataTable({
					'dom': 'ZBfrltip',
					buttons: [{
						extend: 'excel',
						text: '<i class="fa-solid fa-file-excel"></i> Export Report',
						className: 'btn btn-primary light btn-sm'
					}],
					searching: true,
					select: false,   
					pageLength:9,			
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						},
						'search' : '',
						searchPlaceholder: "Search..."
					},
					initComplete: function() {
						var btns = $('#contactsTable_wrapper .dt-buttons').detach();
						var filter = $('#contactsTable_wrapper .dataTables_filter').detach();
						$('#tableContactsExcelBTN').append(btns);
						$('#tableContactsFilter').append(filter);
						$('#tableContactsFilter label').addClass('mb-0');
					}
				});
			}
		}
		
		var handleCustomerTable = function(){
			if(jQuery('#customerTable').length > 0){
				var table = $('#customerTable').DataTable({
					'dom': 'ZBfrltip',
					buttons: [{
						extend: 'excel',
						text: '<i class="fa-solid fa-file-excel"></i> Export Report',
						className: 'btn btn-primary light btn-sm'
					}],
					searching: true,
					select: false,   
					pageLength:9,			
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						},
						'search' : '',
						searchPlaceholder: "Search..."
					},
					initComplete: function() {
						var btns = $('#customerTable_wrapper .dt-buttons').detach();
						var filter = $('#customerTable_wrapper .dataTables_filter').detach();
						$('#tableCustomerExcelBTN').append(btns);
						$('#tableCustomerFilter').append(filter);
						
						$('#tableCustomerFilter label').addClass('mb-0');
					}
				});
			}
		}
		
		var handleUserTable = function(){
			if(jQuery('#userTable').length > 0){
				var table = $('#userTable').DataTable({
					'dom': 'ZBfrltip',
					buttons: [{
						extend: 'excel',
						text: '<i class="fa-solid fa-file-excel"></i> Export Report',
						className: 'btn btn-primary light btn-sm'
					}],
					searching: false,
					pageLength: 12,
					select: false,
					lengthChange: false,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						},
						searchPlaceholder: "Search..."
					},
					initComplete: function() {
						var btns = $('#userTable_wrapper .dt-buttons').detach();
						$('#tableUserExcelBTN').append(btns);
					}
				});
			}
		}
		
		var handleTaskTable = function(){
			if(jQuery('#taskTable').length > 0){
				var table = $('#taskTable').DataTable({
					'dom': 'ZBfrltip',
					buttons: [{
						extend: 'excel',
						text: '<i class="fa-solid fa-file-excel"></i> Export Report',
						className: 'btn btn-primary light btn-sm'
					}],
					searching: false,
					select: false,   
					lengthChange: false,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}
					},
					initComplete: function() {
						var btns = $('#taskTable_wrapper .dt-buttons').detach();
						$('#tableEmpoloyeesTBL1ExcelBTN').append(btns);
					}
				});
			}
		}
		
		var handleManageClientTable = function(){
			if(jQuery('#manageClientTable').length > 0){
				var reportsTable = $('#manageClientTable').DataTable({
					'dom': 'ZBfrltip',
					buttons: [{
						extend: 'excel', text: '<i class="fa-solid fa-file-excel"></i> Export Report',
						className: 'btn btn-primary light btn-sm'
					}],
					searching: true,
					select: false,
					pageLength: 8,
					lengthChange: false,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}
					},
					initComplete: function() {
						var btns = $('#manageClientTable_wrapper .dt-buttons').detach();
						$('#tableManageClientExcelBTN').append(btns);
					}
				});
				
				$('#manageClientTable_filter').hide();
				
				// apply filters when button is clicked
				$('#applyFilter').on('click', function() {
					var status = $('#statusFilter').val().trim();
					var searchFilter = $('#searchFilter').val().trim();
					var gender = $('#genderFilter').val().trim();
					var location = $('#locationFilter').val().trim();

					// Apply filters only if values exist
					reportsTable.search(searchFilter || '', false, false);
					reportsTable.column(3).search(gender ? '^' + gender + '$' : '', true, false);
					reportsTable.column(4).search(location ? '^' + location + '$' : '', true, false);
					reportsTable.column(5).search(status ? '^' + status + '$' : '', true, false);
					reportsTable.draw();
				});
				$('#resetFilter').on('click', function() {
					$('#statusFilter, #searchFilter, #genderFilter, #locationFilter').val('');
					reportsTable.search('').columns().search('').draw();
				});
			}
		}
		
		var handleEmployeesTable = function(){
			if(jQuery('#employeesTable').length > 0){
				var empoloyeesTable = $('#employeesTable').DataTable({
					dom: 'Bfrtip',
					buttons: [{
						extend: 'excel', text: '<i class="fa-solid fa-file-excel"></i> Export Report',
							className: 'btn btn-primary light btn-sm'
						}
					],
					searching: true,
					select: false,
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}
					},
					initComplete: function() {
						var btns = $('#employeesTable_wrapper .dt-buttons').detach();
						$('#employeesTableExcelBTN').append(btns);
					}
				});
				$('#employeesTable_filter').hide();
				
				// apply filters when button is clicked
				$('#applyFilter').on('click', function() {
					var status = $('#statusFilter').val().trim();
					var searchFilter = $('#searchFilter').val().trim();
					var gender = $('#genderFilter').val().trim();
					var department = $('#departmentFilter').val().trim();
					var location = $('#locationFilter').val().trim();
				
					// Apply filters only if values exist
					empoloyeesTable.column(7).search(status ? '^' + status + '$' : '', true, false);
					empoloyeesTable.search(searchFilter || '', false, false);
					empoloyeesTable.column(5).search(gender ? '^' + gender + '$' : '', true, false);
					empoloyeesTable.column(6).search(location ? '^' + location + '$' : '', true, false);
					empoloyeesTable.column(2).search(department || '', false, false);
					empoloyeesTable.draw();
				});
				$('#resetFilter').on('click', function() {
					$('#statusFilter, #searchFilter, #genderFilter, #departmentFilter, #locationFilter').val('');
					empoloyeesTable.search('').columns().search('').draw();
				});
			}
		}
		
		var handleProductsTable = function(){
			if(jQuery('#productsTable').length > 0){
				var table = $('#productsTable').DataTable({
					searching: false,
					select: false,
					pageLength: 7,
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}
					},
				});
			}
		}
		
		var handleProjectsTable = function(){
			if(jQuery('#projectsTable').length > 0){
				var table = $('#projectsTable').DataTable({
					'dom': 'ZBfrltip',
					buttons: [{
						extend: 'excel',
						text: '<i class="fa-solid fa-file-excel"></i> Export Report',
						className: 'btn btn-primary light btn-sm'
					}],
					searching: false,
					pageLength:5,
					select: false,            
					lengthChange:false ,
					language: {
						paginate: {
							next: '<i class="fa-solid fa-angle-right"></i>',
							previous: '<i class="fa-solid fa-angle-left"></i>' 
						}			
					},
					initComplete: function() {
						var btns = $('#projectsTable_wrapper .dt-buttons').detach();
						$('#tableProjectsExcelBTN').append(btns);
					}		
				});

			}
		}
			
		/* Function ============ */
		return {
			init:function(){
				handleDateTimePicker();
				tableEempoloyees();
				NewCustomers();
				NewExperience();
				AllProject();
				overviewChart();
				projectChart();
				handleReportsTable();
				handleFinanceTable();
				handlePerformanceTable();
				handleManagementTable();
				handleRejectionsTable();
				handlePaymentHistoryTable();
				handleContactsTable();
				handleCustomerTable();
				handleUserTable();
				handleTaskTable();
				handleManageClientTable();
				handleEmployeesTable();
				handleProductsTable();
				handleProjectsTable();
				earningChart();
			},
			
			load:function(){
				handleWorldMap();
			},
			
			resize:function(){
				handleWorldMap();
			}
		}
	
	}();
	
	jQuery(document).ready(function() {
		dzDashboard.init();
	});

	jQuery(window).on('load',function(){
		setTimeout(function(){
			dzDashboard.load();
		}, 1000);
	});
	
	jQuery(window).on('resize',function () {
		dzDashboard.resize();
	});
	
})(jQuery);