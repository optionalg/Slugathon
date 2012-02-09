__copyright__ = "Copyright (c) 2005-2011 David Ripton"
__license__ = "GNU GPL v2"


import time

from twisted.python import log

from slugathon.game import Game


class TestGame(object):
    def setup_method(self, method):
        now = time.time()
        self.game = game = Game.Game("g1", "p0", now, now, 2, 6)
        game.add_player("p1")
        player0 = game.players[0]
        player1 = game.players[1]
        player0.assign_starting_tower(200)
        player1.assign_starting_tower(100)
        game.sort_players()
        game.started = True
        game.assign_color("p1", "Blue")
        game.assign_color("p0", "Red")
        game.assign_first_marker("p1", "Bu01")
        game.assign_first_marker("p0", "Rd01")
        player0.pick_marker("Rd02")
        player0.split_legion("Rd01", "Rd02",
          ["Titan", "Centaur", "Centaur", "Gargoyle"],
          ["Angel", "Ogre", "Ogre", "Gargoyle"])
        player0.done_with_splits()

    def test_all_legions(self):
        game = self.game
        log.msg(game.all_legions())
        assert len(game.all_legions()) == 3
        assert len(game.all_legions(200)) == 2
        assert len(game.all_legions(100)) == 1
        assert len(game.all_legions(300)) == 0

    def test_find_normal_moves(self):
        game = self.game
        player = self.game.players[0]
        legion = player.markerid_to_legion["Rd01"]
        masterhex = game.board.hexes[legion.hexlabel]

        moves = self.game.find_normal_moves(legion, masterhex, 1)
        assert moves == set([(6, 5), (10, 1), (108, 3)])

        moves = self.game.find_normal_moves(legion, masterhex, 2)
        assert moves == set([(7, 3), (11, 5), (107, 1)])

        moves = self.game.find_normal_moves(legion, masterhex, 3)
        assert moves == set([(8, 1), (12, 5), (106, 5)])

        moves = self.game.find_normal_moves(legion, masterhex, 4)
        assert moves == set([(9, 5), (13, 1), (105, 1)])

        moves = self.game.find_normal_moves(legion, masterhex, 5)
        assert moves == set([(10, 3), (14, 3), (104, 1)])

        moves = self.game.find_normal_moves(legion, masterhex, 6)
        assert moves == set([(15, 1), (11, 5), (103, 5)])

    def test_find_all_teleport_moves(self):
        game = self.game
        player = game.players[0]
        legion = player.markerid_to_legion["Rd01"]
        masterhex = game.board.hexes[legion.hexlabel]

        moves = game.find_all_teleport_moves(legion, masterhex, 1)
        assert not moves

    def test_find_all_teleport_moves2(self):
        game = self.game
        player = game.players[0]
        legion = player.markerid_to_legion["Rd01"]
        masterhex = game.board.hexes[legion.hexlabel]

        moves = game.find_all_teleport_moves(legion, masterhex, 6)
        for move in moves:
            assert move[1] == Game.TELEPORT
        hexlabels = set([move[0] for move in moves])
        log.msg(sorted(hexlabels))

        assert hexlabels == set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
          15, 16, 17, 21, 37, 41, 42, 101, 102, 103, 104, 105, 106, 107, 108,
          109, 110, 111, 112, 113, 114, 115, 300, 400, 500, 600, 1000, 2000,
          3000, 4000, 6000])

    def test_find_all_moves(self):
        game = self.game
        player = game.players[0]
        legion = player.markerid_to_legion["Rd01"]
        masterhex = game.board.hexes[legion.hexlabel]

        moves = game.find_all_moves(legion, masterhex, 1)
        assert moves == set([(6, 5), (10, 1), (108, 3)])

    def test_find_all_moves2(self):
        game = self.game
        player = game.players[0]
        legion = player.markerid_to_legion["Rd01"]
        masterhex = game.board.hexes[legion.hexlabel]

        moves = game.find_all_moves(legion, masterhex, 6)
        log.msg(sorted(moves))
        hexlabels = set([move[0] for move in moves])
        assert hexlabels == set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
          15, 16, 17, 21, 37, 41, 42, 101, 102, 103, 104, 105, 106, 107, 108,
          109, 110, 111, 112, 113, 114, 115, 300, 400, 500, 600, 1000, 2000,
          3000, 4000, 6000])
        for hexlabel in hexlabels:
            assert (hexlabel, Game.TELEPORT) in moves
        assert (11, 5) in moves
        assert (15, 1) in moves
        assert (103, 5) in moves

    def test_can_move_legion(self):
        game = self.game
        player = game.players[0]
        legion = player.markerid_to_legion["Rd01"]
        player.movement_roll = 1
        assert game.can_move_legion(player, legion, 6, 5, False, None)
        assert game.can_move_legion(player, legion, 10, 1, False, None)
        assert game.can_move_legion(player, legion, 108, 3, False, None)
        assert not game.can_move_legion(player, legion, 108, 3, True, None)

    def test_can_move_legion2(self):
        game = self.game
        player = game.players[0]
        legion = player.markerid_to_legion["Rd01"]
        player.movement_roll = 6
        assert game.can_move_legion(player, legion, 15, 1, False, None)
        assert game.can_move_legion(player, legion, 11, 5, False, None)
        assert game.can_move_legion(player, legion, 103, 5, False, None)
        assert not game.can_move_legion(player, legion, 16, 1, False, None)
        assert game.can_move_legion(player, legion, 16, 1, True, "Titan")
        assert game.can_move_legion(player, legion, 16, 3, True, "Titan")
        assert game.can_move_legion(player, legion, 16, 5, True, "Titan")
        assert not game.can_move_legion(player, legion, 16, 4, True, "Titan")
        assert game.can_move_legion(player, legion, 4000, 1, True, "Titan")

    def test_next_player_and_turn(self):
        game = self.game
        player0 = game.players[0]
        player1 = game.players[1]
        assert game.turn == 1
        assert game.active_player == player0
        assert game.next_player_and_turn == (player1, 1)
        player0.done_with_splits()

    def test_eq_ne(self):
        now = time.time()
        game2 = Game.Game("g1", "p0", now, now, 2, 6)
        assert self.game == game2
        game3 = Game.Game("g2", "p0", now, now, 2, 6)
        assert self.game != game3


def test_update_finish_order():
    now = time.time()
    game = Game.Game("g1", "ai1", now, now, 2, 6)
    game.add_player("ai2")
    game.add_player("ai3")
    game.add_player("ai4")
    game.add_player("ai5")
    game.add_player("ai6")
    ai1 = game.get_player_by_name("ai1")
    ai2 = game.get_player_by_name("ai2")
    ai3 = game.get_player_by_name("ai3")
    ai4 = game.get_player_by_name("ai4")
    ai5 = game.get_player_by_name("ai5")
    ai6 = game.get_player_by_name("ai6")
    ai1.assign_starting_tower(600)
    ai2.assign_starting_tower(500)
    ai3.assign_starting_tower(400)
    ai4.assign_starting_tower(300)
    ai5.assign_starting_tower(200)
    ai6.assign_starting_tower(100)
    ai1.assign_color("Red")
    ai2.assign_color("Blue")
    ai3.assign_color("Black")
    ai4.assign_color("Brown")
    ai5.assign_color("Green")
    ai6.assign_color("Gold")
    for player in game.players:
        player.pick_marker(player.color_abbrev + "01")
        player.create_starting_legion()
    ai3.die(ai5, True)
    ai3.markerid_to_legion = {}
    assert ai3.dead
    game._update_finish_order(ai5, ai3)
    assert game.finish_order == [(ai3, )]
    ai6.die(ai2, True)
    ai6.markerid_to_legion = {}
    game._update_finish_order(ai2, ai6)
    assert game.finish_order == [(ai6, ), (ai3, )]
    ai2.die(ai4, True)
    ai2.markerid_to_legion = {}
    game._update_finish_order(ai4, ai2)
    assert game.finish_order == [(ai2, ), (ai6, ), (ai3, )]
    ai1.die(ai4, True)
    ai1.markerid_to_legion = {}
    game._update_finish_order(ai4, ai1)
    assert game.finish_order == [(ai1, ), (ai2, ), (ai6, ), (ai3, )]
    ai5.die(ai4, True)
    ai5.markerid_to_legion = {}
    game._update_finish_order(ai4, ai5)
    assert game.finish_order == [(ai4, ), (ai5, ), (ai1, ), (ai2, ),
      (ai6, ), (ai3, )]


def test_update_finish_order_3_draws():
    now = time.time()
    game = Game.Game("g1", "ai1", now, now, 2, 6)
    game.add_player("ai2")
    game.add_player("ai3")
    game.add_player("ai4")
    game.add_player("ai5")
    game.add_player("ai6")
    ai1 = game.get_player_by_name("ai1")
    ai2 = game.get_player_by_name("ai2")
    ai3 = game.get_player_by_name("ai3")
    ai4 = game.get_player_by_name("ai4")
    ai5 = game.get_player_by_name("ai5")
    ai6 = game.get_player_by_name("ai6")
    ai1.assign_starting_tower(600)
    ai2.assign_starting_tower(500)
    ai3.assign_starting_tower(400)
    ai4.assign_starting_tower(300)
    ai5.assign_starting_tower(200)
    ai6.assign_starting_tower(100)
    ai1.assign_color("Red")
    ai2.assign_color("Blue")
    ai3.assign_color("Black")
    ai4.assign_color("Brown")
    ai5.assign_color("Green")
    ai6.assign_color("Gold")
    for player in game.players:
        player.pick_marker(player.color_abbrev + "01")
        player.create_starting_legion()
    ai3.die(ai5, False)
    ai3.markerid_to_legion = {}
    assert ai3.dead
    ai5.die(ai3, True)
    ai5.markerid_to_legion = {}
    assert ai5.dead
    game._update_finish_order(ai3, ai5)
    game._update_finish_order(ai5, ai3)
    assert game.finish_order == [(ai3, ai5)]
    ai2.die(ai6, False)
    ai2.markerid_to_legion = {}
    assert ai2.dead
    ai6.die(ai2, True)
    ai6.markerid_to_legion = {}
    assert ai6.dead
    game._update_finish_order(ai2, ai6)
    game._update_finish_order(ai6, ai2)
    assert game.finish_order == [(ai2, ai6), (ai3, ai5)]
    ai4.die(ai1, False)
    ai4.markerid_to_legion = {}
    assert ai4.dead
    ai1.die(ai4, True)
    ai1.markerid_to_legion = {}
    assert ai1.dead
    game._update_finish_order(ai4, ai1)
    game._update_finish_order(ai1, ai4)
    assert game.finish_order == [(ai4, ai1), (ai2, ai6), (ai3, ai5)]
