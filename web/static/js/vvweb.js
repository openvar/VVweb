
$(document).ready(function() {

    console.log("Hello");

    $('.variant-example').each( function(i, val){
        $(this).on("click", function(evt){
            evt.preventDefault();
            var genome = $(this).data()['genome'];
            $('#variant_id').val($(this).text());
            $('input[name=genomebuild][value=' + genome + ']').prop('checked', true);
            $('#validate-btn').focus();

        });
    });

    $('#validate-btn .spinner-border').hide();

    $('#validate-btn').on("click", function() {
        console.log("Clicked validate button");
        $('.overlay').show();
        $('.loading').show();
    });

    $('#myTab a').on('click', function (e) {
      e.preventDefault();
      console.log('clicked on a tab!');
      $(this).tab('show');
    });

    $('#myTab li:first-child a').tab('show'); // Select first tab

    var numberSelected = 0;
    if ($('.res-checkbox').length ){
        $('#results').hide();
    }

    $('.res-checkbox').each(function() {
        var tabid = $(this).data()['tabid'] + '-tab';
        var tab = $('#' + tabid + '');
        tab.hide();
        $(this).change(function(evt){
            if(this.checked) {
                numberSelected += 1;
                tab.show();
                tab.tab('show');
            }else{
                numberSelected -= 1;
                tab.hide();
                $('#myTab a:visible').eq(0).tab('show'); // Select first visible tab
            }
            if (numberSelected > 0 ){
                $('#results').show();
            }else{
                $('#results').hide();
            }
        })
    });

    // Going to find and deal with select genome errors

    $('.errorlist').each(function(){
        var neices = $(this).parent().siblings().find('.form-check-input');
        neices.each(function(){
            $(this).addClass('is-invalid');
        });
        console.log(neices);
    });

    $('.custom-file-input').on('change', function() {
       let fileName = $(this).val().split('\\').pop();
       $(this).next('.custom-file-label').addClass("selected").html(fileName);
    });
});