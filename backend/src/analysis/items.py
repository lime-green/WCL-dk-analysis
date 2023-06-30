from analysis.base import BasePreprocessor


class Trinket:
    def __init__(self, name, item_id, buff_name, proc_duration, proc_cd, on_use=False):
        self.name = name
        self.item_id = item_id
        self.buff_name = buff_name
        self.proc_duration = proc_duration * 1000
        self.proc_cd = proc_cd * 1000
        self.on_use = on_use
        self.icon = None

    @property
    def snapshots_gargoyle(self):
        raise NotImplementedError

    @property
    def snapshots_army_haste(self):
        raise NotImplementedError


class APTrinket(Trinket):
    @property
    def snapshots_gargoyle(self):
        return True

    @property
    def snapshots_army_haste(self):
        return False


class HasteTrinket(Trinket):
    @property
    def snapshots_gargoyle(self):
        return False

    @property
    def snapshots_army_haste(self):
        return True


class TrinketPreprocessor(BasePreprocessor):
    TRINKETS = [
        APTrinket("Darkmoon Card: Greatness", 42987, "Greatness", 15, 45),
        APTrinket("Wrathstone", 45263, "Wrathstone", 20, 120, on_use=True),
        APTrinket("Blood of the Old God", 45522, "Blood of the Old God", 10, 50),
        APTrinket("Pyrite Infuser", 45286, "Pyrite Infusion", 10, 50),
        APTrinket("Mirror of Truth", 40684, "Reflection of Torment", 10, 50),
        APTrinket("Death's Choice", 47464, "Paragon", 15, 45),
        APTrinket("Death's Choice", 47303, "Paragon", 15, 45),
        APTrinket("Death's Verdict", 47131, "Paragon", 15, 45),
        APTrinket("Death's Verdict", 47115, "Paragon", 15, 45),
        HasteTrinket(
            "Mark of Norgannon", 40531, "Mark of Norgannon", 20, 120, on_use=True
        ),
        HasteTrinket("Comet's Trail", 45609, "Comet's Trail", 10, 45),
        HasteTrinket("Meteorite Whetstone", 37390, "Meteorite Whetstone", 10, 45),
    ]
    TRINKET_MAP = {trinket.item_id: trinket for trinket in TRINKETS}

    def __init__(self, combatant_info):
        self._trinkets = self._parse_trinkets(combatant_info)
        self._trinkets_by_buff_name = {
            trinket.buff_name: trinket for trinket in self._trinkets
        }

    def _parse_trinkets(self, combatant_info):
        trinkets = []

        for item in combatant_info.get("gear", []):
            trinket = self._parse_trinket(item)
            if trinket:
                trinket.icon = item["item_icon"]
                trinkets.append(trinket)
        return trinkets

    def _parse_trinket(self, item):
        return self.TRINKET_MAP.get(item["id"])

    def preprocess_event(self, event):
        pass

    def has_trinket(self, buff_name):
        return buff_name in self._trinkets_by_buff_name

    def __iter__(self):
        return iter(self._trinkets)

    def __len__(self):
        return len(self._trinkets)


class T9Preprocessor(BasePreprocessor):
    def __init__(self, combatant_info):
        self.has_2p = False
        self.has_4p = False
        self._calc_num_t9(combatant_info)

    def _calc_num_t9(self, combatant_info):
        count = 0

        for item in combatant_info.get("gear", []):
            if item["id"] in {
                # Ally
                # Head
                48472,
                48483,
                48488,
                # Shoulders
                48478,
                48485,
                48486,
                # Chest
                48474,
                48481,
                48490,
                # Legs
                48476,
                48484,
                48487,
                # Hands
                48480,
                48482,
                48489,
                # Horde
                # Head
                48503,
                48493,
                48498,
                # Shoulders
                48505,
                48495,
                48495,
                # Chest
                48501,
                48491,
                48500,
                # Legs
                48504,
                48494,
                48497,
                # Hands
                48502,
                48492,
                48499,
            }:
                count += 1
        if count >= 2:
            self.has_2p = True
        if count >= 4:
            self.has_4p = True

    def preprocess_event(self, event):
        if event["type"] == "applybuff" and event["ability"] == "Unholy Might":
            self.has_2p = True

    @property
    def max_uptime(self):
        return 0.28


class SigilPreprocessor(BasePreprocessor):
    class Sigil:
        def __init__(self, name, item_id, buff_name, max_uptime):
            self.name = name
            self.item_id = item_id
            self.buff_name = buff_name
            self.max_uptime = max_uptime

    _sigils = [
        Sigil("Sigil of Virulence", 47673, "Unholy Force", 0.70),
    ]
    _sigil_map = {sigil.item_id: sigil for sigil in _sigils}
    _sigil_buff_name_map = {sigil.buff_name: sigil for sigil in _sigils}

    def __init__(self, combatant_info):
        self.sigil = None
        self._calc_sigil(combatant_info)

    def _calc_sigil(self, combatant_info):
        for item in combatant_info.get("gear", []):
            if item["id"] in self._sigil_map:
                self.sigil = self._sigil_map[item["id"]]
                break

    def preprocess_event(self, event):
        if self.sigil:
            return

        if (
            event["type"] == "applybuff"
            and event["ability"] in self._sigil_buff_name_map
        ):
            self.sigil = self._sigil_buff_name_map[event["ability"]]


class ItemPreprocessor(BasePreprocessor):
    def __init__(self, combatant_info):
        self._trinkets = TrinketPreprocessor(combatant_info)
        self._t9 = T9Preprocessor(combatant_info)
        self._sigil = SigilPreprocessor(combatant_info)

        self._processors = [
            self._trinkets,
            self._t9,
            self._sigil,
        ]

    def preprocess_event(self, event):
        for processor in self._processors:
            processor.preprocess_event(event)

    def has_trinket(self, buff_name):
        return self._trinkets.has_trinket(buff_name)

    def has_t9_2p(self):
        return self._t9.has_2p

    def t9_max_uptime(self):
        return self._t9.max_uptime

    @property
    def trinkets(self):
        return list(self._trinkets)

    @property
    def sigil(self):
        return self._sigil.sigil
