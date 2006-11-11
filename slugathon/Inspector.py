#!/usr/bin/env python 

try:
    import pygtk
    pygtk.require("2.0")
except (ImportError, AttributeError):
    pass
import gtk
import gtk.glade
import Chit
import creaturedata
import Creature
import Legion
import Marker
import icon
import guiutils

class Inspector(object):
    """Window to show a legion's contents."""
    def __init__(self, username):
        print "Inspector.__init__", username
        self.glade = gtk.glade.XML("../glade/showlegion.glade")
        self.widgets = ["show_legion_window", "marker_hbox", "chits_hbox",
          "legion_name"]
        for widget_name in self.widgets:
            setattr(self, widget_name, self.glade.get_widget(widget_name))

        self.show_legion_window.set_icon(icon.pixbuf)
        self.show_legion_window.set_title("Inspector - %s" % (username))

        self.legion = None
        self.marker = None


    def show_legion(self, legion):
        self.legion_name.set_text("Legion %s in hex %s" % (legion.markername,
          legion.hexlabel))

        for hbox in [self.marker_hbox, self.chits_hbox]:
            for child in hbox.get_children():
                hbox.remove(child)

        self.marker = Marker.Marker(legion, scale=20)
        self.marker_hbox.pack_start(self.marker.image, expand=False,
          fill=False)
        self.marker.show()

        # TODO Handle unknown creatures correctly
        playercolor = legion.player.color
        for creature in legion.creatures:
            chit = Chit.Chit(creature, playercolor, scale=20)
            chit.show()
            self.chits_hbox.add(chit.event_box)

        self.show_legion_window.show()
