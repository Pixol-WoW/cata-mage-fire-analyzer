import pandas as pd
import numpy as np
from utils.misc import dict_deep_update, get_mmss, wrap_trtd, merge_overlapping_intervals, get_idx_from_bool_series
import importlib
HAS_PYSCRIPT = importlib.util.find_spec('pyscript')

class PixolGraphBase:
    config = {
        'type': 'poly',
        'data_type': None,
        'id_shared_row': None,
        'always_show': False,
        'is_secondary': False,
        'showDecimalsOnPlotLine': False,
        'max_stacks': 1,
        'height': 0.4,
        'yOffset': 0,
        'row_num': np.nan,
        'row_span': 1,
        'y_axis_label': None,
        'y_plot_band': None,
        'color': None,
        'threshold_time_between_casts': np.nan,
        'area_thres': np.nan,
        'url': None,
        'img': None,
        'df_mastery': None,
    }

    def __init__(self, df, metadata, fight_id, **kwargs):
        self.df = df
        self.metadata = metadata
        self.fight_id = fight_id
        self.fight_duration = self.metadata.encounters.loc[self.fight_id].duration
        self.config = self.config.copy()
        self.config.update(kwargs)

        self.num_poly = np.nan # Number of output polygons
        self.df_poly = None
        self.plot_bands = None
        self.plot_lines = None
    
    def set_row_num(self, row_num):
        self.config['row_num'] = row_num

    def generate_poly(self, x, y_center, y_height, max_stacks=1, linkedTo=None, color='red'):
        if pd.isna(x['polyStart']):
            return

        if pd.isna(color):
            color = 'red'
        
        txt = wrap_trtd('Start', get_mmss(x['polyStart']))
        txt += wrap_trtd('End', get_mmss(x['polyEnd']))
        txt += wrap_trtd('Dur', get_mmss(x['polyEnd']-x['polyStart']))
        if x.get('polyStacks'):
            txt += wrap_trtd("Stacks", f"{x['polyStacks']:.0f}")
        if pd.notna(x.get('amount')):
            show_total = False
            # note: crit flag does not get set on fully absorbed damage events
            if 'CRIT' in x['hitTypeStr']:
                str_amt = f"*{x['amount']:,.0f}*"
            else:
                str_amt = f"{x['amount']:,.0f}"
            if x.get('absorbed') != 0:
                str_amt += f" (A: {x['absorbed']:,.0f})"
                show_total = True
            if x.get('overkill') != 0:
                str_amt += f" (O: {x['overkill']:,.0f})"
                show_total = True
            if x.get('resisted') != 0:
                str_amt += f" (R: {x['resistedRatio']*100:,.0f}%)"
                show_total = True
                # str_amt += f" (R{x['resisted']/x['unmitigatedAmount']*100:.0f}: {x['resisted']:.0f})"
            if show_total:
                str_amt += f" (T: {x['amountTotal']:,.0f})"
            txt += wrap_trtd("Amt", str_amt)
        if pd.notna(x.get('dmgMultiplier')):
            txt += wrap_trtd("Bonus", f"{x['dmgMultiplier']:0.2f}x")

        if pd.notna(x.get('targetNameInstanceUnique')):
            txt += wrap_trtd("Target", x['targetNameInstanceUnique'])


        ymax = round(y_center + y_height/2,2)
        if x.get('polyStacks') and (x['polyStacks'] < max_stacks):
            ymin = round(ymax - y_height*(x['polyStacks']/max_stacks),2)
            color = 'yellow'
        elif x.get('polyClip'):
            ymin = round(ymax - y_height*(0.5),2)
            color = 'yellow'
        else:
            ymin = round(y_center - y_height/2,2)
        out = [{
            'type': 'polygon',
            'name': linkedTo or x.get('abilityGameName') or "",
            'linkedTo': linkedTo or x.get('abilityGameName') or "",
            'data': [
                [x['polyStart'], ymin],
                [x['polyStart'], ymax],
                [x['polyEnd'], ymax],
                [x['polyEnd'], ymin],
            ],
            'color': color,
            'custom': {
                'txt': txt,
            },
        }]
        return out

    def generate_area_datapoint(self, x, data_type=None):
        if pd.isna(x['y_val_norm']):
            return
        txt = wrap_trtd('Start', get_mmss(x['timestamp']))
        if self.data_type == 'haste':
            txt += wrap_trtd('Haste', f"{x['haste']:.1f}%")
            txt += wrap_trtd('Spell', x['abilityGameName'])
            if x.get('castDur'):
                txt += wrap_trtd('Dur', get_mmss(x['castDur']))
        elif self.data_type == 'spellpower':
            txt += wrap_trtd('SP', f"{x['spellPower']:,.0f}")
        elif self.data_type == 'mastery':
            txt += wrap_trtd('Mastery', f"{x['mastery']:,.5f}")
        elif self.data_type == 'mana':
            txt += wrap_trtd('Mana', f"{x['mana']:,.0f} / {x['manaMax']:,.0f} ({x['manaPerc']*100:.2f}%)")
        elif self.data_type == 'enemy_health':
            txt += wrap_trtd('HP', f"{x['hitPoints']:,.0f} / {x['maxHitPoints']:,.0f} ({x['healthPerc']*100:.2f}%)")
        elif self.data_type == 'movement':
            txt += wrap_trtd('Dist', f"{x['distMoved']:.0f} yds")
        elif self.data_type == 'heating_up':
            txt += wrap_trtd('Heating Up', f"{x['heatingUp']:.0f}")
        elif self.data_type == 'ignite_storage':
            txt += wrap_trtd('Ignite Stored', f"{x['igniteStorage']:,.0f}")
        elif self.data_type == 'ignite_tick_estimate':
            txt += wrap_trtd('Ignite Tick Estimate', f"{x['y_val']:,.0f}")

        out = {
            'x': x['timestamp'],
            'y': x['y_val_norm'],
            'custom': {
                'txt': txt,
            },
        }
        return out
    
    def generate_scatter(self, x, data_type=None):
        if pd.notna(x.get('startTime')):
            txt = wrap_trtd('Start', get_mmss(x['startTime']))
            txt += wrap_trtd('End', get_mmss(x['timestamp']))
            x_coord = x['startTime']
        else:
            txt = wrap_trtd('Time', get_mmss(x['timestamp']))
            x_coord = x['timestamp']

        txt += wrap_trtd('Spell', x['abilityGameName'])
        txt += wrap_trtd('ID', x['abilityGameID'])
        if pd.notna(x.get('targetNameInstanceUnique')):
            txt += wrap_trtd('Target', x['targetNameInstanceUnique'])

        if pd.notna(x.get('amountTotal')):
            str_amt = f"{x['amountTotal']:,.0f}"
            txt += wrap_trtd("Amt", str_amt)


        # try:
        #     icon = self.metadata.abilities.loc[x['abilityGameID'],'icon']
        # except:
        #     icon = 'inv_misc_questionmark.jpg'
        # label = f"<div style='width: 16px; height: 16px; overflow: hidden; border: 1px solid black;'><img style='width: 19px; height: 19px; margin-left: -7.35%; margin-top: -7.35%' src='https://wow.zamimg.com/images/wow/icons/small/{icon}'></div>"

        out = {
            'x': x_coord,
            'y': x['y_val_norm_scatter'],
            # 'color': 'rgba(1,0,0,1)',
            # 'label': label,
            'custom': {
                'txt': txt,
            },
        }
        return out


    def generate_cast_scatter(self, x, y_center, data_type=None):
        if pd.notna(x.get('startTime')):
            txt = wrap_trtd('Start', get_mmss(x['startTime']))
            txt += wrap_trtd('End', get_mmss(x['timestamp']))
            x_coord = x['startTime']
        else:
            txt = wrap_trtd('Time', get_mmss(x['timestamp']))
            x_coord = x['timestamp']

        txt += wrap_trtd('Spell', x['abilityGameName'])
        txt += wrap_trtd('ID', x['abilityGameID'])
        if pd.notna(x.get('targetNameInstanceUnique')):
            txt += wrap_trtd('Target', x['targetNameInstanceUnique'])
        try:
            icon = self.metadata.abilities.loc[x['abilityGameID'],'icon']
        except:
            icon = 'inv_misc_questionmark.jpg'
        label = f"<div style='width: 16px; height: 16px; overflow: hidden; border: 1px solid black;'><img style='width: 19px; height: 19px; margin-left: -7.35%; margin-top: -7.35%' src='https://wow.zamimg.com/images/wow/icons/small/{icon}'></div>"

        out = {
            'x': x_coord,
            'y': y_center,
            'color': 'rgba(0,0,0,0)',
            'label': label,
            'custom': {
                'txt': txt,
            },
        }
        return out

    def generate_plot_bands(self):
        out = []
        has_url_or_img = pd.notna(self.config['url']) and pd.notna(self.config['img'])
        if has_url_or_img:
            out.append({
                    'from': self.config['row_num'],
                    'to': self.config['row_num'] + self.config['row_span'],
                    'color': "rgba(0, 0, 0, 0)",
                    'label': {
                        'text': f"<a href='{self.config['url']}' target='_blank'><div style='width: 25px; height: 25px; overflow: hidden; border: 1px solid black;'><img style='width: 29px; height: 29px; margin-left: -7.35%; margin-top: -7.35%' src='{self.config['img']}'></div></a>",
                        'useHTML': True,
                        'x': -35,
                        'y': -2,
                        'style': {'color': "#FFFFFF"}
                    },
            })
        if pd.notna(self.config['y_axis_label']) or has_url_or_img:
            out.append({
                'from': self.config['row_num'],
                'to': self.config['row_num'] + self.config['row_span'],
                'color': self.config['row_num']%2 == 0 and "rgba(128, 128, 128, 0.1)" or "rgba(0, 0, 0, 0)",
                'label': {
                    'text': f"{self.config['y_axis_label'] or self.config['id']}",
                    'x': -40,
                    'y': 3,
                    'textAlign': "right",
                    'verticalAlign': "middle",
                    'style': {
                        'color': HAS_PYSCRIPT and "rgba(255, 255, 255, 0.5)" or "rgba(0, 0, 0, 0.5)",
                    },
                },
            })
        if len(out) > 0:
            self.plot_bands = out
            return self.plot_bands
        return

    def generate_plot_lines(self):
        if self.config['type'] == 'area':
            row_spacing = 0.1
            if self.data_type in ['enemy_health','mana','ignite_storage','ignite_tick_estimate']:
                y_val_min = 0
                y_val_norm_min = self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
            else:
                try:
                    idx_min = self.df_poly['y_val'].argmin()
                    y_val_min = self.df_poly.iloc[idx_min]['y_val']
                    y_val_norm_min = self.df_poly.iloc[idx_min]['y_val_norm']
                except:
                    y_val_min = 0
                    y_val_norm_min = self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']

            try:
                idx_max = self.df_poly['y_val'].argmax()
            except:
                idx_max = None
                pass
            y_val_max = self.config.get('y_val_max') or (idx_max and self.df_poly.iloc[idx_max]['y_val']) or 1
            y_val_norm_max = self.config.get('y_val_norm_max') or (idx_max and self.df_poly.iloc[idx_max]['y_val_norm']) or 1
            self.plot_lines = [
                {
                    # 'color': "rgba(255, 255, 255, 0.5)",
                    'width': 1,
                    'value': y_val_norm_min,
                    'dashStyle': "dash",
                    'zIndex': 1,
                    'label': {
                        'text': self.config["showDecimalsOnPlotLine"] and f"{y_val_min:.2f}" or f"{y_val_min:.0f}",
                        'useHTML': True,
                        'align': "left",
                        'textAlign': "right",
                        'x': -5,
                        'y': 0,
                        'rotation': 0,
                        'style': {
                            # 'color': "rgba(255, 255, 255, 0.5)"
                            }
                        },
                },
                {
                    # 'color': "rgba(255, 255, 255, 0.5)",
                    'width': 1,
                    'value': y_val_norm_max,
                    'dashStyle': "dash",
                    'zIndex': 1,
                    'label': {
                        'text': self.config["showDecimalsOnPlotLine"] and f"{y_val_max:.2f}" or f"{y_val_max:.0f}",
                        'useHTML': True,
                        'align': "left",
                        'textAlign': "right",
                        'x': -5,
                        'y': 8,
                        'rotation': 0,
                        'style': {
                            # 'color': "rgba(255, 255, 255, 0.5)"
                            }
                        },
                },
            ]
            return self.plot_lines
        
    def get_uniques(self):
        if isinstance(self.df_poly, pd.DataFrame):
            if 'targetNameInstanceUnique' in self.df_poly.columns:
                return self.df_poly['targetNameInstanceUnique'].unique().tolist()

    def generate_poly_series(self, target=None):
        if self.df_poly is None:
            self.poly_series = None
            return

        if target:
            df_poly = self.df_poly[self.df_poly.targetNameInstanceUnique==target]
        else:
            df_poly = self.df_poly

        if self.config['type'] == 'poly':
            list_poly_results = [ll for l in df_poly['polyResults'].to_list() for ll in l]

            if len(list_poly_results) > 0:
                list_poly_results.append({
                    'type': 'polygon',
                    'name': self.config['id'],
                    'id': self.config['id'],
                    'color': 'red',
                })
                self.poly_series = list_poly_results
                return self.poly_series
        elif self.config['type'] == 'area':
            out = {
                'name': self.config['id'],
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
            }
            
            # if df.get('visible') == False:
            #     out['visible'] = False

            self.poly_series = [out]
            return self.poly_series
        elif self.config['type'] == 'scatter':
            self.poly_series = [{
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
                    'enabled': False,
                    'symbol': 'circle',
                },
                'color': "rgba(158,134,200,1)",
                'turboThreshold': 100000,
                'data': df_poly['results'].to_list(),
            }]
            return self.poly_series
    
class PixolDotDebuff(PixolGraphBase):
    def generate_graph_df(self):
        if self.config.get("ignore_ability_id_grouping") == True:
            groupby_settings = ['sourceNameInstanceUnique','targetNameInstanceUnique']
        else:
            groupby_settings = ['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique']

        mask = (self.df['abilityGameID'].isin(self.config['ability_ids']))

        if self.config.get("show_clip_on_refresh") == True:
            mask = (mask) & (self.df['type'].isin(['damage','applydebuff','refreshdebuff','removedebuff']))
        else:
            mask = (mask) & (self.df['type'].isin(['damage','applydebuff','removedebuff']))

        if self.config.get("ticks_only") == True:
            mask2 = (self.df['type'].isin(['damage'])) & (self.df['tick']!=True)
            mask = (mask) & (~mask2)

        df = self.df[mask].copy()
        df.insert(1, 'polyStart', np.nan)
        df.insert(2, 'polyEnd', np.nan)
        df.insert(3, 'polyClip', False)

        if self.config.get("show_clip_on_refresh") == True:
            mask = (df.groupby(groupby_settings)['type'].shift().isin(['applydebuff','refreshdebuff','damage'])) & (df.groupby(groupby_settings)['type'].shift(0) == 'damage')
        else:
            # ['applydebuff', 'damage'] -> ['damage']
            mask = (df.groupby(groupby_settings)['type'].shift().isin(['applydebuff','damage'])) & (df.groupby(groupby_settings)['type'].shift(0) == 'damage')

        df.loc[mask,'polyStart'] = df.groupby(groupby_settings)['timestamp'].shift()

        if self.config.get("show_clip_on_refresh") == True:
            # ['damage','applydebuff','refreshdebuff'] -> ['refreshdebuff','removedebuff']: clipped if not same timestamp
            mask = (df.groupby(groupby_settings)['type'].shift().isin(['damage','applydebuff','refreshdebuff'])) \
                & (df.groupby(groupby_settings)['type'].shift(0).isin(['refreshdebuff','removedebuff'])) \
                & (df.groupby(groupby_settings)['timestamp'].shift() != df.groupby(groupby_settings)['timestamp'].shift(0))
        else:
            # ['damage','applydebuff'] -> ['removedebuff']: clipped if not same timestamp
            mask = (df.groupby(groupby_settings)['type'].shift().isin(['damage','applydebuff'])) \
                & (df.groupby(groupby_settings)['type'].shift(0).isin(['removedebuff'])) \
                & (df.groupby(groupby_settings)['timestamp'].shift() != df.groupby(groupby_settings)['timestamp'].shift(0))
        df.loc[mask,'polyStart'] = df.groupby(groupby_settings)['timestamp'].shift()
        df.loc[mask,'polyClip'] = True

        mask = df['polyStart'].notna()
        df.loc[mask,'polyEnd'] = df['timestamp']
        df.loc[mask,'polyResults'] = df.loc[mask].apply(self.generate_poly, y_center=0.5+self.config['row_num']+self.config['yOffset'], y_height=self.config['height'], max_stacks=self.config['max_stacks'], linkedTo=self.config['id'], axis=1)

        if sum(mask) > 0:
            self.df_poly = df.loc[mask][['abilityGameID', 'polyStart', 'polyEnd', 'polyClip', 'sourceID', 'sourceNameInstance', 'sourceNameInstanceUnique', 'targetID', 'targetNameInstance', 'targetNameInstanceUnique', 'polyResults']]
            self.num_poly = len(self.df_poly)

class PixolIgniteDebuff(PixolGraphBase):
    def generate_graph_df(self):
        if self.config.get("ignore_ability_id_grouping") == True:
            groupby_settings = ['sourceNameInstanceUnique','targetNameInstanceUnique']
        else:
            groupby_settings = ['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique']
        mask = (self.df['abilityGameID'].isin(self.config['ability_ids']))
        mask = (mask) & (self.df['type'].isin(['damage','applydebuff','removedebuff']))
        if self.config.get("ticks_only") == True:
            mask2 = (self.df['type'].isin(['damage'])) & (self.df['tick']!=True)
            mask = (mask) & (~mask2)
        df = self.df[mask].copy()
        df.insert(1, 'polyStart', np.nan)
        df.insert(2, 'polyEnd', np.nan)
        df.insert(3, 'polyClip', False)

        # ['applydebuff', 'damage'] -> ['damage']
        mask = (df.groupby(groupby_settings)['type'].shift().isin(['applydebuff','damage'])) & (df.groupby(groupby_settings)['type'].shift(0) == 'damage')
        df.loc[mask,'polyStart'] = df.groupby(groupby_settings)['timestamp'].shift()

        # ['damage','applydebuff'] -> ['removedebuff']: clipped if not same timestamp
        mask = (df.groupby(groupby_settings)['type'].shift().isin(['damage','applydebuff'])) \
            & (df.groupby(groupby_settings)['type'].shift(0).isin(['removedebuff'])) \
            & (df.groupby(groupby_settings)['timestamp'].shift() != df.groupby(groupby_settings)['timestamp'].shift(0))
        df.loc[mask,'polyStart'] = df.groupby(groupby_settings)['timestamp'].shift()
        df.loc[mask,'polyClip'] = True

        # ['damage'] -> ['removedebuff'] -> ['damage']: special case for ignite where debuff falls off then tick damage happens
        mask = (df.groupby(groupby_settings)['type'].shift(2).isin(['damage'])) \
            & (df.groupby(groupby_settings)['type'].shift().isin(['removedebuff'])) \
            & (df.groupby(groupby_settings)['type'].shift(0).isin(['damage'])) \
            & ((df.groupby(groupby_settings)['timestamp'].shift(0) - df.groupby(groupby_settings)['timestamp'].shift()) < 0.1)
        df.loc[mask,'polyStart'] = df.groupby(groupby_settings)['timestamp'].shift(2)

        # This basically unsets the polyStart/polyClip from earlier
        # ['damage'] -> ['removedebuff'] -> ['damage']: special case for ignite where debuff falls off then tick damage happens
        mask = (df.groupby(groupby_settings)['type'].shift(1).isin(['damage'])) \
            & (df.groupby(groupby_settings)['type'].shift(0).isin(['removedebuff'])) \
            & (df.groupby(groupby_settings)['type'].shift(-1).isin(['damage'])) \
            & ((df.groupby(groupby_settings)['timestamp'].shift(-1) - df.groupby(groupby_settings)['timestamp'].shift(0)) < 0.1)
        df.loc[mask,'polyStart'] = np.nan
        df.loc[mask,'polyClip'] = False

        mask = df['polyStart'].notna()
        df.loc[mask,'polyEnd'] = df['timestamp']
        df.loc[mask,'polyResults'] = df.loc[mask].apply(self.generate_poly, y_center=0.5+self.config['row_num']+self.config['yOffset'], y_height=self.config['height'], max_stacks=self.config['max_stacks'], linkedTo=self.config['id'], axis=1)
        
        if sum(mask) > 0:
            self.df_poly = df.loc[mask][['abilityGameID', 'polyStart', 'polyEnd', 'polyClip', 'sourceID', 'sourceNameInstance', 'sourceNameInstanceUnique', 'targetID', 'targetNameInstance', 'targetNameInstanceUnique', 'polyResults']]
            self.num_poly = len(self.df_poly)

class PixolMergedDebuff(PixolGraphBase):
    def generate_graph_df(self):
        mask = (self.df['abilityGameID'].isin(self.config['ability_ids'])) & (self.df['type'].isin(['applydebuff','refreshdebuff','removedebuff']))
        if pd.notna(self.config.get('target_ids')):
            mask = (mask) & (self.df.targetID.isin(self.config['target_ids'])) 
        df = self.df[mask].copy()
        # df = self.df[(self.df['abilityGameID'].isin(self.config['ability_ids'])) & (self.df['type'].isin(['applydebuff','refreshdebuff','removedebuff']))].copy()
        df.insert(1, 'polyStart', np.nan)
        df.insert(2, 'polyEnd', np.nan)

        # ['applydebuff', 'refreshdebuff'] -> ['refreshdebuff', 'removedebuff']
        mask = (df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift().isin(['applydebuff','refreshdebuff'])) & (df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift(0).isin(['refreshdebuff','removedebuff']))
        df.loc[mask,'polyStart'] = df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['timestamp'].shift()

        mask = df['polyStart'].notna()
        df.loc[mask,'polyEnd'] = df['timestamp']
        # df.loc[mask,'polyResults'] = df.loc[mask].apply(generate_poly, y_center=0.5+self.config['row_num']+self.config['yOffset'], y_height=self.config['height'], max_stacks=self.config['max_stacks'], linkedTo=self.config['id'], axis=1)

        if sum(mask) > 0:
            df = df.loc[mask][['abilityGameID', 'polyStart', 'polyEnd', 'sourceID', 'sourceNameInstance', 'sourceNameInstanceUnique', 'targetID', 'targetNameInstance', 'targetNameInstanceUnique']].copy()
            df = merge_overlapping_intervals(df, ["targetNameInstanceUnique"], "polyStart", "polyEnd")
            df['polyResults'] = df.apply(self.generate_poly, y_center=0.5+self.config['row_num']+self.config['yOffset'], y_height=self.config['height'], max_stacks=self.config['max_stacks'], linkedTo=self.config['id'], axis=1)
            
            self.df_poly = df
            self.num_poly = len(self.df_poly)

class PixolEnemyHealth(PixolGraphBase):
    data_type = 'enemy_health'

    def generate_graph_df(self):
        df_health = self.df.dropna(subset='resourceActor')

        # get rid of non npcs
        mask = self.metadata.actors["type"].loc[df_health['resourceActorID']] == "NPC"
        df_health = df_health[mask.to_list()]

        df_health['healthPerc'] = df_health['hitPoints'] / df_health['maxHitPoints']
        df_health = df_health.dropna(subset='healthPerc')

        row_spacing = 0.1
        df_health['y_val_norm'] = (1-(df_health['healthPerc']-0)/(1-0)) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
        df_health['results'] = df_health.apply(self.generate_area_datapoint, data_type='health', axis=1)

        self.config['area_thres'] = (1-(0-0)/(1-0)) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']


        df_health.rename({'healthPerc': 'y_val'}, axis=1, inplace=True)
        df_health['y_val'] = df_health['y_val']*100

        # if resourceActor is 1 (source), then update name
        mask = df_health.resourceActor == 1
        df_health.loc[mask,'targetNameInstanceUnique'] = df_health.loc[mask,'sourceNameInstanceUnique']

        self.df_poly = df_health

class PixolHeatingUp(PixolGraphBase):
    data_type = 'heating_up'
    
    def generate_graph_df(self):
    #            (self.df["abilityGameName"].isin(["Fireball","Fire Blast","Scorch","Living Bomb","Frostfire Bolt"])) &\

        mask = (
                    (self.df["type"] == "damage") &
                    (self.df["abilityGameID"].isin([133,44614,2948,11366,2136])) & # Fireball, Frostfire Bolt, Scorch, Pyroblast, Pyroblast
                    (self.df["tick"]!=True)
               )
        if pd.notna(self.config.get('source_ids')):
            mask = mask & (self.df["sourceID"].isin(self.config['source_ids']))

        df = self.df.loc[mask].copy()

        # Incremental count of crits with reset to 0 every time a non-crit occurs
        # https://stackoverflow.com/questions/45964740/python-pandas-cumsum-with-reset-everytime-there-is-a-0
        s = df["hitTypeStr"].isin(['CRIT','RESIST_PARTIAL_CRIT'])
        s = s.cumsum()-s.cumsum().where(~s).ffill().fillna(0).astype(int)

        # Reset every time the counter goes past 2 crits
        mask = s>0
        s.loc[mask] = (s.loc[mask]-1)%2+1

        # Set 2 stacks of heating up back to zero (so the graph looks less confusing)
        mask = s==2
        s.loc[mask] = 0

        df.insert(2, "heatingUp", s)
        # does not account for any heating up values pre-pull but should auto-correct after the first non-crit

        df = df[["timestamp","heatingUp"]]

        row_spacing = 0.1
        df['y_val_norm'] = (1-(df['heatingUp']-0)/(df['heatingUp'].max()-0)) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
        df['results'] = df.apply(self.generate_area_datapoint, data_type='heating_up', axis=1)

        df.rename({'heatingUp': 'y_val'}, axis=1, inplace=True)
        df['targetNameInstanceUnique'] = None

        self.df_poly = df

class PixolSpellPower(PixolGraphBase):
    data_type = 'spellpower'
    
    def generate_graph_df(self):
        df_spellPower = self.df[self.df['resourceActorID'].isin(self.config['source_ids'])].dropna(subset=['spellPower'])

        row_spacing = 0.1
        df_spellPower['y_val_norm'] = (1-(df_spellPower['spellPower']-df_spellPower['spellPower'].min())/(df_spellPower['spellPower'].max()-df_spellPower['spellPower'].min())) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
        df_spellPower['results'] = df_spellPower.apply(self.generate_area_datapoint, data_type='spellpower', axis=1)

        df_spellPower.rename({'spellPower': 'y_val'}, axis=1, inplace=True)
        # df_spellPower['targetNameInstanceUnique'] = df_spellPower.apply(lambda x: x['resourceActor'] == 1 and x['sourceNameInstanceUnique'] or x['resourceActor'] == 2 and x['targetNameInstanceUnique'] or None, axis=1)
        df_spellPower['targetNameInstanceUnique'] = None

        self.df_poly = df_spellPower

class PixolMastery(PixolGraphBase):
    data_type = 'mastery'
    
    def generate_graph_df(self):
        if self.config['df_mastery'] is None:
            self.df_poly = None
            return
        df_mastery = self.config['df_mastery'].copy()

        row_spacing = 0.1
        df_mastery['y_val_norm'] = (1-(df_mastery['mastery']-df_mastery['mastery'].min())/(df_mastery['mastery'].max()-df_mastery['mastery'].min())) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
        df_mastery['results'] = df_mastery.apply(self.generate_area_datapoint, data_type='mastery', axis=1)

        df_mastery.rename({'mastery': 'y_val'}, axis=1, inplace=True)
        df_mastery['targetNameInstanceUnique'] = None

        self.df_poly = df_mastery

class PixolHaste(PixolGraphBase):
    data_type = 'haste'
    
    def generate_graph_df(self):
        dict_abilityGameID_to_castTime = {
            133: 2.25, # Fireball, TODO: detect 4pc haste reduction
            2948: 1.5, # Scorch
        }
        dict_abilityGameID_to_channeledTickTime = {
            47855: 3.0, # DS R6
        }

        y = self.df[(self.df.sourceID.isin(self.config['source_ids'])) & (self.df["abilityGameID"].isin(dict_abilityGameID_to_castTime.keys())) & (self.df["type"].isin(["begincast","cast"]))].copy()
        y.insert(1,'castEnd', np.nan)
        y.insert(1,'castStart', np.nan)
        y.insert(1,'castDur', np.nan)
        y.insert(1,'haste', np.nan)
        mask = (y.groupby(['abilityGameID','sourceNameInstanceUnique'])['type'].shift() == 'begincast') & (y.groupby(['abilityGameID','sourceNameInstanceUnique'])['type'].shift(0) == 'cast')
        mask = mask.shift(-1, fill_value=False)
        y.loc[mask,'castStart'] = y['timestamp']
        mask = y['castStart'].notna()
        y.groupby(['abilityGameID','sourceNameInstanceUnique'])['timestamp'].shift()
        y.loc[mask,'castEnd'] = y.groupby(['abilityGameID','sourceNameInstanceUnique'])['timestamp'].shift(-1)
        y.loc[mask,'castDur'] =  y.groupby(['abilityGameID','sourceNameInstanceUnique'])['timestamp'].shift(-1) - y.groupby(['abilityGameID','sourceNameInstanceUnique'])['timestamp'].shift(0)
        mask = y['castDur'] > 0.01 # Lazy way to ignore insta-cast procs instead of checking for the buff at the time of begincast
        y.loc[mask,'haste'] = y["abilityGameID"].map(dict_abilityGameID_to_castTime)/y['castDur'] - 1
        haste1 = y[['timestamp','haste','abilityGameName','castDur','sourceID','sourceNameInstance','sourceNameInstanceUnique']].dropna(subset=['haste'])

        # ##############################
        y = self.df[(self.df.sourceID.isin(self.config['source_ids'])) & (self.df["abilityGameID"].isin(dict_abilityGameID_to_channeledTickTime.keys())) & (self.df["type"].isin(["cast","damage"]))].copy()
        y.insert(1,'castEnd', np.nan)
        y.insert(1,'castStart', np.nan)
        y.insert(1,'castDur', np.nan)
        y.insert(1,'haste', np.nan)
        mask = (y.groupby(['abilityGameID','sourceNameInstanceUnique'])['type'].shift() == 'cast') & (y.groupby(['abilityGameID','sourceNameInstanceUnique'])['type'].shift(0) == 'damage')
        mask = mask.shift(-1).fillna(False)
        y.loc[mask,'castStart'] = y['timestamp']
        mask = y['castStart'].notna()
        y.groupby(['abilityGameID','sourceNameInstanceUnique'])['timestamp'].shift()
        y.loc[mask,'castEnd'] = y.groupby(['abilityGameID','sourceNameInstanceUnique'])['timestamp'].shift(-1)
        y.loc[mask,'castDur'] =  y.groupby(['abilityGameID','sourceNameInstanceUnique'])['timestamp'].shift(-1) - y.groupby(['abilityGameID','sourceNameInstanceUnique'])['timestamp'].shift(0)
        mask = y['castDur'] > 0.01
        y.loc[mask,'haste'] = y["abilityGameID"].map(dict_abilityGameID_to_channeledTickTime)/y['castDur'] - 1
        haste2 = y[['timestamp','haste','abilityGameName','castDur','sourceID','sourceNameInstance','sourceNameInstanceUnique']].dropna(subset=['haste'])
        # ##############################

        df_haste = pd.concat([haste1,haste2]).sort_index()
        df_haste['haste'] = df_haste['haste'].apply(lambda x: round(100*x,2))
        df_haste['targetNameInstanceUnique'] = None

        row_spacing = 0.1
        df_haste['y_val_norm'] = (1-(df_haste['haste']-df_haste['haste'].min())/(df_haste['haste'].max()-df_haste['haste'].min())) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
        df_haste['results'] = df_haste.apply(self.generate_area_datapoint, data_type='haste', axis=1)
        df_haste.rename({'haste': 'y_val'}, axis=1, inplace=True)

        self.df_poly = df_haste

class PixolMana(PixolGraphBase):
    data_type = 'mana'
    
    def generate_graph_df(self):
        df_mana = self.df[self.df['resourceActorID'].isin(self.config['source_ids'])].dropna(subset='classResources')

        def get_mana(x):
            amt = [[r['amount'],r['max']] for r in x['classResources'] if r['type'] == 0]
            if len(amt) > 0:
                return amt[0]
            return None, None

        df_mana['mana'], df_mana['manaMax'] = zip(*df_mana.apply(get_mana, axis=1))
        df_mana['manaPerc'] = df_mana['mana'] / df_mana['manaMax']
        df_mana = df_mana.dropna(subset='mana')

        row_spacing = 0.1
        # df_mana['y_val_norm'] = (1-(df_mana['mana']-df_mana['mana'].min())/(df_mana['mana'].max()-df_mana['mana'].min())) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
        df_mana['y_val_norm'] = (1-(df_mana['mana']-0)/(df_mana['mana'].max()-0)) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
        df_mana['results'] = df_mana.apply(self.generate_area_datapoint, data_type='mana', axis=1)

        self.config['area_thres'] = (1-(0-0)/(1-0)) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']


        df_mana.rename({'mana': 'y_val'}, axis=1, inplace=True)
        df_mana['targetNameInstanceUnique'] = None

        self.df_poly = df_mana

class PixolMovement(PixolGraphBase):
    data_type = 'movement'
    
    def generate_graph_df(self):
        y = self.df[self.df['resourceActorID'].isin(self.config['source_ids'])].copy()

        y['distMoved'] = (((y['x'].shift() - y['x'])**2 + (y['y'].shift() - y['y'])**2)**0.5)/100
        y['distMoved'] = y['distMoved'].fillna(0)

        # remove any large teleportations such as between HLK's two rooms
        y.loc[y['distMoved'] > 100,'distMoved'] = 0

        time_window = self.config.get('window') or 10
        df_movement = y.groupby(by=y['timestamp'] // time_window * time_window)["distMoved"].sum().reset_index()[["timestamp","distMoved"]]

        row_spacing = 0.1
        df_movement['y_val_norm'] = (1-(df_movement['distMoved']-df_movement['distMoved'].min())/(df_movement['distMoved'].max()-df_movement['distMoved'].min())) * self.config['row_span'] * (1-row_spacing*2/self.config['row_span']) + row_spacing + self.config['row_num']
        df_movement['results'] = df_movement.apply(self.generate_area_datapoint, data_type='movement', axis=1)

        df_movement.rename({'distMoved': 'y_val'}, axis=1, inplace=True)
        df_movement['targetNameInstanceUnique'] = None

        self.df_poly = df_movement

class PixolCasts(PixolGraphBase):
    data_type = 'casts'
    
    def generate_graph_df(self):
        mask = (self.df['sourceID'].isin(self.config['source_ids'])) & (self.df['type'].isin(['begincast','cast']))
        if pd.isna(self.config.get('include_melee')):
            mask = (mask) & (self.df['abilityGameID'] > 1)
        if pd.notna(self.config.get('spell_ids')) is not False:
            mask = (mask) & (self.df['abilityGameID'].isin(self.config['spell_ids']))
        if pd.notna(self.config.get('spell_ids_blacklist')) is not False:
            mask = (mask) & (~self.df['abilityGameID'].isin(self.config['spell_ids_blacklist']))
        y = self.df[mask].copy()

        # get the start time for each begincast
        mask = (y.groupby('abilityGameID').shift()['type'] == "begincast") & (y.groupby('abilityGameID').shift(0)['type'] == "cast")
        y.loc[mask,'startTime'] = y.groupby(['abilityGameID'])['timestamp'].shift()

        df_casts = y[y['type']=='cast'].copy()
        df_casts['results'] = df_casts.apply(self.generate_cast_scatter, y_center=0.5+self.config['row_num']+self.config['yOffset'], axis=1)
        df_casts['targetNameInstanceUnique'] = None

        self.df_poly = df_casts

class PixolBuff(PixolGraphBase):
    def generate_graph_df(self):
        mask = (self.df['abilityGameID'].isin(self.config['ability_ids'])) & (self.df['type'].isin(['applybuff','refreshbuff','removebuff']))
        if pd.notna(self.config.get('target_ids')):
            mask = (mask) & (self.df.targetID.isin(self.config['target_ids'])) 
        df = self.df[mask].copy()
        df.insert(1, 'polyStart', np.nan)
        df.insert(2, 'polyEnd', np.nan)
        df.insert(2, 'polyClip', False)
        df.insert(3, 'polyResults', np.empty((len(df), 0)).tolist())

        # handle cases where there's no initial applybuff event by setting initial timestamp to 0
        # idx = get_idx_from_bool_series(df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique']).nth(0)['type'].isin(['removebuff','refreshbuff'])) # only works for pandas >= 2.1.5?
        idx = df.reset_index().groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique']).nth(0).reset_index()['index']
        idx = get_idx_from_bool_series(df.loc[idx,'type'].isin(['removebuff','refreshbuff']))
        df.loc[idx, 'polyStart'] = 0

        # handle cases where there's no ending event after applybuff
        # idx = get_idx_from_bool_series(df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique']).nth(-1)['type'].isin(['applybuff','applybuff'])) # only works for pandas >= 2.1.5?
        idx = df.reset_index().groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique']).nth(-1).reset_index()['index']
        idx = get_idx_from_bool_series(df.loc[idx,'type'].isin(['applybuff','applybuff']))
        df.loc[idx, 'polyStart'] = df.loc[idx, 'timestamp']
        df.loc[idx, 'polyEnd'] = self.fight_duration

        # ['applybuff', 'refreshbuff'] -> ['refreshbuff', 'removebuff']
        mask = (df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift().isin(['applybuff','refreshbuff'])) & (df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift(0).isin(['refreshbuff','removebuff']))
        df.loc[mask,'polyStart'] = df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['timestamp'].shift()

        if self.config.get("show_clip_on_refresh") == True:
            mask = (df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift().isin(['applybuff','refreshbuff'])) & (df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift(0).isin(['refreshbuff']))
            df.loc[mask,'polyClip'] = True

        mask = df['polyStart'].notna()
        df.loc[mask & (df['polyEnd'].isna()),'polyEnd'] = df['timestamp']
        df.loc[mask,'polyResults'] = df.loc[mask].apply(self.generate_poly, y_center=0.5+self.config['row_num']+self.config['yOffset'], y_height=self.config['height'], max_stacks=self.config['max_stacks'], linkedTo=self.config['id'], axis=1)

        # handle cases where the there's no ending removebuff event by setting initial timestamp to 0
        # idx = get_idx_from_bool_series(df.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique']).nth(-1)['type'].isin(['refreshbuff'])) # only works for pandas >= 2.1.5?
        idx = df.reset_index().groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique']).nth(-1).reset_index()['index']
        idx = get_idx_from_bool_series(df.loc[idx,'type'].isin(['refreshbuff']))
        df2 = df.loc[idx].copy()
        df2.loc[idx,'polyStart'] = df2.loc[idx,'timestamp']
        df2.loc[idx,'polyEnd'] = self.fight_duration
        df.loc[idx,'polyResults'] += df2.apply(self.generate_poly, y_center=0.5+self.config['row_num']+self.config['yOffset'], y_height=self.config['height'], max_stacks=self.config['max_stacks'], linkedTo=self.config['id'], axis=1)

        self.df_poly = df.loc[:,['abilityGameID', 'polyStart', 'polyEnd', 'sourceID', 'sourceNameInstance', 'sourceNameInstanceUnique', 'targetID', 'targetNameInstance', 'targetNameInstanceUnique', 'polyResults']]
        self.num_poly = len(self.df_poly)


