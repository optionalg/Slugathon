#!/usr/bin/env python2.3

import sys
from sets import Set
from twisted.spread import pb
from twisted.cred import checkers, portal
from twisted.python import usage
import twisted.internet.app
import User
import Realm


DEFAULT_PORT = 26569

class Server:
    """A Slugathon server, which can host multiple games in parallel."""
    def __init__(self):
        print "Called Server.init", self
        self.games = []
        self.users = Set()

    def addUser(self, user):
        print "called Server.addUser", self, user
        self.users.add(user)
        for u in self.users:
            u.notifyAddUser(user)

    def delUser(self, user):
        print "called Server.delUser", self, user
        self.users.remove(user)
        for u in self.users:
            u.notifyDelUser(user)

    def getUserNames(self):
        names = [user.name for user in self.users]
        names.sort()
        return names

    def getGames(self):
        return self.games


class Options(usage.Options):
    optParameters = [
      ["port", "p", DEFAULT_PORT, "Port number"],
    ]


def main(config):
    port = int(config["port"])

    server = Server()
    realm = Realm.Realm(server)
    checker = checkers.FilePasswordDB("passwd.txt")
    po = portal.Portal(realm, [checker])

    app = twisted.internet.app.Application("Slugathon")
    pbfact = pb.PBServerFactory(po)
    app.listenTCP(port, pbfact)
    app.run(save=False)


if __name__ == '__main__':
    config = Options()
    try:
        config.parseOptions()
    except usage.UsageError, errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)
    main(config)
