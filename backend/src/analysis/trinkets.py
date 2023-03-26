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
    def snapshots_army(self):
        raise NotImplementedError


class APTrinket(Trinket):
    @property
    def snapshots_gargoyle(self):
        return True

    @property
    def snapshots_army(self):
        return True


class HasteTrinket(Trinket):
    @property
    def snapshots_gargoyle(self):
        return False

    @property
    def snapshots_army(self):
        return True


class TrinketPreprocessor(BasePreprocessor):
    TRINKETS = [
        APTrinket("Darkmoon Card: Greatness", 42987, "Greatness", 15, 45),
        APTrinket("Wrathstone", 45263, "Wrathstone", 20, 120, on_use=True),
        APTrinket("Blood of the Old God", 45522, "Blood of the Old God", 10, 50),
        APTrinket("Pyrite Infuser", 45286, "Pyrite Infusion", 10, 50),
        APTrinket("Mirror of Truth", 40684, "Reflection of Torment", 10, 50),
        HasteTrinket("Mark of Norgannon", 40531, "Mark of Norgannon", 20, 120, on_use=True),
        HasteTrinket("Comet's Trail", 45609, "Comet's Trail", 10, 45),
        HasteTrinket("Meteorite Whetstone", 37390, "Meteorite Whetstone", 10, 45),
    ]
    TRINKET_MAP = {trinket.item_id: trinket for trinket in TRINKETS}

    def __init__(self, combatant_info):
        self._trinkets = self._parse_trinkets(combatant_info)
        self._trinkets_by_buff_name = {trinket.buff_name: trinket for trinket in self._trinkets}

    def _parse_trinkets(self, combatant_info):
        trinkets = []

        for item in combatant_info["gear"]:
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

    def get_trinket(self, buff_name):
        return self._trinkets_by_buff_name[buff_name]

    def __iter__(self):
        return iter(self._trinkets)

    def __len__(self):
        return len(self._trinkets)
