from collections.abc import MutableSequence


class RewindableList(MutableSequence):
    """This is a just-enough-implementation class to provide a list
    that can be rewound to the start during iteration. It is not fully
    functional.
    """

    def __init__(self, items):
        self._items = items
        self._length = len(items)
        self._index = 0

    def __iter__(self):
        return self

    def __getitem__(self, item):
        return self._items[item]

    def __len__(self):
        return len(self._items)

    def __next__(self):
        if self._index < self._length:
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

    # Fail in in your duties ...
    # The following methods should never be called
    def __delitem__(self, key):
        assert False

    def __setitem__(self, key, value):
        assert False

    def insert(self, x, y):
        assert False
