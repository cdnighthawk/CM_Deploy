$(document).ready(function(){

	$('#bsMaterialDatePicker').bootstrapMaterialDatePicker({
		weekStart : 0,
		time: false
	});
	
	$('#bsMaterialTimePicker').bootstrapMaterialDatePicker({
		date: false
	});
	
	$('#bsDateFormat').bootstrapMaterialDatePicker({
		format : 'dddd DD MMMM YYYY - HH:mm'
	});
	
	$('#bsFrDateFormat').bootstrapMaterialDatePicker({
		format : 'DD/MM/YYYY HH:mm',
		lang : 'fr',
		weekStart : 1,
		cancelText : 'ANNULER'
	});
	
	$('#bsMinDate').bootstrapMaterialDatePicker({
		format : 'DD/MM/YYYY HH:mm',
		minDate : new Date()
	});
	
	$('#date-end').bootstrapMaterialDatePicker({
		weekStart : 0
	});
	$('#date-start').bootstrapMaterialDatePicker({
		weekStart : 0
	}).on('change', function(e, date){
		$('#date-end').bootstrapMaterialDatePicker('setMinDate', date);
	});

});