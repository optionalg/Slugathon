__copyright__ = "Copyright (c) 2010-2011 David Ripton"
__license__ = "GNU GPL v2"


"""An attempt at a smarter AI."""


import random
import copy
import time
from sys import maxint
import itertools

from slugathon.ai import DimBot
from slugathon.game import Game, Creature
from slugathon.util.log import log


SQUASH = 0.6
BE_SQUASHED = 1.0
# TODO Make this configurable
TIME_LIMIT = 10


class CleverBot(DimBot.DimBot):
    def __init__(self, playername):
        DimBot.DimBot.__init__(self, playername)
        self.best_moves = []
        self.best_creature_moves = None

    def split(self, game):
        """Split if it's my turn."""
        log("split")
        assert game.active_player.name == self.playername
        player = game.active_player
        legions = player.legions.values()
        caretaker = game.caretaker
        for legion in legions:
            if len(legion) == 8:
                # initial split 4-4, one lord per legion
                new_markername = self._choose_marker(player)
                lord = random.choice(["Titan", "Angel"])
                creatures = ["Centaur", "Gargoyle", "Ogre"]
                creature1 = random.choice(creatures)
                creature2 = creature1
                creature3 = creature1
                while creature3 == creature1:
                    creature3 = random.choice(creatures)
                new_creatures = [lord, creature1, creature2, creature3]
                old_creatures = legion.creature_names
                for creature in new_creatures:
                    old_creatures.remove(creature)
                def1 = self.user.callRemote("split_legion", game.name,
                  legion.markername, new_markername,
                  old_creatures, new_creatures)
                def1.addErrback(self.failure)
                return
            elif len(legion) == 7 and player.markernames:
                good_recruit_rolls = set()
                safe_split_rolls = set()
                lst = legion.sorted_creatures
                for roll in xrange(1, 6 + 1):
                    moves = game.find_all_moves(legion,
                      game.board.hexes[legion.hexlabel], roll)
                    for hexlabel, entry_side in moves:
                        masterhex = game.board.hexes[hexlabel]
                        terrain = masterhex.terrain
                        recruits = legion.available_recruits(terrain,
                          caretaker)
                        if recruits:
                            recruit = Creature.Creature(recruits[-1])
                            if recruit.sort_value > lst[-1].sort_value:
                                good_recruit_rolls.add(roll)
                        enemies = player.enemy_legions(hexlabel)
                        if enemies:
                            enemy = enemies.pop()
                            if (enemy.combat_value < SQUASH *
                              legion.combat_value):
                                safe_split_rolls.add(roll)
                        else:
                            safe_split_rolls.add(roll)
                if good_recruit_rolls and len(safe_split_rolls) == 6:
                    split = lst[-2:]
                    split_names = [creature.name for creature in split]
                    keep = lst[:-2]
                    keep_names = [creature.name for creature in keep]
                    new_markername = self._choose_marker(player)
                    def1 = self.user.callRemote("split_legion", game.name,
                      legion.markername, new_markername, keep_names,
                      split_names)
                    def1.addErrback(self.failure)
                    return

        # No splits, so move on to the next phase.
        def1 = self.user.callRemote("done_with_splits", game.name)
        def1.addErrback(self.failure)

    def move_legions(self, game):
        """Move one or more legions, and then end the Move phase."""
        log("move_legions")
        assert game.active_player.name == self.playername
        player = game.active_player
        legions = player.legions.values()
        if not player.moved_legions:
            # (score, legion, hexlabel, entry_side)
            self.best_moves = []
            for legion in legions:
                moves = game.find_all_moves(legion, game.board.hexes[
                  legion.hexlabel], player.movement_roll)
                for hexlabel, entry_side in moves:
                    score = self._score_move(legion, hexlabel, True)
                    self.best_moves.append(
                      (score, legion, hexlabel, entry_side))
            self.best_moves.sort()

            if player.can_take_mulligan:
                legions_with_good_moves = set()
                for (score, legion, _, _) in self.best_moves:
                    if score > 0:
                        legions_with_good_moves.add(legion)
                if len(legions_with_good_moves) < 2:
                    log("taking a mulligan")
                    def1 = self.user.callRemote("take_mulligan", game.name)
                    def1.addErrback(self.failure)
                    return

        log("best moves", self.best_moves)
        while self.best_moves:
            score, legion, hexlabel, entry_side = self.best_moves.pop()
            if (score > 0 or not player.moved_legions or
              len(player.friendly_legions(legion.hexlabel)) >= 2):
                # keeper; remove other moves for this legion, and moves
                # for other legions to this hex, and other teleports if
                # this move was a teleport.
                new_best_moves = [(score2, legion2, hexlabel2, entry_side2)
                  for (score2, legion2, hexlabel2, entry_side2) in
                  self.best_moves
                  if legion2 != legion and hexlabel2 != hexlabel and not
                  (entry_side == entry_side2 == Game.TELEPORT)]
                self.best_moves = new_best_moves
                if entry_side == Game.TELEPORT:
                    teleport = True
                    masterhex = game.board.hexes[hexlabel]
                    terrain = masterhex.terrain
                    if terrain == "Tower":
                        entry_side = 5
                    else:
                        entry_side = random.choice([1, 3, 5])
                    teleporting_lord = sorted(legion.lord_types)[-1]
                else:
                    teleport = False
                    teleporting_lord = None
                def1 = self.user.callRemote("move_legion", game.name,
                  legion.markername, hexlabel, entry_side, teleport,
                  teleporting_lord)
                def1.addErrback(self.failure)
                return

        # No more legions will move.
        def1 = self.user.callRemote("done_with_moves", game.name)
        def1.addErrback(self.failure)

    def _score_move(self, legion, hexlabel, move):
        """Return a score for legion moving to (or staying in) hexlabel."""
        score = 0
        player = legion.player
        game = player.game
        caretaker = game.caretaker
        board = game.board
        enemies = player.enemy_legions(hexlabel)
        if enemies:
            assert len(enemies) == 1
            enemy = enemies.pop()
            enemy_combat_value = enemy.combat_value
            legion_combat_value = legion.combat_value
            log("legion", legion, "hexlabel", hexlabel)
            log("legion_combat_value", legion_combat_value)
            log("enemy_combat_value", enemy_combat_value)
            if enemy_combat_value < SQUASH * legion_combat_value:
                score += enemy.score
            elif enemy_combat_value >= BE_SQUASHED * legion_combat_value:
                score -= legion_combat_value
        if move and (len(legion) < 7 or enemies):
            masterhex = board.hexes[hexlabel]
            terrain = masterhex.terrain
            recruits = legion.available_recruits(terrain, caretaker)
            if recruits:
                recruit_name = recruits[-1]
                recruit = Creature.Creature(recruit_name)
                score += recruit.sort_value
                log("recruit value", recruit.sort_value)
        return score

    def _gen_legion_moves_inner(self, movesets):
        """Yield tuples of distinct hexlabels, one from each
        moveset, in order, with no duplicates.

        movesets is a list of sets of hexlabels, corresponding
        to the order of remaining creatures in the legion.
        """
        if not movesets:
            yield ()
        elif len(movesets) == 1:
            for move in movesets[0]:
                yield (move,)
        else:
            for move in movesets[0]:
                movesets1 = copy.deepcopy(movesets[1:])
                for moveset in movesets1:
                    moveset.discard(move)
                for moves in self._gen_legion_moves_inner(movesets1):
                    yield (move,) + moves

    def _gen_legion_moves(self, movesets):
        """Yield all possible legion_moves for movesets.

        movesets is a list of sets of hexlabels to which
        each Creature can move (or stay), in the same order as
        Legion.sorted_creatures.
        Like:
        creatures [titan1, ogre1, troll1]
        movesets [{"A1", "A2", "B1"}, {"B1", "B2"}, {"B1", "B3"}]

        A legion_move is a list of hexlabels, in the same order as
        creatures, where each Creature's hexlabel is one from its original
        list, and no two Creatures have the same hexlabel.  Like:
        ["A1", "B1", "B3"]
        """
        log("_gen_legion_moves", movesets)
        for moves in self._gen_legion_moves_inner(movesets):
            if len(moves) == len(movesets):
                yield list(moves)

    def _find_move_order(self, game, creature_moves):
        """Return a new list with creature_moves rearranged so that as
        many of the moves as possible can be legally made.

        creature_moves is a list of (Creature, start_hexlabel, finish_hexlabel)
        tuples.
        """
        log("_find_move_order")
        sort_values = {}
        for creature, start, move in creature_moves:
            sort_values[creature] = creature.sort_value
        max_score = sum(sort_values.itervalues())
        perms = list(itertools.permutations(creature_moves))
        # Scramble the list so we don't get a bunch of similar bad
        # orders jumbled together at the beginning.
        random.shuffle(perms)
        best_score = 0
        best_perm = None
        for perm in perms:
            score = 0
            try:
                for creature, start, move in perm:
                    if (move == creature.hexlabel or move in
                      game.find_battle_moves(creature)):
                        # XXX Modifying game state
                        creature.hexlabel = move
                        score += sort_values[creature]
                if score == max_score:
                    return list(perm)
                elif score > best_score:
                    best_score = score
                    best_perm = perm
            finally:
                for creature, start, move in creature_moves:
                    creature.hexlabel = start
        return list(best_perm)

    def _find_best_creature_moves(self, game):
        """Return a list of up to one (Creature, hexlabel) tuple for
        each Creature in the battle active legion.

        Idea: Find all possible moves for each creature in the legion,
        ignoring mobile allies, and score them in isolation without knowing
        where its allies will end up.  Find the best 7 moves for each creature
        (because with up to 7 creatures in a legion, a creature may have to
        take its 7th-favorite move, and because 7! = 5040, not too big).
        Combine these into legion moves, and score those again, then take
        the best legion move.  Finally, find the order of creature moves
        that lets all the creatures reach their assigned hexes without
        blocking their allies' moves.
        """
        assert game.battle_active_player.name == self.playername
        legion = game.battle_active_legion
        log("_find_best_creature_moves", legion)
        movesets = []  # list of a set of hexlabels for each creature
        creatures = [creature for creature in legion.sorted_creatures if not
          creature.dead]
        for creature in creatures:
            moves = game.find_battle_moves(creature, ignore_mobile_allies=True)
            if moves:
                score_moves = []
                # Not moving is also an option, unless offboard.
                if creature.hexlabel not in ["ATTACKER", "DEFENDER"]:
                    moves.add(creature.hexlabel)
                for move in moves:
                    try:
                        # XXX Modifying game state
                        creature.previous_hexlabel = creature.hexlabel
                        creature.hexlabel = move
                        score = self._score_legion_move(game, [creature])
                        score_moves.append((score, move))
                    finally:
                        creature.hexlabel = creature.previous_hexlabel
                score_moves.sort()
                log("score_moves", creature, score_moves)
                # TODO Randomize tie scores
                best_score_moves = score_moves[-7:]
                moveset = set()
                for score, move in best_score_moves:
                    moveset.add(move)
            else:
                moveset = set([creature.hexlabel])
            movesets.append(moveset)
        best_legion_move = None
        now = time.time()
        legion_moves = list(self._gen_legion_moves(movesets))
        log("found %d legion_moves in %fs" % (len(legion_moves), time.time() -
          now))
        best_score = -maxint
        start = time.time()
        # Scramble the moves, in case we don't have time to look at them all.
        random.shuffle(legion_moves)
        log("len(creatures) %d len(legion_moves[0]) %d" % (len(creatures),
          len(legion_moves[0])))
        for legion_move in legion_moves:
            try:
                for ii, creature in enumerate(creatures):
                    move = legion_move[ii]
                    # XXX Modifying game state
                    creature.previous_hexlabel = creature.hexlabel
                    creature.hexlabel = move
                score = self._score_legion_move(game, creatures)
                if score > best_score:
                    best_legion_move = legion_move
                    best_score = score
                now = time.time()
                if now - start > TIME_LIMIT:
                    break
            finally:
                for creature in creatures:
                    creature.hexlabel = creature.previous_hexlabel
        log("found best_legion_move %s in %fs" % (best_legion_move,
          now - start))
        start_hexlabels = [creature.hexlabel for creature in creatures]
        creature_moves = zip(creatures, start_hexlabels, best_legion_move)
        log("creature_moves", creature_moves)
        ordered_creature_moves = self._find_move_order(game, creature_moves)
        log("ordered_creature_moves", ordered_creature_moves)
        return ordered_creature_moves

    def move_creatures(self, game):
        """Move all creatures in the legion.

        Idea: Find all possible moves for each creature in the legion,
        ignoring mobile allies, and score them in isolation without knowing
        where its allies will end up.  Find the best 7 moves for each creature
        (because with up to 7 creatures in a legion, a creature may have to
        take its 7th-favorite move, and because 7! = 5040, not too big).
        Combine these into legion moves, and score those again, then take
        the best legion move.  Finally, find the order of creature moves
        that lets all the creatures reach their assigned hexes without
        blocking their allies' moves.
        """
        log("move creatures")
        if self.best_creature_moves is None:
            self.best_creature_moves = self._find_best_creature_moves(game)
        # Loop in case a non-move is best.
        while self.best_creature_moves:
            (creature, start, finish) = self.best_creature_moves.pop(0)
            if finish != start:
                log("calling move_creature", creature.name, start, finish)
                def1 = self.user.callRemote("move_creature", game.name,
                  creature.name, start, finish)
                def1.addErrback(self.failure)
                return
        # No moves, so end the maneuver phase.
        log("calling done_with_maneuvers")
        self.best_creature_moves = None
        def1 = self.user.callRemote("done_with_maneuvers", game.name)
        def1.addErrback(self.failure)

    def _score_legion_move(self, game, creatures):
        """Return a score for creatures in their current hexlabels."""
        ATTACKER_AGGRESSION_BONUS = 1.0
        ATTACKER_DISTANCE_PENALTY = 1.0
        HIT_BONUS = 1.0
        KILL_BONUS = 3.0
        DAMAGE_PENALTY = 1.0
        DEATH_PENALTY = 3.0
        ELEVATION_BONUS = 0.5
        NATIVE_BRAMBLE_BONUS = 0.3
        NON_NATIVE_BRAMBLE_PENALTY = 0.5
        TOWER_BONUS = 0.5
        NON_NATIVE_DRIFT_PENALTY = 2.0
        NATIVE_VOLCANO_BONUS = 1.0
        ADJACENT_ALLY_BONUS = 0.5
        RANGESTRIKE_BONUS = 2.0
        TITAN_FORWARD_PENALTY = 1.0

        score = 0
        for creature in creatures:
            legion = creature.legion
            legion2 = game.other_battle_legion(legion)
            battlemap = game.battlemap
            can_rangestrike = False
            engaged = creature.engaged_enemies
            probable_kill = False
            max_mean_hits = 0.0
            total_mean_damage_taken = 0.0
            # melee
            for enemy in engaged:
                # Damage we can do.
                dice = creature.number_of_dice(enemy)
                strike_number = creature.strike_number(enemy)
                mean_hits = dice * (7. - strike_number) / 6
                if mean_hits >= enemy.hits_left:
                    probable_kill = True
                max_mean_hits = max(mean_hits, max_mean_hits)
                # Damage we can take.
                dice = enemy.number_of_dice(creature)
                strike_number = enemy.strike_number(creature)
                mean_hits = dice * (7. - strike_number) / 6
                total_mean_damage_taken += mean_hits
            probable_death = total_mean_damage_taken >= creature.hits_left

            # rangestriking
            if not engaged:
                targets = creature.rangestrike_targets
                for enemy in targets:
                    # Damage we can do
                    dice = creature.number_of_dice(enemy)
                    strike_number = creature.strike_number(enemy)
                    mean_hits = dice * (7. - strike_number) / 6
                    if mean_hits >= enemy.hits_left:
                        probable_kill = True
                    max_mean_hits = max(mean_hits, max_mean_hits)
                    can_rangestrike = True
            if can_rangestrike:
                score += RANGESTRIKE_BONUS

            # Don't encourage titans to charge early.
            if (creature.name != "Titan" or game.battle_turn >= 4 or
              len(legion) == 1):
                score += HIT_BONUS * max_mean_hits
                score += KILL_BONUS * probable_kill
            score -= DAMAGE_PENALTY * total_mean_damage_taken
            score -= DEATH_PENALTY * probable_death

            # attacker must attack to avoid time loss
            # Don't encourage titans to charge early.
            if legion == game.attacker_legion and (creature.name != "Titan"
              or game.battle_turn >= 4 or len(legion) == 1):
                if engaged or targets:
                    score += ATTACKER_AGGRESSION_BONUS
                else:
                    enemy_hexlabels = [enemy.hexlabel for enemy in
                      legion2.living_creatures]
                    min_range = min((battlemap.range(creature.hexlabel,
                      enemy_hexlabel) for enemy_hexlabel in enemy_hexlabels))
                    score -= min_range * ATTACKER_DISTANCE_PENALTY

            battlehex = battlemap.hexes[creature.hexlabel]
            terrain = battlehex.terrain

            # Make titans hang back early.
            if (creature.name == "Titan" and game.battle_turn < 4 and
              terrain != "Tower"):
                if legion == game.attacker_legion:
                    entrance = "ATTACKER"
                else:
                    entrance = "DEFENDER"
                distance = battlemap.range(creature.hexlabel, entrance,
                  allow_entrance=True) - 2
                score -= distance * TITAN_FORWARD_PENALTY

            # terrain
            score += battlehex.elevation * ELEVATION_BONUS
            if terrain == "Bramble":
                if creature.is_native(terrain):
                    score += NATIVE_BRAMBLE_BONUS
                else:
                    score -= NON_NATIVE_BRAMBLE_PENALTY
            elif terrain == "Tower":
                score += TOWER_BONUS
            elif terrain == "Drift":
                if not creature.is_native(terrain):
                    score -= NON_NATIVE_DRIFT_PENALTY
            elif terrain == "Volcano":
                score += NATIVE_VOLCANO_BONUS

            # allies
            for neighbor in battlehex.neighbors:
                for ally in legion.living_creatures:
                    if ally.hexlabel == neighbor:
                        score += ADJACENT_ALLY_BONUS

        return score
