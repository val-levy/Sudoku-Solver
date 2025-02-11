"""

Sudoku Solver
by Val Levy
A Project for CS211 at University of Oregon

02/10/2025

Desc:

A Sudoku board holds a matrix of tiles.
Each row and column and also sub-blocks
are treated as a group (sometimes called
a 'nonet'); when solved, each group must contain
exactly one occurrence of each of the
symbol choices.

"""


from sdk_config import CHOICES, UNKNOWN, ROOT
from sdk_config import NROWS, NCOLS
import logging
import enum
from typing import List, Sequence, Set

logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


# --------------------------------
#  The events for MVC
# --------------------------------

class Event(object):
    """Abstract base class of all events, both for MVC
    and for other purposes.
    """
    pass


# ---------------
# Listeners (base class)
# ---------------

class Listener(object):
    """Abstract base class for listeners.
    Subclass this to make the notification do
    something useful.
    """

    def __init__(self):
        """Default constructor for simple listeners without state"""
        pass

    def notify(self, event: Event):
        """The 'notify' method of the base class must be
        overridden in concrete classes.
        """
        raise NotImplementedError("You must override Listener.notify")


# --------------------------------------
# Events and listeners for Tile objects
# --------------------------------------

class EventKind(enum.Enum):
    TileChanged = 1
    TileGuessed = 2


class TileEvent(Event):
    """Abstract base class for things that happen
    to tiles. We always indicate the tile.  Concrete
    subclasses indicate the nature of the event.
    """

    def __init__(self, tile: 'Tile', kind: EventKind):
        self.tile = tile
        self.kind = kind
        # Note 'Tile' type is a forward reference;
        # Tile class is defined below

    def __str__(self):
        """Printed representation includes name of concrete subclass"""
        return f"{repr(self.tile)}"


class TileListener(Listener):
    def notify(self, event: TileEvent):
        raise NotImplementedError(
            "TileListener subclass needs to override notify(TileEvent)")


class Listenable:
    """Objects to which listeners (like a view component) can be attached"""

    def __init__(self):
        self.listeners = [ ]

    def add_listener(self, listener: Listener):
        self.listeners.append(listener)

    def notify_all(self, event: Event):
        for listener in self.listeners:
            listener.notify(event)


# ----------------------------------------------
#      Tile class
# ----------------------------------------------

class Tile(Listenable):
    """One tile on the Sudoku grid.
    Public attributes (read-only): value, which will be either
    UNKNOWN or an element of CHOICES; candidates, which will
    be a set drawn from CHOICES.  If value is an element of
    CHOICES,then candidates will be the singleton containing
    value.  If candidates is empty, then no tile value can
    be consistent with other tile values in the grid.
    value is a public read-only attribute; change it
    only through the access method set_value or indirectly 
    through method remove_candidates.   
    """

    def __init__(self, row: int, col: int, value=UNKNOWN):
        super().__init__()
        assert value == UNKNOWN or value in CHOICES
        self.row = row
        self.col = col
        self.set_value(value)

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f"Tile({str(self.row)}, {str(self.col)}, '{str(self.value)}')"

    def set_value(self, value: str):
        if value in CHOICES:
            self.value = value
            self.candidates = {value}
        else:
            self.value = UNKNOWN
            self.candidates = set(CHOICES)
        self.notify_all(TileEvent(self, EventKind.TileChanged))

    def could_be(self, value: str) -> bool:
        """True if value is a candidate value for this tile"""
        return value in self.candidates
    
    def __hash__(self) -> int:
        """Hash on position only (not value)"""
        return hash((self.row, self.col))

    def remove_candidates(self, used_values: Set[str]) -> bool:
        """The used values cannot be a value of this unknown tile.
        We remove those possibilities from the list of candidates.
        If there is exactly one candidate left, we set the
        value of the tile.
        Returns:  True means we eliminated at least one candidate,
        False means nothing changed (none of the 'used_values' was
        in our candidates set).
        """
        new_candidates = self.candidates.difference(used_values)
        if new_candidates == self.candidates:
            # Didn't remove any candidates
            return False
        self.candidates = new_candidates
        if len(self.candidates) == 1:
            self.set_value(new_candidates.pop())
        self.notify_all(TileEvent(self, EventKind.TileChanged))
        return True


# ------------------------------
#  Board class
# ------------------------------

class Board(object):
    """A board has a matrix of tiles"""

    def __init__(self):
        """The empty board"""
        # Row/Column structure: Each row contains columns
        self.tiles: List[List[Tile]] = [ ]
        self.groups = [ ]
        for row in range(NROWS):
            cols = [ ]
            for col in range(NCOLS):
                cols.append(Tile(row, col))
            self.tiles.append(cols)
        
        for row in self.tiles: 
            self.groups.append(row)

        for i in range(len(self.tiles)):
            col = []
            for row in self.tiles:
                col.append(row[i])
            self.groups.append(col)

        for block_row in range(ROOT):
            for block_col in range(ROOT):
                group = [ ] 
                for row in range(ROOT):
                    for col in range(ROOT):
                        row_addr = (ROOT * block_row) + row
                        col_addr = (ROOT * block_col) + col
                        group.append(self.tiles[row_addr][col_addr])
                self.groups.append(group)
    
    def set_tiles(self, tile_values: Sequence[Sequence[str]] ):
        """Set the tile values a list of lists or a list of strings"""
        for row_num in range(NROWS):
            for col_num in range(NCOLS):
                tile = self.tiles[row_num][col_num]
                tile.set_value(tile_values[row_num][col_num])

    def __str__(self) -> str:
        """In Sadman Sudoku format"""
        return "\n".join(self.as_list())

    def as_list(self) -> List[str]:
        """Tile values in a format compatible with 
        set_tiles.
        """
        row_syms = [ ]
        for row in self.tiles:
            values = [tile.value for tile in row]
            row_syms.append("".join(values))
        return row_syms

    def is_consistent(self) -> bool:
        for group in self.groups:
            used_symbols = set()
            for tile in group:
                if tile.value != UNKNOWN:
                    if tile.value in used_symbols:
                        return False #board is not consistant
                    else:
                        used_symbols.add(tile.value)
        return True #board is okay so far

    def solve(self):
        """General solver; guess-and-check
        combined with constraint propagation.
        """
        self.propagate()
        if self.is_consistent() and self.is_complete():
            return True
        if not self.is_consistent():
            return False
        else:
            saved = self.as_list()
            min_chosen_tile = self.min_choice_tile()
            for value in min_chosen_tile.candidates:
                min_chosen_tile.set_value(value)
                if self.solve():
                    return True
                else:
                    self.set_tiles(saved)
            return False
        
    def propagate(self):
        """Repeat solution tactics until we
        don't make any progress, whether or not
        the board is solved.
        """
        progress = True
        while progress:
            progress = self.naked_single()
            self.hidden_single()
        return

    def naked_single(self) -> bool:
        """Eliminate candidates and check for sole remaining possibilities.
        Return value True means we crossed off at least one candidate.
        Return value False means we made no progress.
        """
        result = False
        for group in self.groups:
            used_vals = set()
            for tile in group:
                if tile.value != UNKNOWN:
                    used_vals.add(tile.value)
            if len(used_vals) > 0:
                for tile in group:
                    if tile.value == UNKNOWN:
                        if tile.remove_candidates(used_vals):
                            result = True
        return result

    def hidden_single(self) -> bool:
        result = False
        for group in self.groups:
            leftovers = set(CHOICES)
            for tile in group:
                if tile.value in CHOICES:
                    leftovers.discard(tile.value)
            for value in leftovers:
                tiles_and_value = []
                for tile in group:
                    if value in tile.candidates:
                        tiles_and_value.append(tile)
                if len(tiles_and_value) == 1:
                    tiles_and_value[0].set_value(value)
                    result = True
        return result

    def min_choice_tile(self) -> Tile:
        """Returns a tile with value UNKNOWN and
        minimum number of candidates.
        Precondition: There is at least one tile
        with value UNKNOWN.
        """
        min_candidates = 9
        min_candidates_tile = None

        for i in range(len(self.tiles)):
            for tile in self.tiles[i]:
                if tile.value == UNKNOWN:
                    if len(tile.candidates) <= min_candidates:
                        min_candidates = len(tile.candidates)
                        min_candidates_tile = tile
        return min_candidates_tile

    def is_complete(self) -> bool:
        """None of the tiles are UNKNOWN.  
        Note: Does not check consistency; do that 
        separately with is_consistent.
        """
        for i in range(len(self.tiles)):
            for tile in self.tiles[i]:
                if tile.value == UNKNOWN:
                    return False
        return True


