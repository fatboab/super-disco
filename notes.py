from collections import namedtuple

StackEntry = namedtuple('StackEntry', ['note', 'octave'])


class NoteStack:
    BEHAVIOUR_RETRIGGER_NONE = 0x00
    BEHAVIOUR_NODDLE_TOASTER = 0x01
    BEHAVIOUR_RETRIGGER_ALL = 0x02
    BEHAVIOUR_RETRIGGER_LAST = 0x04
    BEHAVIOUR_RETRIGGER_LOWEST = 0x08

    def __init__(self, behaviour=BEHAVIOUR_RETRIGGER_NONE):
        self.behaviour = behaviour
        self.stack = []

    def __repr__(self):
        return '<NoteStack: {}>'.format(self.stack)

    def is_empty(self) -> bool:
        """
        :return: true if the stack is empty, false otherwise
        """
        return len(self.stack) == 0

    def add(self, note, octave):
        """
        Adds a note and the octave it was played in to the stack
        :param note: the note to add; in the base octave
        :param octave: the octave that was applied to the base note
        :return:
        """
        self.stack.append(StackEntry(note, octave))

    def remove(self, note) -> StackEntry:
        """
        Remove the note from the stack
        :param note: the note to remove; in the base octave
        :return: the removed note tuple
        """
        stack_entry = None

        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].note == note:
                stack_entry = self.stack[index]
                del self.stack[index]
                break

        return stack_entry

    def replace(self, note, new_octave):
        """
        Replaces a note in the note stack
        :param note: the note to replace
        :param new_octave: the new octave the note is playing in
        :return:
        """
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].note == note:
                self.stack[index] = StackEntry(note, new_octave)
                break


    def notes_to_retrigger(self) -> list:
        """
        Returns a list of notes, depending on the set behaviour:
            - BEHAVIOUR_RETRIGGER_ALL: all notes in the stack should be re-triggered
            - BEHAVIOUR_RETRIGGER_LAST: the last note appended to the stack should be re-triggered
            - BEHAVIOUR_RETRIGGER_LOWEST: the lowest note (numerical) should be re-triggered
            - BEHAVIOUR_NODDLE_TOASTER: currently teh same as BEHAVIOUR_RETRIGGER_LAST
        :return: a list of notes that need re-triggering
        """
        if self.behaviour == self.BEHAVIOUR_RETRIGGER_NONE:
            return []
        elif self.behaviour == self.BEHAVIOUR_RETRIGGER_ALL:
            return self.stack[:]
        elif self.behaviour == self.BEHAVIOUR_RETRIGGER_LOWEST:
            return min(self.stack, key=lambda value: value.note + (12 * value.octave))
        else:
            return self.stack[-1:]
