import pandas as pd
from datetime import datetime
import numpy as np

class WCLReportMetaData:
    def __init__(
        self,
        metadata,
        includeAllFightsAsEncounters=False,
        reportCode=None,
    ):
        self.reportCode = reportCode
        self.rawData = metadata
        self.title = metadata['title']
        self.guild = metadata['guild']
        self.startTime = metadata['startTime']

        self.fights = pd.DataFrame(metadata['fights']).set_index('id')
        self.fights.insert(self.fights.columns.get_loc('endTime')+1, 'duration', (self.fights['endTime']-self.fights['startTime'])/1000)
        # self.dict_fights = self.fights.set_index('id').to_dict('index')

        if includeAllFightsAsEncounters:
            self.encounters = self.fights
        else:
            self.encounters = self.fights[self.fights['encounterID']>0]

            # Include all fights as encounter if no encounters found (for training dummy logs)
            if len(self.encounters) == 0:
                self.encounters = self.fights

        # format encounter name with start time, duration, and wipe number or kill
        self.encounters.insert(2,'wipeCounter', self.encounters.groupby(['name','kill']).cumcount()+1)
        try:
            self.encounters.insert(2,'formattedName', self._get_formatted_encounter_strings())
        except:
            self.encounters.insert(2,'formattedName',None)
            pass

        # offset phase transition timestamps
        def offset_phase_transition_timestamps(x):
            if x.phaseTransitions:
                for datum in x.phaseTransitions:
                    datum['timestamp'] = (datum['startTime'] - x.startTime)/1000
                    del datum['startTime']
        self.encounters.apply(offset_phase_transition_timestamps, axis=1)

        # self.dict_encounters = self.encounters.set_index('id').to_dict('index')

        self.abilities = pd.DataFrame(metadata['masterData']['abilities']).set_index('gameID')
        self._override_ability_name_icon()
        # self.dict_abilities = self.abilities.set_index('gameID').to_dict('index')

        self.actors = pd.DataFrame(metadata['masterData']['actors']).set_index('id')
        # self.dict_actors = self.actors.set_index('id').to_dict('index')

        try:
            self.dps = pd.DataFrame(metadata['playerDetails']['data']['playerDetails']['dps'])
        except:
            self.dps = pd.DataFrame(columns=['name','id','guid','type','server','icon','specs','minItemLevel','maxItemLevel','potionUse','healthstoneUse','combatantInfo'])

        try:
            self.healers = pd.DataFrame(metadata['playerDetails']['data']['playerDetails']['healers'])
        except:
            self.healers = pd.DataFrame(columns=['name','id','guid','type','server','icon','specs','minItemLevel','maxItemLevel','potionUse','healthstoneUse','combatantInfo'])

        try:
            self.tanks = pd.DataFrame(metadata['playerDetails']['data']['playerDetails']['tanks'])
        except:
            self.tanks = pd.DataFrame(columns=['name','id','guid','type','server','icon','specs','minItemLevel','maxItemLevel','potionUse','healthstoneUse','combatantInfo'])

        self.df_mage_fire = self._get_class_spec('Mage', 'Fire')


    def _get_class_spec(self, c, s):
        def filter_class_spec(_d, _c, _s):
            if _d['type'] == _c:
                for spec in _d['specs']:
                    if ('spec' in spec) and (spec['spec'] == _s):
                        return True
            return False
        return pd.concat([role[role.apply(lambda x: filter_class_spec(x, c, s),axis=1)] for role in [self.dps, self.healers, self.tanks]])

    def _get_formatted_encounter_strings(self):
        def format_encounter_name(x):
            durationInSeconds = (x['endTime']-x['startTime'])//1000

            return f"{datetime.fromtimestamp((x['startTime']+self.startTime)/1000).strftime('%I:%M %p')} - {x['name']}{x['difficulty'] == 4 and ' [H]' or ''} ({durationInSeconds//60:0d}:{durationInSeconds%60:02d}, {(x['kill'] and 'Kill') or ('Wipe ' + str(x['wipeCounter']))})"

        return self.encounters.apply(format_encounter_name, axis=1).to_list()

    def _override_ability_name_icon(self):
        if 17941 in self.abilities.index:
            self.abilities.loc[17941,'name'] = 'Shadow Trance'
            self.abilities.loc[17941,'icon'] = 'spell_shadow_twilight.jpg'

HIT_TYPES = {
    0: "MISS",
    1: "NORMAL",
    2: "CRIT",
    3: "ABSORB",
    4: "BLOCKED_NORMAL",
    5: "BLOCKED_CRIT",
    6: "GLANCING",
    7: "DODGE",
    8: "PARRY",
    9: "DEFLECT",
    10: "IMMUNE",
    11: "MISSFIRE",
    12: "REFLECT",
    13: "EVADE",
    14: "RESIST_FULL",
    15: "CRUSHING",
    16: "RESIST_PARTIAL",
    17: "RESIST_PARTIAL_CRIT",
}

class WCLReportFightData:
    def __init__(
        self,
        events,
        metadata=None,
        fight_id=None,
    ):
        self.rawData = events
        self.events = pd.DataFrame(events)
        self.metadata = metadata
        if 'timestamp' in self.events:
            if self.metadata and fight_id:
                self.events.timestamp = self.events.timestamp - self.metadata.encounters.loc[fight_id]['startTime']
            self.events.timestamp = self.events.timestamp/1000
        self._create_tick_column()
        self._create_total_dmg_column()
        self._create_dmg_multiplier_and_resisted_ratio_columns() # Requires amountTotal to be calculated first
        self._create_hit_type_str_column()
        self._add_is_absorb_full_column() # Requires amountTotal to be calculated first
        self._create_resource_id_column()
        self._create_ability_name_column()
        self._create_target_name_columns('source')
        self._create_target_name_columns('target')

        if 'sourceNameInstanceUnique' in self.events.columns:
            self.events["sourceNameInstanceUnique"] = self.events["sourceNameInstanceUnique"].fillna("Environment")

    def _add_is_absorb_full_column(self):
        if 'amount' not in self.events.columns:
            return
        self.events['isAbsorbFull'] = False
        # todo: full absorbs with resists
        mask = (self.events['type'] == "damage") & (self.events['amountTotal'] > 0) & (self.events['amountTotal'] == self.events['absorbed']) & (self.events['hitType'] == 1)
        self.events.loc[mask,'isAbsorbFull'] = True

    def _create_tick_column(self):
        if 'tick' in self.events.columns:
            self.events['tick'] = self.events['tick'].notna()
        else:
            self.events['tick'] = False

    def _create_total_dmg_column(self):
        if 'amount' not in self.events.columns:
            return

        if 'overkill' not in self.events.columns:
            self.events['overkill'] = 0
        s = self.events.loc[self.events.type=='damage', 'overkill'].fillna(0)
        self.events.loc[s.index,'overkill'] = s

        if 'absorb' not in self.events.columns:
            self.events['absorbed'] = 0
        s = self.events.loc[self.events.type=='damage', 'absorbed'].fillna(0)
        self.events.loc[s.index,'absorbed'] = s

        # todo: check resisted
        self.events['amountTotal'] = self.events['amount'] + self.events['overkill'].fillna(0) + self.events['absorbed'].fillna(0)
        

    def _create_dmg_multiplier_and_resisted_ratio_columns(self):
        if 'amount' not in self.events.columns:
            return
        if 'resisted' not in self.events.columns:
            self.events.loc[:,'resisted'] = 0
            
        s = self.events.loc[(self.events.type=='damage') & (self.events.amountTotal.notna()), 'resisted'].fillna(0)
        self.events.loc[s.index,'resisted'] = s

        # todo: check resisted
        df = self.events[self.events.type=='damage']
        self.events.insert(self.events.columns.get_loc('amountTotal')+1, 'dmgMultiplier', None)
        self.events.loc[df.index,'dmgMultiplier'] = df.amountTotal/(df.unmitigatedAmount-df.resisted)
        self.events.insert(self.events.columns.get_loc('resisted')+1, 'resistedRatio', None)
        self.events.loc[df.index,'resistedRatio'] = df.resisted/df.unmitigatedAmount

    def _create_hit_type_str_column(self):
        if 'hitType' not in self.events.columns:
            return

        self.events.insert(self.events.columns.get_loc('hitType')+1, 'hitTypeStr', None)
        s = self.events.loc[self.events['hitType'].notna(),'hitType'].map(HIT_TYPES)
        self.events.loc[s.index,'hitTypeStr'] = s

    def _create_resource_id_column(self):
        if 'resourceActor' in self.events.columns:
            # def map_resource_actor(x):
            #     return x.resourceActor == 1 and x.sourceID or x.resourceActor == 2 and x.targetID or None
            # self.events.insert(self.events.columns.get_loc('resourceActor')+1, 'resourceActorID', self.events.apply(map_resource_actor, axis=1).to_list())

            self.events.insert(self.events.columns.get_loc('resourceActor')+1, 'resourceActorID', None)
            mask = self.events.resourceActor == 1
            self.events.loc[mask,'resourceActorID'] = self.events.loc[mask,'sourceID']
            mask = self.events.resourceActor == 2
            self.events.loc[mask,'resourceActorID'] = self.events.loc[mask,'targetID']
        return

    def _create_ability_name_column(self):
        if 'abilityGameID' in self.events.columns:
            # def map_ability_id(x):
            #     d = self.metadata.dict_abilities.get(x.abilityGameID)
            #     if d == None:
            #         return None
            #     return d.get('name')
            # self.events.insert(self.events.columns.get_loc('abilityGameID')+1, 'abilityGameName', self.events.apply(map_ability_id, axis=1).to_list())
            self.events.insert(self.events.columns.get_loc('abilityGameID')+1, 'abilityGameName', self.events['abilityGameID'].map(self.metadata.abilities['name']))
        return

    # Add instance values for npcs with the same name (e.g. two Halions)
    def _fix_duplicate_target_instances(self, target='target'):
        # select rows where an ID is given but has no instance value
        mask = (self.events[f'{target}ID'] != -1) & (self.events[f'{target}Instance'].isna())

        # group by names then add a unique instance value for each name-id pair
        self.events.loc[mask,f'{target}Instance'] = self.events[mask].groupby(f'{target}Name')[f'{target}ID'].rank(method='dense', na_option='top').astype('int')

        # remove any that were added (within the mask defined above) that only had 1 instance
        mask2 = (self.events[mask].groupby(['targetNameInstance'])['targetInstance'].transform(max) == 1); mask2 = mask2[mask2].index
        self.events.loc[mask2,'targetInstance'] = None
        return

    def _create_target_name_columns(self, target='target'):
        if f'{target}ID' in self.events.columns:
            # Add source/target name column
            self.events.insert(self.events.columns.get_loc(f'{target}ID')+1, f'{target}Name', None)
            mask = self.events[f'{target}ID'] != -1
            self.events.loc[mask,f'{target}Name'] = self.events.loc[mask,f'{target}ID'].map(self.metadata.actors['name'])

            # add name-instance column
            self.events.insert(self.events.columns.get_loc(f'{target}Name')+1, f'{target}NameInstance', self.events[f'{target}Name'])

            if f'{target}Instance' in self.events.columns:
                # Add instance values for npcs with the same name (e.g. two Halions)
                # self._fix_duplicate_target_instances(target)

                # Add instance value to name (where available)
                mask2 = self.events[f'{target}Instance'].notna()
                self.events.loc[mask2,f'{target}NameInstance'] = self.events.loc[mask2,f'{target}Name'] + "-" + self.events.loc[mask2,f'{target}Instance'].apply(lambda x: f"{x:03.0f}")

                # Add name-instance-id column
                # Used to fix bugs where there are two Halions with the same name, different npc id, but no instance id (since most of the code uses name-based tracking)
                self.events.insert(self.events.columns.get_loc(f'{target}NameInstance')+1, f'{target}NameInstanceUnique', self.events[f'{target}NameInstance'])

                # This blacklist tells the code below not to concatenate the actor id to these mobs
                # Used to fix bugs such as Professor Putricide where Gas Cloud has 2 different WCL actor IDs (first when it spawns then another when it begins moving)
                blacklisted_npcs = [
                    'Gas Cloud',
                    'Volatile Ooze',
                ]
                mask2 = (mask) & (~self.events[f'{target}Name'].isin(blacklisted_npcs))
                self.events.loc[mask2,f'{target}NameInstanceUnique'] = self.events.loc[mask2,f'{target}NameInstance'] + "-" + self.events.loc[mask2,f'{target}ID'].astype(str)
            else:
                # Add name-instance-id column
                self.events.insert(self.events.columns.get_loc(f'{target}NameInstance')+1, f'{target}NameInstanceUnique', self.events[f'{target}NameInstance'] + "-" + self.events[f'{target}ID'].astype(str))
        return










