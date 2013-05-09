
function load_menu() {
    $.getJSON('/get_menu', function(data) {
          var items = [];
           
            // {url: Label}
          $.each(data, function(key, val) {
                var is_act = '';
                if (window.location.pathname == '/'+val[0]) {
                    is_act = ' class="active"'
                }
                $('#menu').append('<li'+is_act+' id="'+val[0]+'"><a onclick="load_content(\''+val[0]+'\');">'+val[1]+'</a></li>');
          });

          if ($('#menu li[class="active"]')[0] === undefined) {
            $('#menu li').first().addClass("active");
          }
        
          load_content($('#menu li[class="active"]').first().attr('id'));
    });
}

function load_content(path) {
    $('#menu li').each(function(index) {$(this).removeClass("active");});
    $('#'+path).first().addClass("active");

    var base_e;
    if (window.location.href.indexOf('?content_only') != -1) {
        base_e = '#wind';
        $('#wind').html('');
    } else {
        base_e = '.main_content';
    }

    $.get('/get_page/'+path+'.html', function(data) {
        $(base_e).html(data); 
    }).fail(function() { 
        var fail_html = '<div class="hero-unit"><h1 class="text-error">Internal server error!</h1><p class="text-error">Page /get_page/'+
            path+'.html does not loaded...</p></div>'
        $(base_e).html(fail_html); });
}

$(function () {
    load_menu();
});
