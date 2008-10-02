"""Outward-facing facade for client side."""

from twisted.spread import pb
from twisted.cred import credentials
from twisted.internet import reactor
from zope.interface import implements

import Server
import Anteroom
from Observer import IObserver
from Observed import Observed
import Action
import Game
import PickColor
import PickMarker
import GUIMasterBoard
import StatusScreen
import GUIBattleMap


class Client(pb.Referenceable, Observed):

    implements(IObserver)

    def __init__(self, username, password, host="localhost", 
      port=Server.DEFAULT_PORT):
        Observed.__init__(self)
        self.username = username
        self.playername = username # In case the same user logs in twice
        self.password = password
        self.host = host
        self.port = port
        self.factory = pb.PBClientFactory()
        self.user = None
        self.anteroom = None
        self.usernames = set()
        self.games = []
        self.guiboards = {}   # Maps game to guiboard
        self.guimaps = {}     # Maps game to guimap
        self.status_screens = {}   # Maps game to status_screen
        self.pickcolor = None      # To prevent gc of dialog

    def remote_set_name(self, name):
        self.playername = name
        return name

    def remote_ping(self, arg):
        return True

    def __repr__(self):
        return "Client " + str(self.username)

    def connect(self):
        user_pass = credentials.UsernamePassword(self.username, self.password)
        reactor.connectTCP(self.host, self.port, self.factory)
        def1 = self.factory.login(user_pass, self)
        def1.addCallback(self.connected)
        def1.addErrback(self.failure)
        return def1

    def connected(self, user):
        if user:
            self.user = user
            self.anteroom = Anteroom.Anteroom(user, self.username)
            self.add_observer(self.anteroom)
            def1 = user.callRemote("get_usernames")
            def1.addCallback(self.got_usernames)
            def1.addErrback(self.failure)

    def got_usernames(self, usernames):
        """Only called when the client first connects to the server."""
        self.usernames.clear()
        for username in usernames:
            self.usernames.add(username)
        self.anteroom.set_usernames(self.usernames)
        def1 = self.user.callRemote("get_games")
        def1.addCallback(self.got_games)
        def1.addErrback(self.failure)

    def got_games(self, game_info_tuples):
        """Only called when the client first connects to the server."""
        del self.games[:]
        for game_info_tuple in game_info_tuples:
            self.add_game(game_info_tuple)
        self.anteroom.set_games(self.games)

    def name_to_game(self, game_name):
        for game in self.games:
            if game.name == game_name:
                return game
        return None

    def add_game(self, game_info_tuple):
        (name, create_time, start_time, min_players, max_players,
          playernames) = game_info_tuple
        owner = playernames[0]
        game = Game.Game(name, owner, create_time, start_time, min_players,
          max_players)
        self.add_observer(game)
        for playername in playernames[1:]:
            game.add_player(playername)
        self.games.append(game)

    def remove_game(self, game_name):
        game = self.name_to_game(game_name)
        if game:
            self.remove_observer(game)
            self.games.remove(game)

    def failure(self, error):
        print "Client.failure", self, error
        reactor.stop()

    # TODO Make this an Action, after adding a filter on Observed.notify
    def remote_receive_chat_message(self, text):
        self.anteroom.receive_chat_message(text)

    def remote_update(self, action):
        """Near-IObserver on the remote User, except observed is
        not passed remotely.

        Delegates to update to honor the interface.
        """
        observed = None
        self.update(observed, action)

    def _maybe_pick_color(self, game):
        if game.next_playername_to_pick_color() == self.username:
            self.pickcolor = PickColor.PickColor(self.user, self.username, 
              game.name, game.colors_left(), self.anteroom.anteroom_window)

    def _maybe_pick_first_marker(self, game, playername):
        if playername == self.username:
            player = game.get_player_by_name(playername)
            markernames = sorted(player.markernames.copy())
            PickMarker.PickMarker(self.username, game.name, markernames,
              self.pick_marker, self.anteroom.anteroom_window)
            self.pickcolor = None

    def pick_marker(self, game_name, username, markername):
        """Callback from PickMarker."""
        game = self.name_to_game(game_name)
        player = game.get_player_by_name(username)
        player.pick_marker(markername)
        if not player.legions:
            def1 = self.user.callRemote("pick_first_marker", game_name, 
              markername)
            def1.addErrback(self.failure)

    def _init_status_screen(self, game):
        self.status_screens[game] = StatusScreen.StatusScreen(game, self.user,
          self.username)
        game.add_observer(self.status_screens[game])

    def _init_guiboard(self, game):
        self.guiboards[game] = GUIMasterBoard.GUIMasterBoard(game.board, game,
          self.user, self.username)
        game.add_observer(self.guiboards[game])

    def _init_guimap(self, game):
        try:
            self.guimaps[game] = GUIBattleMap.GUIBattleMap(
              game.battle.battlemap, self.user, self.username)
            game.add_observer(self.guimaps[game])
        except AttributeError:
            # XXX notify race
            reactor.callLater(1, self._init_guimap, game)

    def update(self, observed, action):
        """Updates from User will come via remote_update, with
        observed set to None."""
        if isinstance(action, Action.AddUsername):
            self.usernames.add(action.username)
        elif isinstance(action, Action.DelUsername):
            self.usernames.remove(action.username)
        elif isinstance(action, Action.FormGame):
            game_info_tuple = (action.game_name, action.create_time,
              action.start_time, action.min_players, action.max_players,
              [action.username])
            self.add_game(game_info_tuple)
        elif isinstance(action, Action.RemoveGame):
            self.remove_game(action.game_name)
        elif isinstance(action, Action.AssignedAllTowers):
            game = self.name_to_game(action.game_name)
            self._maybe_pick_color(game)
            if not self.guiboards.get(game):
                self._init_status_screen(game)
        elif isinstance(action, Action.PickedColor):
            game = self.name_to_game(action.game_name)
            # Do this now rather than waiting for game to be notified.
            game.assign_color(action.playername, action.color)
            self._maybe_pick_color(game)
            self._maybe_pick_first_marker(game, action.playername)
            if not self.guiboards.get(game):
                self._init_guiboard(game)
        elif isinstance(action, Action.Fight):
            game = self.name_to_game(action.game_name)
            self._init_guimap(game)

        self.notify(action)

