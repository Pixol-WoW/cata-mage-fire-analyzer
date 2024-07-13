var doubleclickzoomreset = function(chart) {
    $(chart.container).bind('dblclick', function() {
        chart.zoomOut();   
    })
}

var destroyAllHighcharts = function() {
    for (i = Highcharts.charts.length-1; i >= 0 ; i--) {if (Highcharts.charts[i]) {Highcharts.charts[i].destroy()}; Highcharts.charts.pop()};
}

function customRound(xmin, y, xmax) {
    if (y!==undefined) {
        var tick_interval_base = (10**Math.floor(Math.log10(y)))
        var tick_multiplier = Math.round(10*y/tick_interval_base)/10
        var out = Math.round(xmin/(tick_interval_base*tick_multiplier))*tick_interval_base*tick_multiplier
        return out
    }
    else {
        var tick_intervals = [1, 2.5, 5]
        if (xmax>=60){
            tick_intervals = [1, 1.5, 3]
        }

        var tick_interval_base = 10**Math.floor(Math.log10(xmin))

        var increment = tick_interval_base
        var tmp_min = 10000000
        var tmp_val = 0
        for (let i = 0; i < tick_intervals.length; i++) {
            tmp_val = Math.abs(tick_interval_base*tick_intervals[i]-xmin)
            if (tmp_val <= tmp_min)
            {
                tmp_min = tmp_val
                increment = tick_interval_base*tick_intervals[i]
            }
        }
      return increment
  }
}








function highcharts_cursor_sync_old(e) {
    let chart,
        point,
        i,
        event;

    for (i = 0; i < Highcharts.charts.length; i = i + 1) {
        chart = Highcharts.charts[i];
        // Find coordinates within the chart
        event = chart.pointer.normalize(e);
        chart.xAxis[0].drawCrosshair(event, this);
        // Get the hovered point
        //point = chart.series[0].searchPoint(event, true);
        //if (point) {
          //point.highlight(e);
        //}
    }
}

function highcharts_cursor_sync(e) {
    let chart,i,x_val;
  
  // Check which chart the mouse is in and get the mouseover x axis value
    for (i = 0; i < Highcharts.charts.length; i = i + 1) {
        chart = Highcharts.charts[i];
        chart.pointer.normalize(e);
        if (chart.isInsidePlot(e.chartX - chart.plotLeft, e.chartY - chart.plotTop)) {
            x_val = chart.xAxis[0].toValue(e.chartX)
        }
    }
    if (x_val == undefined){
        for (i = 0; i < Highcharts.charts.length; i = i + 1) {
            chart = Highcharts.charts[i];
            chart.xAxis[0].hideCrosshair(); // Show the crosshair
        }
    }
    else {
        // Convert the mouseover x axis value to each chart's x axis pixel value
        // then draw the crosshair for each chart
        for (i = 0; i < Highcharts.charts.length; i = i + 1) {
            chart = Highcharts.charts[i];
            chart.pointer.normalize(e);
            e.chartX = chart.xAxis[0].toPixels(x_val)
            chart.xAxis[0].drawCrosshair(e); // Show the crosshair
        }
    }
}

/**
 * Override the reset function, we don't need to hide the tooltips and
 * crosshairs.
 */
// Highcharts.Pointer.prototype.reset = function () {
//     return undefined;
// };

/**
 * Highlight a point by showing tooltip, setting hover state and draw crosshair
 */
//Highcharts.Point.prototype.highlight = function (event) {
    //event = this.series.chart.pointer.normalize(event);
    //this.onMouseOver(); // Show the hover marker
    //this.series.chart.tooltip.refresh(this); // Show the tooltip
    //this.series.chart.xAxis[0].drawCrosshair(event, this); // Show the crosshair
//};

function syncExtremes(e) {
    // const thisChart = this.chart;

    // if (e.trigger !== 'syncExtremes') { // Prevent feedback loop
    //     Highcharts.each(Highcharts.charts, function (chart) {
    //         if (chart !== thisChart) {
    //             if (chart.xAxis[0].setExtremes) { // It is null while updating
    //                 chart.xAxis[0].setExtremes(
    //                     e.min,
    //                     e.max,
    //                     undefined,
    //                     false,
    //                     { trigger: 'syncExtremes' }
    //                 );
    //             }
    //         }
    //     });
    // }
} 










Highcharts.setOptions({
    chart: {
        animation: false,
        zooming: {
            mouseWheel: {
              enabled: false,
            },
        },
        zoomType: 'x',
        panning: true,
        panKey: 'shift',
        style: {
            "fontFamily": "'Lucida Grande','Lucida Sans Unicode', Verdana, Arial, Helvetica, sans-serif",
            "fontSize":"14px",
        },
        resetZoomButton: {
            position: {
                x: -40,
                y: -68,
            }
        }
    },
    tooltip: {
        snap: 10,
    },
    plotOptions: {
        series: {
            stickyTracking: false,
            findNearestPointBy: 'xy',
            dataLabels: {
                enabled: false,
            },
            states: {
                inactive: {
                    opacity: 1,
                },
            },
        },
        area: {
            stickyTracking: false,
            findNearestPointBy: 'xy',
            step: 'left',
            dataLabels: {
                enabled: false,
            },
            states: {
                inactive: {
                    opacity: 1,
                },
            },
        },
        polygon: {
            stickyTracking: false,
            findNearestPointBy: 'xy',
            lineColor: 'black',
            lineWidth: 1,
            dataLabels: {
                enabled: false,
            },
            states: {
                inactive: {
                    opacity: 1,
                },
            },
        },
    },
    xAxis: {
        min: 0,
        crosshair: {
            snap: false,
            label: {
                backgroundColor: '#666666',
                enabled: true,
                formatter: function(value) {
                    var mm = Math.floor(value/60)
                    var ss = (value)%60
                    ss = Math.round(ss*1000)/1000
                    return (mm > 0 ? mm + "m " : "") + ss + "s"
                }
            },
        },
        events: {
            setExtremes: syncExtremes,
        },

        // tickPositioner: function () {
        //     var positions = [],
        //         tick = this.min,
        //         x = (this.max - this.min)/5;

        //     var increment = customRound(x, undefined, this.max-this.min)
        //     tick = customRound(this.min,increment)
            
        //     if (this.dataMax !== null && this.dataMin !== null) {
        //         for (tick; tick - increment <= this.max; tick += increment) {
        //             positions.push(tick);
        //         }
        //     }
        //     return positions;
        // },
        // tickWidth: 1,
        // gridLineWidth: 1,
        // startOnTick: false,
        // endOnTick: false,
        // ordinal: false,
        showLastLabel: true,

        labels: {
            formatter: function() {
                var mm = Math.floor(this.value/60)
                var ss = (this.value)%60
                ss = Math.round(ss*10000)/10000
                return (mm > 0 ? mm + "m " : "") + ss + "s"
            }
        },
        allowDecimals: true,

    },
});