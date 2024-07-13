import pandas as pd
import numpy as np
from utils.analyzers.PixolClassAnalyzerGraph import PixolGraphBase
from utils.analyzers.MageFire.CombustionEstimator import CombustionEstimatorClass

from utils.misc import dict_deep_update, get_mmss, wrap_trtd, merge_overlapping_intervals, get_idx_from_bool_series

class PixolIgniteTickEstimate(PixolGraphBase):
    data_type = 'ignite_tick_estimate'
    
    def generate_poly_series(self, target=None):
        if self.df_poly is None:
            self.poly_series = None
            return

        if target:
            df_poly = self.df_poly[self.df_poly.targetNameInstanceUnique==target]
        else:
            df_poly = self.df_poly

        self.poly_series = [{
            'name': self.config['id'] + ' (Est)',
            'id': self.config['id'],
            'type': 'area',
            'step': True,
            'data': df_poly['results'].to_list(),
            'threshold': pd.notna(self.config['area_thres']) and self.config['area_thres'] or df_poly['y_val_norm'].max(),
            'marker': {
                'enabled': False,
                'symbol': 'circle',
            },
            'lineWidth': 1,
            'lineColor': 'rgba(0,0,0,0.5)',
            'turboThreshold': 100000,
        }]

        self.poly_series += [{
            'name': self.config['id'],
            'id': self.config['id'],
            'type': "scatter",
            'dataLabels': {
                'enabled': True,
                'useHTML': True,
                'align': "left",
                'padding': 0,
                'verticalAlign': "middle",
                'allowOverlap': True,
                'format': "{point.label}"
            },
            'marker': {
                'enabled': True,
                'symbol': 'circle',
                'radius': 2,
                'lineColor': "rgba(0,0,0,0.5)",
                'lineWidth': 1,
            },
            'color': "rgba(255,0,0,1)",
            'turboThreshold': 100000,
            'data': df_poly['results_scatter'].to_list(),
        }]
        return self.poly_series

    def generate_graph_df(self):
        mask_ignite_tick_estimates = self.df['i-TickAmount'].notna()
        mask_ignite_ticks = (self.df['abilityGameID'] == 413843) & (self.df['type'] == 'damage')
        idx_ignite_ticks = get_idx_from_bool_series(mask_ignite_ticks)

        mask = mask_ignite_tick_estimates | mask_ignite_ticks
        df_poly = self.df[mask].copy()
        df_poly.rename({'i-TickAmount': 'y_val'}, axis=1, inplace=True)
        
        row_spacing = 0.1
        self.config['y_val_max'] = max(df_poly['y_val'].max(), df_poly.loc[idx_ignite_ticks,'amountTotal'].max())
        self.config['y_val_norm_max'] = (1-(self.config['y_val_max']-0)/(self.config['y_val_max']-0)) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']

        df_poly['y_val_norm'] = (1-(df_poly['y_val']-0)/(self.config['y_val_max']-0)) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']

        df_poly['results'] = df_poly.apply(self.generate_area_datapoint, data_type='ignite_tick_estimate', axis=1)

        df_poly['y_val_norm_scatter'] = (1-(df_poly['amountTotal']-0)/(self.config['y_val_max']-0)) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
        df_poly.loc[idx_ignite_ticks, 'results_scatter'] = df_poly.apply(self.generate_scatter, axis=1)

        # self.df_ignite_estimates = df_ignite_estimates

        self.df_poly = df_poly



class PixolCombustionStats(PixolGraphBase):
    data_type = 'combustion_stats'

    def generate_poly(self, x, y_center, y_height, max_stacks=1, linkedTo=None, color='red'):
        if pd.isna(color):
            color = 'red'
        
        txt = wrap_trtd('Start', get_mmss(x['tsApplied']))
        txt += wrap_trtd('End', get_mmss(x['tsRemoved']))
        txt += wrap_trtd('Dur', f"{get_mmss(x['tsRemoved']-x['tsApplied'])} | {get_mmss(x['tickTimeAvg'])} (Tick)")

        txt += wrap_trtd('# Ticks', f"{x['numTicks']:,.0f} (Actual) | {x['numTicksEst']:,.3f} (Est)")

        txt += wrap_trtd('LB/3', f"<a style='color:orange;'>{x['contributionLBRatio']*100:,.1f}% ({x['contributionLB']:,.0f})</a>")
        txt += wrap_trtd('PB/3', f"<a style='color:cyan;'>{x['contributionPBRatio']*100:,.1f}% ({x['contributionPB']:,.0f})</a>")
        txt += wrap_trtd('Ignite/2', f"<a style='color:red;'>{x['contributionIgniteRatio']*100:,.1f}% ({x['contributionIgnite']:,.0f})</a>")

        txt += wrap_trtd('Tick Dmg', f"{x['tickDmgAvg']:,.0f} (Actual) | {x['tickDmgEst']:,.0f} (Est)")
        txt += wrap_trtd('Snapshot', f"<b>{x['igniteSnapshot']:,.0f} Ign</b> | {x['spellPower']:,.0f} SP | {x['mastery']:,.5f} M")

        dur = x['tsRemoved']-x['tsApplied']
        xmin_lb = x['tsApplied']
        xmax_lb = x['tsApplied'] + dur*x['contributionLBRatio']
        xmin_pb = xmax_lb
        xmax_pb = xmax_lb + dur*x['contributionPBRatio']
        xmin_ignite = xmax_pb
        xmax_ignite = x['tsRemoved']


        ymax = round(y_center + y_height/2,2)
        ymin = round(y_center - y_height/2,2)
        out = [
        { # LB
            'type': 'polygon',
            'name': linkedTo or x.get('abilityGameName') or "",
            'linkedTo': linkedTo or x.get('abilityGameName') or "",
            'data': [
                [xmin_lb, ymin],
                [xmin_lb, ymax],
                [xmax_lb, ymax],
                [xmax_lb, ymin],
            ],
            'color': 'orange',
            'enableMouseTracking': False,
        },
        { # PB
            'type': 'polygon',
            'name': linkedTo or x.get('abilityGameName') or "",
            'linkedTo': linkedTo or x.get('abilityGameName') or "",
            'data': [
                [xmin_pb, ymin],
                [xmin_pb, ymax],
                [xmax_pb, ymax],
                [xmax_pb, ymin],
            ],
            'color': 'cyan',
            'enableMouseTracking': False,
        },
        { # Ignite
            'type': 'polygon',
            'name': linkedTo or x.get('abilityGameName') or "",
            'linkedTo': linkedTo or x.get('abilityGameName') or "",
            'data': [
                [xmin_ignite, ymin],
                [xmin_ignite, ymax],
                [xmax_ignite, ymax],
                [xmax_ignite, ymin],
            ],
            'color': 'red',
            'enableMouseTracking': False,
        },
        { # Overall Tooltip
            'type': 'polygon',
            'name': linkedTo or x.get('abilityGameName') or "",
            'linkedTo': linkedTo or x.get('abilityGameName') or "",
            'data': [
                [x['tsApplied'], ymin],
                [x['tsApplied'], ymax],
                [x['tsRemoved'], ymax],
                [x['tsRemoved'], ymin],
            ],
            'color': 'rgba(0,0,0,0)',
            'custom': {
                'txt': txt,
            },
        }
        ]
        return out

    def generate_graph_df(self):
        combustionEstimatorObj = CombustionEstimatorClass(self.df)
        combustionEstimatorObj.estimate()
        df_combustion_stats = combustionEstimatorObj.getStats()
        df_combustion_stats['polyResults'] = df_combustion_stats.apply(self.generate_poly, y_center=0.5+self.config['row_num']+self.config['yOffset'], y_height=self.config['height'], max_stacks=self.config['max_stacks'], linkedTo=self.config['id'], axis=1)

        self.df_poly = df_combustion_stats
        self.num_poly = len(self.df_poly)


