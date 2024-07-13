import json5
import importlib
HAS_PYSCRIPT = importlib.util.find_spec('pyscript')

# got tired of using highcharts-core, ran into bugs and it was slow converting from python obj to js script

def get_chart_html(chart, target_div="container", files=[]):

    container_script = f"var container = querySelectorAllShadows('div#{target_div}'); container = container[container.length-1];\n"
    requirejs_header_script = ""
    requirejs_footer_script = ""
    hc_config_script = ""

    ###################
    # Only for .ipynb #
    ###################
    if not HAS_PYSCRIPT:
        requirejs_header_script = """
var has_requirejs = typeof requirejs !== 'undefined';
if (has_requirejs) {
    require.config({
        packages: [{name: 'highcharts', main: 'highcharts'}],
        paths: {'highcharts': 'https://code.highcharts.com/11.2.0/'}
    });
    require([
    'highcharts',
    'highcharts/modules/stock',
    'highcharts/highcharts-more',
    'highcharts/modules/exporting',
    'highcharts/modules/accessibility',
    ], function (Highcharts) {
"""

        requirejs_footer_script = """
    });
};
"""

        for file in files:
            with open(file) as f:
                hc_config_script = hc_config_script + f.read() + "\n"
    ###################

    if type(chart) == dict:
        hc_graph_script = "Highcharts.chart(container,\n" + json5.dumps(chart, indent="    ") + ", doubleclickzoomreset);\n"
        # dicts can only contain the js functions as a string, so remove the quote strings around the function
        hc_graph_script = hc_graph_script.replace('"FUNCTIONSTART','').replace('FUNCTIONEND"','').replace("\\n","\n")
    else: # highcharts_core.chart.Chart
        hc_graph_script = chart.to_js_literal()\
        .replace("Highcharts.chart(null","Highcharts.chart(container")\
        .replace("document.addEventListener('DOMContentLoaded', function() {","")[:-6]\
        + "doubleclickzoomreset);\n"

    out = f'<div id="{target_div}" style="text-align: left; width: 90%; width: 90vw; max-width: 2100px; margin: 0;"></div>\n'
    out += '<script>' + requirejs_header_script + hc_config_script + container_script + hc_graph_script + requirejs_footer_script + '</script>'

    return out