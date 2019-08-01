
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
    })


});