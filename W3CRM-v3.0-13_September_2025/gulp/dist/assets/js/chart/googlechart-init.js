document.addEventListener('DOMContentLoaded', function () {
	
	google.charts.load('current', {
		'packages': ['corechart', 'bar', 'line', 'geochart']
	});
	
	google.charts.setOnLoadCallback(() => {
		drawChart();
		drawColColors();
		drawLineColors();
		drawRegionsMap();
		googleAreaChart();
	});
	
	function drawChart() {
		const googlePieChart = document.getElementById('googlePieChart');
		if (!googlePieChart) return;
		
		var data = google.visualization.arrayToDataTable([
			['Task', 'Hours per Day'],
			['Work',     11],
			['Eat',      2],
			['Commute',  2],
			['Watch TV', 2],
			['Sleep',    7]
		]);
		
		var options = {
			title: 'My Daily Activities'
		};

		var chart = new google.visualization.PieChart(googlePieChart);
		chart.draw(data, options);
	}
	
	function drawColColors() {
		
		const googleColumnChart = document.getElementById('googleColumnChart');
		if (!googleColumnChart) return;
		
		var data = new google.visualization.DataTable();
		data.addColumn('timeofday', 'Time of Day');
		data.addColumn('number', 'Motivation Level');
		data.addColumn('number', 'Energy Level');

		data.addRows([
			[{v: [8, 0, 0], f: '8 am'}, 1, .25],
			[{v: [9, 0, 0], f: '9 am'}, 2, .5],
			[{v: [10, 0, 0], f:'10 am'}, 3, 1],
			[{v: [11, 0, 0], f: '11 am'}, 4, 2.25],
			[{v: [12, 0, 0], f: '12 pm'}, 5, 2.25],
			[{v: [13, 0, 0], f: '1 pm'}, 6, 3],
			[{v: [14, 0, 0], f: '2 pm'}, 7, 4],
			[{v: [15, 0, 0], f: '3 pm'}, 8, 5.25],
			[{v: [16, 0, 0], f: '4 pm'}, 9, 7.5],
			[{v: [17, 0, 0], f: '5 pm'}, 10, 10],
		]);

		var options = {
			title: 'Motivation and Energy Level Throughout the Day',
			colors: ['#9575cd', '#33ac71'],
			hAxis: {
				title: 'Time of Day',
				format: 'h:mm a',
				viewWindow: {
					min: [7, 30, 0],
					max: [17, 30, 0]
				}
			},
			vAxis: {
				title: 'Rating (scale of 1-10)'
			}
		};

		var chart = new google.visualization.ColumnChart(googleColumnChart);
		chart.draw(data, options);
	}
	
	function drawLineColors() {
		const googleLineChart = document.getElementById('googleLineChart');
		if (!googleLineChart) return;
		
		var data = google.visualization.arrayToDataTable([
			['Year', 'Sales', 'Expenses'],
			['2004',  1000,      400],
			['2005',  1170,      460],
			['2006',  660,       1120],
			['2007',  1030,      540]
		]);

		var options = {
			title: 'Company Performance',
			curveType: 'function',
			legend: { position: 'bottom' }
		};

		var chart = new google.visualization.LineChart(googleLineChart);
		chart.draw(data, options);
	}

	function drawRegionsMap() {
		const googleGeoChart = document.getElementById('googleGeoChart');
		if (!googleGeoChart) return;
		
		var data = google.visualization.arrayToDataTable([
			['Country', 'Popularity'],
			['Germany', 200],
			['United States', 300],
			['Brazil', 400],
			['Canada', 500],
			['France', 600],
			['RU', 700]
		]);

		var options = {};
		var chart = new google.visualization.GeoChart(googleGeoChart);
		chart.draw(data, options);
	}
	
	function googleAreaChart() {
		const googleAreaChart = document.getElementById('googleAreaChart');
		if (!googleAreaChart) return;
		
		var data = google.visualization.arrayToDataTable([
			['Year', 'Sales', 'Expenses'],
			['2013',  1000,      400],
			['2014',  1170,      460],
			['2015',  660,       1120],
			['2016',  1030,      540]
		]);

		var options = {
			title: 'Company Performance',
			hAxis: {title: 'Year',  titleTextStyle: {color: '#333'}},
			vAxis: {minValue: 0}
		};

		var chart = new google.visualization.AreaChart(googleAreaChart);
		chart.draw(data, options);
	}
	
});