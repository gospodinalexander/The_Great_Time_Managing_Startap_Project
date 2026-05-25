import time
import datetime
import math

free_slots_1 = {
    '01': ['16:00-19:00', '20:00-21:30'],
    '02': ['16:00-18:00', '20:00-21:00'],
    '03': ['17:30-18:00']
}

movable_slots_1 = {
    '02': ['15:00-16:00']
}



class Task:
    def __init__(self, name, start, end, ttype, difficulty, sep=bool):
        self.name = name
        self.start = start
        self.end = end
        self.timeleft = self.end - time.time()
        self.ttype = ttype
        self.difficulty = difficulty
        self.sep = sep

    def __str__(self):
        return self.name

    __repr__ = __str__

    #def free_slots(self):
    #код Стёпы
    #    return free_slots

    #def movable_slots(self):
    #код Стёпы
    #    return movable_slots

    def priority_day(self, free_slots, movable_slots):

        all_slots = {}
        free_slots_c = free_slots.copy()
        movable_slots_c = movable_slots.copy()
        for i in free_slots_c.keys():
            if i not in movable_slots_c.keys():
                all_slots[i] = free_slots_c[i]
            else:
                all_slots[i] = movable_slots_c[i] + free_slots_c[i]
                all_slots[i] = sorted(all_slots[i])


        for num, thing in enumerate(all_slots.values()):
            number = (len(all_slots) - num) * sum(all_slots[thing]) * math.prod(thing) / self.difficulty




    def priority_slot(self, free_slots, movable_slots):
