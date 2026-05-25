import time
import datetime
import math

free_slots_1 = {
    '01': {'16:00-19:00': 3, '20:00-21:30': 1.5},
    '02': {'16:00-18:00': 2, '20:00-21:00': 1},
    '03': {'17:30-18:00': 0.5}
}

movable_slots_1 = {
    '02': {'15:00-16:00': 1}
}

def time_to_minutes(time_str):

    hours, minutes = map(int, time_str.split(':'))

    return hours * 60 + minutes

def time_to_hours(time_str):

    hours, minutes = map(int, time_str.split(':'))

    return int(hours + minutes / 60)

def minutes_to_time(minutes):

    hours = minutes // 60
    mins = minutes % 60

    return f"{hours:02}:{mins:02}"

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

    def slot_choice(self, dict_of_priority_days, all_slots):

        best_day = all_slots[dict_of_priority_days[max(dict_of_priority_days.keys())]]
        possible_slots = {}
        for key, value in best_day.items():
            if self.difficulty >= time_to_hours(value):
                possible_slots[key] = value

        #if len(possible_slots) == 0:
        #    rule_braking()

        if len(possible_slots) > 1:
            possible_slots = sorted(possible_slots.items(), key=lambda item: item[1])

        return possible_slots


    def priority_slot(self, free_slots, movable_slots):

        all_slots = {}
        free_slots_c = free_slots.copy()
        movable_slots_c = movable_slots.copy()

        for i in free_slots_c.keys():
            if i not in movable_slots_c.keys():
                all_slots[i] = free_slots_c[i]
            else:
                all_slots[i] = movable_slots_c[i].extend(free_slots_c[i])
                all_slots[i] = sorted(all_slots[i])

        all_slots_c = all_slots.copy()
        dict_of_priority_days = {}

        for num, key, thing in enumerate(all_slots_c.items()):
            number = (len(thing.values()) - num) * sum(time_to_hours(j) for j in thing.values()) * math.prod(time_to_hours(j) for j in thing.values()) / self.difficulty
            if number not in dict_of_priority_days.keys():
                dict_of_priority_days[number] = key
            else:
                dict_of_priority_days[number - 1] = key

        possible_slots = self.slot_choice(dict_of_priority_days, all_slots)

        if [possible_slots.keys()][0] not in movable_slots_c.keys():

            place_task([possible_slots.keys()][0])

        else:
            replacable_task = summon_task([possible_slots.keys()][0])

            if replacable_task.time_left <= self.timeleft:
                if len(possible_slots) == 1:


            else:
                place_task([possible_slots.keys()][0])
                replacable_task.priority_slot(get_free_events_untill(replacable_task.end), get_events_until(replacable_task.end))

