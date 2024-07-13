import pandas as pd
import numpy as np
import panel as pn
# from utils.analyzers.PixolAnalyzer import run_config
from utils.misc import dict_deep_update
from utils.highcharts.PixolHighcharts import get_chart_html
from bokeh.models.widgets.tables import NumberFormatter
import importlib
HAS_PYSCRIPT = importlib.util.find_spec('pyscript')

class PixolClassAnalyzerBase:
    def __init__(
        self,
        client,
        metadata,
        player_id,
        fight_id,
        # data_player,
        # data_misc,
    ):
        self.client = client
        self.metadata = metadata
        self.player_id = player_id
        self.fight_id = fight_id
        # self.data_player = data_player
        # self.df_player = self.data_player.events
        # self.data_misc = data_misc
        # self.df_misc = self.data_misc.events
        self.fight_duration = self.metadata.encounters.loc[self.fight_id].duration

        # self.config_debuffs = self.load_config_debuffs()
        # self.config_buffs = self.load_config_buffs()

        self.options_kwargs = self.load_config_chart()
        self.add_encounter_phase_lines()

        self.panel_tabs_style = {
            'border': '1px solid #707073',
            'color': '#707073',
        }
        self.df_mastery = None

    def load_configs(self):
        self.config_debuffs = self.load_config_debuffs()
        self.config_buffs = self.load_config_buffs()

    def generate_panel_graphs(self, chart_height_offset_debuffs=0, chart_height_offset_buffs=0):
        pn.extension(design='material', theme='dark')
        self.df_config_debuffs, self.dict_poly_data_debuffs = self.process_config(self.config_debuffs, enable_target=True, chart_height_offset=chart_height_offset_debuffs)
        self.df_config_buffs, self.dict_poly_data_buffs = self.process_config(self.config_buffs, enable_target=False, chart_height_offset=chart_height_offset_buffs)

        # debuffs
        # pn.extension(design='material', theme='dark')
        tabs_debuff = pn.Tabs(styles=self.panel_tabs_style, sizing_mode='stretch_width')

        dict_pane_html = {}
        for k, v in self.dict_poly_data_debuffs.items():
            container_name = f"shadowdomdiv-{k}".replace(" ","-").replace("'","-").replace("(","").replace(")","")
            my_chart_dict = dict_deep_update(self.options_kwargs, v['options'])

            pane_html = pn.pane.HTML(sizing_mode='stretch_width',)
            pane_html.object = get_chart_html(my_chart_dict, container_name, files=["./utils/js/highcharts-dark-unica.js", "./utils/js/querySelectorAllShadows.js", "./utils/js/highchartssetupipynb.js"])
            dict_pane_html[k] = pane_html
            tabs_debuff.append(
                (
                    v['name'],
                    pn.Column(
                        pn.Row(pn.layout.HSpacer(), pn.widgets.StaticText(value=v['subtitle']), pn.layout.HSpacer()),
                        pane_html,
                    )
                )
            )
        if len(tabs_debuff)>0:
            tabs_debuff.active=0

        # buffs
        # pn.extension(design='material', theme='dark')
        tabs_buff = pn.Tabs(styles=self.panel_tabs_style, sizing_mode='stretch_width', tabs_location='below')

        dict_pane_html = {}
        for k, v in self.dict_poly_data_buffs.items():
            container_name = f"shadowdomdiv-{k}".replace(" ","-").replace("'","-").replace("(","").replace(")","")
            my_chart_dict = dict_deep_update(self.options_kwargs, v['options'])

            pane_html = pn.pane.HTML(sizing_mode='stretch_width',)
            pane_html.object = get_chart_html(my_chart_dict, container_name, files=["./utils/js/highcharts-dark-unica.js", "./utils/js/querySelectorAllShadows.js", "./utils/js/highchartssetupipynb.js"])
            dict_pane_html[k] = pane_html
            tabs_buff.append((v['name'],pane_html))

        if len(tabs_buff)>0:
            tabs_buff.active=0

        out = pn.Column(
            tabs_debuff,
            tabs_buff,
            sizing_mode='stretch_width',
        )
        return out


    def process_config(self, config, enable_target=True, chart_height_offset=0):
        df_config = pd.DataFrame(config)
        if df_config.empty:
            return df_config, {}

        for idx, row in df_config.iterrows():
            df_config.at[idx, 'id'] = row.obj.config['id']
            df_config.at[idx, 'type'] = row.obj.config['type']
            df_config.at[idx, 'data_type'] = row.obj.config['data_type']
            df_config.at[idx, 'row_num'] = row.obj.config['row_num']
            df_config.at[idx, 'id_shared_row'] = row.obj.config['id_shared_row']
            df_config.at[idx, 'row_span'] = row.obj.config['row_span']
            df_config.at[idx, 'is_secondary'] = row.obj.config['is_secondary']

        for idx, row in df_config.iterrows():
            # check if any shared rows already have an assigned row number
            row_num = df_config['row_num'][pd.notna(df_config.at[idx, 'id_shared_row']) & (df_config['id_shared_row'] == df_config.at[idx, 'id_shared_row'])].max()

            # otherwise assign a new row number
            if pd.isna(row_num):
                row_num = max(-1, df_config['row_num'].max()) + (idx > 0  and df_config.at[idx-1, 'row_span'] or 1)
            
            row.obj.set_row_num(row_num)
            row.obj.generate_graph_df()
            if row.obj.num_poly > 0 or row.obj.config['always_show'] or (row.obj.df_poly is not None and len(row.obj.df_poly) > 0):
                df_config.at[idx, 'row_num'] = row_num
                row.obj.generate_plot_bands()
                row.obj.generate_plot_lines()
            else:
                row.obj.set_row_num(np.nan)


        mask = (df_config['type'] == 'area') & (df_config['data_type'].isin(['enemy_health','mana']))
        row_spacing = 0.1
        df_config.loc[mask,'area_thres'] = (1-(0-0)/(1-0)) * df_config['row_span'] * (1-row_spacing*2/df_config['row_span']) + row_spacing + df_config['row_num']


        # get unique list of mobs
        list_targets = list(set([n for l in df_config[df_config['is_secondary']==False].apply(lambda x: x.obj.get_uniques(), axis=1).to_list() if l for n in l if n]))

        # sort unique list of mobs by id and instance
        list_targets = [list_targets[i] for i in np.argsort(["-".join(t.split("-")[::-1]) for t in list_targets]).tolist()]

        # ignore blacklisted npcs
        list_blacklist_npcs = [
            "Living Ember"
        ]
        list_targets = [target for target in list_targets if target.split("-")[0] not in list_blacklist_npcs]

        mask = df_config['row_num']>=0

        dict_poly_data = {}
        subtitle_base = f'Fire Mage Analysis<br>{self.metadata.actors.loc[self.player_id,"name"]} (ID: {self.player_id})'
        subtitle_url = f'https://classic.warcraftlogs.com/reports/{self.metadata.reportCode}#fight={self.fight_id}&type=damage-done&source={self.player_id}'
        subtitle_url = f'<a href="{subtitle_url}" target="_blank" style="color:#0072b5;">{subtitle_url}</a>'

        for target in list_targets:
            target_split = target.split("-")
            subtitle = (len(target_split) == 3 and f"{target_split[0]}-{target_split[1]} (ID: {target_split[2]})") or (len(target_split) == 2 and f"{target_split[0]} (ID: {target_split[1]})") or target
            tmp = df_config[mask].apply(lambda x: x.obj.generate_poly_series(target=enable_target and target or None), axis=1)
            tmp = [d for l in tmp if l for d in l]

            h = int(df_config['row_num'].max() + 1)
            dict_poly_data[target] = {
                'name': target,
                'subtitle': f"<center>{subtitle_base} / {subtitle}<br>{subtitle_url}</center>",
                'options': {
                    'series': tmp,
                    'yAxis': {
                        'max': h,
                        'plotBands': [l for ll in df_config[df_config['row_num']>=0].apply(lambda x: x.obj.plot_bands, axis=1) if ll for l in ll],
                        'plotLines': [l for ll in df_config[df_config['row_num']>=0].apply(lambda x: x.obj.plot_lines, axis=1) if ll for l in ll],
                    },
                    'chart': {
                        'marginLeft': 160,
                        'marginRight': 150,
                        'height': h*35 + chart_height_offset,
                    },
                }
            }

        return df_config, dict_poly_data

    def add_encounter_phase_lines(self):
        def phase_to_plot_line(phase):
            return {
                        'value': phase['timestamp'],
                        # 'color': 'black',
                        'dashStyle': 'Dot',
                        'width': 1,
                        'label': {
                            'style': {
                                'color': HAS_PYSCRIPT and "rgba(255, 255, 255, 0.5)" or "rgba(0, 0, 0, 0.5)",
                                'fontWeight': 'bold',
                            },
                            'rotation': 0,
                            'text': f'P{phase["id"]}',
                        }
                    }
        if self.metadata.encounters.loc[self.fight_id].phaseTransitions is not None:
            self.options_kwargs['xAxis']['plotLines'] += [phase_to_plot_line(phase) for phase in self.metadata.encounters.loc[self.fight_id].phaseTransitions[1:]]


    def load_config_chart(self):
        return {
            'title': {
                'text': '',
            },
            'style': {
              'fontFamily': 'serif',
              'stroke': '#dddddd',
            },
            'subtitle': {
                'text': '',
            },
            'credits': {
                'enabled': False,
            },
            'tooltip': {
                'split': False,
                'useHTML': True,
                # 'backgroundColor': 'RGBA(0,0,0,0.5)',
                'positioner': """FUNCTIONSTARTfunction(labelWidth, labelHeight, point) {
                        var plotX = point.plotX;
                        var plotY = point.plotY;
                        return {
                            x: plotX + labelWidth - this.chart.chartWidth + 200 > 0 ? plotX - labelWidth + 100: plotX + 200,
                            y: plotY - labelHeight -10 < 0 ? plotY + 35: plotY - labelHeight -10,
                        };
                }FUNCTIONEND""",
                'formatter': """FUNCTIONSTARTfunction(tooltip) {
                    if (this.point != undefined & this.point.custom != undefined) {
                        if (this.point.custom.tooltipHide != undefined) {
                            return false
                        }
                    }
                    return tooltip.defaultFormatter.call(this, tooltip);
                }FUNCTIONEND""",
            },
            'xAxis': {
                'min': 0,
                'max': self.fight_duration+1,
                'plotLines': [],
            },
            'yAxis': {
                'min': -0.5,
                # 'max': 4,
                'tickInterval': 1,
                'reversed': True,
                'alignTicks': False,
                'title': {
                    'text': '',
                },
                'labels':
                {
                    'enabled': False,
                },
                'startOnTick': False,
                'endOnTick': False,
                'tickAmount': None,
                'minorGridLineWidth': 0,
                'gridLineWidth': 0,
                'tickWidth': 0,
                'tickLength': 0
            },
            'plotOptions': {
                'polygon': {
                    'line_color': 'black',
                    'line_width': 1,
                    'animation': {
                        'duration': 0,
                    },
                    'states': {
                        'inactive': {
                            'opacity': 1,
                        },
                    },
                    'tooltip': {
                        'headerFormat': '<table><tr><th colspan="2" style="text-align: center"><span style="color:{series.color}">\u25CF</span> {series.name}</th></tr>',
                        'footerFormat': '</table>',
                        'useHTML': True,

                        'pointFormatter': """FUNCTIONSTARTfunction() {
                            if (this.series.userOptions.custom != undefined) {
                                return this.series.userOptions.custom.txt
                            }
                            if ((this.custom != undefined) && this.custom.txt != undefined)
                            {
                                return this.custom.txt
                            }
                        }FUNCTIONEND""",
                    },
                },
                'area': {
                    'turboThreshold': 0,
                    'tooltip': {
                        'headerFormat': '<table><tr><th colspan="2" style="text-align: center"><span style="color:{series.color}">\u25CF</span> {series.name}</th></tr>',
                        'footerFormat': '</table>',
                        'useHTML': True,

                        'pointFormatter': """FUNCTIONSTARTfunction() {
                            if (this.series.userOptions.custom != undefined) {
                                return this.series.userOptions.custom.txt
                            }
                            if ((this.custom != undefined) && this.custom.txt != undefined)
                            {
                                return this.custom.txt
                            }
                        }FUNCTIONEND""",
                    },
                },
                'scatter': {
                    'turboThreshold': 0,
                    'tooltip': {
                        'headerFormat': '<table><tr><th colspan="2" style="text-align: center"><span style="color:{series.color}">\u25CF</span> {series.name}</th></tr>',
                        'footerFormat': '</table>',
                        'useHTML': True,

                        'pointFormatter': """FUNCTIONSTARTfunction() {
                            if (this.series.userOptions.custom != undefined) {
                                return this.series.userOptions.custom.txt
                            }
                            if ((this.custom != undefined) && this.custom.txt != undefined)
                            {
                                return this.custom.txt
                            }
                        }FUNCTIONEND""",
                    },
                },
            },
        }

    # define in individual class files
    def load_config_debuffs(self):
        return []

    # define in individual class files
    def load_config_buffs(self):
        return []

    def generate_panel_tables(self):
        ################
        # Damage Table #
        ################
        blacklisted_spells = [22703,32835]
        mask = (self.df_player['sourceID'] == self.player_id) & (self.df_player['type'] == 'damage') & (~self.df_player['abilityGameID'].isin(blacklisted_spells)) & (self.metadata.actors["type"].loc[self.df_player['targetID']] == "NPC").to_list()
        df_table_dmg = self.df_player[mask]
        resist_categories = sorted(df_table_dmg['resistedRatio'].dropna().apply(lambda x: round(x,2)).unique())
        def get_crit_rate(x):
            num_crits = sum(x['hitTypeStr'].isin(['CRIT','RESIST_PARTIAL_CRIT']))
            num_miss = sum(x['hitTypeStr'].isin(['MISS']))

            s = pd.Series(
                {
                    'abilityGameName': x['abilityGameName'].iloc[0],
                    'total': len(x),
                    'numCrits': num_crits,
                    'critRate': round(num_crits/len(x),4),
                    'numMiss': num_miss,
                    'missRate': round(num_miss/len(x),4),
                }
            )

            # Percentage of resisted hits within each resist category (0%, 10%, 20%, etc...)
            for c in resist_categories:
                s[f"R{c*100:.0f}"] = round(sum(x['resistedRatio'].dropna().apply(lambda r: round(r,2)) == c)/len(x),4)

            # Percentage of total dmg resisted (total_resisted_dmg / (total_log_dmg + total_resisted_dmg)
            y = x.dropna(subset='resistedRatio')
            total_log_dmg = sum(y['amount'])
            s['dmg'] = int(total_log_dmg)
            if total_log_dmg>0:
                total_resisted_dmg = sum(y['amount'] / (1-y['resistedRatio']) - y['amount'])
                s['res'] = int(round(total_resisted_dmg,0))
                s['resDmgRate'] = round(total_resisted_dmg / (total_log_dmg + total_resisted_dmg),4)
            else:
                s['res'] = 0
                s['resDmgRate'] = 0

            s['hitDmgMult'] = round(x[x['hitTypeStr'].isin(['HIT','RESIST_PARTIAL'])]['dmgMultiplier'].mean(),4)
            s['critDmgMult'] = round(x[x['hitTypeStr'].isin(['CRIT','RESIST_PARTIAL_CRIT'])]['dmgMultiplier'].mean(),4)

            return s
        df_table_dmg = df_table_dmg.groupby('abilityGameID').apply(get_crit_rate).reset_index().sort_values(by='dmg', ascending=False).set_index("abilityGameID")

        # Add in frozen total row 
        d = {'abilityGameName': 'Total'}
        d['dmg'] = df_table_dmg['dmg'].sum()
        d['res'] = df_table_dmg['res'].sum()
        d['resDmgRate'] = d['resDmgRate'] = d['res']/(d['dmg']+d['res'])

        # Compute weighted average crit-rate (this ignores any spells that hasn't had a crit event, so it may exclude spells that can crit but didn't crit at all)
        d['numCrits'] = df_table_dmg['numCrits'].sum()
        d['critRate'] = (df_table_dmg['numCrits']/d['numCrits']*df_table_dmg['critRate']).sum()

        d['total'] = df_table_dmg['total'].sum()
        d['numMiss'] = df_table_dmg['numMiss'].sum()
        d['missRate'] = d['numMiss']/d['total']

        df_table_dmg.loc['Total'] = pd.Series(d)







        css = """
.tabulator-cell, .tabulator-col-title {
    font-size: 14px;
}
.tabulator-header .tabulator-col {
    background-color: #222222 !important;
}
.tabulator-row-odd {
    background-color: #141414 !important;
}
.tabulator-row-even {
    background-color: #1f1f1f !important;
}
.tabulator-row-odd:hover, .tabulator-row-even:hover {
    background-color: #444444 !important;
    color: #ffffff !important;
}
# .tabulator-tableholder {
#     border: 1px solid #F00;
# }
# .tabulator-cell {
#     # border: 1px solid #F00;
# }
# .tabulator-col {
#     # border: 1px solid #F00;
# }
"""
        dict_col_grps = {
            'Ability': {
                'abilityGameID': 'ID',
                'abilityGameName': 'Name',
                'total': 'Count',
            },
            'Crit': {
                'numCrits': 'Count',
                'critRate': 'Rate',
            },
            'Miss': {
                'numMiss': 'Count',
                'missRate': 'Rate',
            },
            'Dmg Multiplier': {
                'hitDmgMult': 'Hit',
                'critDmgMult': 'Crit',
            },
            'Resist Categories': {f"R{c*100:.0f}": f"{c*100:.0f}%" for c in resist_categories},
            'Total Dmg Done & Resisted': {
                'dmg': 'Dmg',
                'res': 'Res',
                'resDmgRate': 'Rate',
            },
        }
        bokeh_formatters = {
            ('Ability', 'ID'): NumberFormatter(format='0'),
            ('Crit','Rate'): NumberFormatter(format='0.00%'),
            ('Crit','Count'): NumberFormatter(format='0'),
            ('Miss', 'Rate'): NumberFormatter(format='0.00%'),
            ('Miss', 'Count'): NumberFormatter(format='0'),
            ('Resist Categories', '0%'): NumberFormatter(format='0.00%'),
            ('Resist Categories', '10%'): NumberFormatter(format='0.00%'),
            ('Resist Categories', '20%'): NumberFormatter(format='0.00%'),
            ('Total Dmg Done & Resisted', 'Dmg'): NumberFormatter(format='0,'),
            ('Total Dmg Done & Resisted', 'Res'): NumberFormatter(format='0,'),
            ('Total Dmg Done & Resisted', 'Rate'): NumberFormatter(format='0.00%'),
            ('Dmg Multiplier', 'Hit'): NumberFormatter(format='0.000'),
            ('Dmg Multiplier', 'Crit'): NumberFormatter(format='0.000'),
        }
        text_align = {}
        for k, v in bokeh_formatters.items():
            if type(v) == NumberFormatter:
                text_align[k] = 'right'

        df = df_table_dmg.reset_index().rename({col_name_orig: (grp_name, col_name_new) for grp_name, d in dict_col_grps.items() for col_name_orig, col_name_new in d.items()}, axis=1)

        groups = {grp_name: [(grp_name, col_name_new) for col_name_new in d.values()] for grp_name, d in dict_col_grps.items()}
        titles = {(grp_name, col_name_new): col_name_new for grp_name, d in dict_col_grps.items() for col_name_orig, col_name_new in d.items()}
        pn_table_dmg = pn.widgets.Tabulator(df.replace(0,np.nan), theme='default', show_index=False, selectable=False, disabled=True, stylesheets=[css], groups=groups, titles=titles, formatters=bokeh_formatters, text_align=text_align)
        pn_table_dmg.frozen_rows = [-1]




        #################
        # Clipped/Ticks #
        #################
        mask = (self.df_config_debuffs['type']=='poly') & (self.df_config_debuffs['update_fn']=='dot_debuff') & (self.df_config_debuffs['df_poly'].notna())

        df_table_clips = self.df_config_debuffs.loc[mask,['ability_ids','df_poly']].copy()
        # df_table_clips['abilityGameID'] = df_table_clips['ability_ids'].apply(lambda s: s[0] if len(s) == 1 else None)
        df_table_clips['abilityGameID'] = df_table_clips['ability_ids'].apply(lambda s: s[0])
        df_table_clips.drop('ability_ids', axis=1, inplace=True)
        df_table_clips['abilityGameName'] = df_table_clips['abilityGameID'].map(self.metadata.abilities['name'])

        def generate_clip_stats(s):
            df_poly = s['df_poly']

            mask = df_poly['polyClip'] == True
            clipStats = (df_poly.loc[mask,'polyEnd']-df_poly.loc[mask,'polyStart']).describe()

            mask = df_poly['polyClip'] == False
            tickStats = (df_poly.loc[mask,'polyEnd']-df_poly.loc[mask,'polyStart']).describe()

            s_out = pd.Series(
                {
                    'abilityGameID': s['abilityGameID'],
                    'abilityGameName': s['abilityGameName'],

                    'clipCount': clipStats['count'],
                    'clipMean': clipStats['mean'],
                    'clipStd': clipStats['std'],
                    'clipMin': clipStats['min'],
                    'clip25%': clipStats['25%'],
                    'clip50%': clipStats['50%'],
                    'clip75%': clipStats['75%'],
                    'clipMax': clipStats['max'],
                }
            )
            return s_out

        def generate_tick_stats(s):
            df_poly = s['df_poly']

            mask = df_poly['polyClip'] == True
            clipStats = (df_poly.loc[mask,'polyEnd']-df_poly.loc[mask,'polyStart']).describe()

            mask = df_poly['polyClip'] == False
            tickStats = (df_poly.loc[mask,'polyEnd']-df_poly.loc[mask,'polyStart']).describe()

            s_out = pd.Series(
                {
                    'abilityGameID': s['abilityGameID'],
                    'abilityGameName': s['abilityGameName'],

                    'tickCount': tickStats['count'],
                    'tickMean': tickStats['mean'],
                    'tickStd': tickStats['std'],
                    'tickMin': tickStats['min'],
                    'tick25%': tickStats['25%'],
                    'tick50%': tickStats['50%'],
                    'tick75%': tickStats['75%'],
                    'tickMax': tickStats['max'],
                }
            )
            return s_out

        df_table_ticks = df_table_clips.apply(generate_tick_stats,axis=1)
        df_table_clips = df_table_clips.apply(generate_clip_stats,axis=1)

        dict_col_grps = {
            'Ability': {
                'abilityGameID': 'ID',
                'abilityGameName': 'Name',
            },
            'Tick (sec)': {
                'tickCount': 'Count',
                'tickMin':   'Min',
                'tickMean':  'Mean',
                'tickStd':   'Std',
                'tick25%':   '25%',
                'tick50%':   '50%',
                'tick75%':   '75%',
                'tickMax':   'Max',
            },
            'Clipped (sec)': {
                'clipCount': 'Count',
                'clipMin':   'Min',
                'clipMean':  'Mean',
                'clipStd':   'Std',
                'clip25%':   '25%',
                'clip50%':   '50%',
                'clip75%':   '75%',
                'clipMax':   'Max',
            },
        }
        bokeh_formatters = {
            ('Ability', 'ID'): NumberFormatter(format='0'),
            ('Tick (sec)', 'Count'): NumberFormatter(format='0'),
            ('Tick (sec)', 'Min'): NumberFormatter(format='0.000'),
            ('Tick (sec)', 'Mean'): NumberFormatter(format='0.000'),
            ('Tick (sec)', 'Std'): NumberFormatter(format='0.000'),
            ('Tick (sec)', '25%'): NumberFormatter(format='0.000'),
            ('Tick (sec)', '50%'): NumberFormatter(format='0.000'),
            ('Tick (sec)', '75%'): NumberFormatter(format='0.000'),
            ('Tick (sec)', 'Max'): NumberFormatter(format='0.000'),
            ('Clipped (sec)', 'Count'): NumberFormatter(format='0'),
            ('Clipped (sec)', 'Min'): NumberFormatter(format='0.000'),
            ('Clipped (sec)', 'Mean'): NumberFormatter(format='0.000'),
            ('Clipped (sec)', 'Std'): NumberFormatter(format='0.000'),
            ('Clipped (sec)', '25%'): NumberFormatter(format='0.000'),
            ('Clipped (sec)', '50%'): NumberFormatter(format='0.000'),
            ('Clipped (sec)', '75%'): NumberFormatter(format='0.000'),
            ('Clipped (sec)', 'Max'): NumberFormatter(format='0.000'),
            ('Clipped (sec)', 'Count'): NumberFormatter(format='0'),
        }
        text_align = {}
        for k, v in bokeh_formatters.items():
            if type(v) == NumberFormatter:
                text_align[k] = 'right'


        groups = {grp_name: [(grp_name, col_name_new) for col_name_new in d.values()] for grp_name, d in dict_col_grps.items()}
        titles = {(grp_name, col_name_new): col_name_new for grp_name, d in dict_col_grps.items() for col_name_orig, col_name_new in d.items()}

        df = df_table_clips.rename({col_name_orig: (grp_name, col_name_new) for grp_name, d in dict_col_grps.items() for col_name_orig, col_name_new in d.items()}, axis=1)
        pn_table_clips = pn.widgets.Tabulator(df.replace(0,np.nan), theme='default', show_index=False, selectable=False, disabled=True, stylesheets=[css], groups=groups, titles=titles, formatters=bokeh_formatters, text_align=text_align)

        df = df_table_ticks.rename({col_name_orig: (grp_name, col_name_new) for grp_name, d in dict_col_grps.items() for col_name_orig, col_name_new in d.items()}, axis=1)
        pn_table_ticks = pn.widgets.Tabulator(df.replace(0,np.nan), theme='default', show_index=False, selectable=False, disabled=True, stylesheets=[css], groups=groups, titles=titles, formatters=bokeh_formatters, text_align=text_align)

        out = pn.Column(pn_table_dmg, pn_table_clips, pn_table_ticks)
        return out

    def generate_panel_to_div(self, target_div):
        return