#!/usr/bin/env python

__copyright__ = "Copyright (c) 2008-2010 David Ripton"
__license__ = "GNU GPL v2"


from twisted.internet import gtk2reactor
try:
    gtk2reactor.install()
except AssertionError:
    pass
import gtk

from slugathon.gui import icon
from slugathon.util import prefs
from slugathon.util.NullUser import NullUser
from slugathon.util.log import log


class LoadGame(gtk.FileChooserDialog):
    """Load saved game dialog."""
    def __init__(self, user, username, parent):
        title = "Load Saved Game - %s" % username
        gtk.FileChooserDialog.__init__(self, title, parent,
          gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL,
          gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        self.user = user
        self.username = username
        self.set_icon(icon.pixbuf)
        self.set_transient_for(parent)
        self.set_destroy_with_parent(True)
        self.set_current_folder(prefs.SAVE_DIR)
        file_filter = gtk.FileFilter()
        # TODO Hoist constants somewhere
        file_filter.add_pattern("*.save")
        self.set_filter(file_filter)

        response = self.run()
        if response == gtk.RESPONSE_OK:
            self.ok()
        else:
            self.cancel()

    def ok(self):
        filename = self.get_filename()
        def1 = self.user.callRemote("load_game", filename)
        def1.addErrback(self.failure)
        self.destroy()

    def cancel(self):
        self.destroy()

    def failure(self, error):
        log(error)


if __name__ == "__main__":
    from twisted.internet import reactor

    user = NullUser()
    username = "test user"
    loadgame = LoadGame(user, username, None)
    loadgame.connect("destroy", lambda x: reactor.stop())
    reactor.run()
