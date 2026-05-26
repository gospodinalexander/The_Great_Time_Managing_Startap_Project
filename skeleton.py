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

free_slots_2 = {
    '10': {'10:00-14:00': 4, '20:00-21:30': 1.5},
    '11': {'15:00-16:00': 1},
    '12': {'16:00-20:00': 2},
}

movable_slots_2 = {
    '10': {'14:00-17:00': 3}
}

def place_task(string):

    return

def get_free_events_untill(string):
    return free_slots_2

def get_events_until(string):
    return movable_slots_2


class Task:
    def __init__(self, name, start, end, ttype, difficulty, sep=False):
        self.name = name
        self.start = start
        self.end = end
        self.timeleft = self.end - 0#time.time()
        self.ttype = ttype
        self.difficulty = difficulty
        self.sep = sep

    def __str__(self):
        return self.name

    __repr__ = __str__

    @staticmethod
    def summon_task(date):
        name = date
        start = 'idk'
        end = 3
        ttype = 1
        difficulty = 3
        word = Task(name, start, end, ttype, difficulty)
        return word

    def slot_choice(self, dict_of_priority_days, all_slots):

        best_day = all_slots[dict_of_priority_days[max(dict_of_priority_days.keys())]]
        possible_slots = {}
        for key, value in best_day.items():
            if self.difficulty >= value:
                possible_slots[key] = value

        if len(possible_slots) == 0:
            if len(dict_of_priority_days) == 1:
                print('fuck this shit')
            #    rule_braking()
            else:
                del dict_of_priority_days[max(dict_of_priority_days.keys())]
                self.slot_choice(dict_of_priority_days, all_slots)


        if len(possible_slots) > 1:
            possible_slots = dict(sorted(possible_slots.items(), key=lambda item: item[1]))

        return possible_slots


    def placing_or_comparison(self, possible_slots, free_slots, movable_slots):

        if list(possible_slots.keys())[0] not in movable_slots.keys():
            place_task([possible_slots.keys()][0])
            print(list(possible_slots.keys())[0])
            print('Задание добавлено')

            return True

        else:
            replaceable_task = self.summon_task(list(possible_slots.keys())[0])

            if replaceable_task.timeleft >= self.timeleft:
                if len(possible_slots) == 1:

                    return False

                else:
                    del possible_slots[[possible_slots.keys()][0]]
                    self.placing_or_comparison(possible_slots, free_slots, movable_slots)

                    return True

            else:
                place_task([possible_slots.keys()][0])
                replaceable_task.priority_slot(get_free_events_untill(replaceable_task.end), get_events_until(replaceable_task.end))
                print('Задание добавлено вместо другого. Ищем подходящий слот для замененного.')

                return True


    def priority_slot(self, free_slots, movable_slots):

        all_slots = {}
        free_slots_c = free_slots.copy()
        movable_slots_c = movable_slots.copy()

        for i in free_slots_c.keys():
            if i not in movable_slots_c.keys():
                all_slots[i] = free_slots_c[i]
            else:
                movable_slots_c[i].update(free_slots_c[i])
                all_slots[i] = movable_slots_c[i]

        all_slots_c = all_slots.copy()
        dict_of_priority_days = {}

        listik = []
        for i in range(len(all_slots_c)):
            listik.append(i)

        for num in listik:
            for key, thing in all_slots_c.items():
                number = (len(all_slots_c) - num) * sum(thing.values()) * math.prod(thing.values()) / self.difficulty
                if number not in dict_of_priority_days.keys():
                    dict_of_priority_days[number] = key
                else:
                    dict_of_priority_days[number - 1] = key

        possible_slots = self.slot_choice(dict_of_priority_days, all_slots)

        while not self.placing_or_comparison(possible_slots, free_slots, movable_slots):
            if len(dict_of_priority_days) == 1:
                print('fts')
                break
            #   rule_braking()
            else:
                del dict_of_priority_days[max(dict_of_priority_days.keys())]
                self.slot_choice(dict_of_priority_days, all_slots)

        return


new_task = Task('hahaha', '02.01', int(input()), 1, int(input()))
new_task.priority_slot(free_slots_1, movable_slots_1)
