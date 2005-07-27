import Caretaker

def test_init():
    caretaker = Caretaker.Caretaker()
    assert caretaker.num_left("Centaur") == 25
    assert caretaker.num_left("Titan") == 6
    assert caretaker.num_left("Wyvern") == 18

def test_take_one():
    caretaker = Caretaker.Caretaker()
    assert caretaker.num_left("Wyvern") == 18
    caretaker.take_one("Wyvern")
    assert caretaker.num_left("Wyvern") == 17

def test_put_one_back():
    caretaker = Caretaker.Caretaker()
    assert caretaker.num_left("Angel") == 18
    caretaker.take_one("Angel")
    assert caretaker.num_left("Angel") == 17
    caretaker.put_one_back("Angel")
    assert caretaker.num_left("Angel") == 18

def test_kill_one():
    caretaker = Caretaker.Caretaker()
    assert caretaker.num_left("Angel") == 18
    caretaker.take_one("Angel")
    assert caretaker.num_left("Angel") == 17
    caretaker.kill_one("Angel")
    assert caretaker.num_left("Angel") == 18

    assert caretaker.num_left("Centaur") == 25
    caretaker.take_one("Centaur")
    assert caretaker.num_left("Centaur") == 24
    assert caretaker.graveyard["Centaur"] == 0
    caretaker.kill_one("Centaur")
    assert caretaker.num_left("Centaur") == 24
    assert caretaker.graveyard["Centaur"] == 1

def test_number_in_play():
    caretaker = Caretaker.Caretaker()
    assert caretaker.number_in_play("Centaur") == 0
    caretaker.take_one("Centaur")
    assert caretaker.number_in_play("Centaur") == 1
    caretaker.kill_one("Centaur")
    assert caretaker.number_in_play("Centaur") == 0
    caretaker.take_one("Centaur")
    caretaker.take_one("Centaur")
    caretaker.kill_one("Centaur")
    assert caretaker.number_in_play("Centaur") == 1