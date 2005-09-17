from twisted.spread import pb

class Action(pb.Copyable, pb.RemoteCopy):
    def __repr__(self):
        return "%s %s" % (self.__class__.__name__, self.__dict__)

    def __hash__(self):
        """Based on all the attributes of the Action, but not its class,
        so that an Action and its matching UndoAction have the same hash.
        """
        return hash(tuple(sorted(list(self.__dict__.iteritems()))))

    def __eq__(self, other):
        """Based on all the attributes of the Action, and its class."""
        return self.__class__ == other.__class__ and hash(self) == hash(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def undo_action(self):
        """If this action is undoable, construct the appropriate UndoAction."""
        return None

    def undoable(self):
        return (self.undo_action() is not None)


pb.setUnjellyableForClass(Action, Action)

class UndoAction(Action):
    """Abstract base class for Undo actions"""
    pass


class AddUsername(Action):
    def __init__(self, username):
        self.username = username
pb.setUnjellyableForClass(AddUsername, AddUsername)

class DelUsername(Action):
    def __init__(self, username):
        self.username = username
pb.setUnjellyableForClass(DelUsername, DelUsername)


class FormGame(Action):
    def __init__(self, username, game_name, create_time, start_time,
      min_players, max_players):
        self.username = username
        self.game_name = game_name
        self.create_time = create_time
        self.start_time = start_time
        self.min_players = min_players
        self.max_players = max_players
pb.setUnjellyableForClass(FormGame, FormGame)


class RemoveGame(Action):
    def __init__(self, game_name):
        self.game_name = game_name
pb.setUnjellyableForClass(RemoveGame, RemoveGame)


class JoinGame(Action):
    def __init__(self, username, game_name):
        self.username = username
        self.game_name = game_name
pb.setUnjellyableForClass(JoinGame, JoinGame)

class DropFromGame(Action):
    def __init__(self, username, game_name):
        self.username = username
        self.game_name = game_name
pb.setUnjellyableForClass(DropFromGame, DropFromGame)


class AssignTower(Action):
    def __init__(self, game_name, playername, tower_num):
        self.game_name = game_name
        self.playername = playername
        self.tower_num = tower_num
pb.setUnjellyableForClass(AssignTower, AssignTower)

class AssignedAllTowers(Action):
    def __init__(self, game_name):
        self.game_name = game_name
pb.setUnjellyableForClass(AssignedAllTowers, AssignedAllTowers)


class PickedColor(Action):
    def __init__(self, game_name, playername, color):
        self.game_name = game_name
        self.playername = playername
        self.color = color
pb.setUnjellyableForClass(PickedColor, PickedColor)

class AssignedAllColors(Action):
    def __init__(self, game_name):
        self.game_name = game_name
pb.setUnjellyableForClass(AssignedAllColors, AssignedAllColors)


class CreateStartingLegion(Action):
    def __init__(self, game_name, playername, markername):
        self.game_name = game_name
        self.playername = playername
        self.markername = markername
pb.setUnjellyableForClass(CreateStartingLegion, CreateStartingLegion)


class SplitLegion(Action):
    def __init__(self, game_name, playername, parent_markername, 
      child_markername, parent_creature_names, child_creature_names):
        """parent_creature_names and child_creature_names are lists of the 
        actual creature names if known, or lists of height * None if not known
        """
        self.game_name = game_name
        self.playername = playername
        self.parent_markername = parent_markername
        self.child_markername = child_markername
        self.parent_creature_names = tuple(parent_creature_names)
        self.child_creature_names = tuple(child_creature_names)

    def undo_action(self):
        return UndoSplit(self.game_name, self.playername, 
          self.parent_markername, self.child_markername, 
          self.parent_creature_names, self.child_creature_names)

pb.setUnjellyableForClass(SplitLegion, SplitLegion)


class UndoSplit(UndoAction):
    def __init__(self, game_name, playername, parent_markername, 
      child_markername, parent_creature_names, child_creature_names):
        """Used for voluntarily undoing a split during the split phase.
        
        parent_creature_names and child_creature_names are lists of the 
        actual creature names if known, or lists of height * None if not known
        """
        self.game_name = game_name
        self.playername = playername
        self.parent_markername = parent_markername
        self.child_markername = child_markername
        self.parent_creature_names = tuple(parent_creature_names)
        self.child_creature_names = tuple(child_creature_names)
pb.setUnjellyableForClass(UndoSplit, UndoSplit)

class MergeLegions(Action):
    def __init__(self, game_name, playername, parent_markername, 
      child_markername, parent_creature_names, child_creature_names):
        """Used for involuntarily undoing a split during the movement phase,
        because of a lack of legal non-teleport moves.
        
        parent_creature_names and child_creature_names are lists of the 
        actual creature names if known, or lists of height * None if not known
        """
        self.game_name = game_name
        self.playername = playername
        self.parent_markername = parent_markername
        self.child_markername = child_markername
        self.parent_creature_names = tuple(parent_creature_names)
        self.child_creature_names = tuple(child_creature_names)
pb.setUnjellyableForClass(MergeLegions, MergeLegions)


# XXX Do we need a separate DoneWithSplits action?

class RollMovement(Action):
    def __init__(self, game_name, playername, movement_roll):
        """parent_creature_names and child_creature_names are lists of the 
        actual creature names if known, or lists of height * None if not known
        """
        self.game_name = game_name
        self.playername = playername
        self.movement_roll = movement_roll
pb.setUnjellyableForClass(RollMovement, RollMovement)

class MoveLegion(Action):
    def __init__(self, game_name, playername, markername, hexlabel,
      entry_side, teleport, teleporting_lord):
        self.game_name = game_name
        self.playername = playername
        self.markername = markername
        self.hexlabel = hexlabel
        self.entry_side = entry_side
        self.teleport = teleport
        self.teleporting_lord = teleporting_lord

    def undo_action(self):
        return UndoMoveLegion(self.game_name, self.playername, self.markername,
          self.hexlabel, self.entry_side, self.teleport, self.teleporting_lord)

pb.setUnjellyableForClass(MoveLegion, MoveLegion)

class UndoMoveLegion(UndoAction):
    def __init__(self, game_name, playername, markername, hexlabel,
      entry_side, teleport, teleporting_lord):
        self.game_name = game_name
        self.playername = playername
        self.markername = markername
        self.hexlabel = hexlabel
        self.entry_side = entry_side
        self.teleport = teleport
        self.teleporting_lord = teleporting_lord
pb.setUnjellyableForClass(UndoMoveLegion, UndoMoveLegion)

class DoneMoving(Action):
    def __init__(self, game_name, playername):
        self.game_name = game_name
        self.playername = playername
pb.setUnjellyableForClass(DoneMoving, DoneMoving)


# TODO recruiters
class RecruitCreature(Action):
    def __init__(self, game_name, playername, markername, creature_name):
        self.game_name = game_name
        self.playername = playername
        self.markername = markername
        self.creature_name = creature_name

    def undo_action(self):
        return UndoRecruit(self.game_name, self.playername, self.markername, 
          self.creature_name)

pb.setUnjellyableForClass(RecruitCreature, RecruitCreature)


class UndoRecruit(UndoAction):
    def __init__(self, game_name, playername, markername, creature_name):
        self.game_name = game_name
        self.playername = playername
        self.markername = markername
        self.creature_name = creature_name
pb.setUnjellyableForClass(UndoRecruit, UndoRecruit)

class DoneRecruiting(Action):
    def __init__(self, game_name, playername):
        self.game_name = game_name
        self.playername = playername
pb.setUnjellyableForClass(DoneRecruiting, DoneRecruiting)
