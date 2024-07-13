import pandas as pd
import numpy as np
from utils.analyzers.PixolClassAnalyzerGraph import PixolGraphBase
from utils.misc import dict_deep_update, get_mmss, wrap_trtd, merge_overlapping_intervals, get_idx_from_bool_series

class masteryEstimatorClass:
    def __init__(self, df_player, player_id, enableDebug=False):
        self.enableDebug = enableDebug
        self.igniteTrackers = {}
        self.masteryBuffTrackers = {}
        self.masteryPrepullOffset = 0

        self.eventHandler = {}
        self.eventHandler["damage"] = self._on_damage
        self.eventHandler["applydebuff"] = self._on_applydebuff
        self.eventHandler["refreshdebuff"] = self._on_refreshdebuff

        self.eventHandler["applybuff"] = self._on_applybuff
        self.eventHandler["applybuffstack"] = self._on_applybuffstack
        self.eventHandler["refreshbuff"] = self._on_refreshbuff
        self.eventHandler["removebuff"] = self._on_removebuff

        self.list_timestamp_mastery = []
        self.list_timestamp_mastery.append({'idx': -1, 'timestamp': 0, 'masteryOffset': 0})

        self.dict_spellIDs = {
            "IGNITE_DEBUFF": 413841,
            "IGNITE_TICK": 413843,
            "IMPACT_BUFF": 64343,
            "FIRE_BLAST": 2136,
            "CRITS": [133, 11366, 92315, 2120, 11113, 88148, 31661, 44614, 2948, 11129, 2136],
            "COMBUSTION_CAST": 11129,
        }

        # https://www.wowhead.com/cata/spells/uncategorized/name-extended:Mastery?filter=29;189;0#0+1+21
        self.dict_mastery_buffs = {
            96929 : {'mastery':  508, 'stacksMax':  1}, # Blessing of the Shaper
            96092 : {'mastery':  225, 'stacksMax':  1}, # Decree of the Dark Lady
            102662: {'mastery': 1149, 'stacksMax':  1}, # Foul Gift
            105779: {'mastery': 2000, 'stacksMax':  1}, # Fury of the Ancestors
            96161 : {'mastery':  225, 'stacksMax':  1}, # Greymane's Resolve
            92174 : {'mastery': 1710, 'stacksMax':  1}, # Hardened Shell
            92166 : {'mastery':  918, 'stacksMax':  1}, # Hardened Shell
            109993: {'mastery': 1149, 'stacksMax':  1}, # Master Pit Fighter
            109774: {'mastery': 2573, 'stacksMax':  1}, # Master Tactician
            107986: {'mastery': 2904, 'stacksMax':  1}, # Master Tactician
            109776: {'mastery': 3278, 'stacksMax':  1}, # Master Tactician
            102742: {'mastery':  255, 'stacksMax':  1}, # Mastery of Nimbleness
            97141 : {'mastery': 1834, 'stacksMax':  1}, # Matrix Restabilized
            96979 : {'mastery': 1624, 'stacksMax':  1}, # Matrix Restabilized
            109994: {'mastery': 1020, 'stacksMax':  1}, # Pit Fighter
            92320 : {'mastery': 2178, 'stacksMax':  1}, # Revelation
            91024 : {'mastery': 1926, 'stacksMax':  1}, # Revelation
            105647: {'mastery':  710, 'stacksMax':  1}, # Runic Mastery
            97131 : {'mastery':   44, 'stacksMax': 10}, # Soul Fragment
            96962 : {'mastery':   39, 'stacksMax': 10}, # Soul Fragment
            92355 : {'mastery': 1089, 'stacksMax':  1}, # Turn of the Worm
            92235 : {'mastery':  963, 'stacksMax':  1}, # Turn of the Worm
            102664: {'mastery': 1149, 'stacksMax':  1}, # Varo'then's Brooch
            87549 : {'mastery':   90, 'stacksMax':  1}, # Well Fed
            87560 : {'mastery':   60, 'stacksMax':  1}, # Well Fed
        }

        mask_source = df_player['sourceID'] == player_id
        mask_crits = (df_player['abilityGameID'].isin(self.dict_spellIDs["CRITS"])) & (df_player['hitTypeStr'] == "CRIT") & (df_player['tick'] == False)
        mask_crits_absorb_full = (df_player['abilityGameID'].isin(self.dict_spellIDs["CRITS"])) & (df_player['isAbsorbFull'] == True) & (df_player['tick'] == False)
        mask_ignites = (df_player['abilityGameID'].isin([self.dict_spellIDs["IGNITE_DEBUFF"],self.dict_spellIDs["IGNITE_TICK"]]))
        mask_mastery_buffs = (df_player['targetID'] == player_id) & (df_player['abilityGameID'].isin(self.dict_mastery_buffs.keys()))
        mask_impact = (df_player['abilityGameID'].isin([self.dict_spellIDs["IMPACT_BUFF"],self.dict_spellIDs["FIRE_BLAST"]]))
        mask_combust_cast = (df_player['abilityGameID'] == self.dict_spellIDs["COMBUSTION_CAST"]) & (df_player['type'] == "cast")
        mask = ( (mask_source) & (mask_crits | mask_crits_absorb_full | mask_ignites | mask_impact | mask_combust_cast) ) | mask_mastery_buffs
        self.df = df_player.loc[mask,['timestamp','type','targetNameInstanceUnique','abilityGameID','abilityGameName','hitTypeStr','isAbsorbFull','amountTotal']].copy()
        self.df.loc[:,'m-igniteTicksRemaining'] = np.nan
        self.df.loc[:,'m-igniteTicksMax'] = np.nan
        self.df.loc[:,'m-igniteBank'] = np.nan
        self.df.loc[:,'m-bankMaxTicks'] = np.nan
        self.df.loc[:,'m-bankBeforeRefresh'] = np.nan
        self.df.loc[:,'m-igniteListAmount'] = None
        self.df.loc[:,'m-sum_crit'] = np.nan
        self.df.loc[:,'m-mEstimate'] = np.nan
        self.df.loc[:,'m-masteryOffset'] = np.nan
        self.df.loc[:,'m-masteryEstimateInitial'] = np.nan
        self.df.loc[:,'m-masteryEstimate'] = np.nan



    class masteryBuffTracker:
        def __init__(self, parent, spellID, enableDebug=False):
            self.parent = parent
            self.dict_mastery_buffs = self.parent.dict_mastery_buffs
            self.stacksMax = self.dict_mastery_buffs[spellID].get('stacksMax')
            self.masteryPerStack = self.dict_mastery_buffs[spellID].get('mastery') / 179.28 * 0.028 
            self.spellID = spellID
            self.stacks = 0

        def setStacks(self, n):
            self.stacks = n

        def refresh(self):
            if self.stacks == 0:
                self.stacks = self.stacksMax

        def getMastery(self):
            return self.masteryPerStack * self.stacks
        
        def getMasteryAtNStacks(self, n):
            return self.masteryPerStack * n

        def getMasteryMax(self):
            return self.masteryPerStack * self.stacksMax
            

    class igniteTracker:
        def __init__(self, guid, enableDebug=False):
            self.guid = guid
            self.bank = 0
            self.ticksRemaining = 0
            self.ticksMax = 0

            self.listAmount = []
            self.listAmountBuffer = []
            self.readyToMoveListAmountBuffer = False

            self.bankBeforeRefresh = 0

        def setReadyToMoveListAmountBuffer(self, b):
            self.readyToMoveListAmountBuffer = b

        def moveListAmountBuffer(self):
            if self.readyToMoveListAmountBuffer:
                self.listAmount = self.listAmountBuffer
                self.listAmountBuffer = []
                self.readyToMoveListAmountBuffer = False

        def cacheBankBeforeRefresh(self):
            self.bankBeforeRefresh = self.bank

        def setTicksMax(self, n):
            self.ticksMax = n

        def setTicksRemaining(self, n):
            self.ticksRemaining = n

        def decrementTicksRemaining(self):
            self.ticksRemaining -= 1

        def estimateBankFromTickAmount(self, amt):
            if self.ticksMax == 0:
                return
            self.bank = amt * self.ticksRemaining
    
    def _getIgniteFromGUID(self, guid):
        ignite = self.igniteTrackers.get(guid) or self.igniteTracker(guid, enableDebug=self.enableDebug)
        self.igniteTrackers[guid] = ignite
        return ignite
    
    def _getMasteryBuffFromSpellID(self, spellID):
        masteryBuff = self.masteryBuffTrackers.get(spellID) or self.masteryBuffTracker(self, spellID, enableDebug=self.enableDebug)
        self.masteryBuffTrackers[spellID] = masteryBuff
        return masteryBuff
    
    def _getTotalMasteryOffset(self):
        m = 0
        for masteryBuff in self.masteryBuffTrackers.values():
            m += masteryBuff.getMastery()
        return m
    
    def _on_applybuff(self, idx, datum):
        if datum.abilityGameID in self.dict_mastery_buffs.keys():
            masteryBuff = self._getMasteryBuffFromSpellID(datum.abilityGameID)
            masteryBuff.setStacks(1)
            totalMasteryOffset = self._getTotalMasteryOffset()
            self.df.loc[idx,'m-masteryOffset'] = totalMasteryOffset
            self.list_timestamp_mastery.append({'idx': idx, 'timestamp': datum['timestamp'], 'masteryOffset': totalMasteryOffset})

    def _on_applybuffstack(self, idx, datum):
        if datum.abilityGameID in self.dict_mastery_buffs.keys():
            masteryBuff = self._getMasteryBuffFromSpellID(datum.abilityGameID)

            # mastery buff proc'd pre-pull and wasn't logged
            if masteryBuff.stacks == 0:
                self.masteryPrepullOffset = -masteryBuff.getMasteryAtNStacks(datum.stack)

            masteryBuff.setStacks(datum.stack)
            totalMasteryOffset = self._getTotalMasteryOffset()
            self.df.loc[idx,'m-masteryOffset'] = totalMasteryOffset
            self.list_timestamp_mastery.append({'idx': idx, 'timestamp': datum['timestamp'], 'masteryOffset': totalMasteryOffset})
    
    def _on_refreshbuff(self, idx, datum):
        if datum.abilityGameID in self.dict_mastery_buffs.keys():
            masteryBuff = self._getMasteryBuffFromSpellID(datum.abilityGameID)

            # mastery buff proc'd pre-pull and wasn't logged
            if masteryBuff.stacks == 0:
                self.masteryPrepullOffset = -masteryBuff.getMasteryMax()

            masteryBuff.refresh()
            totalMasteryOffset = self._getTotalMasteryOffset()
            self.df.loc[idx,'m-masteryOffset'] = totalMasteryOffset
            self.list_timestamp_mastery.append({'idx': idx, 'timestamp': datum['timestamp'], 'masteryOffset': totalMasteryOffset})

    def _on_removebuff(self, idx, datum):
        if datum.abilityGameID in self.dict_mastery_buffs.keys():
            masteryBuff = self._getMasteryBuffFromSpellID(datum.abilityGameID)

            # mastery buff proc'd pre-pull and wasn't logged (assumes max buff stacks)
            if masteryBuff.stacks == 0:
                self.masteryPrepullOffset = -masteryBuff.getMasteryMax()

            masteryBuff.setStacks(0)
            totalMasteryOffset = self._getTotalMasteryOffset()
            self.df.loc[idx,'m-masteryOffset'] = totalMasteryOffset
            self.list_timestamp_mastery.append({'idx': idx, 'timestamp': datum['timestamp'], 'masteryOffset': totalMasteryOffset})

    def _on_applydebuff(self, idx, datum):
        ignite = self._getIgniteFromGUID(datum.targetNameInstanceUnique)

        if datum.abilityGameID == self.dict_spellIDs["IGNITE_DEBUFF"]:
            ignite.setTicksMax(2)
            ignite.setTicksRemaining(2)
            ignite.cacheBankBeforeRefresh()
            ignite.setReadyToMoveListAmountBuffer(True)
            self.df.loc[idx,'m-igniteTicksRemaining'] = ignite.ticksRemaining
            self.df.loc[idx,'m-igniteTicksMax'] = ignite.ticksMax


    def _on_refreshdebuff(self, idx, datum):
        ignite = self._getIgniteFromGUID(datum.targetNameInstanceUnique)

        if datum.abilityGameID == self.dict_spellIDs["IGNITE_DEBUFF"]:
            ignite.setTicksMax(3)
            ignite.setTicksRemaining(3)
            ignite.cacheBankBeforeRefresh()
            ignite.setReadyToMoveListAmountBuffer(True)
            self.df.loc[idx,'m-igniteTicksRemaining'] = ignite.ticksRemaining
            self.df.loc[idx,'m-igniteTicksMax'] = ignite.ticksMax
            # self.df.at[idx,'igniteListAmount'] = ignite.listAmount

    def _on_damage(self, idx, datum):
        ignite = self._getIgniteFromGUID(datum.targetNameInstanceUnique)

        if datum.abilityGameID == self.dict_spellIDs["IGNITE_TICK"]:
            ignite.decrementTicksRemaining()
            ignite.estimateBankFromTickAmount(datum.amountTotal)
            self.df.loc[idx,'m-igniteBank'] = ignite.bank
            self.df.loc[idx,'m-igniteTicksRemaining'] = ignite.ticksRemaining
            self.df.loc[idx,'m-igniteTicksMax'] = ignite.ticksMax

            ignite.moveListAmountBuffer()

            if len(ignite.listAmount) > 0:
                # c1: crit1 amount scaled by 0.4
                # m1: mastery1 amount corresponding to c1
                # offset1: mastery offset amount from m to m1 (these are given from mastery buffs events in the log)
                # m: mastery amount at the start of the pull (m = m1 + offset1 = ... = m10 + offset10)

                # ignite already exists -> arbitary number of crits, each with varying mastery hits at same time -> ignite refreshes -> ignite ticks -> solve for m from the tick amount
                # total bank after new crit(s) = old bank                 + new crits
                # ignite.ticksMax*datum.amountTotal = ignite.bankBeforeRefresh + (c1*m1 + ... + c10*m10)
                # ignite.ticksMax*datum.amountTotal = ignite.bankBeforeRefresh + c1*(m+offset1) + ... + c10*(m+offset10)
                # ignite.ticksMax*datum.amountTotal = ignite.bankBeforeRefresh + (c1 + ... + c10) * m + (c1*offset1 + ... c10*offset10)
                # m = (ignite.ticksMax*datum.amountTotal - ignite.bankBeforeRefresh - (c1*offset1 + ... c10*offset10)) / (c1 + ... + c10)

                # Compute sums for the formula above
                sum_crit, sum_crit_x_offset = 0, 0
                for datumCrit in ignite.listAmount:
                    sum_crit += datumCrit['amount']
                    sum_crit_x_offset += datumCrit['amount'] * datumCrit['masteryOffset']

                # solve for m (mastery defined at start of pull) using:
                # crits (since the last refresh of ignite) that contributed to this ignite tick
                bankMaxTicks = ignite.ticksMax*datum.amountTotal
                m = (bankMaxTicks - ignite.bankBeforeRefresh - sum_crit_x_offset)/sum_crit

                # calculate mastery at the time of each crit using:
                # the estimated m above and masteryOffsets from mastery buff procs
                for datumCrit in ignite.listAmount:
                    self.df.at[datumCrit['idx'],'m-masteryEstimateInitial'] = m + datumCrit['masteryOffset']

                self.df.loc[idx,'m-mEstimate'] = m

                # debug information
                # self.df.loc[idx,'igniteMultiplierAvg'] = (bankMaxTicks - ignite.bankBeforeRefresh)/sum_crit
                self.df.at[idx,'m-igniteListAmount'] = ignite.listAmount
                self.df.loc[idx,'m-bankMaxTicks'] = bankMaxTicks
                self.df.loc[idx,'m-sum_crit'] = sum_crit
                self.df.loc[idx,'m-bankBeforeRefresh'] = ignite.bankBeforeRefresh

        elif (datum.abilityGameID in self.dict_spellIDs["CRITS"]) and (datum.get('tick') in [None, False]):
            if (datum.hitTypeStr == "CRIT"):
                # store 40% of crit and masteryOffset from mastery buff events
                ignite.listAmountBuffer.append({'idx': idx, 'amount': datum.amountTotal * 0.4, 'masteryOffset': self.masteryPrepullOffset + self._getTotalMasteryOffset()})
                self.df.loc[idx,'m-masteryOffset'] = self.masteryPrepullOffset + self._getTotalMasteryOffset()
            elif (datum.isAbsorbFull == True):
                self.df.loc[idx,'m-masteryOffset'] = self.masteryPrepullOffset + self._getTotalMasteryOffset()
                pass

    def estimateMastery(self):
        for idx, datum in self.df.iterrows():
            if datum.type in self.eventHandler:
                self.eventHandler[datum.type](idx, datum)

        # Take the median of the estimates in hopes of eliminating any errors in calculation due to ignite batching bug
        # where ignite can tick for an unexpected value when it is refreshed at the same time it ticks
        mEstimateMedian = self.df['m-mEstimate'].median() # the median estimate of m (defined as the mastery at start of pull)

        if 'tick' in self.df.columns:
            mask_crits = (self.df['abilityGameID'].isin(self.dict_spellIDs["CRITS"])) & (self.df['hitTypeStr'] == "CRIT") & (self.df['tick'] == False)
            mask_crits_absorb_full = (self.df['abilityGameID'].isin(self.dict_spellIDs["CRITS"])) & (self.df['isAbsorbFull'] == True) & (self.df['tick'] == False)
        else:
            mask_crits = (self.df['abilityGameID'].isin(self.dict_spellIDs["CRITS"])) & (self.df['hitTypeStr'] == "CRIT")
            mask_crits_absorb_full = (self.df['abilityGameID'].isin(self.dict_spellIDs["CRITS"])) & (self.df['isAbsorbFull'] == True)
        mask = mask_crits | mask_crits_absorb_full
        for idx in mask.index:
            self.df.loc[idx,'m-masteryEstimate'] = mEstimateMedian + self.df.loc[idx,'m-masteryOffset']

        return self.df



class igniteEstimatorClass:
    def __init__(self, df, enableDebug=False):
        self.df = df
        self.igniteTrackers = {}
        self.enableDebug = enableDebug
        self.eventHandler = {}
        self.eventHandler["damage"] = self.eventHandler_damage
        self.eventHandler["applydebuff"] = self.eventHandler_applydebuff
        self.eventHandler["refreshdebuff"] = self.eventHandler_refreshdebuff
        self.eventHandler["removedebuff"] = self.eventHandler_removedebuff

        self.eventHandler["cast"] = self.eventHandler_cast

        self.eventHandler["applybuff"] = self.eventHandler_applybuff
        self.eventHandler["refreshbuff"] = self.eventHandler_refreshbuff
        self.eventHandler["removebuff"] = self.eventHandler_removebuff

        self.dict_spellIDs = {
            "IGNITE_DEBUFF": 413841,
            "IGNITE_TICK": 413843,
            "IMPACT_BUFF": 64343,
            "FIRE_BLAST": 2136,
            "CRITS": [133, 11366, 92315, 2120, 11113, 88148, 31661, 44614, 2948, 11129, 2136],
            "COMBUSTION_CAST": 11129,
        }

        if "timestampStr" not in self.df.columns:
            self.df.insert(0, "timestampStr", self.df['timestamp'].apply(lambda ts : self.timestamp_to_mmss(ts)))
        
        self.df.loc[:,'i-Contribution'] = np.nan
        self.df.loc[:,'i-Buffer'] = np.nan
        self.df.loc[:,'i-Bank'] = np.nan
        self.df.loc[:,'i-FromImpact'] = False
        self.df.loc[:,'i-TickAmount'] = np.nan
        self.df.loc[:,'i-TicksRemaining'] = np.nan

        self.impactTracker = self.impactTrackerClass(self, enableDebug=enableDebug)

    class impactTrackerClass:
        def __init__(self, parent, enableDebug=False):
            self.parent = parent
            self.destGUID = None
            self.tsImpactActivated = None
            self.tsFireBlastCast = None
            self.tsFireBlastErrorThres = 0.1
            self.tsImpactSpreadErrorThres = 0.1
            self.impactBuffActive = False
        
        def setImpactBuffActive(self, b):
            self.impactBuffActive = b
        
        def processFireBlastCastEvent(self, destGUID, ts):
            if not self.impactBuffActive:
                return

            self.tsFireBlastCast = ts
            self.destGUID = destGUID

        def processFireBlastDamageEvent(self, destGUID, ts):
            if destGUID != self.destGUID:
                return
            if not self.tsFireBlastCast:
                return
            if (ts - self.tsFireBlastCast) > self.tsFireBlastErrorThres:
                return
            self.tsImpactActivated = ts

        def getIgniteImpactSource(self, destGUID, ts):
            # -- Note on confusing variable naming:
            # -- self.destGUID is the fire blast target's GUID
            # -- input destGUID is the target of the new ignite generated from impact
            if self.destGUID == destGUID:
                return None, False
            if not self.tsImpactActivated:
                return None, False
            # print(format("[%s] [getIgniteImpactSource]", destGUID))
            if (ts - self.tsImpactActivated) > self.tsImpactSpreadErrorThres:
                self.deactivateImpact()
                return None, False
            # print(format("[%s] [getIgniteImpactSource] Success", destGUID))
            return self.parent.igniteTrackers[self.destGUID], True

        def deactivateImpact(self):
            self.tsImpactActivated = None

    class igniteTracker:
        def __init__(self, guid, enableDebug=False):
            self.guid = guid
            self.buffer = 0
            self.bufferAbsorb = 0
            self.bank = 0
            self.ticksRemaining = 0
            self.tickAmount = 0
            self.lastContribution = 0
            self.isFromImpact = False
            self.tsRemoved = -1e6
            self.tsBufferUpdated = -1e6
            self.tsBufferAbsorbUpdated = -1e6
            self.tsThres = 0.1

        def clearOldBuffers(self, ts):
            if (ts - self.tsBufferUpdated) > self.tsThres:
                self.buffer = 0

            if (ts - self.tsBufferAbsorbUpdated) > self.tsThres:
                self.bufferAbsorb = 0
            
            return
        
        def addCritToBuffer(self, amt, mastery, ts):
            self.clearOldBuffers(ts)
            # 22.4% dmg from base Flashburn Mastery
            # 2.8% dmg per Mastery Point
            # 179.28 Mastery Rating per Mastery Point (for lvl 85)
            # self.buffer += amt * 0.4 * (1 + 0.224 + mastery / 179.28 * 0.028)
            self.lastContribution = amt * 0.4 * mastery
            self.buffer += self.lastContribution
            self.tsBufferUpdated = ts

        def addCritToBufferAbsorb(self, amt, mastery, ts):
            self.clearOldBuffers(ts)
            # 22.4% dmg from base Flashburn Mastery
            # 2.8% dmg per Mastery Point
            # 179.28 Mastery Rating per Mastery Point (for lvl 85)
            # self.buffer += amt * 0.4 * (1 + 0.224 + mastery / 179.28 * 0.028)
            self.bufferAbsorb += amt * 0.4 * mastery
            self.tsBufferAbsorbUpdated = ts

        def setTicksRemaining(self, n):
            self.ticksRemaining = n

        def decrementTicksRemaining(self):
            self.ticksRemaining -= 1

        def setTSRemoved(self, ts):
            self.tsRemoved = ts

        def resetBank(self):
            self.bank = 0

        def moveBufferToBank(self):
            self.bank += self.buffer
            self.buffer = 0

            self.bank += self.bufferAbsorb
            self.bufferAbsorb = 0

        def updateTickAmount(self, n=None):
            if n is not None:
                self.tickAmount = n
            else:
                self.tickAmount = self.bank / self.ticksRemaining

        def removeIgniteDamageFromBank(self, amt):
            self.bank -= amt

        def setIsFromImpact(self, b):
            self.isFromImpact = b

        def copyForImpact(self, igniteImpactSource):
            # if copyTSApplied:
                # self.tsApplied = ignite_impact_source.tsApplied
            self.bank = igniteImpactSource.bank
            # self.buffer = 0

    def timestamp_to_mmss(self, ts):
        return f"{int(ts//60):02d}:{ts%60:06.3f}"

    def _getIgniteFromGUID(self, guid):
        ignite = self.igniteTrackers.get(guid) or self.igniteTracker(guid, enableDebug=self.enableDebug)
        self.igniteTrackers[guid] = ignite
        return ignite

    def eventHandler_damage(self, idx, datum):
        ignite = self._getIgniteFromGUID(datum.targetNameInstanceUnique)

        if datum.abilityGameID == self.dict_spellIDs["IGNITE_TICK"]:
            ignite.removeIgniteDamageFromBank(datum.amountTotal)
            ignite.decrementTicksRemaining()
            # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[Ignite {datum.type}] [{ignite.guid}]\tBank: {ignite.bank:.2f}")
        elif (datum.abilityGameID in self.dict_spellIDs["CRITS"]) and (datum.get('tick') in [None, False]):
            if (datum.hitTypeStr == "CRIT"):
                ignite.addCritToBuffer(datum.amountTotal, datum["m-masteryEstimate"], datum.timestamp)
                self.df.loc[idx,'i-Contribution'] = round(ignite.lastContribution, ndigits=2)
                # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[Crit {datum.type}]\t[{ignite.guid}]\tBuffer: {ignite.buffer:.2f}")
            elif (datum.isAbsorbFull == True):
                ignite.addCritToBufferAbsorb(datum.amountTotal, datum["m-masteryEstimate"], datum.timestamp)
                pass

        if datum.abilityGameID == self.dict_spellIDs["FIRE_BLAST"]:
            self.impactTracker.processFireBlastDamageEvent(datum.targetNameInstanceUnique, datum.timestamp)

    def eventHandler_applydebuff(self, idx, datum):
        ignite = self._getIgniteFromGUID(datum.targetNameInstanceUnique)

        if datum.abilityGameID == self.dict_spellIDs["IGNITE_DEBUFF"]:
            igniteImpactSource, shouldHaveImpactSource = self.impactTracker.getIgniteImpactSource(datum.targetNameInstanceUnique, datum.timestamp)
            if shouldHaveImpactSource:
                ignite.copyForImpact(igniteImpactSource)
                ignite.setIsFromImpact(True)
                ignite.setTicksRemaining(2)
                ignite.updateTickAmount()
                # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[{datum.type}]\t[{ignite.guid}]\tImpact Ignite")
                # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[{datum.type}]\t[{ignite.guid}]\tBank: {ignite.bank:.2f}")
            else:
                ignite.resetBank()
                ignite.setIsFromImpact(False)
                ignite.clearOldBuffers(datum.timestamp)
                ignite.moveBufferToBank()
                ignite.setTicksRemaining(2)
                ignite.updateTickAmount()
                # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[{datum.type}]\t[{ignite.guid}]\tBank Reset")
                # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[{datum.type}]\t[{ignite.guid}]\tBank: {ignite.bank:.2f}")

    def eventHandler_refreshdebuff(self, idx, datum):
        ignite = self._getIgniteFromGUID(datum.targetNameInstanceUnique)

        if datum.abilityGameID == self.dict_spellIDs["IGNITE_DEBUFF"]:
            igniteImpactSource, shouldHaveImpactSource = self.impactTracker.getIgniteImpactSource(datum.targetNameInstanceUnique, datum.timestamp)
            if shouldHaveImpactSource:
                ignite.copyForImpact(igniteImpactSource)
                ignite.setIsFromImpact(True)
                ignite.setTicksRemaining(2)
                ignite.updateTickAmount()
                # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[{datum.type}]\t[{ignite.guid}]\tImpact Ignite")
                # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[{datum.type}]\t[{ignite.guid}]\tBank: {ignite.bank:.2f}")
            else:
                ignite.moveBufferToBank()
                ignite.setTicksRemaining(3)
                ignite.updateTickAmount()
                # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[{datum.type}]\t[{ignite.guid}]\tBank: {ignite.bank:.2f}")

    def eventHandler_removedebuff(self, idx, datum):
        ignite = self._getIgniteFromGUID(datum.targetNameInstanceUnique)

        if datum.abilityGameID == self.dict_spellIDs["IGNITE_DEBUFF"] and ignite:
            # ignite.moveBufferToBank()
            # ignite.setTicksRemaining(3)
            ignite.updateTickAmount(0)
            ignite.setTSRemoved(datum.timestamp)
            # print(f"[{self.timestamp_to_mmss(datum.timestamp)}]\t[{datum.type}]\t[{ignite.guid}]\tBank: {ignite.bank:.2f}")

    def eventHandler_cast(self, idx, datum):
        if datum.abilityGameID == self.dict_spellIDs["FIRE_BLAST"]:
            self.impactTracker.processFireBlastCastEvent(datum.targetNameInstanceUnique, datum.timestamp)

    def eventHandler_applybuff(self, idx, datum):
        if datum.abilityGameID == self.dict_spellIDs["IMPACT_BUFF"]:
            self.impactTracker.setImpactBuffActive(True)

    def eventHandler_refreshbuff(self, idx, datum):
        if datum.abilityGameID == self.dict_spellIDs["IMPACT_BUFF"]:
            self.impactTracker.setImpactBuffActive(True)

    def eventHandler_removebuff(self, idx, datum):
        if datum.abilityGameID == self.dict_spellIDs["IMPACT_BUFF"]:
            self.impactTracker.setImpactBuffActive(False)

    def estimateIgnites(self):
        for idx, datum in self.df.iterrows():
            if datum.type in self.eventHandler:
                self.eventHandler[datum.type](idx, datum)
            
            ignite = self.igniteTrackers.get(datum.targetNameInstanceUnique)
            if ignite:
                self.df.loc[idx,'i-Buffer'] = round(ignite.buffer, ndigits=2)
                self.df.loc[idx,'i-Bank'] = round(ignite.bank, ndigits=2)
                self.df.loc[idx,'i-FromImpact'] = ignite.isFromImpact
                self.df.loc[idx,'i-TickAmount'] = round(ignite.tickAmount, ndigits=2)
                self.df.loc[idx,'i-TicksRemaining'] = ignite.ticksRemaining
        return self.df
