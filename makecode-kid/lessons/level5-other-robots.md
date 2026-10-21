# Level 5: the hexapod and the windmill rover
Goal: drive a different robot with almost the same blocks.

Pick the robot in the first block: **start walker as** crab, hexapod or windmill rover. Everything else (walk forward, turn, stop, step size) stays the same.

## Hexapod (6 legs)
1. Plug the two middle legs into channels 8 to 11: middle-left hip 8, knee 9, middle-right hip 10, knee 11.
2. `on start`: **start walker as hexapod**, then **walk forward for 5 seconds**.
3. Three legs step while three stand, so it does not need to lean. The **lean** block does nothing here.
4. Wiggle, nudge and flip work on the new legs: choose **middle left (hexapod)** or **middle right (hexapod)**.

## Windmill rover (4 spinning legs)
1. Plug the four spin motors into channels 0 to 3: front-left 0, front-right 1, back-left 2, back-right 3.
2. **Fix each wheel's stop first.** With the legs off, `on start`: **start walker as windmill rover**. A wheel that creeps should stand still. Use **stop-fix wheel by** a few microseconds, or turn the little screw on the motor, until it stops.
3. **test spin wheel** turns one wheel forward for a second. If it turns the wrong way, use **flip spin direction of wheel**.
4. Put the legs on. Set **top speed** low (40) and **walk forward for 5 seconds**. Turning spins the rover on the spot.
5. Build a bumpy course from books and cushions. Which spoke length and how many spokes climb best? Change them in the Walker Designer and print a new set.

Careful: at high speed the rover can flip over bumps. Raise the speed a little at a time.
