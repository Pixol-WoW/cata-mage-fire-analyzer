import panel as pn
import pandas as pd
import numpy as np

from utils.analyzers.PixolClassAnalyzerBase import PixolClassAnalyzerBase
from utils.analyzers.PixolClassAnalyzerGraph import PixolDotDebuff, PixolIgniteDebuff, PixolMergedDebuff, PixolEnemyHealth, PixolBuff, PixolHeatingUp, PixolSpellPower, PixolMastery, PixolMana, PixolMovement, PixolCasts, PixolHaste
from utils.analyzers.MageFire.PixolClassAnalyzerGraphMageFire import PixolIgniteTickEstimate, PixolCombustionStats
from utils.analyzers.MageFire.MasteryIgniteEstimator import masteryEstimatorClass, igniteEstimatorClass

from utils.misc import dict_deep_update, get_mmss, wrap_trtd, merge_overlapping_intervals, get_idx_from_bool_series

class PixolClassAnalyzerMageFire(PixolClassAnalyzerBase):
    def load_config_debuffs(self):
        # supported parameters
        # id [string] (required): unique string that will be displayed in the highcharts legend. It is also used to link graphs together to the same legend key
        # ability [list of int] (required): list of ability ids to be tracked
        # id_shared_row [int]: debuffs with the same id will be plotted onto the same row
        # update_fn [function] (required): a specified function that will return dataframe of poly data
        # always_show [bool] (default: False): reserves a row for it even if no data is found (useful to show that a debuff wasn't present)
        # is_secondary [bool] (default: False): auto hides all data if there's only secondary data present, e.g. useful for ignoring a bunch of mobs hit by ebon plague (secondary) but not hit by corruption (primary)
        # url [string]: wowhead icon link and tooltip mouseover
        # img [string]: wowhead image icon link
        # df_in [pandas.DataFrame] (required): input dataframe to process data from
        # max_stacks [int] (default: 1): debuffs with stacks will have their graph height modified based on current stacks vs max stacks
        # height [float] (default: 0.4): graph height
        # yOffset [float] (default: 0): graph y-offset

        return [
            {
                'obj': PixolDotDebuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Living Bomb',
                    ability_ids = [44457],
                    always_show = True,
                    show_clip_on_refresh = True,
                    url = 'https://www.wowhead.com/cata/spell=55360/living-bomb&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/ability_mage_livingbomb.jpg',
                )
            },
            {
                'obj': PixolDotDebuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Pyroblast',
                    ability_ids = [11366],
                    always_show = True,
                    ticks_only = True,

                    url = 'https://www.wowhead.com/cata/spell=11366/pyroblast&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_fire_fireball02.jpg',
                )
            },
            {
                'obj': PixolDotDebuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Pyroblast!',
                    ability_ids = [92315],
                    always_show = True,
                    ticks_only = True,
                    url = 'https://www.wowhead.com/cata/spell=11366/pyroblast&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_fire_fireball02.jpg',
                )
            },
            {
                'obj': PixolIgniteDebuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Ignite',
                    ability_ids = [413841, 413843],
                    always_show = True,
                    ignore_ability_id_grouping = True,
                    url = 'https://www.wowhead.com/cata/spell=413841/ignite&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_fire_incinerate.jpg',
                )
            },
            {
                'obj': PixolCombustionStats(self.df_player, self.metadata, self.fight_id,
                    id = 'Combustion Stats',
                    always_show = True,
                    url = 'https://www.wowhead.com/cata/spell=83853/combustion&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_fire_sealoffire.jpg',
                )
            },
            {
                'obj': PixolDotDebuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Combustion',
                    ability_ids = [83853],
                    always_show = True,
                    ticks_only = True,
                    url = 'https://www.wowhead.com/cata/spell=83853/combustion&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_fire_sealoffire.jpg',
                )
            },
            {
                'obj': PixolMergedDebuff(self.df_misc, self.metadata, self.fight_id,
                    id = '8% Magic',
                    # any additional ability ids must be added below in fetch_events function below for df_misc to contain them
                    ability_ids = [1490, 60433, 65142, 86105, 93068], # Curse of the Elements, Earth and Moon, Ebon Plague, Jinx: Curse of the Elements, Master Poisoner
                    always_show = True,
                    is_secondary = True,
                    url = 'https://www.wowhead.com/cata/spell=51735/ebon-plague&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_shadow_nethercloak.jpg',
                    yOffset = 0,
                    height = 0.4,
                )
            },
            {
                'obj': PixolMergedDebuff(self.df_misc, self.metadata, self.fight_id,
                    id = '5% Crit',
                    ability_ids = [17800, 22959], # Shadow and Flame, Critical Mass
                    always_show = True,
                    is_secondary = True,
                    url = 'https://www.wowhead.com/cata/spell=22959/critical-mass',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_nature_wispheal.jpg',
                    yOffset = 0,
                    height = 0.4,
                )
            },
            {
                'obj': PixolIgniteTickEstimate(self.df_player, self.metadata, self.fight_id,
                    id = 'Ignite Tick',
                    source_id = self.player_id,
                    y_axis_label = 'Ignite Tick',
                    row_span = 2,
                    always_show = True,
                    is_secondary = True,
                    type = 'area',
                )
            },
            {
                'obj': PixolEnemyHealth(self.df_misc, self.metadata, self.fight_id,
                    id = 'Health',
                    y_axis_label = 'Health',
                    row_span = 1,
                    always_show = True,
                    is_secondary = True,
                    type = 'area',
                )
            },
        ]
    def load_config_buffs(self):
        return [
            {
                'obj': PixolBuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Hot Streak',
                    ability_ids = [48108],
                    show_clip_on_refresh = True,
                    always_show = True,
                    url = 'https://www.wowhead.com/cata/spell=48108/hot-streak&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/ability_mage_hotstreak.jpg',
                    target_ids = [self.player_id],
                )
            },
            {
                'obj': PixolHeatingUp(self.df_player, self.metadata, self.fight_id,
                    id = 'Heating Up',
                    source_ids = [self.player_id],
                    always_show = True,
                    row_span = 1,
                    type = 'area',
                    y_axis_label = 'Heating Up',
                )
            },
            {
                'obj': PixolBuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Impact',
                    ability_ids = [64343],
                    always_show = True,
                    url = 'https://www.wowhead.com/cata/spell=64343/impact&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_fire_meteorstorm.jpg',
                    target_ids = [self.player_id],
                )
            },
            {
                'obj': PixolBuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Potion',
                    ability_ids = [79476],
                    always_show = True,
                    url = 'https://www.wowhead.com/cata/spell=79476/volcanic-power&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/inv_potiond_3.jpg',
                    target_ids = [self.player_id],
                )
            },
            {
                'obj': PixolBuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Lightweave',
                    ability_ids = [75170],
                    url = 'https://www.wowhead.com/cata/spell=75170/lightweave&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_arcane_prismaticcloak.jpg',
                    target_ids = [self.player_id],
                )
            },
            {
                'obj': PixolBuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Synapse',
                    ability_ids = [96230],
                    url = 'https://www.wowhead.com/cata/spell=96230/synapse-springs&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_shaman_elementaloath.jpg',
                    target_ids = [self.player_id],
                )
            },
            {
                'obj': PixolBuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Berserking',
                    ability_ids = [26297],
                    url = 'https://www.wowhead.com/cata/spell=26297/berserking&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/racial_troll_berserk.jpg',
                    target_ids = [self.player_id],
                )
            },
            {
                'obj': PixolBuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Power Infusion',
                    ability_ids = [10060],
                    url = 'https://www.wowhead.com/cata/spell=10060/power-infusion&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_holy_powerinfusion.jpg',
                    target_ids = [self.player_id],
                )
            },
            {
                'obj': PixolBuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Lust',
                    ability_ids = [32182, 2825, 80353], # Heroism, Bloodlust, Time Warp
                    url = 'https://www.wowhead.com/cata/spell=32182/heroism&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/ability_shaman_heroism.jpg',
                    target_ids = [self.player_id],
                )
            },
            {
                'obj': PixolBuff(self.df_player, self.metadata, self.fight_id,
                    id = 'Pyromaniac',
                    ability_ids = [83582],
                    url = 'https://www.wowhead.com/cata/spell=83582/pyromaniac&buff=true',
                    img = 'https://wow.zamimg.com/images/wow/icons/large/spell_fire_burnout.jpg',
                    target_ids = [self.player_id],
                )
            },
            {
                'obj': PixolSpellPower(self.df_player, self.metadata, self.fight_id,
                    id = 'SP',
                    source_ids = [self.player_id],
                    y_axis_label = 'SP',
                    row_span = 1,
                    always_show = True,
                    type = 'area',
                )
            },
            {
                'obj': PixolHaste(self.df_player, self.metadata, self.fight_id,
                    id = 'Haste',
                    source_ids = [self.player_id],
                    y_axis_label = 'Haste',
                    row_span = 1,
                    always_show = True,
                    type = 'area',
                )
            },
            {
                'obj': PixolMastery(self.df_player, self.metadata, self.fight_id,
                    id = 'Mastery',
                    source_ids = [self.player_id],
                    y_axis_label = 'Mastery',
                    row_span = 1,
                    type = 'area',
                    always_show = True,
                    df_mastery = self.df_mastery,
                    showDecimalsOnPlotLine = True,
                )
            },
            {
                'obj': PixolMana(self.df_player, self.metadata, self.fight_id,
                    id = 'Mana',
                    source_ids = [self.player_id],
                    y_axis_label = 'Mana',
                    row_span = 1,
                    always_show = True,
                    type = 'area',
                )
            },
            {
                'obj': PixolMovement(self.df_player, self.metadata, self.fight_id,
                    id = 'Movement',
                    source_ids = [self.player_id],
                    y_axis_label = 'Movement',
                    row_span = 1,
                    always_show = True,
                    type = 'area',
                    window = 10,
                )
            },
            {
                'obj': PixolCasts(self.df_player, self.metadata, self.fight_id,
                    id = 'Casts',
                    source_ids = [self.player_id],
                    y_axis_label = 'Casts',
                    row_span = 1,
                    always_show = True,
                    type = 'scatter',
                    spell_ids_blacklist = [
                        2139, # Counterspell
                        1953, # Blink
                        55342, # Mirror Image
                        66, # Invisibility
                        12051, # Evocation
                        11113, # Blast Wave
                        82731, # Flame Orb
                        44457, # Living Bomb
                        2120, # Flamestrike
                        31661, # Dragon's Breath
                        45438, # Ice Block
                        80353, # Time Warp
                        6117, # Mage Armor
                        30482, # Molten Armor
                        543, # Mage Ward
                        5405, # Replenish Mana
                        1463, # Mana Shield
                        82174, # Synapse Springs
                        30449, # Spellsteal
                        11129, # Combustion
                        2136, # Fire Blast
                        26297, # Berserking
                        79476, # Volcanic Power

                        
                        64343, # Impact
                    ],
                )
            },
            {
                'obj': PixolCasts(self.df_player, self.metadata, self.fight_id,
                    id = 'Casts (Misc)',
                    source_ids = [self.player_id],
                    y_axis_label = 'Casts (CDs)',
                    row_span = 1,
                    always_show = True,
                    type = 'scatter',
                    spell_ids = [
                        82731, # Flame Orb
                        11129, # Combustion
                    ],
                )
            },
            {
                'obj': PixolCasts(self.df_player, self.metadata, self.fight_id,
                    id = 'Casts (Misc)',
                    source_ids = [self.player_id],
                    y_axis_label = 'Casts (Misc)',
                    row_span = 1,
                    always_show = True,
                    type = 'scatter',
                    spell_ids = [
                        2139, # Counterspell
                        1953, # Blink
                        55342, # Mirror Image
                        66, # Invisibility
                        12051, # Evocation
                        11113, # Blast Wave
                        44457, # Living Bomb
                        2120, # Flamestrike
                        31661, # Dragon's Breath
                        45438, # Ice Block
                        80353, # Time Warp
                        6117, # Mage Armor
                        30482, # Molten Armor
                        543, # Mage Ward
                        5405, # Replenish Mana
                        1463, # Mana Shield
                        82174, # Synapse Springs
                        30449, # Spellsteal
                        2136, # Fire Blast
                        26297, # Berserking
                        79476, # Volcanic Power
                    ],
                )
            },
        ]

    async def fetch_events(self):
        self.data_player, self.data_combatant, _ = await self.client._fetch_events(self.metadata.reportCode, metadata=self.metadata, source_id=self.player_id, fight_id=self.fight_id, include_combatant_info=True)
        if len(self.data_player.events) == 0 or 'amount' not in self.data_player.events.columns:
            raise Exception('No data found for this player')
        self.data_misc, _, _ = await self.client._fetch_events(self.metadata.reportCode, metadata=self.metadata, fight_id=self.fight_id, include_combatant_info=False, filter_exp='ability.id in (1490, 17800, 22959, 60433, 65142, 86105, 93068) or resources.actor.type = "NPC"')

        self.df_player = self.data_player.events
        self.df_misc = self.data_misc.events
        self.add_mastery_data()
        self.add_ignite_data()
        self.load_configs()

    def add_mastery_data(self):
        self.masteryEstimatorObj = masteryEstimatorClass(self.df_player, self.player_id, enableDebug=True)
        self.masteryEstimatorObj.estimateMastery()

        # No Mastery procs
        if len(self.masteryEstimatorObj.list_timestamp_mastery) == 1:
            self.masteryEstimatorObj.list_timestamp_mastery.append({'idx': -1, 'timestamp': self.fight_duration, 'masteryOffset': self.masteryEstimatorObj.list_timestamp_mastery[0]['masteryOffset'] + 1e-6})

        self.df_mastery = pd.DataFrame(self.masteryEstimatorObj.list_timestamp_mastery)
        self.df_mastery['mastery'] = self.df_mastery['masteryOffset'] + self.masteryEstimatorObj.df['m-mEstimate'].median()

        mask = self.df_player["type"].isin(["damage","cast"])
        within_range_mask = self.df_player.loc[mask].index.values[:, np.newaxis] >= self.df_mastery['idx'].values

        # Grab last occuring column of argmax by reversing the columns since argmax returns first occuring column
        within_range_mask = within_range_mask[:,::-1]
        match_index = within_range_mask.shape[1] - 1 - within_range_mask.argmax(axis=1)

        # If no matches, set to -1
        match_index[np.sum(within_range_mask, axis=1) == 0] = -1

        # df_timestamps.loc[match_index>=0, 'range_index'] = timestamp_ranges.loc[match_index[match_index>=0],'val'].values
        self.df_player.loc[get_idx_from_bool_series(mask)[match_index>=0], 'm-masteryEstimate'] = self.df_mastery.loc[match_index[match_index>=0],'mastery'].values

    def add_ignite_data(self):
        df_ignite_estimates = igniteEstimatorClass(self.masteryEstimatorObj.df, enableDebug=True).estimateIgnites()
        idx_ignite_tick_estimates = get_idx_from_bool_series(df_ignite_estimates['i-TickAmount'].notna())
        self.df_player.loc[idx_ignite_tick_estimates,"i-TickAmount"] = df_ignite_estimates['i-TickAmount']
        
    def generate_panel_to_div(self, target_div):
        tabs_graphs = self.generate_panel_graphs(chart_height_offset_debuffs=40)
        out = pn.Tabs(
            ("Graphs", tabs_graphs),
            # ("Tables", tabs_tables),
            styles=self.panel_tabs_style,
            sizing_mode='stretch_width',
        )

        # bokeh.io.output_notebook(INLINE)
        pn.extension("tabulator", design='material', theme='dark')
        out.servable(target=target_div)
        return out

