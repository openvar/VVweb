
$(document).ready(function() {

    console.log("Hello");
    var variant_examples = function() {
        $('.variant-example').each(function (i, val) {
            $(this).on("click", function (evt) {
                evt.preventDefault();
                var genome = $(this).data()['genome'];
                $('#variant_id').val($(this).text());
                $('input[name=genomebuild][value=' + genome + ']').prop('checked', true);
                $('#validate-btn').focus();

            });
        });
    };

    variant_examples();

    $('#validate-btn .spinner-border').hide();

    $('#validate-btn').on("click", function() {
        if ($('#variant_id').val()){
            console.log("Clicked validate button");
            $('.overlay').show();
            $('.loading').show();
        }
    });

    $('#g2t-btn').on("click", function() {
        if ($('#symbol_id').val()){
            console.log("Clicked validate button");
            $('.overlay').show();
            $('.loading').show();
        }
    });

    var validate_tabs = function() {

        $('#myTab a').on('click', function (e) {
            e.preventDefault();
            console.log('clicked on a tab!');
            $(this).tab('show');
        });

        $('#myTab li:first-child a').tab('show'); // Select first tab

        var numberSelected = 0;
        if ($('.res-checkbox').length) {
            $('#results').hide();
        }

        $('.res-checkbox').each(function () {
            var tabid = $(this).data()['tabid'] + '-tab';
            var tab = $('#' + tabid + '');
            tab.hide();
            $(this).change(function (evt) {
                if (this.checked) {
                    numberSelected += 1;
                    tab.show();
                    tab.tab('show');
                } else {
                    numberSelected -= 1;
                    tab.hide();
                    $('#myTab a:visible').eq(0).tab('show'); // Select first visible tab
                }
                if (numberSelected > 0) {
                    $('#results').show();
                } else {
                    $('#results').hide();
                }
            })
        });
    };

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

    var ajax_messages = function() {
        console.log("Changing message text");
        let num = $('#msg-valnum').text();
        num = parseInt(num);
        let newcounter = num - 1;
        if (newcounter > 0) {
            $('#msg-valnum').text(newcounter);
        }else{
            $('.alert.alert-warning').addClass('alert-danger');
            $('#msg-body').html("Please <a href='/accounts/login/?next=/service/validate/' class='alert-link'>login</a> to continue using this service");
            $('#variant_id').val('').attr('disabled', 'disabled');
            $('#grch37').attr('disabled', 'disabled');
            $('#grch38').attr('disabled', 'disabled');
            $('#validate-btn').attr('disabled', 'disabled');
        }
    };


    $('#validate-form').on('submit', function(evt) {
        evt.preventDefault();
        let variant = $('#variant_id').val();
        let genome = $('#genomeselect input:checked').val();
        console.log(variant);
        console.log(genome);
        $.ajax({
            type: 'POST',
            url: '',
            data: {
                variant: variant,
                genomebuild: genome,
                csrfmiddlewaretoken: $('input[name=csrfmiddlewaretoken]').val()
            },
            timeout: 30000,
            success: function(res) {
                console.log('Success!');
                $('.overlay').hide();
                $('.loading').hide();
                // $.getScript('https://assets.varsome.com/static/components/components-bundle.js', function() {
                //     console.log('loaded!');
                // });
                $('#validate-results').html(res);
                // $('#validate-results').html(res);
                $('#myTab li:first-child a').tab('show'); // Select first tab
                window.scrollTo(0, 0);
                // $('#varsome-script').html('<script src="https://assets.varsome.com/static/components/components-bundle.js"></script>');
                // $('#validate-results script').each(function(i, element) {console.log(element.innerHTML); eval(element.innerHTML)});
                ajax_messages();
                variant_examples();
                validate_tabs();
            },
            error: function(xhr,errmsg,err) {
                console.log(errmsg);
                $('.overlay').hide();
                $('.loading').hide();
                if (errmsg === 'timeout') {
                    console.log("Need to show modal and suggest batch validation tool");
                    $('#timeoutModal').modal('show');
                }else {
                    console.log(err);
                    console.log(xhr.status + ": " + xhr.responseText);
                    let error_code = "<div class=\"row\">\n" +
                        "<div class=\"col-md-12 mb-5\">\n" +
                        "<h1>Error</h1>\n" +
                        "<p>Unable to validate the submitted variant <code>" + variant + "</code> against the " + genome + " assembly.</p>\n" +
                        "<p>Please check your submission and re-submit.</p>\n" +
                        "</div>\n" +
                        "</div>\n" +
                        "<hr>";
                    $('#validate-results').html(error_code);
                }
            }
        })
    });
});