__copyright__ = "Copyright (c) 2010-2012 David Ripton"
__license__ = "GNU GPL v2"


"""An attempt at a smarter AI."""


# Manually bump this every time this module changes enough that we want
# results tracking to treat it as a new AI.
VERSION = 1


import random
import copy
import time
from sys import maxint
import itertools
import collections

from twisted.python import log
from zope.interface import implementer

from slugathon.ai.Bot import Bot
from slugathon.game import Game, Creature, Phase


SQUASH = 0.6
BE_SQUASHED = 1.0


def best7(score_moves):
    """Return a set of the the best (highest score) (up to) 7 moves from
    score_moves, which is a sorted list of (score, move) tuples.

    If there's a tie, pick at random.
    """
    score_moves = score_moves[:]
    best_moves = set()
    while score_moves and len(best_moves) < 7:
        choices = []
        best_score = score_moves[-1][0]
        for (score, move) in reversed(score_moves):
            if score == best_score:
                choices.append((score, move))
            else:
                break
        (score, move) = random.choice(choices)
        score_moves.remove((score, move))
        best_moves.add(move)
    return best_moves


@implementer(Bot)
class CleverBot(object):
    def __init__(self, playername, time_limit):
        log.msg("CleverBot", playername, time_limit)
        self.playername = playername
        self.user = None
        self.time_limit = time_limit
        self.best_creature_moves = None

    @property
    def result_info(self):
        """Return a string with information for result-tracking purposes."""
        return str("version=%s time_limit=%s" % (VERSION, self.time_limit))

    def maybe_pick_color(self, game):
        log.msg("maybe_pick_color")
        if game.next_playername_to_pick_color == self.playername:
            color = random.choice(game.colors_left)
            def1 = self.user.callRemote("pick_color", game.name, color)
            def1.addErrback(self.failure)

    def maybe_pick_first_marker(self, game, playername):
        log.msg("maybe_pick_first_marker")
        if playername == self.playername:
            player = game.get_player_by_name(playername)
            markerid = self._choose_marker(player)
            self._pick_marker(game, self.playername, markerid)

    def _pick_marker(self, game, playername, markerid):
        log.msg("pick_marker")
        player = game.get_player_by_name(playername)
        if markerid is None:
            if not player.markerid_to_legion:
                self.maybe_pick_first_marker(game, playername)
        else:
            player.pick_marker(markerid)
            if not player.markerid_to_legion:
                def1 = self.user.callRemote("pick_first_marker", game.name,
                  markerid)
                def1.addErrback(self.failure)

    def _choose_marker(self, player):
        """Pick a legion marker randomly, except prefer my own markers
        to captured ones to be less annoying."""
        own_markerids_left = [name for name in player.markerids_left if
          name[:2] == player.color_abbrev]
        if own_markerids_left:
            return random.choice(own_markerids_left)
        else:
            return random.choice(list(player.markerids_left))

    def choose_engagement(self, game):
        """Resolve engagements."""
        log.msg("choose_engagement")
        if (game.pending_summon or game.pending_reinforcement or
          game.pending_acquire):
            log.msg("choose_engagement bailing early summon",
              game.pending_summon,
              "reinforcement", game.pending_reinforcement,
              "acquire", game.pending_acquire)
            return
        hexlabels = game.engagement_hexlabels
        if hexlabels:
            hexlabel = hexlabels.pop()
            log.msg("calling resolve_engagement")
            def1 = self.user.callRemote("resolve_engagement", game.name,
              hexlabel)
            def1.addErrback(self.failure)
        else:
            log.msg("CleverBot calling done_with_engagements")
            def1 = self.user.callRemote("done_with_engagements", game.name)
            def1.addErrback(self.failure)

    # TODO concede, negotiate
    def resolve_engagement(self, game, hexlabel):
        """Resolve the engagement in hexlabel."""
        log.msg("resolve_engagement", game, hexlabel)
        FLEE_RATIO = 1.5
        attacker = None
        defender = None
        for legion in game.all_legions(hexlabel):
            if legion.player == game.active_player:
                attacker = legion
            else:
                defender = legion
        if attacker:
            log.msg("attacker", attacker, attacker.player.name)
        if defender:
            log.msg("defender", defender, defender.player.name)
        if not attacker or not defender:
            log.msg("no attacker or defender; bailing")
            return
        if defender.player.name == self.playername:
            if game.defender_chose_not_to_flee:
                log.msg("defender already chose not to flee")
            else:
                log.msg("defender hasn't chosen whether to flee yet")
                if defender.can_flee:
                    log.msg("can flee")
                    if (defender.terrain_combat_value * FLEE_RATIO <
                      attacker.terrain_combat_value):
                        log.msg("fleeing")
                        def1 = self.user.callRemote("flee", game.name,
                          defender.markerid)
                        def1.addErrback(self.failure)
                    else:
                        log.msg("not fleeing")
                        def1 = self.user.callRemote("do_not_flee", game.name,
                          defender.markerid)
                        def1.addErrback(self.failure)
                else:
                    log.msg("can't flee")
                    def1 = self.user.callRemote("do_not_flee", game.name,
                      defender.markerid)
                    def1.addErrback(self.failure)
        elif attacker.player.name == self.playername:
            if defender.can_flee and not game.defender_chose_not_to_flee:
                log.msg("waiting for defender")
                # Wait for the defender to choose whether to flee.
                pass
            else:
                log.msg("attacker fighting")
                def1 = self.user.callRemote("fight", game.name,
                  attacker.markerid, defender.markerid)
                def1.addErrback(self.failure)
        else:
            log.msg("not my engagement")

    def recruit(self, game):
        log.msg("CleverBot.recruit")
        if game.active_player.name != self.playername:
            log.msg("not my turn")
            return
        player = game.active_player
        for legion in player.legions:
            if legion.moved and legion.can_recruit:
                masterhex = game.board.hexes[legion.hexlabel]
                caretaker = game.caretaker
                mterrain = masterhex.terrain
                lst = legion.available_recruits_and_recruiters(mterrain,
                  caretaker)
                if lst:
                    # For now, just take the last one.
                    tup = lst[-1]
                    recruit = tup[0]
                    recruiters = tup[1:]
                    log.msg("CleverBot calling recruit_creature",
                      legion.markerid, recruit, recruiters)
                    def1 = self.user.callRemote("recruit_creature", game.name,
                      legion.markerid, recruit, recruiters)
                    def1.addErrback(self.failure)
                    return
        log.msg("CleverBot calling done_with_recruits")
        def1 = self.user.callRemote("done_with_recruits", game.name)
        def1.addErrback(self.failure)

    def reinforce(self, game):
        """Reinforce, during the REINFORCE battle phase"""
        log.msg("CleverBot.reinforce")
        assert game.battle_active_player.name == self.playername
        assert game.battle_phase == Phase.REINFORCE
        legion = game.defender_legion
        assert legion.player.name == self.playername
        mterrain = game.battlemap.mterrain
        caretaker = game.caretaker
        if game.battle_turn == 4 and legion.can_recruit:
            lst = legion.available_recruits_and_recruiters(mterrain, caretaker)
            if lst:
                # For now, just take the last one.
                tup = lst[-1]
                recruit = tup[0]
                recruiters = tup[1:]
                log.msg("CleverBot calling recruit_creature", recruit)
                def1 = self.user.callRemote("recruit_creature", game.name,
                  legion.markerid, recruit, recruiters)
                def1.addErrback(self.failure)
                return

        log.msg("CleverBot calling done_with_reinforcements")
        def1 = self.user.callRemote("done_with_reinforcements", game.name)
        def1.addErrback(self.failure)

    def reinforce_after(self, game):
        """Reinforce, after the battle"""
        log.msg("CleverBot.reinforce_after")
        legion = game.defender_legion
        assert legion.player.name == self.playername
        mterrain = game.battlemap.mterrain
        caretaker = game.caretaker
        if legion.can_recruit:
            lst = legion.available_recruits_and_recruiters(mterrain, caretaker)
            if lst:
                # For now, just take the last one.
                tup = lst[-1]
                recruit = tup[0]
                recruiters = tup[1:]
                log.msg("CleverBot calling recruit_creature", recruit)
                def1 = self.user.callRemote("recruit_creature", game.name,
                  legion.markerid, recruit, recruiters)
                def1.addErrback(self.failure)
                return

        log.msg("CleverBot calling do_not_reinforce", recruit)
        def1 = self.user.callRemote("do_not_reinforce", game.name,
          legion.markerid)
        def1.addErrback(self.failure)

    def summon_angel_during(self, game):
        """Summon, during the REINFORCE battle phase"""
        log.msg("CleverBot.summon_angel_during")
        assert game.active_player.name == self.playername
        if game.battle_phase != Phase.REINFORCE:
            return
        legion = game.attacker_legion
        assert legion.player.name == self.playername
        summonables = []
        if (legion.can_summon and game.first_attacker_kill in
          [game.battle_turn - 1, game.battle_turn]):
            for legion2 in legion.player.legions:
                if not legion2.engaged:
                    for creature in legion2.creatures:
                        if creature.summonable:
                            summonables.append(creature)
            if summonables:
                tuples = sorted(((creature.sort_value, creature)
                  for creature in summonables), reverse=True)
                summonable = tuples[0][1]
                donor = summonable.legion
                log.msg("CleverBot calling _summon_angel", legion.markerid,
                  donor.markerid, summonable.name)
                def1 = self.user.callRemote("summon_angel", game.name,
                  legion.markerid, donor.markerid, summonable.name)
                def1.addErrback(self.failure)
                return

        log.msg("CleverBot calling do_not_summon_angel", legion.markerid)
        def1 = self.user.callRemote("do_not_summon_angel", game.name,
          legion.markerid)
        def1.addErrback(self.failure)

        log.msg("CleverBot calling done_with_reinforcements")
        def1 = self.user.callRemote("done_with_reinforcements", game.name)
        def1.addErrback(self.failure)

    def summon_angel_after(self, game):
        """Summon, after the battle is over."""
        log.msg("CleverBot.summon_angel_after")
        assert game.active_player.name == self.playername
        legion = game.attacker_legion
        assert legion.player.name == self.playername
        summonables = []
        if (legion.can_summon and game.first_attacker_kill in
          [game.battle_turn - 1, game.battle_turn]):
            for legion2 in legion.player.legions:
                if not legion2.engaged:
                    for creature in legion2.creatures:
                        if creature.summonable:
                            summonables.append(creature)
            if summonables:
                tuples = sorted(((creature.sort_value, creature)
                  for creature in summonables), reverse=True)
                summonable = tuples[0][1]
                donor = summonable.legion
                log.msg("CleverBot calling _summon_angel", legion.markerid,
                  donor.markerid, summonable.name)
                def1 = self.user.callRemote("summon_angel", game.name,
                  legion.markerid, donor.markerid, summonable.name)
                def1.addErrback(self.failure)
                return

        log.msg("CleverBot calling do_not_summon_angel", legion.markerid)
        def1 = self.user.callRemote("do_not_summon_angel", game.name,
          legion.markerid)
        def1.addErrback(self.failure)

    def acquire_angels(self, game, markerid, num_angels, num_archangels):
        log.msg("CleverBot.acquire_angels", markerid, num_angels,
          num_archangels)
        player = game.get_player_by_name(self.playername)
        legion = player.markerid_to_legion[markerid]
        starting_height = len(legion)
        acquires = 0
        angel_names = []
        while starting_height + acquires < 7 and num_archangels:
            angel_names.append("Archangel")
            num_archangels -= 1
            acquires += 1
        while starting_height + acquires < 7 and num_angels:
            angel_names.append("Angel")
            num_angels -= 1
            acquires += 1
        if angel_names:
            log.msg("CleverBot calling acquire_angels", markerid, angel_names)
            def1 = self.user.callRemote("acquire_angels", game.name,
              markerid, angel_names)
            def1.addErrback(self.failure)
        else:
            log.msg("CleverBot calling do_not_acquire_angels", markerid)
            def1 = self.user.callRemote("do_not_acquire_angels", game.name,
              markerid)
            def1.addErrback(self.failure)

    def split(self, game):
        """Split if it's my turn."""
        log.msg("split")
        if game.active_player.name != self.playername:
            log.msg("called split out of turn; exiting")
            return
        player = game.active_player
        caretaker = game.caretaker
        for legion in player.legions:
            if len(legion) == 8:
                if game.turn != 1:
                    raise AssertionError("8-high legion", legion)
                # initial split 4-4, one lord per legion
                log.msg("initial split")
                new_markerid = self._choose_marker(player)
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
                log.msg("new_creatures", new_creatures, "old_creatures",
                  old_creatures)
                def1 = self.user.callRemote("split_legion", game.name,
                  legion.markerid, new_markerid, old_creatures, new_creatures)
                def1.addErrback(self.failure)
                return
            elif len(legion) == 7 and player.markerids_left:
                log.msg("7-high")
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
                            if (enemy.terrain_combat_value < SQUASH *
                              legion.combat_value):
                                safe_split_rolls.add(roll)
                        else:
                            safe_split_rolls.add(roll)
                if good_recruit_rolls and len(safe_split_rolls) == 6:
                    split = lst[-2:]
                    split_names = [creature.name for creature in split]
                    keep = lst[:-2]
                    keep_names = [creature.name for creature in keep]
                    new_markerid = self._choose_marker(player)
                    def1 = self.user.callRemote("split_legion", game.name,
                      legion.markerid, new_markerid, keep_names,
                      split_names)
                    def1.addErrback(self.failure)
                    return

        # No splits, so move on to the next phase.
        def1 = self.user.callRemote("done_with_splits", game.name)
        def1.addErrback(self.failure)

    def move_legions(self, game):
        """Move one or more legions, and then end the Move phase."""
        log.msg("move_legions")
        if game.active_player.name != self.playername:
            log.msg("not active player; aborting")
            return
        player = game.active_player
        non_moves = {}  # markerid: score
        while True:
            # Score moves
            # (score, legion, hexlabel, entry_side)
            best_moves = []
            for legion in player.unmoved_legions:
                moves = game.find_all_moves(legion, game.board.hexes[
                  legion.hexlabel], player.movement_roll)
                for hexlabel, entry_side in moves:
                    score = self._score_move(legion, hexlabel, True)
                    best_moves.append(
                      (score, legion, hexlabel, entry_side))
            best_moves.sort()
            log.msg("best moves", best_moves)

            if player.can_take_mulligan:
                legions_with_good_moves = set()
                for (score, legion, _, _) in best_moves:
                    if score > 0:
                        legions_with_good_moves.add(legion)
                if len(legions_with_good_moves) < 2:
                    log.msg("taking a mulligan")
                    def1 = self.user.callRemote("take_mulligan", game.name)
                    def1.addErrback(self.failure)
                    return

            # Score non-moves
            # (score, legion, hexlabel, None)
            # Entry side None means not a move.
            for legion in player.unmoved_legions:
                score = self._score_move(legion, legion.hexlabel, False)
                non_moves[legion.markerid] = score
            log.msg("non_moves", non_moves)

            while best_moves:
                score, legion, hexlabel, entry_side = best_moves.pop()
                non_move_score = non_moves[legion.markerid]
                if (score > non_move_score or not player.moved_legions or
                  len(player.friendly_legions(legion.hexlabel)) >= 2):
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
                      legion.markerid, hexlabel, entry_side, teleport,
                      teleporting_lord)
                    def1.addErrback(self.failure)
                    return

            # No more legions will move.
            def1 = self.user.callRemote("done_with_moves", game.name)
            def1.addErrback(self.failure)
            return

    def _score_move(self, legion, hexlabel, moved):
        """Return a score for legion moving to (or staying in) hexlabel."""
        score = 0
        player = legion.player
        game = player.game
        caretaker = game.caretaker
        board = game.board
        enemies = player.enemy_legions(hexlabel)
        legion_combat_value = legion.combat_value
        legion_sort_value = legion.sort_value

        if enemies:
            assert len(enemies) == 1
            enemy = enemies.pop()
            enemy_combat_value = enemy.terrain_combat_value
            log.msg("legion", legion, "hexlabel", hexlabel)
            log.msg("legion_combat_value", legion_combat_value)
            log.msg("enemy_combat_value", enemy_combat_value)
            if enemy_combat_value < SQUASH * legion_combat_value:
                score += enemy.score
            elif enemy_combat_value >= BE_SQUASHED * legion_combat_value:
                score -= legion_sort_value
        if moved and (len(legion) < 7 or enemies):
            masterhex = board.hexes[hexlabel]
            terrain = masterhex.terrain
            recruits = legion.available_recruits(terrain, caretaker)
            if recruits:
                recruit_name = recruits[-1]
                recruit = Creature.Creature(recruit_name)
                # Only give credit for recruiting if we're likely to live.
                if not enemies or enemy_combat_value < legion_combat_value:
                    recruit_value = recruit.sort_value
                elif enemy_combat_value < BE_SQUASHED * legion_combat_value:
                    recruit_value = 0.5 * recruit.sort_value
                log.msg("recruit value", legion.markerid, hexlabel,
                  recruit_value)
                score += recruit_value
        if game.turn > 1:
            # Do not fear enemy legions on turn 1.  8-high legions will be
            # forced to split, and hanging around in the tower to avoid getting
            # attacked 5-on-4 is too passive.
            try:
                previous_hexlabel = legion.hexlabel
                legion.hexlabel = hexlabel
                for enemy in player.enemy_legions():
                    if (enemy.terrain_combat_value >= BE_SQUASHED *
                      legion_combat_value):
                        for roll in xrange(1, 6 + 1):
                            moves = game.find_normal_moves(enemy,
                              game.board.hexes[enemy.hexlabel], roll).union(
                              game.find_titan_teleport_moves(enemy))
                            hexlabels = set((move[0] for move in moves))
                            if hexlabel in hexlabels:
                                score -= legion_sort_value / 6.0
            finally:
                legion.hexlabel = previous_hexlabel
        return score

    def _gen_legion_moves_inner(self, movesets):
        """Yield tuples of distinct hexlabels, one from each moveset, in order,
        with no duplicates.

        movesets is a list of sets of hexlabels, corresponding to the order of
        remaining creatures in the legion.
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

        movesets is a list of sets of hexlabels to which each Creature can move
        (or stay), in the same order as Legion.sorted_creatures.  Like:
        creatures [titan1, ogre1, troll1]
        movesets [{"A1", "A2", "B1"}, {"B1", "B2"}, {"B1", "B3"}]

        A legion_move is a list of hexlabels, in the same order as creatures,
        where each Creature's hexlabel is one from its original list, and no
        two Creatures have the same hexlabel.  Like:
        ["A1", "B1", "B3"]
        """
        log.msg("_gen_legion_moves", movesets)
        for moves in self._gen_legion_moves_inner(movesets):
            if len(moves) == len(movesets):
                yield list(moves)

    def _gen_fallback_legion_moves(self, movesets):
        """Yield all possible legion_moves for movesets, possibly including
        some missing moves in the case where not all creatures can get onboard.

        movesets is a list of sets of hexlabels to which each Creature can move
        (or stay), in the same order as Legion.sorted_creatures.  Like:
        creatures [titan1, ogre1, troll1]
        movesets [{"A1", "A2", "B1"}, {"B1", "B2"}, {"B1", "B3"}]

        A legion_move is a list of hexlabels, in the same order as creatures,
        where each Creature's hexlabel is one from its original list, and no
        two Creatures have the same hexlabel.  Like:
        ["A1", "B1", "B3"]
        """
        log.msg("_gen_legion_moves", movesets)
        for moves in self._gen_legion_moves_inner(movesets):
            yield list(moves)

    def _score_perm(self, game, sort_values, perm):
        """Score one move order permutation."""
        score = 0
        moved_creatures = set()
        try:
            for creature_name, start, move in perm:
                creature = game.creatures_in_battle_hex(start,
                  creature_name).pop()
                if (move == start or move in
                  game.find_battle_moves(creature)):
                    creature.previous_hexlabel = creature.hexlabel
                    creature.hexlabel = move
                    moved_creatures.add(creature)
                    score += sort_values[creature_name]
            return score
        finally:
            for creature in moved_creatures:
                creature.hexlabel = creature.previous_hexlabel
                creature.previous_hexlabel = None

    def _find_move_order(self, game, creature_moves):
        """Return a new list with creature_moves rearranged so that as
        many of the moves as possible can be legally made.

        creature_moves is a list of (creature_name, start_hexlabel,
        finish_hexlabel) tuples.
        """
        max_score = 0
        sort_values = {}
        for creature_name, start, move in creature_moves:
            creature = game.creatures_in_battle_hex(start, creature_name).pop()
            sort_values[creature_name] = creature.sort_value
            max_score += creature.sort_value
        perms = list(itertools.permutations(creature_moves))
        # Scramble the list so we don't get a bunch of similar bad
        # orders jumbled together at the beginning.
        log.msg("_find_move_order %d perms" % len(perms))
        random.shuffle(perms)
        best_score = -maxint
        best_perm = None
        start_time = time.time()
        for perm in perms:
            score = self._score_perm(game, sort_values, perm)
            if score == max_score:
                best_perm = perm
                log.msg("_find_move_order found perfect order")
                break
            elif score > best_score:
                best_perm = perm
                best_score = score
            if time.time() - start_time > self.time_limit:
                log.msg("_find_move_order time limit")
                break
        log.msg("_find_move_order returning %s" % list(best_perm))
        return list(best_perm)

    def _find_best_creature_moves(self, game):
        """Return a list of up to one (creature_name, start_hexlabel,
        finish_hexlabel) tuple for each Creature in the battle active legion.

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
        if (game.battle_active_player is None or game.battle_active_player.name
          != self.playername):
            return None
        legion = game.battle_active_legion
        creatures = legion.sorted_living_creatures
        log.msg("_find_best_creature_moves", legion, creatures)
        if not creatures:
            return None
        movesets = []  # list of a set of hexlabels for each creature
        previous_creature = None
        moveset = None
        for creature in creatures:
            if (previous_creature and creature.name == previous_creature.name
              and creature.hexlabel == previous_creature.hexlabel):
                # Reuse previous moveset
                moveset = copy.deepcopy(moveset)
            else:
                moves = game.find_battle_moves(creature,
                  ignore_mobile_allies=True)
                if moves:
                    score_moves = []
                    # Not moving is also an option, unless offboard.
                    if creature.hexlabel not in ["ATTACKER", "DEFENDER"]:
                        moves.add(creature.hexlabel)
                    for move in moves:
                        try:
                            creature.previous_hexlabel = creature.hexlabel
                            creature.hexlabel = move
                            score = self._score_legion_move(game, [creature])
                            score_moves.append((score, move))
                        finally:
                            creature.hexlabel = creature.previous_hexlabel
                    score_moves.sort()
                    log.msg("score_moves", creature, score_moves)
                    moveset = best7(score_moves)
                else:
                    moveset = set([creature.hexlabel])
            movesets.append(moveset)
            previous_creature = creature
        best_legion_move = None
        now = time.time()
        legion_moves = list(self._gen_legion_moves(movesets))
        log.msg("found %d legion_moves in %fs" % (len(legion_moves),
          time.time() - now))
        if not legion_moves:
            legion_moves = list(self._gen_fallback_legion_moves(movesets))
            if not legion_moves:
                return None
        best_score = -maxint
        start = time.time()
        # Scramble the moves, in case we don't have time to look at them all.
        random.shuffle(legion_moves)
        log.msg("len(creatures) %d len(legion_moves[0]) %d" % (len(creatures),
          len(legion_moves[0])))
        for legion_move in legion_moves:
            try:
                for ii, creature in enumerate(creatures):
                    move = legion_move[ii]
                    creature.previous_hexlabel = creature.hexlabel
                    creature.hexlabel = move
                score = self._score_legion_move(game, creatures)
                if score > best_score:
                    best_legion_move = legion_move
                    best_score = score
                now = time.time()
                if now - start > self.time_limit:
                    log.msg("_find_best_creature_moves time limit")
                    break
            finally:
                for creature in creatures:
                    creature.hexlabel = creature.previous_hexlabel
        log.msg("found best_legion_move %s in %fs" % (best_legion_move,
          now - start))
        start_hexlabels = [creature.hexlabel for creature in creatures]
        creature_names = [creature.name for creature in creatures]
        creature_moves = zip(creature_names, start_hexlabels, best_legion_move)
        log.msg("creature_moves", creature_moves)
        now = time.time()
        ordered_creature_moves = self._find_move_order(game, creature_moves)
        log.msg("found ordered_creature_moves %s in %fs" % (
          ordered_creature_moves, time.time() - now))
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
        log.msg("CleverBot.move_creatures")
        if self.best_creature_moves is None:
            self.best_creature_moves = self._find_best_creature_moves(game)
        # Loop in case a non-move is best.
        while self.best_creature_moves:
            (creature_name, start, finish) = \
              self.best_creature_moves.pop(0)
            log.msg("checking move", creature_name, start, finish)
            creatures = game.creatures_in_battle_hex(start, creature_name)
            if creatures:
                creature = creatures.pop()
            else:
                log.msg("best_creature_moves was broken")
                self.best_creature_moves = self._find_best_creature_moves(game)
                continue
            if finish != start and finish in game.find_battle_moves(
              creature):
                log.msg("calling move_creature", creature.name, start,
                  finish)
                def1 = self.user.callRemote("move_creature", game.name,
                  creature.name, start, finish)
                def1.addErrback(self.failure)
                return

        # No moves, so end the maneuver phase.
        log.msg("calling done_with_maneuvers")
        self.best_creature_moves = None
        def1 = self.user.callRemote("done_with_maneuvers", game.name)
        def1.addErrback(self.failure)

    def _score_legion_move(self, game, creatures):
        """Return a score for creatures in their current hexlabels."""
        ATTACKER_AGGRESSION_BONUS = 1.0
        ATTACKER_DISTANCE_PENALTY = -1.0
        HIT_BONUS = 1.0
        KILL_MULTIPLIER = 1.0
        DAMAGE_PENALTY = -1.0
        DEATH_MULTIPLIER = -1.0
        ELEVATION_BONUS = 0.5
        NATIVE_BRAMBLE_BONUS = 0.3
        NON_NATIVE_BRAMBLE_PENALTY = -0.7
        TOWER_BONUS = 1.0
        FRONT_OF_TOWER_BONUS = 0.5
        MIDDLE_OF_TOWER_BONUS = 0.25
        CENTER_OF_TOWER_BONUS = 1.0
        TITAN_IN_CENTER_OF_TOWER_BONUS = 2.0
        NON_NATIVE_DRIFT_PENALTY = -2.0
        NATIVE_VOLCANO_BONUS = 1.0
        ADJACENT_ALLY_BONUS = 0.5
        RANGESTRIKE_BONUS = 2.0
        TITAN_FORWARD_PENALTY = -1.0
        DEFENDER_FORWARD_PENALTY = -0.5
        NATIVE_SLOPE_BONUS = 0.5
        NATIVE_DUNE_BONUS = 0.5
        NON_NATIVE_SLOPE_PENALTY = -0.3
        NON_NATIVE_DUNE_PENALTY = -0.3
        ENGAGE_RANGESTRIKER_BONUS = 0.5

        score = 0
        battlemap = game.battlemap
        legion = creatures[0].legion
        legion2 = game.other_battle_legion(legion)

        # For each enemy, figure out the average damage we could do to it if
        # everyone concentrated on hitting it, and if that's enough to kill it,
        # give every creature a kill bonus.
        # (This is not quite right because each creature can only hit one enemy
        # (modulo carries), but it's a start.)
        kill_bonus = 0
        for enemy in legion2.creatures:
            total_mean_hits = 0
            for creature in creatures:
                if (enemy in creature.engaged_enemies or
                  (not creature.engaged and enemy in
                  creature.rangestrike_targets)):
                    dice = creature.number_of_dice(enemy)
                    strike_number = creature.strike_number(enemy)
                    mean_hits = dice * (7. - strike_number) / 6
                    total_mean_hits += mean_hits
            if total_mean_hits >= enemy.hits_left:
                kill_bonus += enemy.sort_value

        for creature in creatures:
            can_rangestrike = False
            engaged = creature.engaged_enemies
            max_mean_hits = 0.0
            total_mean_damage_taken = 0.0
            engaged_with_rangestriker = False
            # melee
            for enemy in engaged:
                # Damage we can do.
                dice = creature.number_of_dice(enemy)
                strike_number = creature.strike_number(enemy)
                mean_hits = dice * (7. - strike_number) / 6
                max_mean_hits = max(mean_hits, max_mean_hits)
                # Damage we can take.
                dice = enemy.number_of_dice(creature)
                strike_number = enemy.strike_number(creature)
                mean_hits = dice * (7. - strike_number) / 6
                total_mean_damage_taken += mean_hits
                if enemy.rangestrikes:
                    engaged_with_rangestriker = True
            # inbound rangestriking
            for enemy in legion2.creatures:
                if enemy not in engaged:
                    if creature in enemy.potential_rangestrike_targets:
                        dice = enemy.number_of_dice(creature)
                        strike_number = enemy.strike_number(creature)
                        mean_hits = dice * (7. - strike_number) / 6
                        total_mean_damage_taken += mean_hits
            probable_death = total_mean_damage_taken >= creature.hits_left

            if engaged_with_rangestriker and not creature.rangestrikes:
                score += ENGAGE_RANGESTRIKER_BONUS
                log.msg(creature, "ENGAGE_RANGESTRIKER_BONUS",
                  ENGAGE_RANGESTRIKER_BONUS)

            # rangestriking
            if not engaged:
                targets = creature.rangestrike_targets
                for enemy in targets:
                    # Damage we can do
                    dice = creature.number_of_dice(enemy)
                    strike_number = creature.strike_number(enemy)
                    mean_hits = dice * (7. - strike_number) / 6
                    max_mean_hits = max(mean_hits, max_mean_hits)
                    can_rangestrike = True
            if can_rangestrike:
                score += RANGESTRIKE_BONUS
                log.msg(creature, "RANGESTRIKE_BONUS", RANGESTRIKE_BONUS)

            # Don't encourage titans to charge early.
            if (creature.name != "Titan" or game.battle_turn >= 4 or
              len(legion) == 1):
                if max_mean_hits:
                    bonus = HIT_BONUS * max_mean_hits
                    score += bonus
                    log.msg(creature, "HIT_BONUS", bonus)
                if kill_bonus:
                    bonus = KILL_MULTIPLIER * kill_bonus
                    score += bonus
                    log.msg(creature, "KILL_BONUS", bonus)
            if total_mean_damage_taken:
                penalty = DAMAGE_PENALTY * total_mean_damage_taken
                score += penalty
                log.msg(creature, "DAMAGE_PENALTY", penalty)
            if probable_death:
                penalty = (DEATH_MULTIPLIER * probable_death *
                  creature.sort_value)
                score += penalty
                log.msg(creature, "DEATH_PENALTY", penalty)

            # attacker must attack to avoid time loss
            # Don't encourage titans to charge early.
            if legion == game.attacker_legion and (creature.name != "Titan"
              or game.battle_turn >= 4 or len(legion) == 1):
                if engaged or targets:
                    score += ATTACKER_AGGRESSION_BONUS
                    log.msg(creature, "ATTACKER_AGGRESSION_BONUS",
                        ATTACKER_AGGRESSION_BONUS)
                else:
                    enemy_hexlabels = [enemy.hexlabel for enemy in
                      legion2.living_creatures]
                    if enemy_hexlabels:
                        min_range = min((battlemap.range(creature.hexlabel,
                          enemy_hexlabel) for enemy_hexlabel in
                          enemy_hexlabels))
                        penalty = min_range * ATTACKER_DISTANCE_PENALTY
                        score += penalty
                        log.msg(creature, "ATTACKER_DISTANCE_PENALTY", penalty)

            battlehex = battlemap.hexes[creature.hexlabel]
            terrain = battlehex.terrain

            # Make titans hang back early.
            if (creature.is_titan and game.battle_turn < 4 and
              terrain != "Tower"):
                if legion == game.attacker_legion:
                    entrance = "ATTACKER"
                else:
                    entrance = "DEFENDER"
                distance = battlemap.range(creature.hexlabel, entrance,
                  allow_entrance=True) - 2
                penalty = distance * TITAN_FORWARD_PENALTY
                if penalty:
                    score += penalty
                    log.msg(creature, "TITAN_FORWARD_PENALTY", penalty)

            # Make defenders hang back early.
            if (legion == game.defender_legion and game.battle_turn < 4 and
              terrain != "Tower"):
                entrance = "DEFENDER"
                distance = battlemap.range(creature.hexlabel, entrance,
                  allow_entrance=True) - 2
                penalty = distance * DEFENDER_FORWARD_PENALTY
                if penalty:
                    score += penalty
                    log.msg(creature, "DEFENDER_FORWARD_PENALTY", penalty)

            # terrain
            if battlehex.elevation:
                bonus = battlehex.elevation * ELEVATION_BONUS
                score += bonus
                log.msg(creature, "ELEVATION_BONUS", bonus)
            if terrain == "Bramble":
                if creature.is_native(terrain):
                    score += NATIVE_BRAMBLE_BONUS
                    log.msg(creature, "NATIVE_BRAMBLE_BONUS",
                      NATIVE_BRAMBLE_BONUS)
                else:
                    score += NON_NATIVE_BRAMBLE_PENALTY
                    log.msg(creature, "NON_NATIVE_BRAMBLE_PENALTY",
                      NON_NATIVE_BRAMBLE_PENALTY)
            elif terrain == "Tower":
                log.msg(creature, "TOWER_BONUS")
                score += TOWER_BONUS
                if battlehex.elevation == 2:
                    if creature.is_titan:
                        score += TITAN_IN_CENTER_OF_TOWER_BONUS
                        log.msg(creature, "TITAN_IN_CENTER_OF_TOWER_BONUS",
                          TITAN_IN_CENTER_OF_TOWER_BONUS)
                    else:
                        score += CENTER_OF_TOWER_BONUS
                        log.msg(creature, "CENTER_OF_TOWER_BONUS",
                          CENTER_OF_TOWER_BONUS)
                # XXX Hardcoded to default Tower map
                elif (legion == game.defender_legion and
                  creature.name != "Titan" and battlehex.label in
                  ["C3", "D3"]):
                    score += FRONT_OF_TOWER_BONUS
                    log.msg(creature, "FRONT_OF_TOWER_BONUS",
                      FRONT_OF_TOWER_BONUS)
                elif (legion == game.defender_legion and
                  creature.name != "Titan" and battlehex.label in
                  ["C4", "E3"]):
                    score += MIDDLE_OF_TOWER_BONUS
                    log.msg(creature, "MIDDLE_OF_TOWER_BONUS",
                      MIDDLE_OF_TOWER_BONUS)
            elif terrain == "Drift":
                if not creature.is_native(terrain):
                    score += NON_NATIVE_DRIFT_PENALTY
                    log.msg(creature, "NON_NATIVE_DRIFT_PENALTY",
                      NON_NATIVE_DRIFT_PENALTY)
            elif terrain == "Volcano":
                score += NATIVE_VOLCANO_BONUS
                log.msg(creature, "NATIVE_VOLCANO_BONUS", NATIVE_VOLCANO_BONUS)

            if "Slope" in battlehex.borders:
                if creature.is_native("Slope"):
                    score += NATIVE_SLOPE_BONUS
                    log.msg(creature, "NATIVE_SLOPE_BONUS", NATIVE_SLOPE_BONUS)
                else:
                    score += NON_NATIVE_SLOPE_PENALTY
                    log.msg(creature, "NON_NATIVE_SLOPE_PENALTY",
                      NON_NATIVE_SLOPE_PENALTY)
            if "Dune" in battlehex.borders:
                if creature.is_native("Dune"):
                    score += NATIVE_DUNE_BONUS
                    log.msg(creature, "NATIVE_DUNE_BONUS", NATIVE_DUNE_BONUS)
                else:
                    score += NON_NATIVE_DUNE_PENALTY
                    log.msg(creature, "NON_NATIVE_DUNE_PENALTY",
                      NON_NATIVE_DUNE_PENALTY)

            # allies
            num_adjacent_allies = 0
            for neighbor in battlehex.neighbors.itervalues():
                for ally in legion.living_creatures:
                    if ally.hexlabel == neighbor.label:
                        num_adjacent_allies += 1
            adjacent_allies_bonus = num_adjacent_allies * ADJACENT_ALLY_BONUS
            if adjacent_allies_bonus:
                score += adjacent_allies_bonus
                log.msg(creature, "ADJACENT_ALLY_BONUS", adjacent_allies_bonus)

        return score

    def strike(self, game):
        log.msg("strike")
        if not game.battle_active_player:
            log.msg("called strike with no battle")
            return
        if game.battle_active_player.name != self.playername:
            log.msg("called strike for wrong player")
            return
        legion = game.battle_active_legion
        # First do the strikers with only one target.
        for striker in legion.sorted_creatures:
            if striker.can_strike:
                hexlabels = striker.find_target_hexlabels()
                if len(hexlabels) == 1:
                    hexlabel = hexlabels.pop()
                    target = game.creatures_in_battle_hex(hexlabel).pop()
                    num_dice = striker.number_of_dice(target)
                    strike_number = striker.strike_number(target)
                    def1 = self.user.callRemote("strike", game.name,
                      striker.name, striker.hexlabel, target.name,
                      target.hexlabel, num_dice, strike_number)
                    def1.addErrback(self.failure)
                    return

        # Then do the ones that have to choose a target.
        target_to_total_mean_hits = collections.defaultdict(float)
        best_target = None
        for striker in legion.sorted_creatures:
            if striker.can_strike:
                hexlabels = striker.find_target_hexlabels()
                for hexlabel in hexlabels:
                    target = game.creatures_in_battle_hex(hexlabel).pop()
                    num_dice = striker.number_of_dice(target)
                    strike_number = striker.strike_number(target)
                    mean_hits = num_dice * (7. - strike_number) / 6
                    target_to_total_mean_hits[target] += mean_hits
        # First find the best target we can kill.
        for target, total_mean_hits in target_to_total_mean_hits.iteritems():
            if total_mean_hits >= target.hits_left:
                if (best_target is None or target.sort_value >
                  best_target.sort_value):
                    best_target = target
        # If we can't kill anything, go after the target we can hurt most.
        if best_target is None:
            max_total_mean_hits = 0
            for target, total_mean_hits in \
              target_to_total_mean_hits.iteritems():
                if total_mean_hits >= max_total_mean_hits:
                    best_target = target
                    max_total_mean_hits = total_mean_hits
        # Find the least valuable striker who can hit best_target.
        for striker in reversed(legion.sorted_creatures):
            if striker.can_strike:
                hexlabels = striker.find_target_hexlabels()
                for hexlabel in hexlabels:
                    target = game.creatures_in_battle_hex(hexlabel).pop()
                    if target is best_target:
                        num_dice = striker.number_of_dice(target)
                        strike_number = striker.strike_number(target)
                        def1 = self.user.callRemote("strike", game.name,
                          striker.name, striker.hexlabel, target.name,
                          target.hexlabel, num_dice, strike_number)
                        def1.addErrback(self.failure)
                        return
        # No strikes, so end the strike phase.
        if game.battle_phase == Phase.STRIKE:
            def1 = self.user.callRemote("done_with_strikes",
              game.name)
            def1.addErrback(self.failure)
        else:
            if game.battle_phase != Phase.COUNTERSTRIKE:
                log.msg("wrong phase")
            def1 = self.user.callRemote("done_with_counterstrikes",
              game.name)
            def1.addErrback(self.failure)

    def carry(self, game, striker_name, striker_hexlabel, target_name,
      target_hexlabel, num_dice, strike_number, carries):
        striker = game.creatures_in_battle_hex(striker_hexlabel).pop()
        target = game.creatures_in_battle_hex(target_hexlabel).pop()
        carry_targets = []
        for creature in striker.engaged_enemies:
            if striker.can_carry_to(creature, target, num_dice, strike_number):
                carry_targets.append(creature)
        best_target = None
        # If there's only one carry target, it's easy.
        if len(carry_targets) == 1:
            best_target = carry_targets[0]
        # First find the best target we can kill.
        if best_target is None:
            for carry_target in carry_targets:
                if carries >= target.hits_left:
                    if (best_target is None or carry_target.sort_value >
                      best_target.sort_value):
                        best_target = carry_target
        # If we can't kill anything then go after the hardest target to hit.
        if best_target is None:
            best_num_dice = None
            best_strike_number = None
            for carry_target in carry_targets:
                num_dice2 = striker.number_of_dice(carry_target)
                strike_number2 = striker.strike_number(carry_target)
                if (best_target is None or num_dice2 < best_num_dice
                  or strike_number2 > best_strike_number):
                    best_target = carry_target
                    best_num_dice = num_dice2
                    best_strike_number = strike_number2
        def1 = self.user.callRemote("carry", game.name,
          best_target.name, best_target.hexlabel, carries)
        def1.addErrback(self.failure)

    def failure(self, error):
        log.err(error)
