import unittest
import pandas as pd
from src.metrics.ball_goal_passing_lanes import calculate_ball_goal_passing_lanes

class BallGoalPassingLaneTests(unittest.TestCase):
 def test_goal_corridor_and_lane_clearance(self):
  info={"home_team":{"id":1},"away_team":{"id":2},"home_team_side":["left_to_right"],"pitch_length":105}
  c=["frame","timestamp","elapsed_seconds","period","team_id","team_acronym","player_id","position","x","y"]
  p=pd.DataFrame([(1,"00",0.,1,1,"H",1,"CB",-30.,1.),(1,"00",0.,1,1,"H",2,"CB",-40.,10.),(1,"00",0.,1,2,"A",3,"FW",-40.,0.)],columns=c)
  b=pd.DataFrame([(1,1,-20.,0.)],columns=["frame","period","ball_x","ball_y"])
  m=calculate_ball_goal_passing_lanes(p,b,info)["frame_metrics"].query("team_id==1").iloc[0]
  self.assertEqual(m.defenders_in_ball_goal_corridor,1)
  self.assertAlmostEqual(m.minimum_defender_clearance_to_ball_goal_segment,1.)
  self.assertEqual(m.open_penalty_corridor_passing_options_over_1m,0)
  self.assertFalse(m.carrier_proxy_central_route_unobstructed)
if __name__=="__main__": unittest.main()
