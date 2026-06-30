export interface TuningProfile {
  id: string;
  world_id: string;
  plan_tuning: string;
  tone_tuning: string;
}

export interface UpdateTuningProfile {
  plan_tuning: string;
  tone_tuning: string;
}
