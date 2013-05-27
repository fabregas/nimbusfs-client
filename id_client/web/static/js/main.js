
function mkbr(message) {
    return message.replace(/\n/g, "<br/>")
}

function load_menu() {
    $.getJSON('/get_menu', function(data) {
          var items = [];

          $.globals.version = data['version'];
           
            // {url: Label}
          $.each(data['menu'], function(key, val) {
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

    hide_help();
    $.get('/get_page/'+path+'.html', function(data) {
        $(base_e).html(data); 
        load_help();
    }).fail(function() { 
        var fail_html = '<div class="hero-unit"><h1 class="text-error">Internal server error!</h1><p class="text-error">Page /get_page/'+
            path+'.html does not loaded...</p></div>'
        $(base_e).html(fail_html); });
}

function show_help() {
    if ($('.popover').is(':visible')) {
        $('.help').popover('hide'); 
    } else {
        //$('.help').popover({html: true}); 
        $('.help').popover($.extend({}, {title: 'ffff'}, {html:true})).popover('show');
    }
}

function hide_help() {
    if ($('.popover').is(':visible')) {
        $('.help').popover('hide'); 
    }
}

function load_help() {
    var page_id = $('#menu li[class=active]').attr('id');
    $.get('/get_page/help_'+page_id+'.html', function(data) {
        $('.help').attr('data-content', data);
    }).fail(function() {
        $('.help').attr('data-content', 'Error! Help does not loaded...');
    });
}


$(function () {
    $.globals = {
        version: 'unknown'
    }
    $('body').on('click', function(event) {
        if (!$(event.target).hasClass('help')) {
            hide_help();
        }
    });

    load_menu();
});
