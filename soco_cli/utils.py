from collections.abc import Sequence


class RewindableList(Sequence):
    """This is a just-enough-implementation class to provide a list
    that can be rewound during iteration.
    """

    def __init__(self, items):
        self._items = items
        self._index = 0

    def __iter__(self):
        return self

    def __getitem__(self, item):
        return self._items[item]

    def __len__(self):
        return len(self._items)

    def __next__(self):
        if self._index < len(self._items):
            item = self._items[self._index]
            self._index += 1
            return item
        else:
            raise StopIteration

    def rewind(self):
        self._index = 0

    def rewind_to(self, index):
        if 0 <= index < len(self._items):
            self._index = index
        else:
            raise IndexError
