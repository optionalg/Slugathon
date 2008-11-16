import shutil

import prefs
import Dice

playername = "unittest"
window_name = "GUIMasterBoard"

def test_save_load_window_position():
    x1 = Dice.roll()[0]
    y1 = Dice.roll()[0]
    prefs.save_window_position(playername, window_name, x1, y1)
    x2, y2 = prefs.load_window_position(playername, window_name)
    assert x2 == x1
    assert y2 == y1

def test_save_load_window_size():
    x1 = Dice.roll()[0]
    y1 = Dice.roll()[0]
    prefs.save_window_size(playername, window_name, x1, y1)
    x2, y2 = prefs.load_window_size(playername, window_name)
    assert x2 == x1
    assert y2 == y1

def teardown_module(module):
    shutil.rmtree(prefs.player_prefs_dir(playername))