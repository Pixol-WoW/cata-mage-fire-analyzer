import pandas as pd
import numpy as np
from utils.misc import dict_deep_update, get_mmss, wrap_trtd, merge_overlapping_intervals, get_idx_from_bool_series

def isAuraActive(df, df_auras, debuffSpellID, auraType="debuff", targetID=None):

    ## Set up df_auras
    mask = (df_auras['abilityGameID'] == debuffSpellID) & (df_auras['type'].isin([f"apply{auraType}",f"remove{auraType}"]))
    df_auras = df_auras.loc[mask,['type','abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique','targetID']].copy()
    df_auras['idx'] = df_auras.index

    # [np.nan, 'applydebuff'] -> ['removedebuff'] (np.nan means applydebuff occured before the log started)
    mask = (df_auras.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift().isin([np.nan, f"apply{auraType}"])) & (df_auras.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift(0).isin([np.nan, f"remove{auraType}"]))
    df_auras.loc[mask,'idxStart'] = df_auras.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['idx'].shift()
    df_auras.loc[mask,'idxEnd'] = df_auras.loc[mask,'idx']

    # ['applybuff'] -> [np.nan] (np.nan means removebuff occured after log ended)
    mask = (df_auras.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift(0) == "applybuff") & (df_auras.groupby(['abilityGameID','sourceNameInstanceUnique','targetNameInstanceUnique'])['type'].shift(-1).isna())
    df_auras.loc[mask,'idxStart'] = df_auras.loc[mask,'idx']
    df_auras.loc[mask,'idxEnd'] = 1e8

    mask = df_auras['idxStart'].notna() | df_auras['idxEnd'].notna()

    # copy subset
    df_auras = df_auras.loc[mask,['targetNameInstanceUnique','targetID','idxStart','idxEnd']].copy()
    df_auras.loc[df_auras['idxStart'].isna(),'idxStart'] = -1

    ## set up mask condition
    if targetID:
        target_mask = df_auras['targetID'].values == targetID
    else:
        target_mask = df['targetNameInstanceUnique'].values[:, np.newaxis] == df_auras['targetNameInstanceUnique'].values
    start_mask = df.index.values[:, np.newaxis] >= df_auras['idxStart'].values
    end_mask = df.index.values[:, np.newaxis] <= df_auras['idxEnd'].values
    within_range_mask = target_mask & start_mask & end_mask

    # match_index = within_range_mask.argmax(axis=1)
    # match_index[np.sum(within_range_mask, axis=1) == 0] = -1
    # df_tmp.loc[match_index>=0, 'idxStart'] = df_lb_timestamps.loc[df_lb_timestamps.index[match_index[match_index>=0]],'idxStart'].values
    # df_tmp.loc[match_index>=0, 'idxEnd'] = df_lb_timestamps.loc[df_lb_timestamps.index[match_index[match_index>=0]],'idxEnd'].values
    return within_range_mask.any(axis=1)

class CombustionEstimatorClass:
    def __init__(self, df, enableDebug=False):
        self.df_player = df
        mask_castdebuff = (df['abilityGameID'].isin([11129,83853])) & (df['type'].isin(["cast","applydebuff","removedebuff"]))
        mask_tick = (df['abilityGameID'].isin([11129,83853])) & (df['type'] == 'damage') & (df['tick'] == True)
        mask = mask_castdebuff | mask_tick

        self.df = df[mask].copy()
        self.combustionTrackers = {}
        self.enableDebug = enableDebug
        self.eventHandler = {}
        self.eventHandler["cast"] = self.eventHandler_cast
        self.eventHandler["applydebuff"] = self.eventHandler_applydebuff
        self.eventHandler["removedebuff"] = self.eventHandler_removedebuff
        self.eventHandler["damage"] = self.eventHandler_damage

    class combustionTracker:
        def __init__(self, guid, idx, enableDebug=False):
            self.idx = idx # df index of cast event
            self.guid = guid
            self.list_tickTime = []
            self.list_tickDmg = []
            self.tsApplied = None
            self.tsRemoved = None
            self.tsLastTick = 0

    def eventHandler_cast(self, idx, datum):
        combustion = self.combustionTracker(datum.targetNameInstanceUnique, idx, enableDebug=self.enableDebug)
        self.combustionTrackers[datum.targetNameInstanceUnique] = combustion

    def eventHandler_applydebuff(self, idx, datum):
        combustion = self.combustionTrackers.get(datum.targetNameInstanceUnique)
        if not combustion:
            return
        combustion.tsApplied = datum.timestamp
        combustion.tsLastTick = datum.timestamp

    def eventHandler_removedebuff(self, idx, datum):
        combustion = self.combustionTrackers.get(datum.targetNameInstanceUnique)
        if not combustion:
            return
        combustion.tsRemoved = datum.timestamp

        results = {
            'targetNameInstanceUnique': self.df.loc[combustion.idx, 'targetNameInstanceUnique'],

            'tsApplied': combustion.tsApplied,
            'tsRemoved': combustion.tsRemoved,

            'contributionIgniteRatio': self.df.loc[combustion.idx, 'c-Ignite']/self.df.loc[combustion.idx, 'c-TickAmount'],
            'contributionLBRatio': self.df.loc[combustion.idx, 'c-LB']/self.df.loc[combustion.idx, 'c-TickAmount'],
            'contributionPBRatio': self.df.loc[combustion.idx, 'c-PB']/self.df.loc[combustion.idx, 'c-TickAmount'],

            'spellPower': self.df.loc[combustion.idx, 'spellPower'],
            'mastery': self.df.loc[combustion.idx, 'm-masteryEstimate'],
            'igniteSnapshot': self.df.loc[combustion.idx, 'c-IgniteSnapshot'],

            'contributionIgnite': self.df.loc[combustion.idx, 'c-Ignite'],
            'contributionLB': self.df.loc[combustion.idx, 'c-LB'],
            'contributionPB': self.df.loc[combustion.idx, 'c-PB'],
            'tickDmgEst': self.df.loc[combustion.idx, 'c-TickAmount'],

            'tickDmgAvg': np.mean(combustion.list_tickDmg),

            'tickTimeAvg': np.mean(combustion.list_tickTime),
            'numTicks': len(combustion.list_tickTime),
            'numTicksEst': round(10/np.mean(combustion.list_tickTime), ndigits=3),
        }

        # Remove
        self.combustionTrackers[datum.targetNameInstanceUnique] = None

        return results

    def eventHandler_damage(self, idx, datum):
        if datum.tick == False:
            return
        
        combustion = self.combustionTrackers.get(datum.targetNameInstanceUnique)
        if not combustion:
            return
        
        combustion.list_tickTime.append(datum.timestamp - combustion.tsLastTick)
        combustion.tsLastTick = datum.timestamp
        combustion.list_tickDmg.append(datum.amountTotal/datum.dmgMultiplier)
    
    def estimate(self):
        mask = self.df['type'] == "cast"
        self.df.loc[mask,'isLBActive'] = isAuraActive(self.df[mask], self.df_player, 44457, auraType="debuff")
        self.df.loc[mask,'isPBActive'] = isAuraActive(self.df[mask], self.df_player, 11366, auraType="debuff") | isAuraActive(self.df[mask], self.df_player, 92315, auraType="debuff")

        # self.df['is10%SPActive'] = True or isAuraActive(self.df, self.df_player, 53646, auraType="buff", targetID=obj_analyzer.player_id) | isAuraActive(self.df, self.df_player, 77747, auraType="buff", targetID=obj_analyzer.player_id)
        self.df.loc[mask,'spellPower'] = self.df.loc[mask,'spellPower']*1.1 # Combat Log doesn't track 10% SP buff properly at beginning of encounter, so just assume it's up.

        masteryFloored = np.floor(self.df.loc[mask,'m-masteryEstimate']*100)/100
        self.df.loc[mask,'c-LB'] = self.df.loc[mask,'isLBActive']*(np.floor(937.33*0.25 + 0.5) + 0.258*self.df.loc[mask,'spellPower']) * (1.25) * (1.03) * (1.15) / 3 * masteryFloored
        self.df.loc[mask,'c-PB'] = self.df.loc[mask,'isPBActive']*(np.floor(937.33*0.175 + 0.5) + 0.18*self.df.loc[mask,'spellPower']) * (1.25) * (1.03) / 3 * masteryFloored
        self.df.loc[mask,'c-Ignite'] = self.df.loc[mask,'i-TickAmount'] / 2 / self.df.loc[mask,'m-masteryEstimate'] * masteryFloored
        self.df.loc[mask,'c-IgniteSnapshot'] = self.df.loc[mask,'i-TickAmount']
        self.df.loc[mask,'c-TickAmount'] = self.df.loc[mask,'c-LB'] + self.df.loc[mask,'c-PB'] + self.df.loc[mask,'c-Ignite']

    def getStats(self):
        out = []
        for idx, datum in self.df.iterrows():
            if datum.type in self.eventHandler:
                results = self.eventHandler[datum.type](idx, datum)
                if results:
                    out.append(results)
        return pd.DataFrame(out)
    
